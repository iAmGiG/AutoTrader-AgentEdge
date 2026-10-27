"""Market data comes from the cache, then Alpaca, then Alpha Vantage; Polygon is gone (#607)."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

import src.market_data as market_data
from src.market_data import unified_market_tool as tool

BARS = pd.DataFrame({"close": [100.0, 101.0]})


@pytest.fixture
def sources(monkeypatch):
    """Cache misses; each source is a mock (no API calls)."""
    cache = MagicMock()
    cache.get_market_data.return_value = None
    monkeypatch.setattr(tool, "cache_adapter", cache)
    alpaca, alpha_vantage = MagicMock(return_value=BARS), MagicMock(return_value=BARS)
    monkeypatch.setattr(tool, "_fetch_from_alpaca", alpaca)
    monkeypatch.setattr(tool, "_fetch_from_alpha_vantage", alpha_vantage)
    return cache, alpaca, alpha_vantage


def test_alpaca_is_tried_first(sources):
    cache, alpaca, alpha_vantage = sources

    data = tool.fetch_unified_market_data("SPY", "2024-01-02", "2024-01-31")

    assert data is BARS
    alpha_vantage.assert_not_called()
    assert cache.set_market_data.call_args.args[3] == "alpaca"


def test_alpha_vantage_is_the_only_fallback(sources):
    cache, alpaca, alpha_vantage = sources
    alpaca.return_value = None

    tool.fetch_unified_market_data("SPY", "2024-01-02", "2024-01-31")

    alpha_vantage.assert_called_once()
    assert cache.set_market_data.call_args.args[3] == "alpha_vantage"


def test_asking_for_polygon_says_it_was_removed(sources):
    _, alpaca, alpha_vantage = sources

    with pytest.raises(ValueError, match="Polygon was removed.*alpha_vantage"):
        tool.fetch_unified_market_data("SPY", "2024-01-02", "2024-01-31", source="polygon")
    alpaca.assert_not_called()  # no live source stands in for it
    alpha_vantage.assert_not_called()


def test_rows_cached_from_polygon_are_still_served(sources):
    cache, alpaca, _ = sources
    cache.get_market_data.return_value = BARS

    data = tool.fetch_unified_market_data("SPY", "2023-01-03", "2023-12-29", source="polygon")

    assert data is BARS
    assert cache.get_market_data.call_args.args[3] == "polygon"
    alpaca.assert_not_called()


def test_no_polygon_tool_is_exported():
    assert not hasattr(tool, "_fetch_from_polygon")
    assert all("olygon" not in name for name in market_data.__all__)
    with pytest.raises(AttributeError):
        market_data.PolygonHistoricalTool
