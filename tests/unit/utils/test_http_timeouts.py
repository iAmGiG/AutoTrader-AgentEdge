"""Requests to a broker or data vendor that stops answering fail instead of hanging forever."""

import socket
import time
from unittest.mock import Mock

import pytest
import requests
from alpaca.trading.client import TradingClient

import src.utils.market_hours as mh
from src.market_data import alpha_vantage_market
from src.market_data.alpha_vantage_market import AlphaVantageMarketTool
from src.utils import http_timeouts
from src.utils.http_timeouts import set_default_timeout, with_default_timeout


@pytest.fixture
def silent_port():
    """The port of a local server that takes connections (its backlog) and never answers."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    yield server.getsockname()[1]
    server.close()


def test_the_defaults_are_ten_seconds_to_connect_and_thirty_to_read():
    assert http_timeouts.DEFAULT_TIMEOUT == (10, 30)


def test_a_request_without_a_timeout_gets_the_default():
    session = requests.Session()
    seen = []
    session.request = lambda method, url, **kwargs: seen.append(kwargs) or "response"

    set_default_timeout(session)
    assert session.request("GET", "http://example.invalid/") == "response"

    assert seen == [{"timeout": (10, 30)}]


def test_an_explicit_timeout_wins_even_none():
    session = requests.Session()
    seen = []
    session.request = lambda method, url, **kwargs: seen.append(kwargs)

    set_default_timeout(session, (1, 2))
    session.request("GET", "http://example.invalid/", timeout=5)
    session.request("GET", "http://example.invalid/", timeout=None)

    assert seen == [{"timeout": 5}, {"timeout": None}]


def test_a_silent_port_fails_a_session_within_the_timeout(silent_port):
    port = silent_port
    session = set_default_timeout(requests.Session(), (1, 0.5))

    started = time.monotonic()
    with pytest.raises(requests.exceptions.Timeout):
        session.get(f"http://127.0.0.1:{port}/")

    assert time.monotonic() - started < 5


def test_a_silent_port_fails_a_real_alpaca_client_within_the_timeout(silent_port):
    port = silent_port
    client = TradingClient("key", "secret", url_override=f"http://127.0.0.1:{port}")
    with_default_timeout(client, (1, 0.5))

    started = time.monotonic()
    with pytest.raises(requests.exceptions.Timeout):
        client.get_account()

    assert time.monotonic() - started < 5


def test_an_explicit_timeout_wins_against_a_silent_port(silent_port):
    port = silent_port
    session = set_default_timeout(requests.Session(), (60, 60))

    started = time.monotonic()
    with pytest.raises(requests.exceptions.Timeout):
        session.get(f"http://127.0.0.1:{port}/", timeout=(1, 0.5))

    assert time.monotonic() - started < 5


def test_a_client_without_a_session_is_left_alone_with_a_warning(caplog):
    client = object()

    assert with_default_timeout(client) is client
    assert "no default timeout" in caplog.text


def test_the_market_calendar_client_gets_the_default_timeout(monkeypatch):
    class Config:
        def get(self, key, default=None):
            return {"ALPACA_PAPER_API_KEY": "pk", "ALPACA_PAPER_SECRET": "ps"}.get(key, default)

    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", mh._UNSET)
    monkeypatch.setattr(mh, "ConfigLoader", Config)
    monkeypatch.setattr(mh, "TradingClient", TradingClient)
    seen = []
    monkeypatch.setattr(requests.Session, "request", lambda self, m, u, **kw: seen.append(kw))

    client = mh._get_alpaca_calendar()
    client._session.request("GET", "http://example.invalid/")

    assert seen == [{"timeout": (10, 30)}]


def test_every_alpha_vantage_request_has_a_timeout(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        return Mock(status_code=500, text="down")

    monkeypatch.setattr(alpha_vantage_market.requests, "get", fake_get)
    cache = Mock()
    cache.get.return_value = None
    tool = AlphaVantageMarketTool(cache_manager=cache)

    tool.fetch_stock_data("SPY", "2026-10-01", "2026-10-09")
    tool.fetch_company_overview("SPY")
    tool.fetch_intraday_data("SPY")
    tool.fetch_fx_data("EUR", "USD")

    assert len(calls) == 4
    assert all(call["timeout"] == (10, 30) for call in calls)
