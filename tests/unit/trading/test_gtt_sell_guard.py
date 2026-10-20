"""GTT sell triggers never sell shares the broker's orders hold, or more than are held."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.trading.scheduling import trading_cycle
from src.trading.scheduling.trading_cycle import CostEfficientTradeCycle
from src.trading.state.state_reconciler import Discrepancy


def _trigger(qty=14, side="sell", action="place_order", trigger_id=2, symbol="SPY"):
    config = {"order_type": "market", "side": side, "qty": qty}
    return SimpleNamespace(id=trigger_id, symbol=symbol, action_type=action, action_config=config)


def _state(quantity=14, sell_orders=(), qty_available=None):
    return {
        "positions": {
            "SPY": {
                "quantity": quantity,
                "current_price": 730.0,
                "side": "long",
                "qty_available": qty_available,
            }
        },
        "orders": {"SPY": [{"side": "sell", "quantity": q} for q in sell_orders]},
    }


@pytest.fixture
def run_gtt(monkeypatch):
    """check_gtt_triggers with the given triggers firing: (executed triggers, skip results)."""

    def run(triggers, broker_state):
        evaluator = MagicMock()
        evaluator.evaluate_triggers_batch.return_value = triggers
        executor = MagicMock()
        executor.execute_triggers_batch.side_effect = lambda fired, prices: [
            SimpleNamespace(success=True, trigger=t) for t in fired
        ]
        monkeypatch.setattr(trading_cycle, "GTT_AVAILABLE", True)
        monkeypatch.setattr(
            trading_cycle, "get_trigger_evaluator", lambda: evaluator, raising=False
        )
        monkeypatch.setattr(trading_cycle, "get_action_executor", lambda: executor, raising=False)
        cycle = object.__new__(CostEfficientTradeCycle)
        results = cycle.check_gtt_triggers(broker_state)
        executed = [r.trigger for r in results if hasattr(r, "trigger")]
        skipped = [r for r in results if not hasattr(r, "trigger")]
        return executed, skipped

    return run


def test_a_sell_is_skipped_while_the_broker_stop_holds_the_shares(run_gtt):
    executed, skipped = run_gtt([_trigger()], _state(sell_orders=[14], qty_available=0))

    assert executed == []  # the trigger stays active for a later run
    assert [(r.trigger_id, r.success, r.details["skipped"]) for r in skipped] == [(2, False, True)]
    assert "no free shares" in skipped[0].message  # shown in the routine report


def test_a_sell_is_cut_to_the_shares_held(run_gtt):
    executed, _ = run_gtt([_trigger(qty=14)], _state(quantity=7, qty_available=7))

    assert [t.action_config["qty"] for t in executed] == [7]


def test_bracket_legs_on_the_same_shares_are_counted_once(run_gtt):
    # 20 held, a bracket's take-profit and stop-loss legs both cover the same 10
    state = _state(quantity=20, sell_orders=[10, 10], qty_available=10)

    executed, _ = run_gtt([_trigger(qty=10)], state)

    assert [t.action_config["qty"] for t in executed] == [10]


def test_triggers_on_one_symbol_share_the_free_shares(run_gtt):
    first, second = _trigger(qty=14, trigger_id=2), _trigger(qty=10, trigger_id=3)

    executed, skipped = run_gtt([first, second], _state(qty_available=14))

    assert executed == [first]
    assert [r.trigger_id for r in skipped] == [3]


def test_without_qty_available_open_sell_orders_are_subtracted(run_gtt):
    executed, _ = run_gtt([_trigger(qty=14)], _state(quantity=14, sell_orders=[10]))

    assert [t.action_config["qty"] for t in executed] == [4]


def test_an_unusable_quantity_skips_only_that_trigger(run_gtt):
    bad, good = _trigger(qty=None, trigger_id=5), _trigger(qty=4, trigger_id=6)

    executed, skipped = run_gtt([bad, good], _state(qty_available=14))

    assert executed == [good]
    assert [r.trigger_id for r in skipped] == [5]


def test_buys_and_alerts_are_untouched(run_gtt):
    buy, alert = _trigger(side="buy", trigger_id=3), _trigger(action="alert", trigger_id=4)

    executed, _ = run_gtt([buy, alert], _state(sell_orders=[14], qty_available=0))

    assert executed == [buy, alert]


def test_the_evening_gtt_check_sees_stops_placed_in_the_same_run(monkeypatch, tmp_path):
    """After a repair the broker state is fetched again, as the morning routine does."""
    import src.trading.scheduling.trading_cycle as cycle_module

    monkeypatch.setattr(cycle_module, "is_market_hours", lambda: True)
    before, after = {"positions": {}, "orders": {}}, {"positions": {}, "orders": {"SPY": []}}
    cycle = object.__new__(CostEfficientTradeCycle)
    cycle.fetch_broker_state = MagicMock(side_effect=[before, after])
    cycle.record_daily = MagicMock(return_value=[])
    cycle.reconcile_state = MagicMock(return_value=[])
    placed = Discrepancy(type="MISSING_STOP", symbol="SPY", details={}, action="AUTO_FIXED")
    cycle.check_and_repair_stops = MagicMock(return_value=[placed])
    cycle.check_position_alerts = MagicMock(return_value=[])
    cycle.check_gtt_triggers = MagicMock(return_value=[])
    cycle.raise_stops = MagicMock(return_value=([], None))
    cycle.trailing_stop_manager = MagicMock()
    cycle.local_state_manager = MagicMock(state={})
    cycle.generate_routine_report = MagicMock(return_value="report")
    cycle._get_report_file_path = MagicMock(return_value=str(tmp_path / "report.md"))
    cycle.last_report_path = None

    cycle.evening_routine()

    cycle.fetch_broker_state.assert_called_with(force_refresh=True)
    cycle.check_gtt_triggers.assert_called_once_with(after)


def test_broker_state_carries_alpacas_free_share_count():
    from src.trading.state.broker_state_cache import BrokerStateCache

    monitor = MagicMock()
    position = {"symbol": "SPY", "qty": 20.0, "avg_entry_price": 657.6, "market_value": 15000.0}
    monitor.get_positions.return_value = [
        {**position, "unrealized_pl": 0.0, "side": "long", "qty_available": 10.0}
    ]
    monitor.get_orders.return_value = []
    monitor.get_account_status.return_value = {}

    state = BrokerStateCache(monitor, use_persistent_cache=False).fetch()

    assert state["positions"]["SPY"]["qty_available"] == 10
