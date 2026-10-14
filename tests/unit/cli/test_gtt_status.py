"""/gtt status <id> shows that trigger, not triggers for a symbol named <id>."""

from unittest.mock import MagicMock

import src.cli.tools.gtt_tools as gtt_tools
from src.cli.commands.slash_commands import _gtt_handle_subcommand
from src.trading.gtt.gtt_manager import GTTTrigger


def _manager_with(trigger):
    manager = MagicMock()
    manager.get_trigger.side_effect = lambda trigger_id: (
        trigger if trigger and trigger_id == trigger.id else None
    )
    return manager


def test_status_shows_the_trigger(monkeypatch):
    trigger = GTTTrigger(id=5, symbol="SPY", trigger_value=700.0, notes="breakout watch")
    monkeypatch.setattr(gtt_tools, "_get_gtt_manager", lambda: _manager_with(trigger))

    output = _gtt_handle_subcommand("status", "5")

    assert "GTT Trigger 5" in output
    assert "[5] SPY" in output
    assert "breakout watch" in output


def test_status_unknown_id(monkeypatch):
    monkeypatch.setattr(gtt_tools, "_get_gtt_manager", lambda: _manager_with(None))

    assert _gtt_handle_subcommand("status", "9") == "No GTT trigger with ID 9"


def test_status_rejects_a_non_numeric_id():
    assert _gtt_handle_subcommand("status", "SPY") == "[ERROR] Invalid trigger ID: SPY"
