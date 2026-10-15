"""Daily account records (#574 stage B): account, positions, fills and realized P&L."""

import sys
import types
from unittest.mock import Mock

import pytest

from src.trading.scheduling import trading_cycle
from src.trading.scheduling.trading_cycle import CostEfficientTradeCycle
from src.trading.state import broker_state_cache, daily_records
from src.trading.state.daily_records import DailyRecords

DAY = "2026-10-15"


@pytest.fixture
def records(monkeypatch):
    """Records in the test's state dir, with a settable clock (UTC ISO)."""
    clock = {"now": "2026-10-15T13:25:00+00:00"}  # 09:25 ET, the morning routine
    monkeypatch.setattr(daily_records, "_utc_now", lambda: clock["now"])
    store = DailyRecords()
    store.clock = clock
    return store


def _order(order_id, symbol, side, qty, price, at, order_type="market", legs=()):
    return {
        "id": order_id,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "filled_qty": qty if price else 0.0,
        "filled_avg_price": price,
        "filled_at": at if price else None,
        "order_type": order_type,
        "order_class": "bracket" if legs else "simple",
        "legs": list(legs),
    }


def _position(qty, price):
    return {"quantity": qty, "entry_price": price, "current_price": price, "unrealized_pl": 0.0}


def test_fills_include_bracket_legs_and_are_recorded_once(records):
    stop = _order("leg-1", "SPY", "sell", 14, 624.7, "2026-10-15T15:02:00Z", "stop")
    target = _order("leg-2", "SPY", "sell", 14, None, None, "limit")  # cancelled with the OCO
    parent = _order("p-1", "SPY", "buy", 14, 660.0, "2026-09-12T14:31:00Z", legs=[stop, target])

    new = records.record_fills([parent])

    assert [f["id"] for f in new] == ["p-1", "leg-1"]  # oldest first
    assert records.fills_on(DAY)[0]["parent_order_id"] == "p-1"
    assert records.record_fills([parent]) == []


def test_a_growing_partial_fill_is_recorded_again(records):
    partial = _order("o-1", "QQQ", "buy", 3, 585.0, "2026-10-15T14:00:00Z")
    partial["filled_qty"] = 1
    records.record_fills([partial])

    partial["filled_qty"] = 3
    assert [f["id"] for f in records.record_fills([partial])] == ["o-1"]
    assert records.fills_on(DAY)[0]["filled_qty"] == 3


def test_fills_belong_to_their_eastern_trading_day(records):
    late = _order("o-1", "SPY", "sell", 1, 650.0, "2026-10-16T00:30:00+00:00")  # 20:30 ET

    records.record_fills([late])

    assert [f["order_id"] for f in records.fills_on(DAY)] == ["o-1"]


def test_a_sale_is_realized_against_the_recorded_cost_basis(records):
    records.record_positions(DAY, "morning", {"SPY": _position(10, 100.0)})
    records.record_fills([_order("s-1", "SPY", "sell", 10, 110.0, "2026-10-15T15:00:00Z", "stop")])

    (sale,) = records.realized_on(DAY)

    assert (sale["cost_basis"], sale["pnl"], sale["order_type"]) == (100.0, 100.0, "stop")


def test_buys_after_the_record_average_into_the_cost(records):
    records.record_positions(DAY, "morning", {"SPY": _position(10, 100.0)})
    records.record_fills(
        [
            _order("b-1", "SPY", "buy", 10, 120.0, "2026-10-15T14:00:00Z"),
            _order("s-1", "SPY", "sell", 5, 130.0, "2026-10-15T15:00:00Z"),
        ]
    )

    (sale,) = records.realized_on(DAY)

    assert (sale["cost_basis"], sale["pnl"]) == (110.0, 100.0)


def test_a_same_day_round_trip_uses_the_buy_price(records):
    records.record_fills(
        [
            _order("b-1", "AMD", "buy", 5, 50.0, "2026-10-15T14:00:00Z"),
            _order("s-1", "AMD", "sell", 5, 45.0, "2026-10-15T15:00:00Z"),
        ]
    )

    assert records.realized_on(DAY)[0]["pnl"] == -25.0


def test_a_sale_without_a_known_cost_basis_is_flagged(records):
    records.record_fills([_order("s-1", "UPS", "sell", 3, 90.0, "2026-10-15T15:00:00Z")])

    (sale,) = records.realized_on(DAY)
    lines = records.summary_lines(DAY, [])

    assert (sale["cost_basis"], sale["pnl"]) == (None, None)
    assert "- Realized P&L today: +0.00 over 0 sale(s); 1 with unknown cost basis" in lines


def test_a_rerun_routine_replaces_its_records(records):
    records.record_account(DAY, "morning", {"equity": 100_000.0, "last_equity": 99_000.0})
    records.record_positions(
        DAY, "morning", {"SPY": _position(14, 660.0), "UPS": _position(1, 9.0)}
    )

    records.clock["now"] = "2026-10-15T13:30:00+00:00"  # the retry
    records.record_account(DAY, "morning", {"equity": 100_500.0, "last_equity": 99_000.0})
    records.record_positions(DAY, "morning", {"SPY": _position(14, 660.0)})

    assert records.equity_series() == [
        {
            "market_date": DAY,
            "routine": "morning",
            "equity": 100_500.0,
            "last_equity": 99_000.0,
            "day_pnl": 1_500.0,
        }
    ]
    with records._connect() as conn:
        symbols = [r[0] for r in conn.execute("SELECT symbol FROM position_daily")]
    assert symbols == ["SPY"]


def test_summary_reports_equity_and_new_fills(records):
    records.record_account(DAY, "evening", {"equity": 101_000.0, "last_equity": 100_000.0})
    fill = _order("s-1", "QQQ", "sell", 3, 600.0, "2026-10-15T15:00:00Z", "stop")
    new = records.record_fills([fill])

    lines = records.summary_lines(DAY, new)

    assert "- Equity $101,000.00 (day P&L +1,000.00 vs the previous close)" in lines
    assert "  - QQQ sell 3 @ $600.00 (stop, 2026-10-15)" in lines


@pytest.fixture
def on_day(monkeypatch):
    monkeypatch.setattr(trading_cycle, "market_today", lambda: DAY)


def _cycle_with_records(store):
    cycle = object.__new__(CostEfficientTradeCycle)
    cycle._daily_records = store
    cycle.account_monitor = Mock()
    return cycle


def test_routines_record_the_account_positions_and_closed_orders(records, on_day):
    cycle = _cycle_with_records(records)
    fill = _order("s-1", "SPY", "sell", 14, 624.7, "2026-10-15T15:00:00Z", "stop")
    cycle.account_monitor.get_orders.return_value = [fill]
    broker_state = {
        "account": {"equity": 100_000.0, "last_equity": 100_000.0},
        "positions": {"SPY": _position(14, 660.0)},
    }

    lines = cycle.record_daily("evening", broker_state)

    cycle.account_monitor.get_orders.assert_called_once_with(status="closed", limit=100)
    assert "- New fills since the last run: 1" in lines
    assert records.account_on(DAY)["routine"] == "evening"


def test_a_records_failure_is_reported_not_raised(records, on_day):
    cycle = _cycle_with_records(records)
    cycle.account_monitor.get_orders.side_effect = ConnectionError("broker down")

    lines = cycle.record_daily("morning", {"account": {}, "positions": {}})

    assert lines[-1] == "⚠️ Daily records not saved: broker down"


def test_broker_snapshots_load_the_cache_from_its_current_module(monkeypatch):
    sentinel = object()
    module = types.ModuleType("src.cache.unified_broker_cache")
    module.unified_broker_cache = sentinel
    monkeypatch.setitem(sys.modules, "src.cache.unified_broker_cache", module)
    monkeypatch.setattr(broker_state_cache, "_unified_cache", None)

    assert broker_state_cache._get_unified_cache() is sentinel


def test_broker_state_carries_equity_and_the_previous_close():
    monitor = Mock()
    monitor.get_positions.return_value = []
    monitor.get_orders.return_value = []
    monitor.get_account_status.return_value = {
        "buying_power": 1.0,
        "portfolio_value": 2.0,
        "cash": 3.0,
        "equity": 100_500.0,
        "last_equity": 100_000.0,
    }

    state = broker_state_cache.BrokerStateCache(monitor, use_persistent_cache=False).fetch()

    assert (state["account"]["equity"], state["account"]["last_equity"]) == (100_500.0, 100_000.0)
