"""
BaseAgent on Microsoft Agent Framework (#606): LLM conversations with tool calling.

A fake model server (httpx2.MockTransport) stands in for OpenAI, so nothing leaves
the machine and no API key is needed.
"""

import asyncio
import json

import httpx2
import openai
import pytest
from agent_framework import FunctionInvocationConfiguration, FunctionTool
from agent_framework.openai import OpenAIChatCompletionClient

from src.autogen_agents.core import base_agent
from src.autogen_agents.core.base_agent import BaseAgent

executed = []


def lookup_price(symbol: str) -> str:
    """Stand-in market tool."""
    executed.append(symbol)
    return json.dumps({"symbol": symbol, "price": 744.47})


LOOKUP = FunctionTool(func=lookup_price, name="lookup_price", description="Latest price")


class _Agent(BaseAgent):
    def generate_reply(self, messages, context=None) -> str:
        return ""


def _reply(message, finish):
    return httpx2.Response(
        200,
        json={
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini",
            "choices": [{"index": 0, "finish_reason": finish, "message": message}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )


def _tool_call(call_id):
    return _reply(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": "lookup_price", "arguments": '{"symbol": "SPY"}'},
                }
            ],
        },
        "tool_calls",
    )


def _agent_with_fake_model(answer_after_tool=True):
    """An agent whose chat client talks to a fake model; returns (agent, requests seen)."""
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        tools_allowed = bool(body.get("tools")) and body.get("tool_choice") != "none"
        tool_result = [m for m in body["messages"] if m.get("role") == "tool"]
        if tools_allowed and not (answer_after_tool and tool_result):
            return _tool_call(f"call_{len(requests)}")
        return _reply({"role": "assistant", "content": "SPY's stop is $744.47."}, "stop")

    agent = _Agent(name="tester", tools=[LOOKUP])
    async_client = openai.AsyncOpenAI(
        api_key="sk-test", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )
    agent._model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        async_client=async_client,
        function_invocation_configuration=FunctionInvocationConfiguration(
            max_iterations=agent.max_tool_rounds
        ),
    )
    return agent, requests


@pytest.fixture(autouse=True)
def _clear_executed():
    executed.clear()


def test_an_agent_needs_no_api_key_until_it_calls_the_llm(monkeypatch):
    monkeypatch.setattr(base_agent, "open_ai_key", None)

    agent = _Agent(name="calc_only")  # building it is fine

    assert agent.name == "calc_only" and agent._model_client is None
    assert "OpenAI API key not found" in agent.process_with_tools("hello")


def test_the_model_calls_a_tool_and_answers_from_its_result():
    agent, requests = _agent_with_fake_model()

    answer = agent.process_with_tools("What is SPY's stop?", system_prompt="You manage stops.")

    assert answer == "SPY's stop is $744.47."
    assert executed == ["SPY"]
    first = requests[0]
    assert first["messages"][0] == {"role": "system", "content": "You manage stops."}
    assert [t["function"]["name"] for t in first["tools"]] == ["lookup_price"]
    assert (first["temperature"], first["top_p"]) == (0.2, 0.95)
    assert first.get("max_tokens", first.get("max_completion_tokens")) == 4096


def test_tool_rounds_are_capped_then_the_model_must_answer_in_text():
    agent, requests = _agent_with_fake_model(answer_after_tool=False)  # always wants a tool

    answer = agent.process_with_tools("Keep looking things up")

    assert answer == "SPY's stop is $744.47."
    assert len(executed) == agent.max_tool_rounds == 2
    assert [r.get("tool_choice") for r in requests] == ["auto", "auto", "none"]


def test_inside_an_event_loop_the_caller_awaits_the_answer():
    agent, _ = _agent_with_fake_model()

    async def run():
        pending = agent.process_with_tools("What is SPY's stop?")
        assert asyncio.iscoroutine(pending)
        return await pending

    assert asyncio.run(run()) == "SPY's stop is $744.47."


def test_agents_get_the_market_tools_by_default():
    names = {tool.name for tool in _Agent(name="default").tools}

    assert {"fetch_unified_market_data", "fetch_market_context_data"} <= names
