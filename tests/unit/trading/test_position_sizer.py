#!/usr/bin/env python3
"""
Unit tests for PositionSizer

Issue #416: Position Sizing Automation - Profile-Based Allocation

Tests cover:
- Profile-based sizing (conservative/moderate/aggressive)
- Per-ticker limit integration (#415)
- Buying power validation
- Existing position awareness
- Risk calculation with stop prices
- Edge cases
"""

import os
import tempfile
import unittest

from src.core.trading_modes import TradingMode, TradingModeManager
from src.trading.approved_tickers import ApprovedTickersManager
from src.trading.position_sizer import PositionSizer, SizingMode
from src.trading.ticker_database import TickerMode


class TestPositionSizerBasics(unittest.TestCase):
    """Test basic PositionSizer functionality."""

    def setUp(self):
        """Create position sizer with mode manager."""
        self.mode_manager = TradingModeManager()
        self.sizer = PositionSizer(mode_manager=self.mode_manager)

    def test_init(self):
        """Test initialization."""
        self.assertIsNotNone(self.sizer)
        self.assertEqual(self.sizer.default_sizing_mode, SizingMode.PROFILE_BASED)

    def test_calculate_moderate_mode(self):
        """Test moderate mode sizing (10% max)."""
        self.mode_manager.set_mode(TradingMode.MODERATE)

        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.symbol, "AAPL")
        self.assertEqual(result.trading_mode, TradingMode.MODERATE)
        self.assertEqual(result.max_position_pct, 0.10)

        # 10% of $50k = $5000, but max_position_value is also $5000
        # At $185.50, that's 26 shares ($4,823)
        self.assertEqual(result.shares, 26)
        self.assertAlmostEqual(result.position_value, 26 * 185.50, places=2)

    def test_calculate_conservative_mode(self):
        """Test conservative mode sizing (5% max)."""
        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
            mode=TradingMode.CONSERVATIVE,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.trading_mode, TradingMode.CONSERVATIVE)
        self.assertEqual(result.max_position_pct, 0.05)

        # 5% of $50k = $2500
        # At $185.50, that's 13 shares ($2,411.50)
        self.assertEqual(result.shares, 13)

    def test_calculate_aggressive_mode(self):
        """Test aggressive mode sizing (20% max)."""
        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
            mode=TradingMode.AGGRESSIVE,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.trading_mode, TradingMode.AGGRESSIVE)
        self.assertEqual(result.max_position_pct, 0.20)

        # 20% of $50k = $10000
        # At $185.50, that's 53 shares ($9,831.50)
        self.assertEqual(result.shares, 53)


class TestBuyingPowerValidation(unittest.TestCase):
    """Test buying power constraint handling."""

    def setUp(self):
        """Create position sizer."""
        self.mode_manager = TradingModeManager()
        self.sizer = PositionSizer(mode_manager=self.mode_manager)

    def test_limited_buying_power(self):
        """Test sizing when buying power is limiting factor."""
        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=2000.0,  # Only $2000 available
            mode=TradingMode.AGGRESSIVE,
        )

        self.assertTrue(result.is_valid)
        # Should be limited to $2000, not 20% of portfolio
        self.assertLessEqual(result.position_value, 2000.0)
        self.assertEqual(result.shares, 10)  # $1855

    def test_insufficient_buying_power(self):
        """Test when buying power is insufficient for even 1 share."""
        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=100.0,  # Can't afford 1 share
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.shares, 0)
        self.assertIn("Insufficient buying power", result.validation_message)


class TestExistingPositionAwareness(unittest.TestCase):
    """Test handling of existing positions."""

    def setUp(self):
        """Create position sizer."""
        self.mode_manager = TradingModeManager()
        self.sizer = PositionSizer(mode_manager=self.mode_manager)

    def test_existing_position_reduces_size(self):
        """Test that existing position reduces available allocation."""
        # No existing position
        result_new = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
            existing_position_value=0.0,
            mode=TradingMode.MODERATE,
        )

        # With existing position
        result_existing = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
            existing_position_value=3000.0,  # Already have $3000 in AAPL
            mode=TradingMode.MODERATE,
        )

        # Should suggest fewer shares when position exists
        self.assertLess(result_existing.shares, result_new.shares)
        # 10% of $50k = $5000 limit, $3000 existing = $2000 available
        self.assertEqual(result_existing.shares, 10)  # $1855

    def test_position_at_limit(self):
        """Test when existing position is already at limit."""
        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
            existing_position_value=5000.0,  # Already at 10% limit
            mode=TradingMode.MODERATE,
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.shares, 0)


class TestPerTickerLimits(unittest.TestCase):
    """Test integration with ApprovedTickersManager per-ticker limits (#415)."""

    def setUp(self):
        """Create position sizer with tickers manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_tickers.db")
        self.tickers_manager = ApprovedTickersManager(db_path=self.db_path)
        self.mode_manager = TradingModeManager()
        self.sizer = PositionSizer(
            mode_manager=self.mode_manager,
            tickers_manager=self.tickers_manager,
        )

    def tearDown(self):
        """Clean up temporary database."""
        self.tickers_manager.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_ticker_limit_overrides_mode(self):
        """Test that per-ticker limit can override mode limit."""
        # Set a per-ticker limit lower than mode limit
        self.tickers_manager.add_ticker(
            symbol="TSLA",
            mode=TickerMode.BUY_ADD,
            max_position=3000.0,  # Lower than aggressive 20% of $50k
        )

        result = self.sizer.calculate_position_size(
            symbol="TSLA",
            current_price=250.0,
            portfolio_value=50000.0,
            buying_power=50000.0,
            mode=TradingMode.AGGRESSIVE,  # Would normally allow $10k
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.ticker_limit, 3000.0)
        # Should be limited to $3000, not $10k
        self.assertLessEqual(result.position_value, 3000.0)
        self.assertEqual(result.shares, 12)  # 12 * $250 = $3000

    def test_disabled_ticker_rejected(self):
        """Test that disabled tickers are rejected."""
        self.tickers_manager.add_ticker(
            symbol="AAPL",
            mode=TickerMode.DISABLED,
        )

        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
        )

        self.assertFalse(result.is_valid)
        self.assertIn("disabled", result.validation_message.lower())

    def test_watch_only_ticker_rejected(self):
        """Test that watch-only tickers cannot trade."""
        self.tickers_manager.add_ticker(
            symbol="GOOGL",
            mode=TickerMode.WATCH_ONLY,
        )

        result = self.sizer.calculate_position_size(
            symbol="GOOGL",
            current_price=175.0,
            portfolio_value=50000.0,
            buying_power=50000.0,
        )

        self.assertFalse(result.is_valid)
        self.assertIn("watch-only", result.validation_message.lower())


class TestRiskCalculation(unittest.TestCase):
    """Test risk calculation with stop prices."""

    def setUp(self):
        """Create position sizer."""
        self.mode_manager = TradingModeManager()
        self.sizer = PositionSizer(mode_manager=self.mode_manager)

    def test_risk_with_stop_price(self):
        """Test risk calculation when stop price provided."""
        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
            mode=TradingMode.MODERATE,
            stop_price=176.22,  # ~5% below current
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.stop_price, 176.22)
        self.assertIsNotNone(result.risk_per_share)
        self.assertAlmostEqual(result.risk_per_share, 185.50 - 176.22, places=2)
        self.assertIsNotNone(result.total_risk)
        self.assertAlmostEqual(result.total_risk, result.risk_per_share * result.shares, places=2)

    def test_shares_from_risk_amount(self):
        """Test calculating shares from fixed risk amount."""
        shares, value = self.sizer.calculate_shares_from_risk(
            risk_amount=500.0,  # Risk $500
            current_price=185.50,
            stop_price=176.22,  # $9.28 risk per share
            buying_power=50000.0,
        )

        # $500 / $9.28 = 53 shares
        self.assertEqual(shares, 53)
        self.assertAlmostEqual(value, 53 * 185.50, places=2)


class TestFixedSizingModes(unittest.TestCase):
    """Test fixed dollar and fixed shares sizing modes."""

    def setUp(self):
        """Create position sizer."""
        self.mode_manager = TradingModeManager()
        self.sizer = PositionSizer(mode_manager=self.mode_manager)
        self.sizer.fixed_dollar_amount = 5000.0
        self.sizer.fixed_shares_count = 100

    def test_fixed_dollar_mode(self):
        """Test fixed dollar sizing mode."""
        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=100000.0,
            buying_power=100000.0,
            sizing_mode=SizingMode.FIXED_DOLLAR,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.sizing_mode, SizingMode.FIXED_DOLLAR)
        # $5000 / $185.50 = 26 shares
        self.assertEqual(result.shares, 26)

    def test_fixed_shares_mode(self):
        """Test fixed shares sizing mode."""
        result = self.sizer.calculate_position_size(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=100000.0,
            buying_power=100000.0,
            sizing_mode=SizingMode.FIXED_SHARES,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.sizing_mode, SizingMode.FIXED_SHARES)
        # 100 shares * $185.50 = $18,550
        # But constrained by mode limit: min(10% of $100k, $5k) = $5,000
        # So should be 26 shares ($5,000 / $185.50)
        self.assertEqual(result.shares, 26)


class TestSummaryOutput(unittest.TestCase):
    """Test human-readable summary output."""

    def setUp(self):
        """Create position sizer."""
        self.mode_manager = TradingModeManager()
        self.sizer = PositionSizer(mode_manager=self.mode_manager)

    def test_summary_format(self):
        """Test summary output formatting."""
        summary = self.sizer.get_suggested_size_summary(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
            mode=TradingMode.MODERATE,
        )

        self.assertIn("Position Sizing", summary)
        self.assertIn("Moderate", summary)
        self.assertIn("Max position", summary)
        self.assertIn("Suggested:", summary)
        self.assertIn("shares", summary)

    def test_summary_with_stop(self):
        """Test summary includes risk info when stop provided."""
        summary = self.sizer.get_suggested_size_summary(
            symbol="AAPL",
            current_price=185.50,
            portfolio_value=50000.0,
            buying_power=50000.0,
            stop_price=176.22,
        )

        self.assertIn("Stop @", summary)
        self.assertIn("Risk:", summary)


class TestCanOpenPosition(unittest.TestCase):
    """Test quick position check functionality."""

    def setUp(self):
        """Create position sizer with tickers manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_tickers.db")
        self.tickers_manager = ApprovedTickersManager(db_path=self.db_path)
        self.mode_manager = TradingModeManager()
        self.sizer = PositionSizer(
            mode_manager=self.mode_manager,
            tickers_manager=self.tickers_manager,
        )

    def tearDown(self):
        """Clean up temporary database."""
        self.tickers_manager.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_can_open_approved_ticker(self):
        """Test can open position for approved ticker."""
        self.tickers_manager.add_ticker("AAPL", mode=TickerMode.BUY_ADD)

        self.assertTrue(self.sizer.can_open_position("AAPL", 185.50, 10000.0))

    def test_cannot_open_disabled_ticker(self):
        """Test cannot open position for disabled ticker."""
        self.tickers_manager.add_ticker("AAPL", mode=TickerMode.DISABLED)

        self.assertFalse(self.sizer.can_open_position("AAPL", 185.50, 10000.0))

    def test_cannot_open_insufficient_funds(self):
        """Test cannot open when buying power too low."""
        self.tickers_manager.add_ticker("AAPL", mode=TickerMode.BUY_ADD)

        self.assertFalse(self.sizer.can_open_position("AAPL", 185.50, 100.0))


if __name__ == "__main__":
    unittest.main()
