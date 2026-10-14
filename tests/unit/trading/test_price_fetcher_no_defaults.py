"""
No made-up prices: without a real price the fetcher returns None and callers skip.

The fetcher used to return hard-coded prices (SOXL $28.40, $100 for unknown symbols)
that fed bracket and trailing-stop calculations.
"""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import src.trading.utils.unified_price_fetcher as upf
from src.trading.orders.trailing_stop_manager import TrailingStopManager


@pytest.fixture
def fetcher(monkeypatch):
    monkeypatch.setattr(upf.UnifiedPriceFetcher, "_cache", {})
    instance = object.__new__(upf.UnifiedPriceFetcher)  # skip the shared singleton
    instance.market_data = MagicMock()
    instance.market_data.get_latest_trade.return_value = None
    instance.market_data.get_latest_quote.return_value = None
    instance.market_data.get_bars.return_value = None
    return instance


@pytest.mark.parametrize("symbol", ["SOXL", "SPY", "XYZ"])
def test_no_real_price_returns_none(fetcher, symbol):
    assert fetcher.get_current_price(symbol) is None
    assert symbol not in upf.UnifiedPriceFetcher._cache


def test_real_trade_price_is_returned(fetcher):
    fetcher.market_data.get_latest_trade.return_value = {"price": 120.38}

    assert fetcher.get_current_price("SOXL") == 120.38


def test_day_old_cache_entry_is_not_fresh(fetcher):
    stale = upf.get_datetime_now() - timedelta(days=1, seconds=10)
    upf.UnifiedPriceFetcher._cache["SPY"] = {"price": 600.0, "timestamp": stale}
    fetcher.market_data.get_latest_trade.return_value = {"price": 661.5}

    assert fetcher.get_current_price("SPY") == 661.5


def test_trailing_stops_skip_symbols_without_a_price():
    manager = TrailingStopManager(order_manager=MagicMock())
    manager.stop_states = {"SPY": MagicMock()}
    manager.update_stop = MagicMock()

    results = manager.check_all_positions(price_fetcher=lambda symbol: None)

    assert results["SPY"]["status"] == "error"
    manager.update_stop.assert_not_called()
