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
from src.trading.state.state_reconciler import (StateReconciler,
                                                StopAdjustment, StopRepair)

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

    def test_shares_held_by_another_sell_order_go_to_review(self):
        take_profit = {
            "id": "tp-1",
            "type": "limit",
            "side": "sell",
            "quantity": 14,
            "limit_price": 712.8,
            "time_in_force": "gtc",
            "created_at": (NOW - timedelta(days=5)).isoformat(),
        }
        review, repairs = _reconciler().check_protective_stops(
            _broker(orders=[take_profit]), _local(), NOW
        )

        assert repairs == []
        assert review[0].type == "MISSING_STOP"
        assert "held by open sell orders" in review[0].details["reason"]

    def test_aging_trailing_stop_goes_to_review(self):
        trailing = _stop_order(85)
        trailing["type"] = "trailing_stop"

        review, repairs = _reconciler().check_protective_stops(
            _broker(orders=[trailing]), _local(), NOW
        )

        assert repairs == []
        assert (review[0].type, review[0].action) == ("STOP_EXPIRING", "NEEDS_HUMAN_REVIEW")

    def test_aging_take_profit_is_noticed_next_to_a_renewed_stop(self):
        take_profit = {
            "id": "tp-1",
            "type": "limit",
            "side": "sell",
            "quantity": 14,
            "limit_price": 712.8,
            "time_in_force": "gtc",
            "created_at": (NOW - timedelta(days=85)).isoformat(),
        }

        review, repairs = _reconciler().check_protective_stops(
            _broker(orders=[_stop_order(85), take_profit]), _local(), NOW
        )

        assert [r.kind for r in repairs] == ["STOP_EXPIRING"]
        assert [(d.type, d.details["order_id"]) for d in review] == [("TARGET_EXPIRING", "tp-1")]

    def test_age_uses_utc_by_default(self):
        # A stop created 85 days ago in UTC; `now` is left to the default
        order = _stop_order(0)
        order["created_at"] = (datetime.now(timezone.utc) - timedelta(days=85)).isoformat()

        _, repairs = _reconciler().check_protective_stops(_broker(orders=[order]), _local())

        assert repairs and repairs[0].kind == "STOP_EXPIRING"

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

        discrepancies = cycle.check_and_repair_stops(_broker())

        om.place_stop_order.assert_called_once_with(
            symbol="SPY", qty=14, side="sell", stop_price=627.0, time_in_force="gtc"
        )
        assert discrepancies[0].type == "MISSING_STOP"
        assert discrepancies[0].action == "AUTO_FIXED"
        assert discrepancies[0].details["order_id"] == "new-sl"
        cycle.broker_cache.invalidate.assert_called_once()

    def test_failed_placement_needs_review(self):
        om = MagicMock()
        om.place_stop_order.return_value = {"status": "error", "message": "insufficient qty"}
        cycle = _cycle(om)

        discrepancies = cycle.check_and_repair_stops(_broker())

        assert discrepancies[0].action == "NEEDS_HUMAN_REVIEW"
        assert discrepancies[0].details["error"] == "insufficient qty"
        cycle.broker_cache.invalidate.assert_not_called()

    def test_aging_stop_is_renewed_by_replacing_it(self):
        om = MagicMock()
        om.modify_order.return_value = {"status": "submitted", "order_id": "sl-2"}
        cycle = _cycle(om)

        discrepancies = cycle.check_and_repair_stops(_broker(orders=[_stop_order(85)]))

        om.modify_order.assert_called_once_with(order_id="sl-1", stop_price=627.0)
        om.place_stop_order.assert_not_called()
        assert (discrepancies[0].type, discrepancies[0].action) == ("STOP_EXPIRING", "AUTO_FIXED")

    def test_unplaceable_stop_is_reported_without_an_order(self):
        om = MagicMock()
        cycle = _cycle(om)

        discrepancies = cycle.check_and_repair_stops(_broker(price=600.0))

        om.place_stop_order.assert_not_called()
        assert discrepancies[0].action == "NEEDS_HUMAN_REVIEW"

    def test_check_errors_do_not_escape(self):
        om = MagicMock()
        cycle = _cycle(om)
        cycle.local_state_manager.state = {"positions": {}}  # forces the config lookup
        cycle.reconciler.config.get_risk_config.side_effect = KeyError("stop_loss")

        discrepancies = cycle.check_and_repair_stops(_broker())

        assert (discrepancies[0].type, discrepancies[0].action) == (
            "STOP_CHECK_FAILED",
            "NEEDS_HUMAN_REVIEW",
        )
        om.place_stop_order.assert_not_called()


def test_failed_stop_modification_is_not_counted_as_success():
    om = MagicMock()
    om.modify_order.return_value = {"status": "error", "message": "order not found"}
    cycle = _cycle(om)
    adjustment = StopAdjustment("SPY", "sl-1", 627.0, 700.0, "trail", 0.17)

    results = cycle.batch_modify_orders([adjustment])

    assert results["modifications"] == 0
    assert not results["success"]
    assert "order not found" in results["errors"][0]


def test_report_shows_stop_details():
    from src.trading.state.state_reconciler import Discrepancy
    from src.trading.utils.report_generator import ReportGenerator, RoutineType

    disc = Discrepancy(
        type="MISSING_STOP",
        symbol="SPY",
        details={"quantity": 14, "stop_price": 624.72, "reason": "no live stop order"},
        action="AUTO_FIXED",
        severity="HIGH",
    )
    broker_state = {"positions": {}, "orders": {}, "account": {}}
    report = ReportGenerator().generate_routine_report(
        RoutineType.MORNING, broker_state, {"positions": {}}, [disc], [], []
    )

    assert "MISSING_STOP: SPY" in report
    assert "stop $624.72, 14 shares, no live stop order - AUTO_FIXED" in report


def test_morning_routine_adjusts_stops_against_fresh_broker_state(monkeypatch, tmp_path):
    import src.trading.scheduling.trading_cycle as cycle_module
    from src.trading.state.state_reconciler import Discrepancy

    monkeypatch.setattr(cycle_module, "GTT_AVAILABLE", False)
    cycle = _cycle(MagicMock())
    stale, fresh = {"positions": {}, "orders": {}}, {"positions": {}, "orders": {"SPY": []}}
    placed = Discrepancy("MISSING_STOP", "SPY", {}, "AUTO_FIXED", "HIGH")
    cycle.fetch_broker_state = MagicMock(side_effect=[stale, fresh])
    cycle.reconcile_state = MagicMock(return_value=[])
    cycle.check_and_repair_stops = MagicMock(return_value=[placed])
    cycle.check_position_alerts = MagicMock(return_value=[])
    cycle.check_gtt_triggers = MagicMock(return_value=[])
    cycle.calculate_stop_adjustments = MagicMock(return_value=[])
    cycle.generate_routine_report = MagicMock(return_value="report")
    cycle._get_report_file_path = lambda routine: str(tmp_path / f"{routine}.md")

    cycle.morning_routine()

    cycle.fetch_broker_state.assert_called_with(force_refresh=True)
    cycle.calculate_stop_adjustments.assert_called_once_with(fresh)
