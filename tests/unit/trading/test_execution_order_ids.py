"""Execution results carry the bracket's real leg IDs, never IDs made up from the entry."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import src.trading.broker.alpaca_execution_manager as execution_module
from src.core.models import OrderType
from src.trading.broker.advanced_orders import _bracket_leg_ids


class _DefaultsConfig:
    def get(self, key, default=None):
        return default


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(execution_module, "ConfigLoader", _DefaultsConfig)
    monkeypatch.setattr(execution_module, "is_market_hours", lambda: True)
    order_manager = MagicMock()
    return execution_module.AlpacaExecutionManager(order_manager=order_manager), order_manager


def test_leg_ids_from_submitted_bracket():
    order = SimpleNamespace(
        legs=[
            SimpleNamespace(id="tp-1", stop_price=None, limit_price=712.8),
            SimpleNamespace(id="sl-1", stop_price=627.0, limit_price=None),
        ]
    )

    assert _bracket_leg_ids(order) == {"stop_order_id": "sl-1", "take_profit_order_id": "tp-1"}
    assert _bracket_leg_ids(SimpleNamespace(legs=None)) == {
        "stop_order_id": None,
        "take_profit_order_id": None,
    }


def test_bracket_buy_reports_real_leg_ids(manager):
    em, om = manager
    om.place_bracket_order.return_value = {
        "status": "submitted",
        "order_id": "entry-1",
        "stop_order_id": "sl-1",
        "take_profit_order_id": "tp-1",
    }

    result = asyncio.run(em._place_order("SPY", 7, "BUY", 660.0, 627.0, 712.8, OrderType.MARKET))

    assert (result.entry_order_id, result.stop_order_id, result.target_order_id) == (
        "entry-1",
        "sl-1",
        "tp-1",
    )


def test_sell_reports_no_leg_ids(manager):
    em, om = manager
    om.place_market_order.return_value = {"status": "submitted", "order_id": "exit-1"}

    result = asyncio.run(em._place_order("SPY", 7, "SELL", 660.0, 627.0, 712.8, OrderType.MARKET))

    assert result.entry_order_id == "exit-1"
    assert result.stop_order_id is None and result.target_order_id is None
    assert "bracket" not in result.message


def test_order_declined_at_live_confirmation_is_not_reported_as_placed(manager):
    em, om = manager
    om.place_bracket_order.return_value = {
        "status": "cancelled",
        "message": "Order cancelled by user",
    }

    result = asyncio.run(em._place_order("SPY", 7, "BUY", 660.0, 627.0, 712.8, OrderType.MARKET))

    assert not result.success
    assert result.entry_order_id is None


def test_success_display_shows_none_for_missing_legs(capsys):
    from src.cli.utils.suggestion_display import display_result
    from src.core.models import OrderResult

    display_result(OrderResult(success=True, entry_order_id="exit-1", ticker="SPY", quantity=7))

    out = capsys.readouterr().out
    assert "Stop Order:   none" in out
    assert "None" not in out
