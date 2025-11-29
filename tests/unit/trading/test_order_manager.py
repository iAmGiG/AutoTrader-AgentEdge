#!/usr/bin/env python3
"""
Unit tests for OrderManager.

Tests order placement, fill monitoring, cancellation, and state management.
Issue #408: Unit Testing and CLI Testing (Pre-Live Trading Validation)

Priority 1 Component - Money-Handling
Target Coverage: 80%+
"""

import os
import sys
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

# Mock alpaca imports before importing OrderManager
sys.modules["alpaca"] = MagicMock()
sys.modules["alpaca.trading"] = MagicMock()
sys.modules["alpaca.trading.requests"] = MagicMock()

from src.trading.order_manager import OrderManager

# =============================================================================
# Mock Order Response
# =============================================================================


def create_mock_order_response(
    order_id="order-123",
    symbol="SPY",
    qty="10",
    side="buy",
    order_type="market",
    status="accepted",
    submitted_at=None,
    filled_at=None,
    filled_qty=None,
    filled_avg_price=None,
    limit_price=None,
    stop_price=None,
    order_class=None,
    legs=None,
):
    """Create a mock Alpaca order response object."""
    mock_order = MagicMock()
    mock_order.id = order_id
    mock_order.symbol = symbol
    mock_order.qty = qty
    mock_order.side = MagicMock()
    mock_order.side.value = side
    mock_order.order_type = MagicMock()
    mock_order.order_type.value = order_type
    mock_order.status = MagicMock()
    mock_order.status.value = status
    mock_order.submitted_at = submitted_at or datetime.now()
    mock_order.filled_at = filled_at
    mock_order.filled_qty = filled_qty
    mock_order.filled_avg_price = filled_avg_price
    mock_order.limit_price = limit_price
    mock_order.stop_price = stop_price
    mock_order.time_in_force = MagicMock()
    mock_order.time_in_force.value = "day"
    mock_order.order_class = MagicMock()
    mock_order.order_class.value = order_class or "simple"
    mock_order.legs = legs
    return mock_order


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_broker():
    """Create a mock broker client."""
    broker = MagicMock()
    broker.submit_order.return_value = create_mock_order_response()
    broker.cancel_order_by_id.return_value = None
    broker.cancel_orders.return_value = []
    return broker


@pytest.fixture
def mock_position_manager():
    """Create a mock position manager."""
    pm = MagicMock()
    pm.get_order.return_value = None
    pm.get_position.return_value = None
    pm.refresh_cache.return_value = None
    return pm


@pytest.fixture
def order_manager(mock_broker, mock_position_manager):
    """Create an OrderManager instance with mocks."""
    return OrderManager(mock_broker, mock_position_manager)


# =============================================================================
# Initialization Tests
# =============================================================================


class TestOrderManagerInit:
    """Test OrderManager initialization."""

    def test_init_with_dependencies(self, mock_broker, mock_position_manager):
        """Test basic initialization."""
        om = OrderManager(mock_broker, mock_position_manager)

        assert om.broker == mock_broker
        assert om.position_manager == mock_position_manager
        assert om.pending_orders == {}
        assert om.fill_check_interval == 30

    def test_init_default_values(self, order_manager):
        """Test default initialization values."""
        assert order_manager.last_fill_check == 0
        assert order_manager.__class__.__name__ == "OrderManager"


# =============================================================================
# Market Order Tests
# =============================================================================


class TestPlaceMarketOrder:
    """Test place_market_order() method."""

    def test_place_buy_market_order(self, order_manager, mock_broker):
        """Test placing a buy market order."""
        mock_broker.submit_order.return_value = create_mock_order_response(
            order_id="mkt-001",
            symbol="SPY",
            qty="10",
            side="buy",
            order_type="market",
            status="accepted",
        )

        result = order_manager.place_market_order("SPY", 10, "buy")

        assert result["id"] == "mkt-001"
        assert result["symbol"] == "SPY"
        assert result["qty"] == 10.0
        assert result["side"] == "buy"
        assert result["order_type"] == "market"
        assert "error" not in result

    def test_place_sell_market_order(self, order_manager, mock_broker):
        """Test placing a sell market order."""
        mock_broker.submit_order.return_value = create_mock_order_response(
            order_id="mkt-002",
            symbol="AAPL",
            qty="5",
            side="sell",
            order_type="market",
            status="accepted",
        )

        result = order_manager.place_market_order("AAPL", 5, "sell")

        assert result["id"] == "mkt-002"
        assert result["side"] == "sell"
        assert "error" not in result

    def test_market_order_added_to_pending(self, order_manager, mock_broker):
        """Test that market orders are added to pending orders."""
        mock_broker.submit_order.return_value = create_mock_order_response(order_id="mkt-003")

        order_manager.place_market_order("SPY", 10, "buy")

        assert "mkt-003" in order_manager.pending_orders

    def test_market_order_api_error(self, order_manager, mock_broker):
        """Test handling of API errors during order placement."""
        mock_broker.submit_order.side_effect = Exception("API connection failed")

        result = order_manager.place_market_order("SPY", 10, "buy")

        assert "error" in result
        assert "API connection failed" in result["error"]


# =============================================================================
# Limit Order Tests
# =============================================================================


class TestPlaceLimitOrder:
    """Test place_limit_order() method."""

    def test_place_buy_limit_order(self, order_manager, mock_broker):
        """Test placing a buy limit order."""
        mock_response = create_mock_order_response(
            order_id="lmt-001",
            symbol="SPY",
            qty="10",
            side="buy",
            order_type="limit",
            status="new",
        )
        mock_response.limit_price = "595.00"
        mock_broker.submit_order.return_value = mock_response

        result = order_manager.place_limit_order("SPY", 10, "buy", 595.00)

        assert result["id"] == "lmt-001"
        assert result["order_type"] == "limit"
        assert result["limit_price"] == 595.0
        assert "error" not in result

    def test_place_sell_limit_order(self, order_manager, mock_broker):
        """Test placing a sell limit order."""
        mock_response = create_mock_order_response(
            order_id="lmt-002",
            symbol="AAPL",
            qty="20",
            side="sell",
            order_type="limit",
            status="new",
        )
        mock_response.limit_price = "185.50"
        mock_broker.submit_order.return_value = mock_response

        result = order_manager.place_limit_order("AAPL", 20, "sell", 185.50)

        assert result["id"] == "lmt-002"
        assert result["side"] == "sell"
        assert result["limit_price"] == 185.5

    def test_limit_order_added_to_pending(self, order_manager, mock_broker):
        """Test that limit orders are added to pending orders."""
        mock_response = create_mock_order_response(order_id="lmt-003")
        mock_response.limit_price = "100.00"
        mock_broker.submit_order.return_value = mock_response

        order_manager.place_limit_order("MSFT", 5, "buy", 100.00)

        assert "lmt-003" in order_manager.pending_orders

    def test_limit_order_api_error(self, order_manager, mock_broker):
        """Test handling of API errors during limit order placement."""
        mock_broker.submit_order.side_effect = Exception("Insufficient funds")

        result = order_manager.place_limit_order("SPY", 10, "buy", 600.00)

        assert "error" in result


# =============================================================================
# Bracket Order Tests
# =============================================================================


class TestPlaceBracketOrder:
    """Test place_bracket_order() method."""

    def test_place_bracket_order_success(self, order_manager, mock_broker):
        """Test placing a bracket order with stop loss and take profit."""
        mock_response = create_mock_order_response(
            order_id="brk-001",
            symbol="SPY",
            qty="10",
            side="buy",
            order_type="market",
            status="accepted",
            order_class="bracket",
            legs=[MagicMock(id="leg-001"), MagicMock(id="leg-002")],
        )
        mock_broker.submit_order.return_value = mock_response

        result = order_manager.place_bracket_order(
            symbol="SPY",
            qty=10,
            stop_price=580.00,
            target_price=620.00,
        )

        assert result["entry_id"] == "brk-001"
        assert result["stop_price"] == 580.00
        assert result["target_price"] == 620.00
        assert result["status"] == "submitted"
        assert len(result["legs"]) == 2

    def test_bracket_order_added_to_pending(self, order_manager, mock_broker):
        """Test that bracket orders are added to pending orders."""
        mock_response = create_mock_order_response(order_id="brk-002", legs=[])
        mock_broker.submit_order.return_value = mock_response

        order_manager.place_bracket_order("SPY", 10, 580.00, 620.00)

        assert "brk-002" in order_manager.pending_orders

    def test_bracket_order_api_error(self, order_manager, mock_broker):
        """Test handling of API errors during bracket order placement."""
        mock_broker.submit_order.side_effect = Exception("Invalid bracket order")

        result = order_manager.place_bracket_order("SPY", 10, 580.00, 620.00)

        assert "error" in result


# =============================================================================
# Order Cancellation Tests
# =============================================================================


class TestCancelOrder:
    """Test order cancellation methods."""

    def test_cancel_order_success(self, order_manager, mock_broker):
        """Test successful order cancellation."""
        order_manager.pending_orders["order-001"] = {"id": "order-001"}

        result = order_manager.cancel_order("order-001")

        assert result is True
        assert "order-001" not in order_manager.pending_orders
        mock_broker.cancel_order_by_id.assert_called_once_with("order-001")

    def test_cancel_order_api_error(self, order_manager, mock_broker):
        """Test order cancellation with API error."""
        mock_broker.cancel_order_by_id.side_effect = Exception("Order not found")
        order_manager.pending_orders["order-002"] = {"id": "order-002"}

        result = order_manager.cancel_order("order-002")

        assert result is False

    def test_cancel_all_orders(self, order_manager, mock_broker):
        """Test cancelling all orders."""
        order_manager.pending_orders = {
            "order-001": {"id": "order-001"},
            "order-002": {"id": "order-002"},
        }
        mock_broker.cancel_orders.return_value = [MagicMock(), MagicMock()]

        count = order_manager.cancel_all_orders()

        assert count == 2
        assert order_manager.pending_orders == {}

    def test_cancel_all_orders_api_error(self, order_manager, mock_broker):
        """Test cancel all orders with API error."""
        mock_broker.cancel_orders.side_effect = Exception("API error")

        count = order_manager.cancel_all_orders()

        assert count == 0


# =============================================================================
# Fill Monitoring Tests
# =============================================================================


class TestMonitorOrderFills:
    """Test monitor_order_fills() method."""

    def test_monitor_respects_rate_limit(self, order_manager):
        """Test that fill monitoring respects rate limit."""
        order_manager.last_fill_check = time.time()

        result = order_manager.monitor_order_fills()

        assert result == []

    def test_monitor_detects_filled_order(self, order_manager, mock_position_manager):
        """Test detection of filled orders."""
        order_manager.pending_orders["order-001"] = {
            "id": "order-001",
            "symbol": "SPY",
        }
        order_manager.last_fill_check = 0

        mock_position_manager.get_order.return_value = {
            "id": "order-001",
            "symbol": "SPY",
            "status": "filled",
            "side": "buy",
            "filled_qty": 10,
            "filled_avg_price": 595.50,
            "filled_at": "2025-01-15T10:30:00",
        }

        filled = order_manager.monitor_order_fills()

        assert len(filled) == 1
        assert filled[0]["id"] == "order-001"
        assert filled[0]["filled_price"] == 595.50
        assert "order-001" not in order_manager.pending_orders

    def test_monitor_removes_cancelled_orders(self, order_manager, mock_position_manager):
        """Test that cancelled orders are removed from pending."""
        order_manager.pending_orders["order-001"] = {"id": "order-001"}
        order_manager.last_fill_check = 0

        mock_position_manager.get_order.return_value = {
            "id": "order-001",
            "status": "cancelled",
        }

        filled = order_manager.monitor_order_fills()

        assert len(filled) == 0
        assert "order-001" not in order_manager.pending_orders

    def test_monitor_removes_expired_orders(self, order_manager, mock_position_manager):
        """Test that expired orders are removed from pending."""
        order_manager.pending_orders["order-001"] = {"id": "order-001"}
        order_manager.last_fill_check = 0

        mock_position_manager.get_order.return_value = {
            "id": "order-001",
            "status": "expired",
        }

        filled = order_manager.monitor_order_fills()

        assert len(filled) == 0
        assert "order-001" not in order_manager.pending_orders

    def test_monitor_updates_pending_status(self, order_manager, mock_position_manager):
        """Test that pending orders have their status updated."""
        order_manager.pending_orders["order-001"] = {
            "id": "order-001",
            "status": "new",
        }
        order_manager.last_fill_check = 0

        mock_position_manager.get_order.return_value = {
            "id": "order-001",
            "status": "partially_filled",
            "filled_qty": 5,
        }

        order_manager.monitor_order_fills()

        assert order_manager.pending_orders["order-001"]["status"] == "partially_filled"
        assert order_manager.pending_orders["order-001"]["filled_qty"] == 5


# =============================================================================
# Replace Stop Order Tests
# =============================================================================


class TestReplaceStopOrder:
    """Test replace_stop_order() method."""

    def test_replace_stop_order_success(self, order_manager, mock_broker, mock_position_manager):
        """Test successful stop order replacement."""
        # Setup existing order
        mock_position_manager.get_order.return_value = {
            "id": "stop-001",
            "symbol": "SPY",
            "qty": 10,
        }

        # Mock new order response
        new_order = create_mock_order_response(
            order_id="stop-002",
            symbol="SPY",
            qty="10",
            order_type="stop",
            status="new",
        )
        new_order.stop_price = "590.00"
        mock_broker.submit_order.return_value = new_order

        with patch("time.sleep"):  # Speed up test
            result = order_manager.replace_stop_order("stop-001", 590.00)

        assert result["id"] == "stop-002"
        assert result["replaced_order_id"] == "stop-001"
        assert "stop-002" in order_manager.pending_orders

    def test_replace_stop_order_with_provided_params(
        self, order_manager, mock_broker, mock_position_manager
    ):
        """Test stop order replacement with provided symbol and qty."""
        new_order = create_mock_order_response(
            order_id="stop-003",
            symbol="AAPL",
            qty="20",
            order_type="stop",
        )
        new_order.stop_price = "175.00"
        mock_broker.submit_order.return_value = new_order

        with patch("time.sleep"):
            result = order_manager.replace_stop_order("stop-001", 175.00, symbol="AAPL", qty=20)

        assert result["id"] == "stop-003"
        assert "error" not in result

    def test_replace_stop_order_missing_params(self, order_manager, mock_position_manager):
        """Test error when order not found and params not provided."""
        mock_position_manager.get_order.return_value = None

        result = order_manager.replace_stop_order("stop-001", 590.00)

        assert "error" in result

    def test_replace_stop_order_cancel_fails(
        self, order_manager, mock_broker, mock_position_manager
    ):
        """Test error handling when cancel fails."""
        mock_position_manager.get_order.return_value = {
            "id": "stop-001",
            "symbol": "SPY",
            "qty": 10,
        }
        mock_broker.cancel_order_by_id.side_effect = Exception("Cancel failed")

        result = order_manager.replace_stop_order("stop-001", 590.00)

        assert "error" in result


# =============================================================================
# Pending Orders and Status Tests
# =============================================================================


class TestPendingOrdersAndStatus:
    """Test pending order tracking and status methods."""

    def test_get_pending_orders_returns_copy(self, order_manager):
        """Test that get_pending_orders returns a copy."""
        order_manager.pending_orders["order-001"] = {"id": "order-001"}

        pending = order_manager.get_pending_orders()

        # Modify the returned dict
        pending["order-002"] = {"id": "order-002"}

        # Original should be unchanged
        assert "order-002" not in order_manager.pending_orders

    def test_get_order_status_delegates_to_position_manager(
        self, order_manager, mock_position_manager
    ):
        """Test that get_order_status uses position manager."""
        mock_position_manager.get_order.return_value = {
            "id": "order-001",
            "status": "filled",
        }

        result = order_manager.get_order_status("order-001")

        assert result["status"] == "filled"
        mock_position_manager.get_order.assert_called_once_with("order-001")


# =============================================================================
# Fill Notification Handler Tests
# =============================================================================


class TestHandleFillNotification:
    """Test handle_fill_notification() method."""

    def test_handle_buy_fill(self, order_manager, mock_position_manager):
        """Test handling a buy fill notification."""
        filled_order = {
            "id": "order-001",
            "symbol": "SPY",
            "side": "buy",
            "qty": 10,
            "filled_price": 595.50,
            "filled_at": "2025-01-15T10:30:00",
        }

        mock_position_manager.get_position.return_value = {
            "symbol": "SPY",
            "qty": 10,
            "market_value": 5955.00,
        }

        result = order_manager.handle_fill_notification(filled_order)

        assert result["action"] == "position_opened"
        assert result["symbol"] == "SPY"
        assert result["fill_price"] == 595.50
        mock_position_manager.refresh_cache.assert_called_once()

    def test_handle_sell_fill(self, order_manager, mock_position_manager):
        """Test handling a sell fill notification."""
        filled_order = {
            "id": "order-002",
            "symbol": "AAPL",
            "side": "sell",
            "qty": 20,
            "filled_price": 185.00,
            "filled_at": "2025-01-15T14:00:00",
        }

        mock_position_manager.get_position.return_value = None  # Position closed

        result = order_manager.handle_fill_notification(filled_order)

        assert result["action"] == "position_closed"
        assert result["symbol"] == "AAPL"


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
