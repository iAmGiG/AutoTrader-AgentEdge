"""GTT sell triggers never sell shares the broker's stop holds, or more than are held."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.trading.scheduling import trading_cycle
from src.trading.scheduling.trading_cycle import CostEfficientTradeCycle


def _trigger(qty=14, side="sell", action="place_order", trigger_id=2):
    config = {"order_type": "market", "side": side, "qty": qty}
    return SimpleNamespace(id=trigger_id, symbol="SPY", action_type=action, action_config=config)


def _state(quantity=14, sell_orders=()):
    return {
        "positions": {"SPY": {"quantity": quantity, "current_price": 730.0, "side": "long"}},
        "orders": {"SPY": [{"side": "sell", "quantity": q} for q in sell_orders]},
    }


@pytest.fixture
def run_gtt(monkeypatch):
    """check_gtt_triggers with the given triggers firing; returns what was executed."""

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
        return [r.trigger for r in results]

    return run


def test_a_sell_is_skipped_while_the_broker_stop_holds_the_shares(run_gtt):
    trigger = _trigger()

    executed = run_gtt([trigger], _state(sell_orders=[14]))

    assert executed == []  # stays active for a later run


def test_a_sell_is_cut_to_the_shares_held(run_gtt):
    executed = run_gtt([_trigger(qty=14)], _state(quantity=7))

    assert [t.action_config["qty"] for t in executed] == [7]


def test_only_shares_not_in_open_sell_orders_are_sold(run_gtt):
    executed = run_gtt([_trigger(qty=14)], _state(quantity=14, sell_orders=[10]))

    assert [t.action_config["qty"] for t in executed] == [4]


def test_buys_and_alerts_are_untouched(run_gtt):
    buy, alert = _trigger(side="buy", trigger_id=3), _trigger(action="alert", trigger_id=4)

    executed = run_gtt([buy, alert], _state(sell_orders=[14]))

    assert executed == [buy, alert]
