"""
Entry planning CLI tools: daily bars through fetch_market_data. They imported a
fetch_historical that doesn't exist, so every call returned an error.

During the session the data ends with today's bar so far (or one made from the last
trade, volume 0): its close is the current price, and the indicators use completed bars.
"""

import numpy as np
import pandas as pd
import pytest

from src.cli.tools import entry_planning_tools as tools

TODAY = "2026-10-27"


def _bars(sessions=100, today_bar=True):
    """Daily bars stamped like Alpaca's (midnight ET in UTC), ending with today's."""
    days = pd.bdate_range(end="2026-10-26", periods=sessions)
    rng = np.random.default_rng(7)
    close = 600 * np.cumprod(1 + rng.normal(0.0005, 0.01, sessions))
    frame = pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.integers(2_000_000, 4_000_000, sessions),
        },
        index=pd.DatetimeIndex(days + pd.Timedelta(hours=4), tz="UTC", name="timestamp"),
    )
    if today_bar:
        now = pd.Timestamp("2026-10-27 14:30", tz="UTC")
        last = round(float(close[-1]) * 1.002, 2)
        frame.loc[now] = [last, last, last, last, 0]  # synthetic: the last trade, no volume
    return frame


@pytest.fixture
def fetch(monkeypatch):
    calls = []

    def fake(symbol, start, end, timeframe="1Day"):
        calls.append((symbol, start, end, timeframe))
        return fake.frame

    fake.frame = _bars()
    fake.calls = calls
    monkeypatch.setattr(tools, "fetch_market_data", fake)
    monkeypatch.setattr(tools, "market_today", lambda: TODAY)
    monkeypatch.setattr(tools, "is_market_hours", lambda: True)
    return fake


def _atr_of(frame, lookback=60):
    bars = frame.tail(lookback)
    return tools.calculate_atr(bars["High"], bars["Low"], bars["Close"]).iloc[-1]


def test_the_request_covers_the_lookback_in_trading_days_through_today(fetch):
    tools.get_atr("spy")

    symbol, start, end, timeframe = fetch.calls[0]
    assert (symbol, timeframe) == ("SPY", "1Day")
    assert start == "2026-07-20"  # 60 + 10 NYSE trading days before 2026-10-27 (Labor Day closed)
    assert end == "2026-10-28"  # the end date's own bar isn't returned


@pytest.mark.parametrize(
    "tool, heading",
    [
        (lambda: tools.get_entry_plan("SPY", "buy"), "Entry Plan for SPY (BUY)"),
        (lambda: tools.get_support_resistance("SPY"), "Support/Resistance for SPY"),
        (lambda: tools.get_volume_analysis("SPY"), "Volume Analysis for SPY"),
        (lambda: tools.get_atr("SPY"), "ATR Analysis for SPY"),
    ],
)
def test_each_tool_works_again(fetch, tool, heading):
    text = tool()

    assert heading in text
    assert "Error" not in text and "Insufficient" not in text


def test_in_session_the_price_is_live_and_indicators_use_completed_bars(fetch):
    text = tools.get_atr("SPY", lookback_days=60)

    assert f"Current Price: ${fetch.frame['Close'].iloc[-1]:.2f} (live)" in text
    assert f"ATR (14):     ${_atr_of(fetch.frame.iloc[:-1]):.2f}" in text


def test_before_the_open_the_price_is_the_last_close_and_says_so(fetch, monkeypatch):
    monkeypatch.setattr(tools, "is_market_hours", lambda: False)
    fetch.frame = _bars(today_bar=False)

    text = tools.get_support_resistance("SPY")

    assert f"Current Price: ${fetch.frame['Close'].iloc[-1]:.2f} (2026-10-26 close)" in text


def test_after_the_close_todays_bar_counts(fetch, monkeypatch):
    monkeypatch.setattr(tools, "is_market_hours", lambda: False)
    final = _bars(today_bar=False)
    last = float(final["Close"].iloc[-1])
    final.loc[pd.Timestamp("2026-10-27 04:00", tz="UTC")] = [
        last,
        last * 1.01,
        last * 0.99,
        last,
        3e6,
    ]
    fetch.frame = final

    assert "Last Session:   3,000,000" in tools.get_volume_analysis("SPY")
    assert "(2026-10-27 close)" in tools.get_atr("SPY")


def test_volume_is_the_last_completed_session_not_todays_zero(fetch):
    text = tools.get_volume_analysis("SPY")

    last_session = int(fetch.frame["Volume"].iloc[-2])
    assert f"Last Session:   {last_session:,}" in text
    assert "Last Session:   0" not in text


def test_bars_newest_first_are_put_in_order(fetch):
    """Alpha Vantage returns daily bars newest first, on a naive index."""
    ascending = tools.get_atr("SPY")
    newest_first = fetch.frame.iloc[::-1].copy()
    newest_first.index = newest_first.index.tz_convert("America/New_York").tz_localize(None)
    fetch.frame = newest_first

    assert tools.get_atr("SPY") == ascending


def test_a_date_column_works_when_the_index_is_not_dates(fetch):
    with_column = fetch.frame.reset_index().rename(columns={"timestamp": "date"})
    fetch.frame = with_column

    bars, price, as_of = tools._completed_bars("SPY", 60)

    assert len(bars) == 60 and as_of == "live"
    assert bars["Volume"].iloc[-1] > 0  # the synthetic bar was left out
    assert price == with_column["Close"].iloc[-1]


def test_if_the_calendar_fails_todays_bar_is_left_out(fetch, monkeypatch):
    def unreachable():
        raise ConnectionError("calendar timeout")

    monkeypatch.setattr(tools, "is_market_hours", unreachable)

    bars, _, as_of = tools._completed_bars("SPY", 60)

    assert bars.index[-1] == pd.Timestamp("2026-10-26 04:00", tz="UTC") and as_of == "live"


def test_the_lookback_is_trimmed_to_the_latest_bars(fetch):
    bars, price, _ = tools._completed_bars("SPY", 60)

    assert len(bars) == 60 and price == fetch.frame["Close"].iloc[-1]
    assert bars.index[-1] == pd.Timestamp("2026-10-26 04:00", tz="UTC")


@pytest.mark.parametrize(
    "call, message",
    [
        (lambda: tools.get_entry_plan("SPY", "buy", lookback_days=10), "at least 20."),
        (lambda: tools.get_support_resistance("SPY", lookback_days=10), "at least 20."),
        (lambda: tools.get_volume_analysis("SPY", lookback_days=10), "at least 20."),
        (lambda: tools.get_atr("SPY", period=30, lookback_days=25), "at least 31."),
    ],
)
def test_too_short_a_lookback_is_explained(fetch, call, message):
    assert f"lookback_days must be {message}" in call()
    assert fetch.calls == []


def test_no_data_and_too_little_data_say_which(fetch):
    fetch.frame = pd.DataFrame()
    assert "No daily bars for SPY: the data request failed" in tools.get_support_resistance("SPY")
    assert "No daily bars for SPY" in tools.get_atr("SPY")

    fetch.frame = _bars(sessions=15)
    assert "Insufficient data for SPY: 15 completed daily bars, need at least 20." in (
        tools.get_entry_plan("SPY", "buy")
    )
