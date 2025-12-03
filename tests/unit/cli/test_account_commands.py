"""
Unit tests for AccountCommands CLI (Issue #401, #408).

Tests account management CLI functionality:
- List accounts
- Switch account
- Show current account
- Refresh accounts
- Agent data retrieval
"""

import sys
from unittest.mock import MagicMock, patch

import pytest


# Mock config_defaults before any imports
@pytest.fixture(autouse=True, scope="module")
def mock_config_defaults():
    """Mock config_defaults module."""
    mock_message_loader = MagicMock()
    mock_message_loader.CLIMessages = MagicMock()
    mock_message_loader.get_alert_severity_emoji = MagicMock(return_value="!")
    mock_message_loader.get_pl_emoji = MagicMock(return_value="$")
    mock_message_loader.get_signal_emoji = MagicMock(return_value=">")
    mock_message_loader.get_status_emoji = MagicMock(return_value="*")

    sys.modules["config_defaults"] = MagicMock()
    sys.modules["config_defaults.message_loader"] = mock_message_loader
    sys.modules["config_defaults.trading_config"] = MagicMock()
    sys.modules["config_defaults.accounts_config"] = MagicMock()

    yield

    # Cleanup
    for mod in list(sys.modules.keys()):
        if mod.startswith("config_defaults"):
            del sys.modules[mod]


class TestAccountCommands:
    """Tests for AccountCommands class."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self, mock_config_defaults):
        """Reset singleton state before each test."""
        # Clear any cached imports
        for mod in list(sys.modules.keys()):
            if "account_commands" in mod:
                del sys.modules[mod]

        yield

    @pytest.fixture
    def mock_account_manager(self):
        """Create a mock AccountManager."""
        manager = MagicMock()
        manager.list_accounts.return_value = []
        manager.get_active_account_id.return_value = None
        manager.get_active_account.return_value = None
        manager.get_account.return_value = None
        manager.set_active_account.return_value = False
        manager.discover_all_accounts.return_value = {}
        return manager

    @pytest.fixture
    def mock_safe_print(self):
        """Mock safe_print utilities."""
        with patch("src.utils.safe_print.safe_print"):
            with patch("src.utils.safe_print.get_symbol", return_value="*"):
                yield

    @pytest.fixture
    def account_commands(self, mock_account_manager, mock_safe_print):
        """Create AccountCommands with mocked dependencies."""
        with patch(
            "src.cli.commands.account_commands.get_account_manager",
            return_value=mock_account_manager,
        ):
            with patch("src.cli.commands.account_commands.safe_print"):
                with patch("src.cli.commands.account_commands.get_symbol", return_value="*"):
                    # Reset singleton
                    import src.cli.commands.account_commands as acc_module
                    from src.cli.commands.account_commands import AccountCommands

                    acc_module._account_commands = None

                    return AccountCommands()


class TestListAccounts(TestAccountCommands):
    """Tests for list_accounts command."""

    def test_list_accounts_no_accounts(self, account_commands, mock_account_manager):
        """Test list_accounts with no configured accounts."""
        mock_account_manager.list_accounts.return_value = []

        result = account_commands.list_accounts()

        assert result["status"] == "no_accounts"
        assert result["accounts"] == []

    def test_list_accounts_with_accounts(self, account_commands, mock_account_manager):
        """Test list_accounts with configured accounts."""
        mock_account_manager.list_accounts.return_value = [
            {
                "id": "paper_main",
                "alias": "Paper Trading",
                "has_info": True,
                "is_active": True,
                "enabled": True,
                "account_type": "paper",
                "account_number": "PA123456",
                "status": "ACTIVE",
                "portfolio_value": 100000.0,
                "buying_power": 50000.0,
            },
            {
                "id": "paper_test",
                "alias": None,
                "has_info": True,
                "is_active": False,
                "enabled": True,
                "account_type": "paper",
                "portfolio_value": 25000.0,
                "buying_power": 25000.0,
            },
        ]
        mock_account_manager.get_active_account_id.return_value = "paper_main"

        result = account_commands.list_accounts()

        assert result["status"] == "success"
        assert len(result["accounts"]) == 2
        assert result["active"] == "paper_main"

    def test_list_accounts_disabled_account(self, account_commands, mock_account_manager):
        """Test list_accounts shows disabled accounts correctly."""
        mock_account_manager.list_accounts.return_value = [
            {
                "id": "disabled_acc",
                "has_info": False,
                "is_active": False,
                "enabled": False,
                "last_error": "API key invalid",
            }
        ]

        result = account_commands.list_accounts()

        assert result["status"] == "success"
        assert len(result["accounts"]) == 1


class TestSwitchAccount(TestAccountCommands):
    """Tests for switch_account command."""

    def test_switch_account_success(self, account_commands, mock_account_manager):
        """Test successful account switch."""
        mock_info = MagicMock()
        mock_info.account_type = MagicMock()
        mock_info.account_type.value = "paper"
        mock_info.portfolio_value = 100000.0

        mock_account = MagicMock()
        mock_account.info = mock_info

        mock_account_manager.set_active_account.return_value = True
        mock_account_manager.get_active_account.return_value = mock_account

        result = account_commands.switch_account("paper_main")

        assert result["status"] == "success"
        assert result["account_id"] == "paper_main"
        assert result["account_type"] == "paper"
        assert result["portfolio_value"] == 100000.0

    def test_switch_account_failure(self, account_commands, mock_account_manager):
        """Test failed account switch."""
        mock_account_manager.set_active_account.return_value = False

        result = account_commands.switch_account("nonexistent")

        assert result["status"] == "error"
        assert result["account_id"] == "nonexistent"

    def test_switch_account_no_info(self, account_commands, mock_account_manager):
        """Test switch to account without info."""
        mock_account = MagicMock()
        mock_account.info = None

        mock_account_manager.set_active_account.return_value = True
        mock_account_manager.get_active_account.return_value = mock_account

        result = account_commands.switch_account("uninitialized")

        assert result["status"] == "error"


class TestShowCurrentAccount(TestAccountCommands):
    """Tests for show_current_account command."""

    def test_show_current_no_active(self, account_commands, mock_account_manager):
        """Test show_current_account with no active account."""
        mock_account_manager.get_active_account_id.return_value = None

        result = account_commands.show_current_account()

        assert result["status"] == "no_active_account"

    def test_show_current_not_initialized(self, account_commands, mock_account_manager):
        """Test show_current_account with uninitialized account."""
        mock_account_manager.get_active_account_id.return_value = "paper_main"
        mock_account_manager.get_active_account.return_value = None

        result = account_commands.show_current_account()

        assert result["status"] == "not_initialized"

    def test_show_current_success(self, account_commands, mock_account_manager):
        """Test show_current_account success."""
        mock_info = MagicMock()
        mock_info.alias = "Paper Trading"
        mock_info.account_type = MagicMock()
        mock_info.account_type.value = "paper"
        mock_info.account_number = "PA123456"
        mock_info.status = "ACTIVE"
        mock_info.portfolio_value = 100000.0
        mock_info.cash = 25000.0
        mock_info.buying_power = 50000.0
        mock_info.pattern_day_trader = False
        mock_info.trading_blocked = False
        mock_info.account_blocked = False

        mock_account = MagicMock()
        mock_account.info = mock_info

        mock_account_manager.get_active_account_id.return_value = "paper_main"
        mock_account_manager.get_active_account.return_value = mock_account

        result = account_commands.show_current_account()

        assert result["status"] == "success"
        assert result["account_id"] == "paper_main"
        assert result["account_info"]["type"] == "paper"


class TestRefreshAccounts(TestAccountCommands):
    """Tests for refresh_accounts command."""

    def test_refresh_accounts_all_success(self, account_commands, mock_account_manager):
        """Test refresh_accounts with all accounts discovered."""
        mock_info = MagicMock()

        mock_account_manager.discover_all_accounts.return_value = {
            "paper_main": mock_info,
            "paper_test": mock_info,
        }

        result = account_commands.refresh_accounts()

        assert result["status"] == "success"
        assert result["discovered"] == 2
        assert result["total"] == 2

    def test_refresh_accounts_partial_failure(self, account_commands, mock_account_manager):
        """Test refresh_accounts with some failures."""
        mock_info = MagicMock()
        mock_failed_account = MagicMock()
        mock_failed_account.last_error = "API timeout"

        mock_account_manager.discover_all_accounts.return_value = {
            "paper_main": mock_info,
            "failed_acc": None,
        }
        mock_account_manager.get_account.return_value = mock_failed_account

        result = account_commands.refresh_accounts()

        assert result["status"] == "success"
        assert result["discovered"] == 1
        assert result["total"] == 2


class TestGetAccountForAgent(TestAccountCommands):
    """Tests for get_account_for_agent method."""

    def test_get_account_for_agent_active(self, account_commands, mock_account_manager):
        """Test getting active account for agent."""
        mock_info = MagicMock()
        mock_info.account_id = "paper_main"
        mock_info.account_type = MagicMock()
        mock_info.account_type.value = "paper"
        mock_info.portfolio_value = 100000.0
        mock_info.buying_power = 50000.0
        mock_info.cash = 25000.0
        mock_info.trading_blocked = False

        mock_account = MagicMock()
        mock_account.info = mock_info

        mock_account_manager.get_active_account.return_value = mock_account

        result = account_commands.get_account_for_agent()

        assert result is not None
        assert result["account_id"] == "paper_main"
        assert result["account_type"] == "paper"

    def test_get_account_for_agent_not_found(self, account_commands, mock_account_manager):
        """Test getting nonexistent account for agent."""
        mock_account_manager.get_account.return_value = None

        result = account_commands.get_account_for_agent("nonexistent")

        assert result is None

    def test_get_account_for_agent_no_info(self, account_commands, mock_account_manager):
        """Test getting account without info for agent."""
        mock_account = MagicMock()
        mock_account.info = None

        mock_account_manager.get_active_account.return_value = mock_account

        result = account_commands.get_account_for_agent()

        assert result is None
