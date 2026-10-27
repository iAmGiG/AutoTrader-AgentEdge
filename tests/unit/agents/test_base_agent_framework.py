"""
BaseAgent on Microsoft Agent Framework (#606): LLM conversations with tool calling.

A fake model server (httpx2.MockTransport) stands in for OpenAI, so nothing leaves
the machine and no API key is needed.
"""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx2
import openai
import pandas as pd
import pytest
from agent_framework import FunctionTool

from src.autogen_agents.core import base_agent
from src.autogen_agents.core.base_agent import BaseAgent
from src.autogen_agents.tools.market_tools import market_data_result, unified_market_tool

RealAsyncOpenAI = openai.AsyncOpenAI
executed = []


def lookup_price(symbol: str) -> str:
    """Stand-in market tool."""
    executed.append(symbol)
    return json.dumps({"symbol": symbol, "price": 744.47})


LOOKUP = FunctionTool(func=lookup_price, name="lookup_price", description="Latest price")


class _Agent(BaseAgent):
    def generate_reply(self, messages, context=None) -> str:
        return ""


def _completion(message, finish):
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "finish_reason": finish, "message": message}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


ANSWER = _completion({"role": "assistant", "content": "SPY's stop is $744.47."}, "stop")


def _tool_call(call_id, name="lookup_price", arguments='{"symbol": "SPY"}'):
    call = {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}
    return _completion({"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls")


@pytest.fixture
def credentials(monkeypatch):
    """A key and model for the agent's own client factory (no config.json in CI)."""
    monkeypatch.setattr(base_agent, "open_ai_key", "sk-test")
    monkeypatch.setattr(base_agent, "model_name", "gpt-4o-mini")


@pytest.fixture
def fake_model(monkeypatch, credentials):
    """Route the agent's OpenAI clients to a fake model; returns the requests it saw."""
    requests = []
    behaviour = {
        "answer_after_tool": True,
        "tool": "lookup_price",
        "arguments": '{"symbol": "SPY"}',
    }

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        tools_allowed = bool(body.get("tools")) and body.get("tool_choice") != "none"
        tool_result = [m for m in body["messages"] if m.get("role") == "tool"]
        if tools_allowed and not (behaviour["answer_after_tool"] and tool_result):
            reply = _tool_call(f"call_{len(requests)}", behaviour["tool"], behaviour["arguments"])
        else:
            reply = ANSWER
        return httpx2.Response(200, json=reply)

    def fake_async_openai(**kwargs):
        transport = httpx2.MockTransport(handler)
        return RealAsyncOpenAI(
            api_key="sk-test", http_client=httpx2.AsyncClient(transport=transport)
        )

    monkeypatch.setattr(base_agent.openai, "AsyncOpenAI", fake_async_openai)
    return requests, behaviour


def _tool_messages(request):
    return [json.dumps(m) for m in request["messages"] if m.get("role") == "tool"]


@pytest.fixture(autouse=True)
def _clear_executed():
    executed.clear()


def test_an_agent_needs_no_api_key_until_it_calls_the_llm(monkeypatch):
    monkeypatch.setattr(base_agent, "open_ai_key", None)

    agent = _Agent(name="calc_only")  # building it is fine

    assert agent.name == "calc_only" and agent._model_client is None
    assert "OpenAI API key not found" in agent.process_with_tools("hello")


def test_the_model_calls_a_tool_and_answers_from_its_result(fake_model):
    requests, _ = fake_model
    agent = _Agent(name="tester", tools=[LOOKUP])

    answer = agent.process_with_tools("What is SPY's stop?", system_prompt="You manage stops.")

    assert answer == "SPY's stop is $744.47."
    assert executed == ["SPY"]
    first = requests[0]
    assert first["messages"][0] == {"role": "system", "content": "You manage stops."}
    assert [t["function"]["name"] for t in first["tools"]] == ["lookup_price"]
    assert (first["temperature"], first["top_p"]) == (0.2, 0.95)
    assert first.get("max_tokens", first.get("max_completion_tokens")) == 4096


def test_tool_rounds_are_capped_then_the_model_must_answer_in_text(fake_model):
    requests, behaviour = fake_model
    behaviour["answer_after_tool"] = False  # the model always wants a tool
    agent = _Agent(name="tester", tools=[LOOKUP])

    answer = agent.process_with_tools("Keep looking things up")

    assert answer == "SPY's stop is $744.47."
    assert len(executed) == agent.max_tool_rounds == 2
    assert [r.get("tool_choice") for r in requests] == ["auto", "auto", "none"]


def test_a_change_to_the_cap_applies_to_the_next_call(fake_model):
    requests, behaviour = fake_model
    behaviour["answer_after_tool"] = False
    agent = _Agent(name="tester", tools=[LOOKUP])

    async def two_calls():  # one event loop, so the second call reuses the client
        await agent.process_with_tools_async("Keep looking things up")
        requests.clear()
        agent.max_tool_rounds = 1
        await agent.process_with_tools_async("Keep looking things up")

    asyncio.run(two_calls())

    assert [r.get("tool_choice") for r in requests] == ["auto", "none"]


def test_inside_an_event_loop_the_caller_awaits_the_answer(fake_model):
    agent = _Agent(name="tester", tools=[LOOKUP])

    async def run():
        pending = agent.process_with_tools("What is SPY's stop?")
        assert asyncio.iscoroutine(pending)
        return await pending

    assert asyncio.run(run()) == "SPY's stop is $744.47."


def test_market_bars_reach_the_model_as_json_records(fake_model):
    requests, behaviour = fake_model
    behaviour["tool"] = "fetch_bars"
    index = pd.DatetimeIndex(["2026-10-20", "2026-10-21"], name="date")
    bars = pd.DataFrame({"close": [741.2, 744.47], "volume": [1, 2]}, index=index)
    tool = FunctionTool(
        func=lambda symbol: bars, name="fetch_bars", result_parser=market_data_result
    )
    agent = _Agent(name="tester", tools=[tool])

    assert agent.process_with_tools("SPY bars?") == "SPY's stop is $744.47."

    (sent,) = _tool_messages(requests[1])
    records = json.loads(json.loads(sent)["content"])
    assert records[1]["close"] == 744.47 and records[1]["date"].startswith("2026-10-21")
    assert unified_market_tool.result_parser is market_data_result


def test_the_model_is_told_why_a_tool_failed(fake_model):
    requests, _ = fake_model

    def failing(symbol: str) -> str:
        raise ValueError("Polygon was removed as a data source (#607)")

    agent = _Agent(name="tester", tools=[FunctionTool(func=failing, name="lookup_price")])

    agent.process_with_tools("What is SPY's stop?")

    (sent,) = _tool_messages(requests[1])
    assert "Polygon was removed as a data source" in sent


class _KeepAliveModel(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive, so a client's pool reuses connections

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps(ANSWER).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_repeated_synchronous_calls_each_get_a_working_client(monkeypatch, credentials):
    # Each synchronous call runs in a new event loop (asyncio.run); a client whose pooled
    # connection belongs to the previous, closed loop fails with "Event loop is closed".
    server = ThreadingHTTPServer(("127.0.0.1", 0), _KeepAliveModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_address[1]}/v1")
    agent = _Agent(name="tester", tools=[])

    try:
        answers = [agent.process_with_tools("What is SPY's stop?") for _ in range(3)]
    finally:
        server.shutdown()

    assert answers == ["SPY's stop is $744.47."] * 3


def test_agents_get_the_market_tools_by_default():
    names = {tool.name for tool in _Agent(name="default").tools}

    assert {"fetch_unified_market_data", "fetch_market_context_data"} <= names
