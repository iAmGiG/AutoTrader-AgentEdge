"""
Agents can't activate a live account: only a confirmed paper account can be switched
or rotated to without the user's typed confirmation in the CLI.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import src.trading.accounts.account_tools as account_tools
from src.trading.accounts.account_manager import (AccountManager, AccountType,
                                                  needs_live_confirmation)


def _managed(account_type=None, enabled=True):
    info = None if account_type is None else SimpleNamespace(account_type=account_type)
    return SimpleNamespace(enabled=enabled, info=info, is_active=False)


def _manager_with(account):
    manager = MagicMock()
    manager.get_account.return_value = account
    manager.discover_account.return_value = None  # discovery fails, info stays None
    return manager


class TestNeedsLiveConfirmation:
    def test_paper_account_needs_none(self):
        assert not needs_live_confirmation(_manager_with(_managed(AccountType.PAPER)), "p")

    def test_live_account_needs_it(self):
        assert needs_live_confirmation(_manager_with(_managed(AccountType.LIVE)), "l")

    def test_undiscoverable_account_counts_as_live(self):
        manager = _manager_with(_managed(None))

        assert needs_live_confirmation(manager, "x")
        manager.discover_account.assert_called_once_with("x")

    def test_unknown_id_is_left_to_set_active_account(self):
        assert not needs_live_confirmation(_manager_with(None), "missing")


def test_rotation_never_activates_a_live_account():
    manager = AccountManager(config_loader=MagicMock())
    manager._accounts = {
        "paper_main": _managed(AccountType.PAPER),
        "live_main": _managed(AccountType.LIVE),
    }
    manager._accounts["paper_main"].is_active = True
    manager._active_account_id = "paper_main"

    assert manager.rotate_active_account() == "paper_main"
    assert manager.get_active_account_id() == "paper_main"
    assert not manager._accounts["live_main"].is_active


def test_switch_tool_refuses_a_live_account(monkeypatch):
    manager = _manager_with(_managed(AccountType.LIVE))
    monkeypatch.setattr(account_tools, "get_account_manager", lambda: manager)

    result = account_tools.switch_active_account("live_main")

    assert not result["success"]
    manager.set_active_account.assert_not_called()


def test_placeholder_account_is_discovered_before_deciding():
    # Accounts configured with an alias start with an UNKNOWN-type placeholder
    account = _managed(AccountType.UNKNOWN)
    manager = _manager_with(account)

    def discover(account_id):
        account.info = SimpleNamespace(account_type=AccountType.PAPER)
        return account.info

    manager.discover_account.side_effect = discover

    assert not needs_live_confirmation(manager, "paper_alias")
    manager.discover_account.assert_called_once_with("paper_alias")


def test_set_active_account_needs_allow_live_for_a_live_account():
    manager = AccountManager(config_loader=MagicMock())
    manager._accounts = {"live_main": _managed(AccountType.LIVE)}

    assert not manager.set_active_account("live_main")
    assert manager.get_active_account_id() is None

    assert manager.set_active_account("live_main", allow_live=True)
    assert manager.get_active_account_id() == "live_main"


def test_set_active_account_discovers_a_placeholder_first():
    manager = AccountManager(config_loader=MagicMock())
    manager._accounts = {"paper_alias": _managed(AccountType.UNKNOWN)}

    def discover(account_id):
        manager._accounts[account_id].info = SimpleNamespace(account_type=AccountType.PAPER)
        return manager._accounts[account_id].info

    manager.discover_account = discover

    assert manager.set_active_account("paper_alias")
    assert manager.get_active_account().info.account_type == AccountType.PAPER
