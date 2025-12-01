#!/usr/bin/env python3
"""
Unit tests for PortfolioManager

Issue #333: Portfolio Manager Agent - Risk & Position Sizing

Tests cover:
- Configuration loading
- Portfolio allocation tracking
- Pre-trade risk assessment
- Position and exposure limits
- Integration with PositionSizer
"""

import unittest
from unittest.mock import MagicMock

from src.core.trading_modes import TradingMode, TradingModeManager
from src.trading.portfolio_manager import (PortfolioConfig, PortfolioManager,
                                           TradeAssessment, TradeCheckResult)


class TestPortfolioConfig(unittest.TestCase):
    """Test PortfolioConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PortfolioConfig.default()

        self.assertEqual(config.risk_per_trade_pct, 0.02)
        self.assertEqual(config.max_position_pct, 0.10)
        self.assertEqual(config.max_exposure_pct, 0.80)
        self.assertEqual(config.max_open_positions, 10)

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "portfolio": {
                "size_usd": 100000,
                "risk_per_trade_pct": 0.03,
                "max_position_pct": 0.15,
            },
            "limits": {
                "max_open_positions": 5,
            },
        }

        config = PortfolioConfig.from_dict(data)

        self.assertEqual(config.size_usd, 100000)
        self.assertEqual(config.risk_per_trade_pct, 0.03)
        self.assertEqual(config.max_position_pct, 0.15)
        self.assertEqual(config.max_open_positions, 5)


class TestPortfolioManager(unittest.TestCase):
    """Test PortfolioManager functionality."""

    def setUp(self):
        """Create portfolio manager with test config."""
        self.mode_manager = TradingModeManager()
        self.manager = PortfolioManager(mode_manager=self.mode_manager)

        # Set up test account data
        self.manager.update_from_broker(
            positions={},
            account_info={
                "portfolio_value": 50000.0,
                "buying_power": 50000.0,
                "equity": 50000.0,
            },
        )

    def test_init(self):
        """Test initialization."""
        self.assertIsNotNone(self.manager)
        self.assertIsNotNone(self.manager.config)
        self.assertIsNotNone(self.manager.position_sizer)

    def test_get_portfolio_value(self):
        """Test getting portfolio value from broker."""
        self.assertEqual(self.manager.get_portfolio_value(), 50000.0)

    def test_get_buying_power(self):
        """Test getting buying power."""
        self.assertEqual(self.manager.get_buying_power(), 50000.0)

    def test_get_exposure_empty_portfolio(self):
        """Test exposure calculation with no positions."""
        self.assertEqual(self.manager.get_total_exposure(), 0.0)
        self.assertEqual(self.manager.get_exposure_pct(), 0.0)

    def test_get_exposure_with_positions(self):
        """Test exposure calculation with positions."""
        self.manager.update_from_broker(
            positions={
                "AAPL": {"symbol": "AAPL", "qty": 10, "market_value": 1855.0},
                "GOOGL": {"symbol": "GOOGL", "qty": 5, "market_value": 875.0},
            },
            account_info={
                "portfolio_value": 50000.0,
                "buying_power": 47270.0,
            },
        )

        self.assertEqual(self.manager.get_total_exposure(), 2730.0)
        self.assertAlmostEqual(self.manager.get_exposure_pct(), 0.0546, places=4)


class TestTradeAssessment(unittest.TestCase):
    """Test pre-trade risk assessment."""

    def setUp(self):
        """Create portfolio manager for assessment tests."""
        self.mode_manager = TradingModeManager()
        self.manager = PortfolioManager(mode_manager=self.mode_manager)

        self.manager.update_from_broker(
            positions={},
            account_info={
                "portfolio_value": 50000.0,
                "buying_power": 50000.0,
            },
        )

    def test_assess_basic_trade(self):
        """Test basic trade assessment with conservative mode (5% < 8% warning)."""
        assessment = self.manager.assess_trade(
            symbol="AAPL",
            current_price=185.50,
            mode=TradingMode.CONSERVATIVE,  # 5% max, below 8% warning threshold
        )

        self.assertEqual(assessment.symbol, "AAPL")
        self.assertTrue(assessment.is_approved())
        self.assertEqual(assessment.result, TradeCheckResult.APPROVED)
        self.assertIsNotNone(assessment.size_result)
        self.assertTrue(assessment.size_result.is_valid)

    def test_assess_with_existing_position(self):
        """Test assessment warns about existing position."""
        self.manager.update_from_broker(
            positions={
                "AAPL": {"symbol": "AAPL", "qty": 10, "market_value": 1855.0},
            },
            account_info={
                "portfolio_value": 50000.0,
                "buying_power": 48145.0,
            },
        )

        assessment = self.manager.assess_trade(
            symbol="AAPL",
            current_price=185.50,
        )

        self.assertTrue(assessment.is_approved())
        self.assertEqual(assessment.existing_position_value, 1855.0)
        self.assertTrue(any("Existing position" in w for w in assessment.warnings))

    def test_assess_insufficient_buying_power(self):
        """Test assessment blocks when insufficient buying power."""
        self.manager.update_from_broker(
            positions={},
            account_info={
                "portfolio_value": 50000.0,
                "buying_power": 100.0,  # Only $100 available
            },
        )

        assessment = self.manager.assess_trade(
            symbol="AAPL",
            current_price=185.50,
        )

        self.assertFalse(assessment.is_approved())
        self.assertEqual(assessment.result, TradeCheckResult.BLOCKED)

    def test_assess_near_position_limit(self):
        """Test assessment warns when near max positions."""
        # Create max positions
        positions = {
            f"TICK{i}": {"symbol": f"TICK{i}", "qty": 1, "market_value": 100}
            for i in range(10)  # Max is 10
        }
        self.manager.update_from_broker(
            positions=positions,
            account_info={
                "portfolio_value": 50000.0,
                "buying_power": 49000.0,
            },
        )

        assessment = self.manager.assess_trade(
            symbol="NEWSTOCK",
            current_price=100.0,
        )

        # Should warn (or block if hard_block enabled)
        self.assertTrue(
            any("max positions" in w.lower() for w in assessment.warnings)
            or any("max positions" in m.lower() for m in assessment.messages)
        )


class TestAllocationDisplay(unittest.TestCase):
    """Test portfolio allocation display."""

    def setUp(self):
        """Create portfolio manager with positions."""
        self.mode_manager = TradingModeManager()
        self.manager = PortfolioManager(mode_manager=self.mode_manager)

        self.manager.update_from_broker(
            positions={
                "AAPL": {
                    "symbol": "AAPL",
                    "qty": 50,
                    "market_value": 9275.0,
                    "unrealized_pl": 125.0,
                    "unrealized_pl_percent": 0.0137,
                },
                "GOOGL": {
                    "symbol": "GOOGL",
                    "qty": 20,
                    "market_value": 3500.0,
                    "unrealized_pl": -50.0,
                    "unrealized_pl_percent": -0.0141,
                },
            },
            account_info={
                "portfolio_value": 50000.0,
                "buying_power": 37225.0,
            },
        )

    def test_allocation_summary(self):
        """Test allocation summary data."""
        summary = self.manager.get_allocation_summary()

        self.assertEqual(summary["portfolio_value"], 50000.0)
        self.assertEqual(summary["total_exposure"], 12775.0)
        self.assertAlmostEqual(summary["exposure_pct"], 0.2555, places=4)
        self.assertEqual(summary["position_count"], 2)
        self.assertEqual(len(summary["positions"]), 2)

    def test_allocation_display_format(self):
        """Test allocation display formatting."""
        display = self.manager.format_allocation_display()

        self.assertIn("Portfolio Allocation", display)
        self.assertIn("AAPL", display)
        self.assertIn("GOOGL", display)
        self.assertIn("50,000", display)  # Portfolio value

    def test_empty_portfolio_display(self):
        """Test display with no positions."""
        self.manager.update_from_broker(
            positions={},
            account_info={
                "portfolio_value": 50000.0,
                "buying_power": 50000.0,
            },
        )

        display = self.manager.format_allocation_display()

        self.assertIn("No positions", display)


class TestConfigOverrides(unittest.TestCase):
    """Test configuration overrides."""

    def test_config_size_override(self):
        """Test portfolio size override from config."""
        # Create config with explicit size
        manager = PortfolioManager()
        manager.config.size_usd = 100000.0  # Override

        manager.update_from_broker(
            positions={},
            account_info={
                "portfolio_value": 50000.0,  # Broker says $50k
                "buying_power": 50000.0,
            },
        )

        # Should use config override, not broker value
        self.assertEqual(manager.get_portfolio_value(), 100000.0)


class TestTradeAssessmentSummary(unittest.TestCase):
    """Test TradeAssessment summary formatting."""

    def test_approved_summary(self):
        """Test summary for approved trade."""
        size_result = MagicMock()
        size_result.is_valid = True
        size_result.shares = 26
        size_result.price_per_share = 185.50
        size_result.position_value = 4823.0

        assessment = TradeAssessment(
            symbol="AAPL",
            result=TradeCheckResult.APPROVED,
            messages=[],
            warnings=[],
            size_result=size_result,
            portfolio_value=50000.0,
            buying_power=50000.0,
            current_exposure_pct=0.0,
            existing_position_value=0.0,
            projected_exposure_pct=0.0965,
            projected_position_pct=0.0965,
        )

        summary = assessment.get_summary()

        self.assertIn("✅", summary)
        self.assertIn("AAPL", summary)
        self.assertIn("26 shares", summary)

    def test_blocked_summary(self):
        """Test summary for blocked trade."""
        assessment = TradeAssessment(
            symbol="AAPL",
            result=TradeCheckResult.BLOCKED,
            messages=["Insufficient buying power"],
            warnings=[],
            size_result=None,
            portfolio_value=50000.0,
            buying_power=100.0,
            current_exposure_pct=0.0,
            existing_position_value=0.0,
            projected_exposure_pct=0.0,
            projected_position_pct=0.0,
        )

        summary = assessment.get_summary()

        self.assertIn("❌", summary)
        self.assertIn("Insufficient buying power", summary)


if __name__ == "__main__":
    unittest.main()
