#!/usr/bin/env python3
"""
Unit tests for PositionManager.

Tests broker reconciliation, caching, fallback behavior, and edge cases.
Issue #408: Unit Testing and CLI Testing (Pre-Live Trading Validation)

Priority 1 Component - Money-Handling
Target Coverage: 80%+
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.trading.position_manager import PositionManager


class TestPositionManagerInit:
    """Test PositionManager initialization."""

    def test_init_with_broker_client(self, mock_broker_client, tmp_path):
        """Test basic initialization with broker client."""
        with patch("src.trading.position_manager.Path") as mock_path:
            # Mock the state file path to use temp directory
            mock_path.return_value = tmp_path / "state" / "positions.json"

            pm = PositionManager(mock_broker_client)

            assert pm.broker == mock_broker_client
            assert pm._session_cache == {}
            assert pm._cache_timestamp is None
            assert pm._cache_ttl_seconds == 60

    def test_init_creates_state_directory(self, mock_broker_client, tmp_path):
        """Test that init creates state directory if missing."""
        with patch("builtins.open", MagicMock(side_effect=FileNotFoundError)):
            with patch.object(Path, "mkdir"):
                pm = PositionManager(mock_broker_client)
                # Should not raise even if config file missing
                assert pm is not None

    def test_init_with_custom_config(self, mock_broker_client, tmp_path):
        """Test initialization with custom paths config."""
        config_content = {"state_files": {"positions": str(tmp_path / "custom_positions.json")}}

        config_file = tmp_path / "paths_config.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        with patch("src.trading.position_manager.open", MagicMock()):
            pm = PositionManager(mock_broker_client)
            assert pm is not None


class TestGetPositions:
    """Test get_positions() method."""

    def test_get_positions_from_broker(self, mock_broker_with_positions, tmp_path):
        """Test fetching positions from broker."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            positions = pm.get_positions()

            assert len(positions) == 3
            assert "SPY" in positions
            assert "AAPL" in positions
            assert "MSFT" in positions

    def test_position_data_format(self, mock_broker_with_positions, tmp_path):
        """Test position data is correctly formatted."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            positions = pm.get_positions()
            spy = positions["SPY"]

            # Verify all expected fields
            assert spy["symbol"] == "SPY"
            assert spy["qty"] == 10.0
            assert spy["side"] == "long"
            assert spy["avg_entry_price"] == 450.0
            assert spy["market_value"] == 4800.0
            assert spy["unrealized_pl"] == 300.0
            assert spy["cost_basis"] == 4500.0
            assert "last_updated" in spy

    def test_cache_prevents_repeated_api_calls(self, mock_broker_with_positions, tmp_path):
        """Test that cache prevents repeated API calls within TTL."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            # First call
            pm.get_positions()
            # Second call (should use cache)
            pm.get_positions()
            # Third call (should use cache)
            pm.get_positions()

            # API should only be called once
            assert mock_broker_with_positions.get_all_positions.call_count == 1

    def test_force_refresh_bypasses_cache(self, mock_broker_with_positions, tmp_path):
        """Test force_refresh bypasses cache."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            # First call
            pm.get_positions()
            # Force refresh call
            pm.get_positions(force_refresh=True)

            # API should be called twice
            assert mock_broker_with_positions.get_all_positions.call_count == 2

    def test_cache_expires_after_ttl(self, mock_broker_with_positions, tmp_path):
        """Test cache expires after TTL."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"
            pm._cache_ttl_seconds = 1  # 1 second TTL for testing

            # First call
            pm.get_positions()

            # Wait for cache to expire
            import time

            time.sleep(1.5)

            # Second call (cache expired)
            pm.get_positions()

            # API should be called twice
            assert mock_broker_with_positions.get_all_positions.call_count == 2

    def test_empty_positions(self, mock_broker_client, tmp_path):
        """Test handling of empty positions."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_client)
            pm.state_file = tmp_path / "positions.json"

            positions = pm.get_positions()

            assert positions == {}

    def test_api_error_uses_cache_fallback(self, mock_broker_with_positions, tmp_path):
        """Test API error falls back to cached data."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            # First call (populates cache)
            positions1 = pm.get_positions(force_refresh=True)
            assert len(positions1) == 3

            # Simulate API error
            mock_broker_with_positions.get_all_positions.side_effect = Exception("API Error")

            # Clear cache timestamp to force API call
            pm._cache_timestamp = None

            # Second call (should use cached data)
            positions2 = pm.get_positions()

            assert positions2 == positions1

    def test_api_error_uses_file_backup(self, mock_broker_api_error, tmp_path):
        """Test API error with no cache falls back to file backup."""
        backup_data = {
            "positions": {
                "SPY": {
                    "symbol": "SPY",
                    "qty": 5,
                    "market_value": 2500.0,
                }
            },
            "saved_at": "2025-01-15T10:00:00",
        }

        backup_file = tmp_path / "positions.json"
        with open(backup_file, "w") as f:
            json.dump(backup_data, f)

        pm = PositionManager(mock_broker_api_error)
        pm.state_file = backup_file

        positions = pm.get_positions()

        assert "SPY" in positions
        assert positions["SPY"]["qty"] == 5


class TestGetPosition:
    """Test get_position() method for single symbol."""

    def test_get_existing_position(self, mock_broker_with_positions, tmp_path):
        """Test getting an existing position."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            position = pm.get_position("SPY")

            assert position is not None
            assert position["symbol"] == "SPY"
            assert position["qty"] == 10.0

    def test_get_nonexistent_position(self, mock_broker_with_positions, tmp_path):
        """Test getting a position that doesn't exist."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            position = pm.get_position("NVDA")

            assert position is None


class TestHasPosition:
    """Test has_position() method."""

    def test_has_position_true(self, mock_broker_with_positions, tmp_path):
        """Test has_position returns True for existing position."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            assert pm.has_position("SPY") is True

    def test_has_position_false(self, mock_broker_with_positions, tmp_path):
        """Test has_position returns False for non-existing position."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            assert pm.has_position("NVDA") is False


class TestPositionValues:
    """Test position value calculation methods."""

    def test_get_position_value(self, mock_broker_with_positions, tmp_path):
        """Test get_position_value returns market value."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            value = pm.get_position_value("SPY")
            assert value == 4800.0

    def test_get_position_value_no_position(self, mock_broker_with_positions, tmp_path):
        """Test get_position_value returns 0 for no position."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            value = pm.get_position_value("NVDA")
            assert value == 0.0

    def test_get_unrealized_pl(self, mock_broker_with_positions, tmp_path):
        """Test get_unrealized_pl returns correct P&L."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            # SPY is profitable
            assert pm.get_unrealized_pl("SPY") == 300.0
            # AAPL is at loss
            assert pm.get_unrealized_pl("AAPL") == -200.0
            # MSFT is breakeven
            assert pm.get_unrealized_pl("MSFT") == 0.0

    def test_get_portfolio_value(self, mock_broker_with_positions, tmp_path):
        """Test get_portfolio_value returns total value."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            # SPY: 4800 + AAPL: 3400 + MSFT: 2000 = 10200
            total_value = pm.get_portfolio_value()
            assert total_value == 10200.0

    def test_get_portfolio_pl(self, mock_broker_with_positions, tmp_path):
        """Test get_portfolio_pl returns total P&L."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            # SPY: +300 + AAPL: -200 + MSFT: 0 = +100
            total_pl = pm.get_portfolio_pl()
            assert total_pl == 100.0


class TestAccountInfo:
    """Test get_account_info() method."""

    def test_get_account_info(self, mock_broker_client, tmp_path):
        """Test getting account information."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_client)
            pm.state_file = tmp_path / "positions.json"

            account = pm.get_account_info()

            assert account["buying_power"] == 100000.0
            assert account["cash"] == 50000.0
            assert account["portfolio_value"] == 150000.0
            assert account["equity"] == 150000.0
            assert account["status"] == "ACTIVE"
            assert "last_updated" in account

    def test_get_account_info_api_error(self, mock_broker_api_error, tmp_path):
        """Test get_account_info handles API errors."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_api_error)
            pm.state_file = tmp_path / "positions.json"

            account = pm.get_account_info()

            assert account == {}


class TestOrders:
    """Test order-related methods."""

    def test_get_orders(self, mock_broker_with_orders, tmp_path):
        """Test getting orders from broker."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_orders)
            pm.state_file = tmp_path / "positions.json"

            orders = pm.get_orders()

            assert len(orders) == 3
            assert orders[0]["id"] == "order-001"
            assert orders[0]["symbol"] == "SPY"

    def test_get_orders_with_status_filter(self, mock_broker_with_orders, tmp_path):
        """Test get_orders passes status parameter."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_orders)
            pm.state_file = tmp_path / "positions.json"

            pm.get_orders(status="closed")

            mock_broker_with_orders.get_orders.assert_called_with(status="closed", limit=100)

    def test_get_orders_api_error(self, mock_broker_api_error, tmp_path):
        """Test get_orders handles API errors."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_api_error)
            pm.state_file = tmp_path / "positions.json"

            orders = pm.get_orders()

            assert orders == []

    def test_get_single_order(self, mock_broker_with_orders, tmp_path):
        """Test getting a single order by ID."""
        # Set up mock for single order fetch
        mock_order = MagicMock()
        mock_order.id = "order-001"
        mock_order.symbol = "SPY"
        mock_order.qty = "5"
        mock_order.side = "buy"
        mock_order.order_type = "limit"
        mock_order.status = "new"
        mock_order.submitted_at = datetime.now()
        mock_order.filled_at = None
        mock_order.filled_qty = None
        mock_order.filled_avg_price = None
        mock_order.limit_price = "595.00"
        mock_order.stop_price = None
        mock_order.time_in_force = "gtc"
        mock_order.order_class = "simple"
        mock_order.legs = None

        mock_broker_with_orders.get_order.return_value = mock_order

        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_orders)
            pm.state_file = tmp_path / "positions.json"

            order = pm.get_order("order-001")

            assert order is not None
            assert order["id"] == "order-001"
            assert order["symbol"] == "SPY"


class TestCacheManagement:
    """Test cache management methods."""

    def test_refresh_cache(self, mock_broker_with_positions, tmp_path):
        """Test refresh_cache forces API call."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            # Initial fetch
            pm.get_positions()
            call_count_before = mock_broker_with_positions.get_all_positions.call_count

            # Refresh
            pm.refresh_cache()
            call_count_after = mock_broker_with_positions.get_all_positions.call_count

            assert call_count_after == call_count_before + 1

    def test_clear_cache(self, mock_broker_with_positions, tmp_path):
        """Test clear_cache clears session cache."""
        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_with_positions)
            pm.state_file = tmp_path / "positions.json"

            # Populate cache
            pm.get_positions()
            assert pm._session_cache != {}
            assert pm._cache_timestamp is not None

            # Clear cache
            pm.clear_cache()

            assert pm._session_cache == {}
            assert pm._cache_timestamp is None


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_short_position_detected(self, mock_broker_client, tmp_path):
        """Test that short positions are correctly identified."""
        from tests.conftest import MockPosition

        mock_broker_client.get_all_positions.return_value = [
            MockPosition(
                symbol="TSLA",
                qty="-10",  # Short position
                avg_cost="250.00",
                market_value="-2400.00",
                unrealized_pl="100.00",  # Profit on short
                unrealized_plpc="0.04",
                cost_basis="-2500.00",
            )
        ]

        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_client)
            pm.state_file = tmp_path / "positions.json"

            positions = pm.get_positions()

            assert positions["TSLA"]["side"] == "short"
            assert positions["TSLA"]["qty"] == -10.0

    def test_zero_quantity_position(self, mock_broker_client, tmp_path):
        """Test handling of zero quantity (closed) positions."""
        from tests.conftest import MockPosition

        mock_broker_client.get_all_positions.return_value = [
            MockPosition(
                symbol="AMD",
                qty="0",
                avg_cost="0.00",
                market_value="0.00",
                unrealized_pl="0.00",
                unrealized_plpc="0.00",
                cost_basis="0.00",
            )
        ]

        with patch("builtins.open", MagicMock()):
            pm = PositionManager(mock_broker_client)
            pm.state_file = tmp_path / "positions.json"

            # Should not crash on division by zero
            positions = pm.get_positions()
            assert positions["AMD"]["current_price"] == 0

    def test_corrupted_backup_file(self, mock_broker_api_error, tmp_path):
        """Test handling of corrupted backup file."""
        backup_file = tmp_path / "positions.json"
        with open(backup_file, "w") as f:
            f.write("not valid json {{{")

        pm = PositionManager(mock_broker_api_error)
        pm.state_file = backup_file

        # Should return empty dict, not crash
        positions = pm.get_positions()
        assert positions == {}

    def test_missing_backup_file(self, mock_broker_api_error, tmp_path):
        """Test handling of missing backup file."""
        pm = PositionManager(mock_broker_api_error)
        pm.state_file = tmp_path / "nonexistent.json"

        # Should return empty dict, not crash
        positions = pm.get_positions()
        assert positions == {}


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
