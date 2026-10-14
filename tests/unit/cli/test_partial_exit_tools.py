"""
/partial works against saved plans (#524, #584).

The CLI used to build PartialExitManager() without its order manager (so every
command failed), read a `positions` attribute that doesn't exist, and saw no plan
saved by another process. Plans now live in state/partial_exits.json (the test state
dir here). No orders are placed.
"""

import json
from unittest.mock import MagicMock

import pytest

import src.cli.tools.partial_exit_tools as tools
from src.cli.commands.slash_commands import _partial_handle_modify
from src.trading.orders.partial_exit_manager import (
    ExitTarget,
    PartialExitManager,
    PartialExitState,
    default_state_file,
    load_partial_exit_manager,
)


def _save_plan(order_id=None, filled=False):
    manager = load_partial_exit_manager()
    manager.exit_states["AAPL"] = PartialExitState(
        symbol="AAPL",
        entry_price=150.0,
        total_quantity=10,
        stop_price=142.5,
        targets=[
            ExitTarget(1, 5, 0.5, "limit", exit_price=156.0, order_id=order_id, filled=filled),
            ExitTarget(2, 5, 0.5, "trailing"),
        ],
    )
    manager.save()


def test_plans_round_trip_through_the_state_dir(isolated_state_dir):
    _save_plan(order_id="tp-1")

    assert default_state_file().parent == isolated_state_dir
    reloaded = load_partial_exit_manager().exit_states["AAPL"]
    assert reloaded.targets[0].order_id == "tp-1"
    assert reloaded.get_remaining_quantity() == 10


def test_no_plans_is_not_an_error():
    assert tools.show_all_partial_exits() == tools.NO_PLANS
    assert tools.get_exit_summary() == "[INFO] No partial exit positions registered."


def test_views_show_a_saved_plan():
    _save_plan()

    everything = tools.show_all_partial_exits()
    assert "[AAPL] 10 shares @ $150.00" in everything
    assert "Limit @ $156.00 (+4.0% gain)" in everything
    assert "Trailing Stop" in everything

    plan = tools.show_partial_exit_plan("aapl")
    assert "Partial Exit Plan: AAPL" in plan
    assert "Stop Price: $142.50" in plan
    assert "[ACTIVE] Target 1: 5 shares" in plan

    assert "Target 2: 5 shares" in tools.show_exit_targets("AAPL")
    assert "[AAPL] 2 target(s), 10 shares remaining" in tools.list_active_exits()
    assert "Active Targets: 2" in tools.get_exit_summary()


def test_modify_saves_the_new_price():
    _save_plan()

    output = _partial_handle_modify("AAPL 1 160")

    assert output.startswith("[OK] Modified AAPL target 1")
    assert load_partial_exit_manager().exit_states["AAPL"].targets[0].exit_price == 160.0


@pytest.mark.parametrize(
    "plan, args, expected",
    [
        ({"order_id": "tp-1"}, ("AAPL", 1, 160.0), "has a live order"),
        ({"filled": True}, ("AAPL", 1, 160.0), "already been filled"),
        ({}, ("AAPL", 2, 160.0), "trailing target, not a limit"),
        ({}, ("AAPL", 1, 0.0), "must be a positive number"),
        ({}, ("AAPL", 1, float("nan")), "must be a positive number"),
        ({}, ("MSFT", 1, 160.0), "No partial exit plan found for MSFT"),
    ],
)
def test_modify_refusals(plan, args, expected):
    _save_plan(**plan)

    output = tools.modify_exit_target(*args)

    assert output.startswith("[ERROR]")
    assert expected in output
    assert load_partial_exit_manager().exit_states["AAPL"].targets[0].exit_price == 156.0


def test_unreadable_plans_file_is_moved_aside_not_overwritten():
    default_state_file().parent.mkdir(parents=True, exist_ok=True)
    default_state_file().write_text("{not json")

    manager = load_partial_exit_manager()
    assert manager.exit_states == {}

    aside = list(default_state_file().parent.glob("partial_exits.json.unreadable-*"))
    assert len(aside) == 1 and aside[0].read_text() == "{not json"


def test_saving_one_plan_keeps_plans_saved_by_another_process():
    trading = load_partial_exit_manager()  # loaded before the CLI saves AAPL
    _save_plan()
    trading.exit_states["MSFT"] = PartialExitState(
        symbol="MSFT", entry_price=400.0, total_quantity=4, stop_price=380.0, targets=[]
    )

    trading.save("MSFT")

    saved = json.loads(default_state_file().read_text())["positions"]
    assert set(saved) == {"AAPL", "MSFT"}


def test_fill_update_does_not_undo_a_cli_edit():
    manager = load_partial_exit_manager()
    manager.exit_states["AAPL"] = PartialExitState(
        symbol="AAPL",
        entry_price=150.0,
        total_quantity=10,
        stop_price=142.5,
        targets=[
            ExitTarget(1, 5, 0.5, "limit", exit_price=156.0),
            ExitTarget(2, 5, 0.5, "limit", exit_price=165.0, order_id="tp-2"),
        ],
    )
    manager.save()
    trading = PartialExitManager(order_manager=MagicMock(), state_file=default_state_file())
    trading.order_manager.position_manager.get_order.return_value = {"status": "filled"}

    tools.modify_exit_target("AAPL", 1, 160.0)  # the CLI, in another process
    trading.update_position_fills("AAPL")  # its in-memory copy still says 156

    saved = load_partial_exit_manager().exit_states["AAPL"]
    assert saved.targets[0].exit_price == 160.0
    assert saved.targets[1].filled


def test_factory_saves_plans_where_the_cli_reads_them():
    mode_manager = MagicMock()
    manager = PartialExitManager.from_mode_manager(MagicMock(), None, mode_manager)

    assert manager.state_file == default_state_file()


def test_short_target_shows_a_gain_and_unpriced_limit_is_not_trailing():
    manager = load_partial_exit_manager()
    manager.exit_states["TSLA"] = PartialExitState(
        symbol="TSLA",
        entry_price=150.0,
        total_quantity=4,
        stop_price=157.5,
        side="short",
        targets=[
            ExitTarget(1, 2, 0.5, "limit", exit_price=144.0),
            ExitTarget(2, 2, 0.5, "limit", exit_price=None),
        ],
    )
    manager.save()

    targets = tools.show_exit_targets("TSLA")

    assert "Limit @ $144.00 (+4.0% gain)" in targets
    assert "Limit (no price set)" in targets
    assert "Trailing Stop" not in targets


def test_malformed_plan_gives_an_error_reply_not_an_exception():
    plan = {
        "symbol": "AAPL",
        "entry_price": 150.0,
        "total_quantity": 10,
        "stop_price": None,  # can't be formatted as a price
        "targets": [],
    }
    default_state_file().parent.mkdir(parents=True, exist_ok=True)
    default_state_file().write_text(json.dumps({"positions": {"AAPL": plan}}))

    assert tools.show_all_partial_exits().startswith("[ERROR] Failed to retrieve partial exits")
    assert tools.show_partial_exit_plan("AAPL").startswith("[ERROR]")
