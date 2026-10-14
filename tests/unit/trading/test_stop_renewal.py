"""
Protective stops don't lapse silently (#586).

Alpaca cancels GTC orders 90 days after creation, bracket legs included. A long
position with no live stop gets one re-placed at its last known stop, and a GTC stop
nearing 90 days is renewed. All broker calls are mocked; no orders are placed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.trading.scheduling.trading_cycle import CostEfficientTradeCycle
from src.trading.state.state_reconciler import (
    StateReconciler,
    StopAdjustment,
    StopRepair,
)

NOW = datetime(2026, 10, 14, 13, 0, tzinfo=timezone.utc)


def _reconciler():
    config = MagicMock()
    config.get_risk_config.return_value = 0.05  # stop loss
    return StateReconciler(config=config)


def _broker(price=769.2, quantity=14, orders=(), side="long"):
    return {
        "positions": {
            "SPY": {
                "symbol": "SPY",
                "quantity": quantity,
                "entry_price": 657.6,
                "current_price": price,
                "side": side,
            }
        },
        "orders": {"SPY": list(orders)} if orders else {},
    }


def _local(stop_price=627.0):
    return {"positions": {"SPY": {"entry_price": 657.6, "quantity": 14, "stop_price": stop_price}}}


def _stop_order(age_days, tif="gtc", order_id="sl-1"):
    return {
        "id": order_id,
        "type": "stop",
        "side": "sell",
        "quantity": 14,
        "stop_price": 627.0,
        "time_in_force": tif,
        "created_at": (NOW - timedelta(days=age_days)).isoformat(),
    }


class TestCheckProtectiveStops:
    def test_missing_stop_is_replaced_at_last_known_stop(self):
        review, repairs = _reconciler().check_protective_stops(_broker(), _local(), NOW)

        assert review == []
        assert repairs == [
            StopRepair(
                kind="MISSING_STOP",
                symbol="SPY",
                quantity=14,
                stop_price=627.0,
                reason="no live stop order (GTC stops lapse after 90 days)",
            )
        ]

    def test_missing_stop_without_saved_level_uses_entry_minus_stop_loss(self):
        _, repairs = _reconciler().check_protective_stops(_broker(), _local(None), NOW)

        assert repairs[0].stop_price == round(657.6 * 0.95, 2)

    def test_position_below_its_stop_is_left_for_review(self):
        review, repairs = _reconciler().check_protective_stops(_broker(price=600.0), _local(), NOW)

        assert repairs == []
        assert review[0].type == "MISSING_STOP"
        assert review[0].action == "NEEDS_HUMAN_REVIEW"

    def test_aging_gtc_stop_is_renewed(self):
        broker = _broker(orders=[_stop_order(age_days=85)])

        review, repairs = _reconciler().check_protective_stops(broker, _local(), NOW)

        assert review == []
        assert len(repairs) == 1
        assert repairs[0].kind == "STOP_EXPIRING"
        assert repairs[0].replaces_order_id == "sl-1"
        assert repairs[0].stop_price == 627.0

    @pytest.mark.parametrize("order", [_stop_order(age_days=10), _stop_order(85, tif="day")])
    def test_fresh_or_day_stop_needs_nothing(self, order):
        review, repairs = _reconciler().check_protective_stops(
            _broker(orders=[order]), _local(), NOW
        )

        assert (review, repairs) == ([], [])

    def test_short_positions_are_skipped(self):
        review, repairs = _reconciler().check_protective_stops(_broker(side="short"), _local(), NOW)

        assert (review, repairs) == ([], [])


def _cycle(order_manager):
    cycle = object.__new__(CostEfficientTradeCycle)  # no broker clients
    cycle.order_manager = order_manager
    cycle.broker_cache = MagicMock()
    cycle.reconciler = _reconciler()
    cycle.local_state_manager = MagicMock(state=_local())
    return cycle


class TestRepairStops:
    def test_missing_stop_is_placed_as_gtc_sell_stop(self):
        om = MagicMock()
        om.place_stop_order.return_value = {"status": "submitted", "order_id": "new-sl"}
        cycle = _cycle(om)

        discrepancies, lines = cycle.check_and_repair_stops(_broker())

        om.place_stop_order.assert_called_once_with(
            symbol="SPY", qty=14, side="sell", stop_price=627.0, time_in_force="gtc"
        )
        assert discrepancies[0].type == "MISSING_STOP"
        assert discrepancies[0].action == "AUTO_FIXED"
        assert discrepancies[0].details["order_id"] == "new-sl"
        assert lines[0].startswith("[+] SPY: stop placed at $627.00")
        cycle.broker_cache.invalidate.assert_called_once()

    def test_failed_placement_needs_review(self):
        om = MagicMock()
        om.place_stop_order.return_value = {"status": "error", "message": "insufficient qty"}
        cycle = _cycle(om)

        discrepancies, lines = cycle.check_and_repair_stops(_broker())

        assert discrepancies[0].action == "NEEDS_HUMAN_REVIEW"
        assert "insufficient qty" in lines[0]
        cycle.broker_cache.invalidate.assert_not_called()

    def test_aging_stop_is_renewed_by_replacing_it(self):
        om = MagicMock()
        om.modify_order.return_value = {"status": "submitted", "order_id": "sl-2"}
        cycle = _cycle(om)

        discrepancies, _ = cycle.check_and_repair_stops(_broker(orders=[_stop_order(85)]))

        om.modify_order.assert_called_once_with(order_id="sl-1", stop_price=627.0)
        om.place_stop_order.assert_not_called()
        assert (discrepancies[0].type, discrepancies[0].action) == ("STOP_EXPIRING", "AUTO_FIXED")

    def test_unplaceable_stop_is_reported_without_an_order(self):
        om = MagicMock()
        cycle = _cycle(om)

        discrepancies, lines = cycle.check_and_repair_stops(_broker(price=600.0))

        om.place_stop_order.assert_not_called()
        assert discrepancies[0].action == "NEEDS_HUMAN_REVIEW"
        assert "needs review" in lines[0]


def test_failed_stop_modification_is_not_counted_as_success():
    om = MagicMock()
    om.modify_order.return_value = {"status": "error", "message": "order not found"}
    cycle = _cycle(om)
    adjustment = StopAdjustment("SPY", "sl-1", 627.0, 700.0, "trail", 0.17)

    results = cycle.batch_modify_orders([adjustment])

    assert results["modifications"] == 0
    assert not results["success"]
    assert "order not found" in results["errors"][0]
