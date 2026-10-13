"""market_context_tool loads bars through the unified data path (#578)."""

import pandas as pd
import pytest

import src.market_data.market_context_tool as mct


def _bars(dates, closes, upper=False, tz=None):
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    if tz:
        idx = idx.tz_localize(tz)
    df = pd.DataFrame({"close": closes, "volume": [1000] * len(closes)}, index=idx)
    if upper:
        df["Close"] = df["close"]
        df["Volume"] = df["volume"]
    return df


@pytest.fixture
def fake_fetch(monkeypatch):
    calls = []

    def install(frame):
        def _fetch(symbol, start_date, end_date, source="auto", timeframe="1Day"):
            calls.append((symbol, start_date, end_date, source, timeframe))
            return frame

        monkeypatch.setattr(mct, "fetch_unified_market_data", _fetch)
        return calls

    return install


def test_uses_unified_fetch_for_recent_dates(fake_fetch):
    dates = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"]
    calls = fake_fetch(_bars(dates, [100.0, 101.0, 102.0, 103.0, 104.0]))
    out = mct.fetch_market_context_data(date="2026-10-09", symbols=["SPY"])
    spy = out["market_context"]["SPY"]
    assert spy["current_price"] == pytest.approx(104.0)
    assert spy["daily_change_pct"] == pytest.approx(round((104 - 103) / 103 * 100, 2))
    assert "error" not in spy
    # One day past the target (Alpaca end is exclusive); later bars are filtered out
    assert calls[0][0] == "SPY" and calls[0][2] == "2026-10-10" and calls[0][3] == "auto"


def test_excludes_bars_after_the_date(fake_fetch):
    dates = ["2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12"]
    fake_fetch(_bars(dates, [100.0, 101.0, 102.0, 999.0]))
    spy = mct.fetch_market_context_data(date="2026-10-09", symbols=["SPY"])["market_context"]["SPY"]
    assert spy["current_price"] == pytest.approx(102.0)


def test_handles_mixed_case_columns_duplicates_and_tz(fake_fetch):
    frame = _bars(
        ["2026-10-08", "2026-10-08", "2026-10-09"], [100.0, 100.0, 105.0], upper=True, tz="UTC"
    )
    fake_fetch(frame)
    spy = mct.fetch_market_context_data(date="2026-10-09", symbols=["SPY"])["market_context"]["SPY"]
    assert spy["current_price"] == pytest.approx(105.0)
    assert spy["daily_change_pct"] == pytest.approx(5.0)


def test_empty_data_returns_placeholder(fake_fetch):
    fake_fetch(pd.DataFrame())
    spy = mct.fetch_market_context_data(date="2026-10-09", symbols=["SPY"])["market_context"]["SPY"]
    assert spy["current_price"] == 0.0
    assert "No data available" in spy["interpretation"]
