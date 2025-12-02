"""
Unit tests for TimeframeCommands CLI (Issue #365, #408).

Tests timeframe management CLI functionality:
- List timeframes
- Set timeframe
- Show current timeframe
- Timeframe recommendations
- Validate timeframe
- Agent data retrieval
"""

import sys
from unittest.mock import MagicMock, patch

import pytest


# Mock config_defaults before any imports
@pytest.fixture(autouse=True, scope="module")
def mock_config_defaults():
    """Mock config_defaults module."""
    mock_trading_config = MagicMock()

    # Mock TimeframeConfig
    mock_timeframe_config = MagicMock()
    mock_timeframe_config.default = "1d"
    mock_timeframe_config.enabled_timeframes = [
        "1m",
        "5m",
        "15m",
        "30m",
        "1h",
        "4h",
        "1d",
        "1w",
    ]
    mock_timeframe_config.is_valid.return_value = True

    mock_config = MagicMock()
    mock_config.get_timeframe_config.return_value = mock_timeframe_config

    mock_trading_config.get_config.return_value = mock_config

    sys.modules["config_defaults"] = MagicMock()
    sys.modules["config_defaults.trading_config"] = mock_trading_config
    sys.modules["config_defaults.message_loader"] = MagicMock()

    yield

    # Cleanup
    for mod in list(sys.modules.keys()):
        if mod.startswith("config_defaults"):
            del sys.modules[mod]


class TestTimeframeCommands:
    """Tests for TimeframeCommands class."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self, mock_config_defaults):
        """Reset singleton state before each test."""
        # Clear any cached imports
        for mod in list(sys.modules.keys()):
            if "timeframe_commands" in mod or "timeframe_tools" in mod:
                if mod in sys.modules:
                    del sys.modules[mod]

        yield

    @pytest.fixture
    def mock_timeframe_manager(self):
        """Create a mock TimeframeManager."""
        manager = MagicMock()
        manager.get_current_timeframe.return_value = "1d"
        manager.list_timeframes.return_value = {
            "timeframes": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
            "current": "1d",
        }
        manager.set_timeframe.return_value = {
            "success": True,
            "message": "Timeframe changed to 1 hour (1h)",
            "current_timeframe": "1h",
        }
        manager.validate_timeframe.return_value = {
            "timeframe": "1h",
            "valid": True,
            "message": "Valid timeframe",
            "available": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        }
        manager.get_timeframe_info.return_value = {
            "timeframe": "1d",
            "description": "1 day - VALIDATED DEFAULT, best Sharpe (0.856), position trading",
            "current": True,
        }
        manager.get_available_timeframes.return_value = {
            "scalping": ["1m", "2m", "3m", "5m"],
            "day_trading": ["8m", "13m", "15m", "21m", "30m"],
            "swing_trading": ["34m", "45m", "55m", "1h", "2h", "4h"],
            "position_trading": ["1d"],
            "intermediate_term": ["1w"],
            "long_term": ["1M"],
            "fibonacci": ["2m", "3m", "5m", "8m", "13m", "21m", "34m", "55m"],
            "all_enabled": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        }
        return manager

    @pytest.fixture
    def timeframe_commands(self, mock_timeframe_manager):
        """Create TimeframeCommands with mocked dependencies."""
        with patch(
            "src.cli.timeframe_commands._get_timeframe_manager",
            return_value=mock_timeframe_manager,
        ):
            from src.cli.timeframe_commands import TimeframeCommands

            # Reset singleton
            TimeframeCommands._instance = None
            TimeframeCommands._initialized = False

            cmd = TimeframeCommands()
            cmd.manager = mock_timeframe_manager
            return cmd


class TestListTimeframes(TestTimeframeCommands):
    """Tests for list_timeframes command."""

    def test_list_timeframes_basic(self, timeframe_commands, mock_timeframe_manager):
        """Test list_timeframes basic output."""
        mock_timeframe_manager.list_timeframes.return_value = {
            "timeframes": ["1m", "5m", "15m", "1h", "1d"],
            "current": "1d",
        }

        result = timeframe_commands.list_timeframes()

        assert "Available Timeframes" in result
        assert "1d" in result
        assert "Current:" in result

    def test_list_timeframes_verbose(self, timeframe_commands, mock_timeframe_manager):
        """Test list_timeframes with verbose output."""
        mock_timeframe_manager.list_timeframes.return_value = {
            "timeframes": [
                {"tf": "1d", "current": True, "info": "1 day - position trading"},
                {"tf": "1h", "current": False, "info": "1 hour - swing trading"},
            ],
            "current": "1d",
        }

        result = timeframe_commands.list_timeframes(verbose=True)

        assert "Available Timeframes" in result
        assert "1d" in result

    def test_list_timeframes_empty(self, timeframe_commands, mock_timeframe_manager):
        """Test list_timeframes with no timeframes."""
        mock_timeframe_manager.list_timeframes.return_value = {
            "timeframes": [],
            "current": None,
        }

        result = timeframe_commands.list_timeframes()

        assert "Available Timeframes" in result


class TestSetTimeframe(TestTimeframeCommands):
    """Tests for set_timeframe command."""

    def test_set_timeframe_success(self, timeframe_commands, mock_timeframe_manager):
        """Test successful timeframe change."""
        mock_timeframe_manager.set_timeframe.return_value = {
            "success": True,
            "message": "Timeframe changed to 1 hour (1h)",
            "current_timeframe": "1h",
        }

        result = timeframe_commands.set_timeframe("1h")

        assert "1h" in result or "hour" in result

    def test_set_timeframe_invalid(self, timeframe_commands, mock_timeframe_manager):
        """Test setting invalid timeframe."""
        mock_timeframe_manager.set_timeframe.return_value = {
            "success": False,
            "message": "Invalid timeframe 'invalid'. Valid options: 1m, 5m, 15m, 1h, 1d",
            "current_timeframe": "1d",
        }

        result = timeframe_commands.set_timeframe("invalid")

        assert "Invalid" in result or "invalid" in result


class TestShowCurrentTimeframe(TestTimeframeCommands):
    """Tests for show_current_timeframe command."""

    def test_show_current_timeframe(self, timeframe_commands, mock_timeframe_manager):
        """Test show_current_timeframe output."""
        mock_timeframe_manager.get_current_timeframe.return_value = "1d"
        mock_timeframe_manager.get_timeframe_info.return_value = {
            "timeframe": "1d",
            "description": "1 day - position trading",
            "current": True,
        }

        result = timeframe_commands.show_current_timeframe()

        assert "Current Timeframe" in result
        assert "1d" in result


class TestShowTimeframeRecommendations(TestTimeframeCommands):
    """Tests for show_timeframe_recommendations command."""

    def test_show_recommendations(self, timeframe_commands, mock_timeframe_manager):
        """Test show_timeframe_recommendations output."""
        result = timeframe_commands.show_timeframe_recommendations()

        assert "Recommendations" in result
        assert "Scalping" in result
        assert "Day Trading" in result


class TestValidateAndInfo(TestTimeframeCommands):
    """Tests for validate_and_info command."""

    def test_validate_valid_timeframe(self, timeframe_commands, mock_timeframe_manager):
        """Test validating a valid timeframe."""
        mock_timeframe_manager.validate_timeframe.return_value = {
            "timeframe": "1h",
            "valid": True,
            "message": "Valid timeframe",
            "available": ["1m", "5m", "15m", "1h", "1d"],
        }
        mock_timeframe_manager.get_timeframe_info.return_value = {
            "timeframe": "1h",
            "description": "1 hour - swing trading",
            "current": False,
        }

        result = timeframe_commands.validate_and_info("1h")

        assert "1h" in result

    def test_validate_invalid_timeframe(self, timeframe_commands, mock_timeframe_manager):
        """Test validating an invalid timeframe."""
        mock_timeframe_manager.validate_timeframe.return_value = {
            "timeframe": "invalid",
            "valid": False,
            "message": "Invalid timeframe",
            "available": ["1m", "5m", "15m", "1h", "1d"],
        }

        result = timeframe_commands.validate_and_info("invalid")

        assert "Invalid" in result

    def test_validate_current_timeframe(self, timeframe_commands, mock_timeframe_manager):
        """Test validating the current timeframe shows marker."""
        mock_timeframe_manager.validate_timeframe.return_value = {
            "timeframe": "1d",
            "valid": True,
            "message": "Valid timeframe",
            "available": ["1m", "5m", "15m", "1h", "1d"],
        }
        mock_timeframe_manager.get_timeframe_info.return_value = {
            "timeframe": "1d",
            "description": "1 day - position trading",
            "current": True,
        }

        result = timeframe_commands.validate_and_info("1d")

        assert "1d" in result
        assert "(current)" in result


class TestGetForAgent(TestTimeframeCommands):
    """Tests for get_for_agent method."""

    def test_get_for_agent_current(self, timeframe_commands, mock_timeframe_manager):
        """Test get_for_agent with 'current' command."""
        mock_timeframe_manager.get_current_timeframe.return_value = "1d"

        result = timeframe_commands.get_for_agent("current")

        assert result["type"] == "current_timeframe"
        assert result["timeframe"] == "1d"

    def test_get_for_agent_set(self, timeframe_commands, mock_timeframe_manager):
        """Test get_for_agent with 'set' command."""
        mock_timeframe_manager.set_timeframe.return_value = {
            "success": True,
            "message": "Changed to 4h",
            "current_timeframe": "4h",
        }

        result = timeframe_commands.get_for_agent("set", "4h")

        assert result["success"] is True

    def test_get_for_agent_list(self, timeframe_commands, mock_timeframe_manager):
        """Test get_for_agent with 'list' command."""
        mock_timeframe_manager.list_timeframes.return_value = {
            "timeframes": ["1m", "5m", "1d"],
            "current": "1d",
        }

        result = timeframe_commands.get_for_agent("list")

        assert "timeframes" in result

    def test_get_for_agent_validate(self, timeframe_commands, mock_timeframe_manager):
        """Test get_for_agent with 'validate' command."""
        mock_timeframe_manager.validate_timeframe.return_value = {
            "timeframe": "1h",
            "valid": True,
        }

        result = timeframe_commands.get_for_agent("validate", "1h")

        assert result["valid"] is True

    def test_get_for_agent_info(self, timeframe_commands, mock_timeframe_manager):
        """Test get_for_agent with 'info' command."""
        mock_timeframe_manager.get_timeframe_info.return_value = {
            "timeframe": "1d",
            "description": "1 day",
            "current": True,
        }

        result = timeframe_commands.get_for_agent("info", "1d")

        assert result["timeframe"] == "1d"

    def test_get_for_agent_recommendations(self, timeframe_commands, mock_timeframe_manager):
        """Test get_for_agent with 'recommendations' command."""
        result = timeframe_commands.get_for_agent("recommendations")

        assert "scalping" in result
        assert "day_trading" in result

    def test_get_for_agent_unknown_command(self, timeframe_commands, mock_timeframe_manager):
        """Test get_for_agent with unknown command."""
        result = timeframe_commands.get_for_agent("unknown_command")

        assert "error" in result

    def test_get_for_agent_set_default(self, timeframe_commands, mock_timeframe_manager):
        """Test get_for_agent set without arg defaults to 1d."""
        timeframe_commands.get_for_agent("set")

        mock_timeframe_manager.set_timeframe.assert_called_with("1d")


class TestSingletonPattern(TestTimeframeCommands):
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self, mock_timeframe_manager):
        """Test TimeframeCommands returns singleton."""
        with patch(
            "src.cli.timeframe_commands._get_timeframe_manager",
            return_value=mock_timeframe_manager,
        ):
            from src.cli.timeframe_commands import TimeframeCommands

            # Reset singleton
            TimeframeCommands._instance = None

            cmd1 = TimeframeCommands()
            cmd2 = TimeframeCommands()

            assert cmd1 is cmd2

    def test_get_timeframe_commands_singleton(self, mock_timeframe_manager):
        """Test get_timeframe_commands returns singleton."""
        with patch(
            "src.cli.timeframe_commands._get_timeframe_manager",
            return_value=mock_timeframe_manager,
        ):
            from src.cli.timeframe_commands import (TimeframeCommands,
                                                    get_timeframe_commands)

            # Reset singleton
            TimeframeCommands._instance = None

            cmd1 = get_timeframe_commands()
            cmd2 = get_timeframe_commands()

            assert cmd1 is cmd2


class TestEdgeCases(TestTimeframeCommands):
    """Tests for edge cases."""

    def test_set_timeframe_empty_string(self, timeframe_commands, mock_timeframe_manager):
        """Test set_timeframe with empty string."""
        mock_timeframe_manager.set_timeframe.return_value = {
            "success": False,
            "message": "Invalid timeframe ''",
            "current_timeframe": "1d",
        }

        result = timeframe_commands.set_timeframe("")

        assert "Invalid" in result or "success" in str(result).lower()

    def test_validate_empty_timeframe(self, timeframe_commands, mock_timeframe_manager):
        """Test validate_and_info with empty string."""
        mock_timeframe_manager.validate_timeframe.return_value = {
            "timeframe": "",
            "valid": False,
            "message": "Invalid timeframe",
            "available": ["1m", "5m", "1d"],
        }

        result = timeframe_commands.validate_and_info("")

        assert "Invalid" in result
