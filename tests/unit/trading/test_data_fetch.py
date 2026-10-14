"""fetch_market_data standardizes column names without touching the (possibly cached) source."""

import pandas as pd

import src.trading.instruments.data_fetch as data_fetch


def test_columns_renamed_on_a_copy(monkeypatch):
    source = pd.DataFrame(
        {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5], "volume": [10]}
    )
    monkeypatch.setattr(data_fetch, "fetch_unified_market_data", lambda *a, **k: source)

    data = data_fetch.fetch_market_data("SPY", "2026-10-01", "2026-10-09")

    assert list(data.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert list(source.columns) == ["open", "high", "low", "close", "volume"]


def test_no_data_returns_none(monkeypatch):
    monkeypatch.setattr(data_fetch, "fetch_unified_market_data", lambda *a, **k: pd.DataFrame())

    assert data_fetch.fetch_market_data("SPY", "2026-10-01", "2026-10-09") is None
