#!/usr/bin/env python3
"""
Unit tests for Advanced Trailing Stop Automation (Issue #414).

Tests the enhanced TrailingStopManager with:
- Configurable climb rates (slow/medium/fast)
- Volatility-aware adjustments via ATR
- Profit-zone awareness
- Integration with TradingModeManager
"""

import sys
import unittest
from unittest.mock import MagicMock

# Mock problematic imports before importing modules
sys.modules["alpaca"] = MagicMock()
sys.modules["alpaca.trading"] = MagicMock()
sys.modules["alpaca.trading.client"] = MagicMock()
sys.modules["alpaca.data"] = MagicMock()
sys.modules["alpaca.data.historical"] = MagicMock()
sys.modules["src.trading.unified_price_fetcher"] = MagicMock()
sys.modules["src.data_sources.sources.market.alpaca_market_data"] = MagicMock()
sys.modules["src.utils.market_hours"] = MagicMock()

from config_defaults.trading_config import ClimbRate, TrailingStopConfig

from src.trading.trailing_stop_manager import StopState, TrailingStopManager


class TestClimbRate(unittest.TestCase):
    """Test ClimbRate gain lock percentages."""

    def test_slow_climb_rate(self):
        """Slow climb rate should lock smaller gains."""
        locks = ClimbRate.get_gain_locks("slow")
        # (breakeven, zone1, zone2, zone3)
        self.assertEqual(locks, (0.0, 0.20, 0.40, 0.60))

    def test_medium_climb_rate(self):
        """Medium climb rate should lock moderate gains."""
        locks = ClimbRate.get_gain_locks("medium")
        self.assertEqual(locks, (0.0, 0.25, 0.50, 0.75))

    def test_fast_climb_rate(self):
        """Fast climb rate should lock larger gains quickly."""
        locks = ClimbRate.get_gain_locks("fast")
        self.assertEqual(locks, (0.0, 0.33, 0.60, 0.80))

    def test_invalid_climb_rate_defaults_to_medium(self):
        """Invalid climb rate should default to medium."""
        locks = ClimbRate.get_gain_locks("invalid")
        self.assertEqual(locks, (0.0, 0.25, 0.50, 0.75))


class TestTrailingStopConfigAdvanced(unittest.TestCase):
    """Test TrailingStopConfig with Issue #414 features."""

    def test_default_config_has_new_fields(self):
        """Default config should have Issue #414 fields."""
        config = TrailingStopConfig()
        self.assertEqual(config.climb_rate, "medium")
        self.assertFalse(config.volatility_aware)
        self.assertEqual(config.atr_multiplier, 1.5)
        self.assertEqual(config.atr_period, 14)
        self.assertEqual(config.profit_zone_start_pct, 0.02)

    def test_get_gain_lock_percentages(self):
        """Config should return correct gain lock percentages."""
        config = TrailingStopConfig(climb_rate="fast")
        locks = config.get_gain_lock_percentages()
        self.assertEqual(locks, (0.0, 0.33, 0.60, 0.80))


class TestTrailingStopManagerAdvanced(unittest.TestCase):
    """Test TrailingStopManager with Issue #414 features."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_order_manager = MagicMock()
        self.mock_order_manager.replace_stop_order.return_value = {
            "id": "new_order_123",
            "status": "accepted",
        }

    def test_init_with_climb_rate(self):
        """Manager should initialize with climb rate from config."""
        config = TrailingStopConfig(climb_rate="fast")
        manager = TrailingStopManager(
            order_manager=self.mock_order_manager,
            trailing_config=config,
        )
        self.assertEqual(manager.trailing_config.climb_rate, "fast")
        self.assertEqual(manager._gain_locks, (0.0, 0.33, 0.60, 0.80))

    def test_init_with_atr_fetcher(self):
        """Manager should accept ATR fetcher."""
        atr_fetcher = MagicMock(return_value=2.5)
        manager = TrailingStopManager(
            order_manager=self.mock_order_manager,
            atr_fetcher=atr_fetcher,
        )
        self.assertIsNotNone(manager.atr_fetcher)

    def test_stop_state_tracks_profit_zone(self):
        """StopState should track profit zone entry."""
        state = StopState(
            symbol="AAPL",
            entry_price=100.0,
            current_stop=95.0,
            quantity=10,
        )
        self.assertFalse(state.in_profit_zone)
        state.in_profit_zone = True
        self.assertTrue(state.in_profit_zone)

    def test_stop_state_tracks_atr(self):
        """StopState should track ATR for volatility awareness."""
        state = StopState(
            symbol="AAPL",
            entry_price=100.0,
            current_stop=95.0,
            quantity=10,
            current_atr=2.5,
        )
        self.assertEqual(state.current_atr, 2.5)

    def test_calculate_stop_with_slow_climb_rate(self):
        """Slow climb rate should lock 20% of gains in zone 1."""
        config = TrailingStopConfig(
            climb_rate="slow",
            progressive_enabled=True,
            progressive_breakeven_pct=0.02,
            progressive_lock_25_pct=0.04,
            progressive_trail_50_pct=0.06,
        )
        manager = TrailingStopManager(
            order_manager=self.mock_order_manager,
            trailing_config=config,
        )

        # Register position at $100
        manager.register_position("AAPL", 100.0, 95.0, 10)

        # At 5% profit ($105), should lock 20% of gains (slow)
        new_stop = manager.calculate_new_stop("AAPL", 105.0)
        # Gain = $5, 20% of gain = $1, stop = $100 + $1 = $101
        self.assertEqual(new_stop, 101.0)

    def test_calculate_stop_with_fast_climb_rate(self):
        """Fast climb rate should lock 33% of gains in zone 1."""
        config = TrailingStopConfig(
            climb_rate="fast",
            progressive_enabled=True,
            progressive_breakeven_pct=0.02,
            progressive_lock_25_pct=0.04,
            progressive_trail_50_pct=0.06,
        )
        manager = TrailingStopManager(
            order_manager=self.mock_order_manager,
            trailing_config=config,
        )

        # Register position at $100
        manager.register_position("AAPL", 100.0, 95.0, 10)

        # At 5% profit ($105), should lock 33% of gains (fast)
        new_stop = manager.calculate_new_stop("AAPL", 105.0)
        # Gain = $5, 33% of gain = $1.65, stop = $100 + $1.65 = $101.65
        self.assertEqual(new_stop, 101.65)

    def test_volatility_adjusted_stop(self):
        """Volatility-aware stops should use ATR buffer."""
        config = TrailingStopConfig(
            climb_rate="medium",
            volatility_aware=True,
            atr_multiplier=1.5,
            progressive_enabled=True,
            progressive_breakeven_pct=0.02,
            progressive_lock_25_pct=0.04,
            progressive_trail_50_pct=0.06,
        )

        # Mock ATR fetcher
        atr_fetcher = MagicMock(return_value=2.0)

        manager = TrailingStopManager(
            order_manager=self.mock_order_manager,
            trailing_config=config,
            atr_fetcher=atr_fetcher,
        )

        # Register position at $100
        manager.register_position("AAPL", 100.0, 95.0, 10)

        # At 5% profit ($105), ATR buffer = 2.0 * 1.5 = $3
        # Volatility stop = $105 - $3 = $102
        # Base stop (25% lock) = $100 + ($5 * 0.25) = $101.25
        # Use lower (more conservative): $101.25
        new_stop = manager.calculate_new_stop("AAPL", 105.0)

        # Verify ATR was fetched
        atr_fetcher.assert_called_once()
        self.assertIsNotNone(new_stop)

    def test_profit_zone_tracking(self):
        """Manager should track when position enters profit zone."""
        config = TrailingStopConfig(
            profit_zone_start_pct=0.02,  # 2%
            progressive_enabled=True,
            progressive_breakeven_pct=0.02,
        )
        manager = TrailingStopManager(
            order_manager=self.mock_order_manager,
            trailing_config=config,
        )

        # Register position at $100
        manager.register_position("AAPL", 100.0, 95.0, 10)
        state = manager.get_state("AAPL")

        # Initially not in profit zone
        self.assertFalse(state.in_profit_zone)

        # Check at 1% profit - still not in profit zone
        manager.calculate_new_stop("AAPL", 101.0)
        self.assertFalse(state.in_profit_zone)

        # Check at 2% profit - should enter profit zone
        manager.calculate_new_stop("AAPL", 102.0)
        self.assertTrue(state.in_profit_zone)

    def test_get_summary_includes_advanced_features(self):
        """Summary should include Issue #414 config."""
        config = TrailingStopConfig(
            climb_rate="fast",
            volatility_aware=True,
            atr_multiplier=2.0,
            profit_zone_start_pct=0.015,
        )
        manager = TrailingStopManager(
            order_manager=self.mock_order_manager,
            trailing_config=config,
        )

        summary = manager.get_summary()

        self.assertEqual(summary["config"]["climb_rate"], "fast")
        self.assertEqual(summary["config"]["gain_lock_percentages"], (0.0, 0.33, 0.60, 0.80))
        self.assertTrue(summary["config"]["volatility_aware"])
        self.assertEqual(summary["config"]["atr_multiplier"], 2.0)
        self.assertEqual(summary["config"]["profit_zone_start"], 0.015)

    def test_summary_tracks_positions_in_profit_zone(self):
        """Summary should count positions in profit zone."""
        manager = TrailingStopManager(
            order_manager=self.mock_order_manager,
            trailing_config=TrailingStopConfig(profit_zone_start_pct=0.02),
        )

        # Register two positions
        manager.register_position("AAPL", 100.0, 95.0, 10)
        manager.register_position("GOOGL", 200.0, 190.0, 5)

        # Put AAPL in profit zone
        manager.calculate_new_stop("AAPL", 103.0)

        summary = manager.get_summary()
        self.assertEqual(summary["positions_tracked"], 2)
        self.assertEqual(summary["positions_in_profit_zone"], 1)


class TestTrailingStopManagerFactoryMethod(unittest.TestCase):
    """Test from_mode_manager factory method."""

    def test_from_mode_manager(self):
        """Factory method should create manager from mode manager."""
        mock_order_manager = MagicMock()
        mock_mode_manager = MagicMock()
        mock_mode_manager.get_trailing_stop_config_dict.return_value = {
            "enabled": True,
            "progressive_enabled": True,
            "progressive_breakeven_pct": 0.03,
            "progressive_lock_25_pct": 0.06,
            "progressive_trail_50_pct": 0.10,
            "min_update_interval_seconds": 30,
            "never_move_stop_down": True,
            "climb_rate": "fast",
            "volatility_aware": True,
            "atr_multiplier": 1.0,
            "profit_zone_start_pct": 0.025,
        }

        manager = TrailingStopManager.from_mode_manager(
            order_manager=mock_order_manager,
            mode_manager=mock_mode_manager,
        )

        # Verify config was applied from mode manager
        self.assertEqual(manager.trailing_config.climb_rate, "fast")
        self.assertTrue(manager.trailing_config.volatility_aware)
        self.assertEqual(manager.trailing_config.atr_multiplier, 1.0)
        self.assertEqual(manager.trailing_config.progressive_breakeven_pct, 0.03)


class TestVolatilityAdjustment(unittest.TestCase):
    """Test volatility adjustment calculations."""

    def test_volatility_adjustment_widens_stop(self):
        """ATR adjustment should widen stop when volatility is high."""
        config = TrailingStopConfig(
            volatility_aware=True,
            atr_multiplier=2.0,
        )
        manager = TrailingStopManager(
            order_manager=MagicMock(),
            trailing_config=config,
        )

        # Base stop at $100, current price $105, ATR $3
        # ATR buffer = $3 * 2.0 = $6
        # Volatility stop = $105 - $6 = $99
        adjusted = manager._calculate_volatility_adjusted_stop(
            current_price=105.0,
            base_stop=100.0,
            atr=3.0,
        )

        # Should use volatility stop since it's lower (more conservative)
        self.assertEqual(adjusted, 99.0)

    def test_volatility_adjustment_keeps_base_when_lower(self):
        """Should keep base stop when it's more conservative than volatility stop."""
        config = TrailingStopConfig(
            volatility_aware=True,
            atr_multiplier=1.0,
        )
        manager = TrailingStopManager(
            order_manager=MagicMock(),
            trailing_config=config,
        )

        # Base stop at $95, current price $105, ATR $2
        # ATR buffer = $2 * 1.0 = $2
        # Volatility stop = $105 - $2 = $103
        # Base stop ($95) is lower, so use base
        adjusted = manager._calculate_volatility_adjusted_stop(
            current_price=105.0,
            base_stop=95.0,
            atr=2.0,
        )

        self.assertEqual(adjusted, 95.0)


if __name__ == "__main__":
    unittest.main()
