"""Daily account records (#574 stage B): account, positions, fills and realized P&L."""

import sqlite3
import sys
import types
from unittest.mock import Mock, call

import pytest

from src.cache.unified_broker_cache import UnifiedBrokerCache
from src.trading.scheduling import trading_cycle
from src.trading.scheduling.trading_cycle import CostEfficientTradeCycle
from src.trading.state import broker_state_cache
from src.trading.state.daily_records import DailyRecords

DAY = "2026-10-15"
MORNING = "2026-10-15T13:25:00+00:00"  # 09:25 ET
EVENING = "2026-10-15T19:50:00+00:00"  # 15:50 ET


@pytest.fixture
def records():
    """Records in the test's state dir (tests/unit/conftest.py isolates it)."""
    return DailyRecords()


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


def _run(records, routine, at, positions=None, equity=100_000.0, last_equity=100_000.0):
    """A routine run: the account and positions as fetched at ``at``."""
    account = {"equity": equity, "last_equity": last_equity}
    records.record_account(DAY, routine, account, at)
    records.record_positions(DAY, routine, positions or {}, at)


def test_fills_include_bracket_legs_and_are_recorded_once(records):
    stop = _order("leg-1", "SPY", "sell", 14, 624.7, "2026-10-15T15:02:00Z", "stop")
    target = _order("leg-2", "SPY", "sell", 14, None, None, "limit")  # cancelled with the OCO
    parent = _order("p-1", "SPY", "buy", 14, 660.0, "2026-09-12T14:31:00Z", legs=[stop, target])

    new = records.record_fills([parent])

    assert [f["id"] for f in new] == ["p-1", "leg-1"]  # oldest first
    assert records.fills_on(DAY)[0]["parent_order_id"] == "p-1"
    assert records.record_fills([parent]) == []


def test_a_leg_listed_at_top_level_too_keeps_its_parent(records):
    stop = _order("leg-1", "SPY", "sell", 14, 624.7, "2026-10-15T15:02:00Z", "stop")
    parent = _order("p-1", "SPY", "buy", 14, 660.0, "2026-09-12T14:31:00Z", legs=[stop])

    records.record_fills([stop, parent])  # get_orders() can return an ID-only leg both ways

    assert records.fills_on(DAY)[0]["parent_order_id"] == "p-1"


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
    _run(records, "morning", MORNING, {"SPY": _position(10, 100.0)})
    records.record_fills([_order("s-1", "SPY", "sell", 10, 110.0, "2026-10-15T15:00:00Z", "stop")])

    (sale,) = records.realized_on(DAY)

    assert (sale["cost_basis"], sale["pnl"], sale["order_type"]) == (100.0, 100.0, "stop")


def test_buys_after_the_run_average_into_the_cost(records):
    _run(records, "morning", MORNING, {"SPY": _position(10, 100.0)})
    records.record_fills(
        [
            _order("b-1", "SPY", "buy", 10, 120.0, "2026-10-15T14:00:00Z"),
            _order("s-1", "SPY", "sell", 5, 130.0, "2026-10-15T15:00:00Z"),
        ]
    )

    (sale,) = records.realized_on(DAY)

    assert (sale["cost_basis"], sale["pnl"]) == (110.0, 100.0)


def test_a_round_trip_after_a_run_without_the_symbol_uses_the_buy_price(records):
    _run(records, "morning", MORNING, {"SPY": _position(10, 100.0)})  # AMD not held
    records.record_fills(
        [
            _order("b-1", "AMD", "buy", 5, 50.0, "2026-10-15T14:00:00Z"),
            _order("s-1", "AMD", "sell", 5, 45.0, "2026-10-15T15:00:00Z"),
        ]
    )

    assert records.realized_on(DAY)[0]["pnl"] == -25.0


def test_a_sale_before_any_run_has_an_unknown_basis(records):
    records.record_fills(
        [
            _order("b-1", "SOXL", "buy", 20, 125.0, "2026-10-14T14:00:00Z"),
            _order("s-1", "SOXL", "sell", 20, 120.0, "2026-10-15T13:33:00Z"),
        ]
    )
    _run(records, "morning", "2026-10-15T14:00:00+00:00")  # records begin after the sale

    (sale,) = records.realized_on(DAY)
    lines = records.summary_lines(DAY, "morning")

    assert (sale["cost_basis"], sale["pnl"]) == (None, None)
    assert "- Realized P&L today: +0.00 over 0 sale(s); 1 with unknown cost basis" in lines


def test_fills_that_dont_add_up_give_an_unknown_basis_not_an_error(records):
    _run(records, "morning", MORNING)  # UPS not held
    records.record_fills(
        [
            _order("s-1", "UPS", "sell", 5, 90.0, "2026-10-15T14:00:00Z"),  # its buy is missing
            _order("b-1", "UPS", "buy", 5, 88.0, "2026-10-15T14:30:00Z"),
            _order("s-2", "UPS", "sell", 5, 91.0, "2026-10-15T15:00:00Z"),
        ]
    )

    assert [s["cost_basis"] for s in records.realized_on(DAY)] == [None, None]


def test_a_rerun_routine_replaces_its_records(records):
    _run(records, "morning", MORNING, {"SPY": _position(14, 660.0), "UPS": _position(1, 9.0)})
    retry = "2026-10-15T13:30:00+00:00"
    _run(
        records,
        "morning",
        retry,
        {"SPY": _position(14, 660.0)},
        equity=100_500.0,
        last_equity=99_000.0,
    )

    assert records.equity_series() == [
        {
            "market_date": DAY,
            "routine": "morning",
            "equity": 100_500.0,
            "last_equity": 99_000.0,
            "day_pnl": 1_500.0,
        }
    ]
    assert records.last_symbols() == ["SPY"]


def test_a_retry_still_reports_the_fills_since_the_previous_run(records):
    _run(records, "morning", MORNING)
    stop = _order("s-1", "QQQ", "sell", 3, 600.0, "2026-10-15T15:00:00Z", "stop")
    _run(records, "evening", EVENING, equity=101_000.0)
    records.record_fills([stop])

    _run(records, "evening", "2026-10-15T19:55:00+00:00", equity=101_000.0)  # the retry
    records.record_fills([stop])  # nothing new to the store
    lines = records.summary_lines(DAY, "evening")

    assert "- Fills since the previous run: 1" in lines
    assert "  - QQQ sell 3 @ $600.00 (stop, 2026-10-15)" in lines


def test_summary_reports_equity_and_day_pnl(records):
    _run(records, "evening", EVENING, equity=101_000.0, last_equity=100_000.0)

    lines = records.summary_lines(DAY, "evening")

    assert "- Equity $101,000.00 (day P&L +1,000.00 vs the previous close)" in lines
    assert "- No fills since the previous run" in lines


@pytest.fixture
def on_day(monkeypatch):
    monkeypatch.setattr(trading_cycle, "market_today", lambda: DAY)


def _cycle_with_records(store):
    cycle = object.__new__(CostEfficientTradeCycle)
    cycle._daily_records = store
    cycle.account_monitor = Mock()
    return cycle


def test_routines_also_fetch_closed_orders_of_held_symbols(records, on_day):
    _run(records, "morning", MORNING, {"QQQ": _position(3, 585.0)})
    cycle = _cycle_with_records(records)
    old_bracket_leg = _order("leg-1", "QQQ", "sell", 3, 580.0, "2026-10-15T18:00:00Z", "stop")
    cycle.account_monitor.get_orders.side_effect = [[], [old_bracket_leg]]
    broker_state = {
        "account": {"equity": 100_000.0, "last_equity": 100_000.0},
        "positions": {"SPY": _position(14, 660.0)},
        "fetched_at": EVENING,
    }

    lines = cycle.record_daily("evening", broker_state)

    assert cycle.account_monitor.get_orders.call_args_list == [
        call(status="closed", limit=100),
        call(status="closed", limit=500, symbols=["QQQ", "SPY"]),  # held then, held now
    ]
    assert "  - QQQ sell 3 @ $580.00 (stop, 2026-10-15)" in lines
    assert records.realized_on(DAY)[0]["pnl"] == -15.0
    assert records.account_on(DAY)["recorded_at"] == EVENING  # the fetch time


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


def test_broker_state_carries_equity_the_previous_close_and_fetch_time():
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
    assert state["fetched_at"].endswith("+00:00")


def test_snapshots_store_the_order_type_and_a_price(tmp_path):
    cache = UnifiedBrokerCache(db_path=str(tmp_path / "trading_data.db"))
    position = {"symbol": "SPY", "qty": 14.0, "avg_entry_price": 660.0, "market_value": 9100.0}
    order = {"id": "o-1", "symbol": "SPY", "side": "sell", "order_type": "stop", "qty": 14.0}

    cache.store_position_snapshot("paper", [position])
    cache.store_order_snapshot("paper", [order])

    with sqlite3.connect(cache.db_path) as conn:
        price = conn.execute("SELECT current_price FROM position_snapshots").fetchone()[0]
        order_type = conn.execute("SELECT order_type FROM order_snapshots").fetchone()[0]
    assert (price, order_type) == (650.0, "stop")


def test_old_snapshots_are_cleaned_up_once_a_day(monkeypatch):
    unified = Mock()
    monkeypatch.setattr(broker_state_cache, "_unified_cache", unified)
    monkeypatch.setattr(broker_state_cache, "_last_snapshot_cleanup", None)
    cache = broker_state_cache.BrokerStateCache(Mock(), use_persistent_cache=True)

    cache._store_to_persistent_cache({}, [{"symbol": "SPY"}], [])
    cache._store_to_persistent_cache({}, [{"symbol": "SPY"}], [])

    unified.cleanup_old_snapshots.assert_called_once_with(days_to_keep=90)
