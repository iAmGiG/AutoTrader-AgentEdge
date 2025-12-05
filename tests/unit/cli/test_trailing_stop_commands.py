#!/usr/bin/env python3
"""
Unit tests for TrailingStopCommands

Issue #424: Trailing Stop CLI Commands - Visibility & Control

Tests cover:
- Show trailing stops display
- Show configuration display
- Manual stop override
- Error handling for missing manager
- Validation of stop prices
"""

import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock, Mock, patch

# Mock imports that require external dependencies
sys.modules["alpaca"] = MagicMock()
sys.modules["alpaca.trading"] = MagicMock()
sys.modules["alpaca.trading.client"] = MagicMock()
sys.modules["alpaca.trading.requests"] = MagicMock()
sys.modules["alpaca.data"] = MagicMock()
sys.modules["alpaca.data.historical"] = MagicMock()

from src.cli.commands.trailing_stop_commands import TrailingStopCommands


class TestTrailingStopCommands(unittest.TestCase):
    """Test TrailingStopCommands class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock stop manager
        self.mock_stop_manager = Mock()
        self.mock_stop_manager.stop_states = {}
        self.mock_stop_manager.order_manager = None

        # Create mock config
        self.mock_config = Mock()
        self.mock_config.climb_rate = "medium"
        self.mock_config.volatility_aware = True
        self.mock_config.atr_multiplier = 1.5
        self.mock_config.profit_zone_start_pct = 0.02
        self.mock_config.progressive_breakeven_pct = 0.02
        self.mock_config.progressive_lock_25_pct = 0.04
        self.mock_config.progressive_trail_50_pct = 0.06
        self.mock_config.min_update_interval_seconds = 60
        self.mock_config.never_move_stop_down = True

        self.mock_stop_manager.trailing_config = self.mock_config

        # Create commands instance
        self.commands = TrailingStopCommands(self.mock_stop_manager)

    def test_initialization(self):
        """Test TrailingStopCommands initialization."""
        self.assertIsNotNone(self.commands.stop_manager)
        self.assertEqual(self.commands.stop_manager, self.mock_stop_manager)

    def test_initialization_no_manager(self):
        """Test initialization without stop manager."""
        commands = TrailingStopCommands(None)
        self.assertIsNone(commands.stop_manager)

    @patch("sys.stdout", new_callable=StringIO)
    def test_show_trailing_stops_no_manager(self, mock_stdout):
        """Test show_trailing_stops when manager is not available."""
        commands = TrailingStopCommands(None)
        result = commands.show_trailing_stops()

        self.assertEqual(result["status"], "no_manager")
        self.assertEqual(result["positions"], [])

    @patch("sys.stdout", new_callable=StringIO)
    def test_show_trailing_stops_empty(self, mock_stdout):
        """Test show_trailing_stops with no positions."""
        result = self.commands.show_trailing_stops()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["positions"], [])
        self.assertEqual(result["count"], 0)

    @patch("sys.stdout", new_callable=StringIO)
    def test_show_trailing_stops_with_positions(self, mock_stdout):
        """Test show_trailing_stops with active positions."""
        # Create mock position states
        mock_state_aapl = Mock()
        mock_state_aapl.symbol = "AAPL"
        mock_state_aapl.entry_price = 150.0
        mock_state_aapl.highest_price_seen = 157.5
        mock_state_aapl.current_stop = 153.75
        mock_state_aapl.quantity = 100
        mock_state_aapl.in_profit_zone = True
        mock_state_aapl.adjustments_count = 4

        mock_state_googl = Mock()
        mock_state_googl.symbol = "GOOGL"
        mock_state_googl.entry_price = 2800.0
        mock_state_googl.highest_price_seen = 2850.0
        mock_state_googl.current_stop = 2820.0
        mock_state_googl.quantity = 10
        mock_state_googl.in_profit_zone = False
        mock_state_googl.adjustments_count = 0

        self.mock_stop_manager.stop_states = {"AAPL": mock_state_aapl, "GOOGL": mock_state_googl}

        result = self.commands.show_trailing_stops()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["positions"]), 2)

        # Check AAPL position data
        aapl_data = next(p for p in result["positions"] if p["symbol"] == "AAPL")
        self.assertEqual(aapl_data["entry_price"], 150.0)
        self.assertEqual(aapl_data["current_stop"], 153.75)
        self.assertAlmostEqual(aapl_data["profit_pct"], 5.0, places=1)
        self.assertTrue(aapl_data["in_profit_zone"])
        self.assertEqual(aapl_data["adjustments"], 4)

    @patch("sys.stdout", new_callable=StringIO)
    def test_show_config(self, mock_stdout):
        """Test show_config display."""
        result = self.commands.show_config()

        self.assertEqual(result["status"], "success")
        config = result["config"]

        self.assertEqual(config["climb_rate"], "medium")
        self.assertTrue(config["volatility_aware"])
        self.assertEqual(config["atr_multiplier"], 1.5)
        self.assertEqual(config["profit_zone_start_pct"], 0.02)
        self.assertEqual(config["progressive_breakeven_pct"], 0.02)
        self.assertEqual(config["min_update_interval_seconds"], 60)

    @patch("sys.stdout", new_callable=StringIO)
    def test_show_config_no_manager(self, mock_stdout):
        """Test show_config when manager is not available."""
        commands = TrailingStopCommands(None)
        result = commands.show_config()

        self.assertEqual(result["status"], "no_manager")

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_manual_stop_success(self, mock_stdout):
        """Test successful manual stop override."""
        # Create mock position state
        mock_state = Mock()
        mock_state.entry_price = 100.0
        mock_state.highest_price_seen = 110.0
        mock_state.current_stop = 102.0
        mock_state.quantity = 50
        mock_state.stop_order_id = "stop-123"
        mock_state.adjustments_count = 2

        self.mock_stop_manager.stop_states = {"AAPL": mock_state}

        result = self.commands.set_manual_stop("AAPL", 105.0)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["old_stop"], 102.0)
        self.assertEqual(result["new_stop"], 105.0)

        # Verify state was updated
        self.assertEqual(mock_state.current_stop, 105.0)
        self.assertEqual(mock_state.adjustments_count, 3)

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_manual_stop_with_broker_update(self, mock_stdout):
        """Test manual stop override with broker order update."""
        # Create mock position state
        mock_state = Mock()
        mock_state.entry_price = 100.0
        mock_state.highest_price_seen = 110.0
        mock_state.current_stop = 102.0
        mock_state.quantity = 50
        mock_state.stop_order_id = "stop-123"
        mock_state.adjustments_count = 2

        self.mock_stop_manager.stop_states = {"AAPL": mock_state}

        # Mock order manager
        mock_order_manager = Mock()
        mock_order_manager.replace_stop_order.return_value = {"id": "stop-456"}
        self.mock_stop_manager.order_manager = mock_order_manager

        result = self.commands.set_manual_stop("AAPL", 105.0)

        self.assertEqual(result["status"], "success")

        # Verify broker order was updated
        mock_order_manager.replace_stop_order.assert_called_once_with(
            order_id="stop-123", new_stop_price=105.0, symbol="AAPL", qty=50
        )

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_manual_stop_not_found(self, mock_stdout):
        """Test manual stop override for non-existent position."""
        result = self.commands.set_manual_stop("TSLA", 200.0)

        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["symbol"], "TSLA")

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_manual_stop_invalid_price_too_high(self, mock_stdout):
        """Test manual stop override with price above highest."""
        mock_state = Mock()
        mock_state.entry_price = 100.0
        mock_state.highest_price_seen = 110.0
        mock_state.current_stop = 102.0
        mock_state.quantity = 50
        mock_state.adjustments_count = 2

        self.mock_stop_manager.stop_states = {"AAPL": mock_state}

        result = self.commands.set_manual_stop("AAPL", 115.0)  # Above highest

        self.assertEqual(result["status"], "invalid_price")
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["stop_price"], 115.0)

        # Verify state was NOT updated
        self.assertEqual(mock_state.current_stop, 102.0)
        self.assertEqual(mock_state.adjustments_count, 2)

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_manual_stop_invalid_price_below_entry(self, mock_stdout):
        """Test manual stop override with price below entry."""
        mock_state = Mock()
        mock_state.entry_price = 100.0
        mock_state.highest_price_seen = 110.0
        mock_state.current_stop = 102.0
        mock_state.quantity = 50
        mock_state.adjustments_count = 2

        self.mock_stop_manager.stop_states = {"AAPL": mock_state}

        result = self.commands.set_manual_stop("AAPL", 95.0)  # Below entry

        self.assertEqual(result["status"], "invalid_price")

        # Verify state was NOT updated
        self.assertEqual(mock_state.current_stop, 102.0)

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_manual_stop_no_manager(self, mock_stdout):
        """Test manual stop override when manager is not available."""
        commands = TrailingStopCommands(None)
        result = commands.set_manual_stop("AAPL", 105.0)

        self.assertEqual(result["status"], "no_manager")

    def test_get_mode_description_conservative(self):
        """Test mode description for conservative settings."""
        config = Mock()
        config.progressive_breakeven_pct = 0.02
        config.stop_loss = 0.02

        result = self.commands._get_mode_description(config)
        self.assertEqual(result, "Conservative")

    def test_get_mode_description_aggressive(self):
        """Test mode description for aggressive settings."""
        config = Mock()
        config.progressive_breakeven_pct = 0.03

        result = self.commands._get_mode_description(config)
        self.assertEqual(result, "Aggressive")

    def test_get_mode_description_moderate(self):
        """Test mode description for moderate settings."""
        config = Mock()
        config.progressive_breakeven_pct = 0.025

        result = self.commands._get_mode_description(config)
        self.assertEqual(result, "Moderate")

    def test_get_climb_rate_description_slow(self):
        """Test climb rate description for slow."""
        result = self.commands._get_climb_rate_description("slow")
        self.assertEqual(result, "(20%/40%/60% gain locks)")

    def test_get_climb_rate_description_medium(self):
        """Test climb rate description for medium."""
        result = self.commands._get_climb_rate_description("medium")
        self.assertEqual(result, "(25%/50%/75% gain locks)")

    def test_get_climb_rate_description_fast(self):
        """Test climb rate description for fast."""
        result = self.commands._get_climb_rate_description("fast")
        self.assertEqual(result, "(33%/60%/80% gain locks)")

    def test_get_climb_rate_description_unknown(self):
        """Test climb rate description for unknown rate."""
        result = self.commands._get_climb_rate_description("turbo")
        self.assertEqual(result, "(unknown)")


if __name__ == "__main__":
    unittest.main()
