#!/usr/bin/env python3
"""
Unit tests for ApprovedTickersManager and TickerDatabase

Issue #415: Approved Ticker List with Entry Modes

Tests cover:
- Ticker metadata CRUD
- Leveraged ETF lookups (2x/3x)
- Underlying asset queries
- Approved ticker management
- Mode changes and filters
- Database persistence
"""

import os
import tempfile
import unittest

from src.core.trading_modes import TradingMode
from src.trading.approved_tickers import ApprovedTickersManager
from src.trading.ticker_database import TickerDatabase, TickerMode, TickerType


class TestTickerDatabase(unittest.TestCase):
    """Test TickerDatabase SQLite backend."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_tickers.db")
        self.db = TickerDatabase(self.db_path)

    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    # Metadata Tests

    def test_add_ticker_metadata(self):
        """Test adding ticker metadata."""
        self.db.add_ticker_metadata(
            symbol="AAPL",
            name="Apple Inc.",
            ticker_type=TickerType.STOCK,
            multiplier=1.0,
        )

        retrieved = self.db.get_ticker_metadata("AAPL")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.symbol, "AAPL")
        self.assertEqual(retrieved.name, "Apple Inc.")
        self.assertEqual(retrieved.ticker_type, TickerType.STOCK)

    def test_get_nonexistent_metadata(self):
        """Test retrieving nonexistent metadata returns None."""
        result = self.db.get_ticker_metadata("INVALID")
        self.assertIsNone(result)

    def test_list_by_type(self):
        """Test listing tickers by type."""
        # Add stocks
        self.db.add_ticker_metadata(symbol="AAPL", ticker_type=TickerType.STOCK)
        self.db.add_ticker_metadata(symbol="GOOGL", ticker_type=TickerType.STOCK)

        # Add ETFs
        self.db.add_ticker_metadata(symbol="SPY", ticker_type=TickerType.ETF_1X)
        self.db.add_ticker_metadata(symbol="TQQQ", ticker_type=TickerType.ETF_3X_BULL)

        stocks = self.db.list_by_type(TickerType.STOCK)
        self.assertEqual(len(stocks), 2)
        self.assertEqual(set(t.symbol for t in stocks), {"AAPL", "GOOGL"})

    def test_list_by_underlying(self):
        """Test listing tickers by underlying asset."""
        self.db.add_ticker_metadata(
            symbol="UPRO",
            ticker_type=TickerType.ETF_3X_BULL,
            underlying="SPY",
            multiplier=3.0,
        )
        self.db.add_ticker_metadata(
            symbol="SPXU",
            ticker_type=TickerType.ETF_3X_BEAR,
            underlying="SPY",
            multiplier=-3.0,
        )
        self.db.add_ticker_metadata(
            symbol="TQQQ",
            ticker_type=TickerType.ETF_3X_BULL,
            underlying="QQQ",
            multiplier=3.0,
        )

        spy_etfs = self.db.list_by_underlying("SPY")
        self.assertEqual(len(spy_etfs), 2)
        self.assertEqual(set(t.symbol for t in spy_etfs), {"UPRO", "SPXU"})

    def test_list_leveraged_etfs(self):
        """Test filtering leveraged ETFs by multiplier."""
        self.db.add_ticker_metadata(
            symbol="SSO", ticker_type=TickerType.ETF_2X_BULL, multiplier=2.0
        )
        self.db.add_ticker_metadata(
            symbol="UPRO", ticker_type=TickerType.ETF_3X_BULL, multiplier=3.0
        )
        self.db.add_ticker_metadata(
            symbol="TQQQ", ticker_type=TickerType.ETF_3X_BULL, multiplier=3.0
        )

        etfs_3x = self.db.list_leveraged_etfs(multiplier=3.0)
        self.assertEqual(len(etfs_3x), 2)
        self.assertEqual(set(t.symbol for t in etfs_3x), {"UPRO", "TQQQ"})

    # Approved Tickers Tests

    def test_approve_ticker(self):
        """Test approving a ticker."""
        approved = self.db.approve_ticker(
            symbol="AAPL", mode=TickerMode.BUY_ADD, max_position=10000.0, min_confidence=0.70
        )

        self.assertEqual(approved.symbol, "AAPL")
        self.assertEqual(approved.mode, TickerMode.BUY_ADD)
        self.assertEqual(approved.max_position, 10000.0)

        retrieved = self.db.get_approved("AAPL")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.mode, TickerMode.BUY_ADD)

    def test_remove_approved(self):
        """Test removing approved ticker."""
        self.db.approve_ticker(symbol="AAPL", mode=TickerMode.BUY_ADD)

        result = self.db.remove_approved("AAPL")
        self.assertTrue(result)

        retrieved = self.db.get_approved("AAPL")
        self.assertIsNone(retrieved)

    def test_list_approved(self):
        """Test listing all approved tickers."""
        self.db.approve_ticker(symbol="AAPL", mode=TickerMode.BUY_ADD)
        self.db.approve_ticker(symbol="GOOGL", mode=TickerMode.BUY)
        self.db.approve_ticker(symbol="TSLA", mode=TickerMode.WATCH_ONLY)

        tickers = self.db.list_approved()
        self.assertEqual(len(tickers), 3)
        symbols = {t.symbol for t in tickers}
        self.assertEqual(symbols, {"AAPL", "GOOGL", "TSLA"})

    def test_list_approved_by_mode(self):
        """Test filtering approved tickers by mode."""
        self.db.approve_ticker(symbol="AAPL", mode=TickerMode.BUY_ADD)
        self.db.approve_ticker(symbol="GOOGL", mode=TickerMode.BUY_ADD)
        self.db.approve_ticker(symbol="TSLA", mode=TickerMode.WATCH_ONLY)

        buy_add_tickers = self.db.list_approved(mode=TickerMode.BUY_ADD)
        self.assertEqual(len(buy_add_tickers), 2)
        self.assertEqual(set(t.symbol for t in buy_add_tickers), {"AAPL", "GOOGL"})

    def test_seed_common_tickers(self):
        """Test seeding database with common tickers."""
        self.db.seed_common_tickers()

        # Check stocks
        aapl = self.db.get_ticker_metadata("AAPL")
        self.assertIsNotNone(aapl)
        self.assertEqual(aapl.ticker_type, TickerType.STOCK)

        # Check 3x bull ETF
        tqqq = self.db.get_ticker_metadata("TQQQ")
        self.assertIsNotNone(tqqq)
        self.assertEqual(tqqq.ticker_type, TickerType.ETF_3X_BULL)
        self.assertEqual(tqqq.multiplier, 3.0)


class TestApprovedTickersManager(unittest.TestCase):
    """Test ApprovedTickersManager with database backend."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_tickers.db")
        self.manager = ApprovedTickersManager(db_path=self.db_path)

    def tearDown(self):
        """Clean up temporary database."""
        self.manager.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_add_ticker(self):
        """Test adding ticker via manager."""
        ticker = self.manager.add_ticker(
            symbol="AAPL", mode=TickerMode.BUY_ADD, max_position=10000.0
        )

        self.assertEqual(ticker.symbol, "AAPL")
        self.assertEqual(ticker.mode, TickerMode.BUY_ADD)
        self.assertEqual(ticker.max_position, 10000.0)

    def test_remove_ticker(self):
        """Test removing ticker via manager."""
        self.manager.add_ticker(symbol="AAPL")
        result = self.manager.remove_ticker("AAPL")
        self.assertTrue(result)

    def test_set_ticker_mode(self):
        """Test changing ticker mode."""
        self.manager.add_ticker(symbol="AAPL", mode=TickerMode.BUY)
        self.manager.set_ticker_mode("AAPL", TickerMode.WATCH_ONLY)

        ticker = self.manager.get_ticker("AAPL")
        self.assertEqual(ticker.mode, TickerMode.WATCH_ONLY)

    def test_list_approved(self):
        """Test listing all approved tickers."""
        self.manager.add_ticker(symbol="AAPL")
        self.manager.add_ticker(symbol="GOOGL")
        self.manager.add_ticker(symbol="TSLA", mode=TickerMode.DISABLED)

        all_tickers = self.manager.list_approved()
        self.assertEqual(len(all_tickers), 3)

        active_only = self.manager.list_approved(active_only=True)
        self.assertEqual(len(active_only), 2)

    def test_is_approved(self):
        """Test checking if ticker is approved."""
        self.manager.add_ticker(symbol="AAPL", mode=TickerMode.BUY_ADD)
        self.manager.add_ticker(symbol="TSLA", mode=TickerMode.DISABLED)

        self.assertTrue(self.manager.is_approved("AAPL"))
        self.assertFalse(self.manager.is_approved("TSLA"))  # Disabled
        self.assertFalse(self.manager.is_approved("INVALID"))

    def test_can_open_position(self):
        """Test checking if can open new positions."""
        self.manager.add_ticker(symbol="AAPL", mode=TickerMode.BUY)
        self.manager.add_ticker(symbol="GOOGL", mode=TickerMode.BUY_ADD)
        self.manager.add_ticker(symbol="TSLA", mode=TickerMode.WATCH_ONLY)

        self.assertTrue(self.manager.can_open_position("AAPL"))
        self.assertTrue(self.manager.can_open_position("GOOGL"))
        self.assertFalse(self.manager.can_open_position("TSLA"))

    def test_get_summary(self):
        """Test getting summary statistics."""
        self.manager.add_ticker(symbol="AAPL", mode=TickerMode.BUY_ADD)
        self.manager.add_ticker(symbol="GOOGL", mode=TickerMode.BUY)
        self.manager.add_ticker(symbol="TSLA", mode=TickerMode.WATCH_ONLY)
        self.manager.add_ticker(
            symbol="NVDA", mode=TickerMode.BUY_ADD, profile=TradingMode.CONSERVATIVE
        )

        summary = self.manager.get_summary()

        self.assertEqual(summary["total_approved"], 4)
        self.assertEqual(summary["buy_add_count"], 2)
        self.assertEqual(summary["buy_only_count"], 1)
        self.assertEqual(summary["profile_overrides"], 1)

    def test_seed_common_tickers(self):
        """Test seeding common tickers via manager."""
        self.manager.seed_common_tickers()

        # Verify stocks exist
        aapl = self.manager.get_ticker_metadata("AAPL")
        self.assertIsNotNone(aapl)

        # Verify leveraged ETFs exist
        tqqq = self.manager.get_ticker_metadata("TQQQ")
        self.assertIsNotNone(tqqq)
        self.assertEqual(tqqq.multiplier, 3.0)


if __name__ == "__main__":
    unittest.main()
