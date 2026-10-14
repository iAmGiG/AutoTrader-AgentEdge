"""
The off-hours bracket fallback places a market BUY, so it must only follow a failed
bracket entry. A failed SELL retried that way would add to the position it was exiting.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

import src.trading.broker.alpaca_execution_manager as execution_module
from src.core.models import OrderType

# HTTP 422 with Alpaca's generic 4221xxxx code: classified as a bracket validation error
VALIDATION_ERROR = {
    "status": "error",
    "message": "invalid order",
    "error_code": 42210000,
    "status_code": 422,
}


class _DefaultsConfig:
    """Stands in for ConfigLoader so no config/config.json is needed."""

    def get(self, key, default=None):
        return default


@pytest.fixture
def offhours_manager(monkeypatch):
    monkeypatch.setattr(execution_module, "ConfigLoader", _DefaultsConfig)
    monkeypatch.setattr(execution_module, "is_market_hours", lambda: False)
    order_manager = MagicMock()
    manager = execution_module.AlpacaExecutionManager(order_manager=order_manager)
    return manager, order_manager


def test_failed_offhours_sell_is_not_retried_as_buy(offhours_manager):
    manager, order_manager = offhours_manager
    order_manager.place_market_order.side_effect = lambda symbol, qty, side: (
        VALIDATION_ERROR if side == "sell" else {"status": "submitted", "order_id": "buy-1"}
    )

    with pytest.raises(Exception, match="invalid order"):
        asyncio.run(manager._place_order("SOXL", 20, "SELL", 30.0, 28.5, 32.4, OrderType.MARKET))

    sides = [c.kwargs["side"] for c in order_manager.place_market_order.call_args_list]
    assert sides == ["sell"]


def test_failed_offhours_bracket_buy_still_falls_back(offhours_manager):
    manager, order_manager = offhours_manager
    order_manager.place_bracket_order.return_value = VALIDATION_ERROR
    order_manager.place_market_order.return_value = {"status": "submitted", "order_id": "buy-1"}

    result = asyncio.run(
        manager._place_order("SOXL", 20, "BUY", 30.0, 28.5, 32.4, OrderType.MARKET)
    )

    assert result.success
    assert result.entry_order_id == "buy-1"
    order_manager.place_market_order.assert_called_once_with(symbol="SOXL", qty=20, side="buy")
