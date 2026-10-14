"""
/partial works against saved plans (#524, #584).

The CLI used to build PartialExitManager() without its order manager (so every
command failed), read a `positions` attribute that doesn't exist, and saw no plan
saved by another process. Plans now live in state/partial_exits.json (the test state
dir here). No orders are placed.
"""

import pytest

import src.cli.tools.partial_exit_tools as tools
from src.cli.commands.slash_commands import _partial_handle_modify
from src.trading.orders.partial_exit_manager import (
    ExitTarget,
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
    assert "Limit @ $156.00 (+4.0%)" in everything
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
        ({}, ("AAPL", 1, 0.0), "must be positive"),
        ({}, ("MSFT", 1, 160.0), "No partial exit plan found for MSFT"),
    ],
)
def test_modify_refusals(plan, args, expected):
    _save_plan(**plan)

    output = tools.modify_exit_target(*args)

    assert output.startswith("[ERROR]")
    assert expected in output
    assert load_partial_exit_manager().exit_states["AAPL"].targets[0].exit_price == 156.0
