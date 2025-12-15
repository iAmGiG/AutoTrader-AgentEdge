"""
Tests for New CLI Tools (Issues #488, #489, #490)

Tests the new CLI FunctionTool implementations:
- #488: Voter tools (VoterAgent configuration)
- #489: Enhanced timeframe tools (multi-timeframe presets)
- #490: Backup tools (database backup/restore)

Run with: conda run -n AutoTrader python -m pytest tests/test_cli_tools_new.py -v

NOTE: Uses direct module imports to avoid config loading issues.
"""

# ruff: noqa: N806

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add project root to path BEFORE any imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def import_module_directly(module_path: str, module_name: str):
    """Import a module directly from file path, bypassing package __init__."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def voter_tools_module():
    """Load voter_tools module directly."""

    # First mock the TradingConfig dependency
    class MockMACD:
        fast = 13
        slow = 34
        signal = 8

    class MockRSI:
        period = 14
        oversold = 30
        overbought = 70

    class MockTradingConfig:
        def get_macd_config(self):
            return MockMACD()

        def get_rsi_config(self):
            return MockRSI()

    # Mock the config_defaults module
    class MockConfigModule:
        TradingConfig = MockTradingConfig

    sys.modules["config_defaults.trading_config"] = MockConfigModule()

    # Mock autogen_core.tools
    class MockFunctionTool:
        def __init__(self, func, description="", name=None):
            self.func = func
            self.description = description
            self.name = name or func.__name__

    class MockAutoGenTools:
        FunctionTool = MockFunctionTool

    sys.modules["autogen_core.tools"] = MockAutoGenTools()

    module_path = project_root / "src" / "cli" / "tools" / "voter_tools.py"
    return import_module_directly(str(module_path), "voter_tools_test")


@pytest.fixture
def backup_tools_module():
    """Load backup_tools module directly."""

    # Mock autogen_core.tools
    class MockFunctionTool:
        def __init__(self, func, description="", name=None):
            self.func = func
            self.description = description
            self.name = name or func.__name__

    class MockAutoGenTools:
        FunctionTool = MockFunctionTool

    sys.modules["autogen_core.tools"] = MockAutoGenTools()

    module_path = project_root / "src" / "cli" / "tools" / "backup_tools.py"
    return import_module_directly(str(module_path), "backup_tools_test")


@pytest.fixture
def temp_backup_dir():
    """Create temporary backup directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# =============================================================================
# Tests: Issue #488 - Voter Tools
# =============================================================================


class TestVoterTools:
    """Test voter CLI tools (Issue #488)."""

    def test_show_voter_config_returns_string(self, voter_tools_module):
        """Test show_voter_config returns formatted string."""
        result = voter_tools_module.show_voter_config()

        assert isinstance(result, str)
        assert "VoterAgent Configuration" in result
        assert "MACD Parameters" in result
        assert "RSI Parameters" in result

    def test_explain_voting_logic_returns_string(self, voter_tools_module):
        """Test explain_voting_logic returns formatted explanation."""
        result = voter_tools_module.explain_voting_logic()

        assert isinstance(result, str)
        assert "Voting Logic" in result
        assert "STRONG" in result
        assert "WEAK" in result
        assert "CONFLICT" in result

    def test_explain_macd_params_returns_string(self, voter_tools_module):
        """Test explain_macd_params returns formatted explanation."""
        result = voter_tools_module.explain_macd_params()

        assert isinstance(result, str)
        assert "MACD Parameters" in result
        assert "Fibonacci" in result
        assert "13/34/8" in result

    def test_explain_rsi_params_returns_string(self, voter_tools_module):
        """Test explain_rsi_params returns formatted explanation."""
        result = voter_tools_module.explain_rsi_params()

        assert isinstance(result, str)
        assert "RSI Parameters" in result
        assert "Oversold" in result
        assert "Overbought" in result

    def test_get_voter_parameters_returns_dict(self, voter_tools_module):
        """Test get_voter_parameters returns structured data."""
        result = voter_tools_module.get_voter_parameters()

        assert isinstance(result, dict)
        assert "macd" in result
        assert "rsi" in result
        assert "thresholds" in result
        assert "performance" in result

        # Check MACD values
        assert result["macd"]["fast"] == 13
        assert result["macd"]["slow"] == 34
        assert result["macd"]["signal"] == 8

    def test_compare_with_traditional_returns_string(self, voter_tools_module):
        """Test compare_with_traditional returns comparison table."""
        result = voter_tools_module.compare_with_traditional()

        assert isinstance(result, str)
        assert "Comparison" in result
        assert "Fibonacci" in result
        assert "Traditional" in result

    def test_show_signal_interpretation_valid_signals(self, voter_tools_module):
        """Test show_signal_interpretation for all signal types."""
        for signal_type in ["STRONG", "WEAK", "CONFLICT", "NEUTRAL"]:
            result = voter_tools_module.show_signal_interpretation(signal_type)

            assert isinstance(result, str)
            assert signal_type in result
            assert "Position" in result

    def test_show_signal_interpretation_invalid_signal(self, voter_tools_module):
        """Test show_signal_interpretation with invalid signal."""
        result = voter_tools_module.show_signal_interpretation("INVALID")

        assert "Unknown signal type" in result

    def test_voter_tools_collection_exists(self, voter_tools_module):
        """Test CLI_VOTER_TOOLS collection is properly defined."""
        CLI_VOTER_TOOLS = voter_tools_module.CLI_VOTER_TOOLS

        assert isinstance(CLI_VOTER_TOOLS, list)
        assert len(CLI_VOTER_TOOLS) == 7  # 7 voter tools


# =============================================================================
# Tests: Issue #489 - Enhanced Timeframe Tools (Subset - Direct Functions Only)
# =============================================================================


class TestEnhancedTimeframeToolsFunctions:
    """Test enhanced timeframe helper functions (Issue #489).

    These tests only cover the pure functions that don't require
    the full timeframe_commands infrastructure.
    """

    @pytest.fixture
    def timeframe_helpers(self):
        """Load just the helper functions from timeframe_tools."""

        # Mock all dependencies
        class MockFunctionTool:
            def __init__(self, func=None, description="", name=None):
                self.func = func
                self.description = description
                self.name = name

        sys.modules["autogen_core.tools"] = MagicMock()
        sys.modules["autogen_core.tools"].FunctionTool = MockFunctionTool

        # Create a mock timeframe commands
        mock_tf_commands = MagicMock()
        mock_tf_commands.manager.get_current_timeframe.return_value = "1d"
        mock_tf_commands.validate_and_info.return_value = "Valid"

        # Create a mock module for the commands
        mock_tf_module = MagicMock()
        mock_tf_module.get_timeframe_commands.return_value = mock_tf_commands

        sys.modules["src.cli.commands.timeframe_commands"] = mock_tf_module

        module_path = project_root / "src" / "cli" / "tools" / "timeframe_tools.py"
        return import_module_directly(str(module_path), "timeframe_tools_test")

    def test_parse_timeframe_to_minutes_minutes(self, timeframe_helpers):
        """Test parsing minute-based timeframes."""
        parse = timeframe_helpers._parse_timeframe_to_minutes

        assert parse("30m") == 30
        assert parse("60m") == 60
        assert parse("90m") == 90

    def test_parse_timeframe_to_minutes_hours(self, timeframe_helpers):
        """Test parsing hour-based timeframes."""
        parse = timeframe_helpers._parse_timeframe_to_minutes

        assert parse("1h") == 60
        assert parse("2h") == 120
        assert parse("1.5h") == 90
        assert parse("4h") == 240

    def test_parse_timeframe_to_minutes_days(self, timeframe_helpers):
        """Test parsing day-based timeframes."""
        parse = timeframe_helpers._parse_timeframe_to_minutes

        assert parse("1d") == 1440
        assert parse("2d") == 2880

    def test_parse_timeframe_to_minutes_weeks(self, timeframe_helpers):
        """Test parsing week-based timeframes."""
        parse = timeframe_helpers._parse_timeframe_to_minutes

        assert parse("1w") == 10080
        assert parse("2w") == 20160

    def test_parse_timeframe_to_minutes_invalid(self, timeframe_helpers):
        """Test parsing invalid timeframes."""
        parse = timeframe_helpers._parse_timeframe_to_minutes

        assert parse("invalid") is None
        assert parse("abc") is None

    def test_get_base_timeframe_short(self, timeframe_helpers):
        """Test base timeframe for short periods."""
        get_base = timeframe_helpers._get_base_timeframe

        assert get_base(30) == "1m"
        assert get_base(60) == "1m"

    def test_get_base_timeframe_medium(self, timeframe_helpers):
        """Test base timeframe for medium periods."""
        get_base = timeframe_helpers._get_base_timeframe

        assert get_base(120) == "5m"
        assert get_base(240) == "5m"

    def test_get_base_timeframe_long(self, timeframe_helpers):
        """Test base timeframe for long periods."""
        get_base = timeframe_helpers._get_base_timeframe

        assert get_base(720) == "15m"
        assert get_base(1440) == "15m"

    def test_get_base_timeframe_very_long(self, timeframe_helpers):
        """Test base timeframe for very long periods."""
        get_base = timeframe_helpers._get_base_timeframe

        assert get_base(2880) == "1h"
        assert get_base(10080) == "1h"

    def test_multi_tf_presets_defined(self, timeframe_helpers):
        """Test MULTI_TF_PRESETS constant is defined."""
        presets = timeframe_helpers.MULTI_TF_PRESETS

        assert isinstance(presets, dict)
        assert "trend_following" in presets
        assert "intraday" in presets
        assert "position" in presets
        assert "scalping" in presets

    def test_multi_tf_presets_have_required_keys(self, timeframe_helpers):
        """Test each preset has required configuration keys."""
        presets = timeframe_helpers.MULTI_TF_PRESETS

        for name, config in presets.items():
            assert "description" in config, f"{name} missing description"
            assert "timeframes" in config, f"{name} missing timeframes"
            assert "style" in config, f"{name} missing style"

    def test_multi_tf_presets_weights_sum_to_one(self, timeframe_helpers):
        """Test each preset's timeframe weights sum approximately to 1.0."""
        presets = timeframe_helpers.MULTI_TF_PRESETS

        for name, config in presets.items():
            total = sum(config["timeframes"].values())
            # Allow for small floating point error
            assert 0.95 <= total <= 1.05, f"{name} weights sum to {total}, not ~1.0"


# =============================================================================
# Tests: Issue #490 - Backup Tools
# =============================================================================


class TestBackupTools:
    """Test backup CLI tools (Issue #490)."""

    def test_show_backup_info_returns_string(self, backup_tools_module):
        """Test show_backup_info returns formatted info."""
        result = backup_tools_module.show_backup_info()

        assert isinstance(result, str)
        assert "Backup System Info" in result
        assert "Databases" in result

    def test_get_backup_params_returns_dict(self, backup_tools_module):
        """Test get_backup_params returns structured data."""
        result = backup_tools_module.get_backup_params()

        assert isinstance(result, dict)
        assert "state_db" in result
        assert "cache_db" in result
        assert "backup_dir" in result
        assert "backup_count" in result
        assert "backups" in result

    def test_backup_database_missing_file(self, backup_tools_module):
        """Test backup_database with missing database file."""
        result = backup_tools_module.backup_database("nonexistent.db")

        assert "not found" in result or "failed" in result.lower()

    def test_restore_backup_missing_backup(self, backup_tools_module):
        """Test restore_backup with missing backup file."""
        result = backup_tools_module.restore_backup("nonexistent_backup.db")

        assert "not found" in result

    def test_list_backups_no_directory(self, backup_tools_module, temp_backup_dir):
        """Test list_backups behavior."""
        # Patch BACKUP_DIR to temp directory that doesn't exist yet
        nonexistent = Path(temp_backup_dir) / "nonexistent"
        original_backup_dir = backup_tools_module.BACKUP_DIR

        backup_tools_module.BACKUP_DIR = str(nonexistent)
        try:
            result = backup_tools_module.list_backups()
            assert "No backups" in result or "no directory" in result.lower()
        finally:
            backup_tools_module.BACKUP_DIR = original_backup_dir

    def test_backup_tools_collection_exists(self, backup_tools_module):
        """Test CLI_BACKUP_TOOLS collection is properly defined."""
        CLI_BACKUP_TOOLS = backup_tools_module.CLI_BACKUP_TOOLS

        assert isinstance(CLI_BACKUP_TOOLS, list)
        assert len(CLI_BACKUP_TOOLS) == 7  # 7 backup tools

    def test_default_paths_defined(self, backup_tools_module):
        """Test default path constants are defined."""
        assert backup_tools_module.STATE_DB == "state/user.db"
        assert backup_tools_module.CACHE_DB == ".cache/trading_data.db"
        assert backup_tools_module.BACKUP_DIR == "backups"


# =============================================================================
# Tests: Pure Function Tests (No Import Required)
# =============================================================================


class TestPureFunctions:
    """Test pure functions that can be tested without module imports."""

    def test_multi_tf_preset_names(self):
        """Test expected multi-timeframe preset names."""
        expected_presets = ["trend_following", "intraday", "position", "scalping"]

        # These are hardcoded in the module - just verify naming convention
        for preset in expected_presets:
            assert "_" in preset or preset.isalpha()
            assert preset.islower()

    def test_signal_types(self):
        """Test expected signal type names."""
        expected_signals = ["STRONG", "WEAK", "CONFLICT", "NEUTRAL"]

        for signal in expected_signals:
            assert signal.isupper()
            assert signal.isalpha()
