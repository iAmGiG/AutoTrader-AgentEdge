"""
LLMParser (#606): one LLM call; the arguments of its parse_trade_request tool call
are the parsed request. A fake model server stands in for OpenAI.
"""

import asyncio
import json

import httpx2
import openai
import pytest
from agent_framework.openai import RawOpenAIChatCompletionClient

from src.parsers import AutoGenLLMParser, LLMParser


def _parser(handler):
    requests = []

    def recording(request):
        requests.append(json.loads(request.content))
        return handler(request)

    async_client = openai.AsyncOpenAI(
        api_key="sk-test",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(recording)),
    )
    client = RawOpenAIChatCompletionClient(model="gpt-4o-mini", async_client=async_client)
    return LLMParser(model_client=client), requests


def _completion(message, finish="stop"):
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


def _parse_call(arguments):
    return _completion(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "parse_trade_request", "arguments": json.dumps(arguments)},
                }
            ],
        },
        "tool_calls",
    )


def test_the_tool_call_arguments_are_the_parsed_request():
    args = {"request_type": "trade", "ticker": "aapl", "action": "buy", "quantity": 50}
    parser, requests = _parser(lambda r: _parse_call(args))

    request = asyncio.run(parser.parse("buy 50 AAPL"))

    assert (request.ticker, request.action, request.quantity) == ("AAPL", "buy", 50)
    assert request.raw_input == "buy 50 AAPL"
    assert len(requests) == 1  # the tool is offered, not run (no second call)
    assert [t["function"]["name"] for t in requests[0]["tools"]] == ["parse_trade_request"]
    assert requests[0]["temperature"] == 0.0


def test_a_status_query_and_entry_timing_come_through():
    args = {"request_type": "status_query", "ticker": "", "action": "review", "timing": None}
    parser, _ = _parser(lambda r: _parse_call(args))

    request = asyncio.run(parser.parse("any open orders?"))

    assert (request.request_type, request.ticker, request.timing) == ("status_query", "", None)


def test_no_tool_call_is_a_parse_error():
    parser, _ = _parser(lambda r: _completion({"role": "assistant", "content": "Sure!"}))

    with pytest.raises(ValueError, match="Could not parse input"):
        asyncio.run(parser.parse("hello"))


def test_an_authentication_failure_is_a_configuration_error():
    parser, _ = _parser(
        lambda r: httpx2.Response(401, json={"error": {"message": "Incorrect API key"}})
    )

    with pytest.raises(ValueError, match="Configuration error"):
        asyncio.run(parser.parse("buy 50 AAPL"))


def test_the_old_name_still_works():
    assert AutoGenLLMParser is LLMParser
