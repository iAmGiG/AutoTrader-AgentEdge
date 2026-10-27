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


def test_the_request_covers_the_lookback_in_trading_days_through_today(fetch):
    tools.get_atr("spy")

    symbol, start, end, timeframe = fetch.calls[0]
    assert (symbol, timeframe) == ("SPY", "1Day")
    assert start == "2026-07-27"  # 65 NYSE trading days before 2026-10-27 (Labor Day closed)
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


def test_the_current_price_is_the_latest_and_indicators_use_completed_bars(fetch):
    text = tools.get_atr("SPY", lookback_days=60)
    completed = fetch.frame.iloc[:-1].tail(60)
    atr = tools.calculate_atr(completed["High"], completed["Low"], completed["Close"]).iloc[-1]

    assert f"Current Price: ${fetch.frame['Close'].iloc[-1]:.2f}" in text
    assert f"ATR (14):     ${atr:.2f}" in text


def test_volume_is_the_last_completed_session_not_todays_zero(fetch):
    text = tools.get_volume_analysis("SPY")

    last_session = int(fetch.frame["Volume"].iloc[-2])
    assert f"Last Session:   {last_session:,}" in text
    assert "Last Session:   0" not in text


def test_after_the_close_todays_bar_counts(fetch, monkeypatch):
    monkeypatch.setattr(tools, "is_market_hours", lambda: False)
    fetch.frame = _bars(today_bar=False)
    final = fetch.frame.copy()
    last = float(final["Close"].iloc[-1])
    final.loc[pd.Timestamp("2026-10-27 04:00", tz="UTC")] = [
        last,
        last * 1.01,
        last * 0.99,
        last,
        3e6,
    ]
    fetch.frame = final

    text = tools.get_volume_analysis("SPY")

    assert "Last Session:   3,000,000" in text


def test_the_lookback_is_trimmed_to_the_latest_bars(fetch):
    bars, price = tools._daily_bars("SPY", 60)

    assert len(bars) == 60 and price == fetch.frame["Close"].iloc[-1]
    assert bars.index[-1] == pd.Timestamp("2026-10-26 04:00", tz="UTC")


@pytest.mark.parametrize(
    "call, message",
    [
        (lambda: tools.get_entry_plan("SPY", "buy", lookback_days=10), "at least 20"),
        (lambda: tools.get_support_resistance("SPY", lookback_days=10), "at least 20"),
        (lambda: tools.get_volume_analysis("SPY", lookback_days=10), "at least 20"),
        (lambda: tools.get_atr("SPY", period=30, lookback_days=25), "at least period + 1"),
    ],
)
def test_too_short_a_lookback_is_explained(fetch, call, message):
    assert message in call()
    assert fetch.calls == []


def test_no_data_or_too_little_is_reported(fetch):
    fetch.frame = pd.DataFrame()
    assert "Insufficient data for SPY" in tools.get_support_resistance("SPY")
    assert "Insufficient data for SPY" in tools.get_atr("SPY")

    fetch.frame = _bars(sessions=15)
    assert "Insufficient data for SPY" in tools.get_entry_plan("SPY", "buy")
