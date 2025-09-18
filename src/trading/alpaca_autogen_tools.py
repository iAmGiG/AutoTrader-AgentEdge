"""
AutoGen tool wrappers for Alpaca Trading Client.

This module provides AutoGen-compatible tool wrappers for the Alpaca trading system,
enabling agents to access account information and place orders with unified live/paper support.
"""

from typing import Dict, List, Any, Optional
import logging

from .alpaca_trading_client import AlpacaAccountMonitor, AlpacaOrderManager

logger = logging.getLogger(__name__)


class AlpacaAccountTool:
    """
    AutoGen tool wrapper for read-only account operations.

    Provides safe, read-only access to account information, positions,
    and order history for AutoGen agents.
    """

    def __init__(self, mode: str = "paper"):
        """
        Initialize account tool.

        Args:
            mode: "paper" or "live" trading mode
        """
        self.monitor = AlpacaAccountMonitor(mode=mode)
        self.name = "alpaca_account"
        self.description = (
            f"Access account information, positions, and orders from Alpaca {mode} trading account. "
            "Read-only operations only - no order placement capability."
        )

    def get_account_status(self) -> Dict[str, Any]:
        """
        Get comprehensive account status.

        Returns:
            Dict with buying power, cash, portfolio value, etc.
        """
        try:
            return self.monitor.get_account_status()
        except Exception as e:
            logger.error(f"Failed to get account status: {e}")
            return {"error": str(e), "status": "failed"}

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all current positions.

        Returns:
            List of position dictionaries with symbol, quantity, P&L, etc.
        """
        try:
            return self.monitor.get_positions()
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return [{"error": str(e), "status": "failed"}]

    def get_orders(self, status: str = "open", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders filtered by status.

        Args:
            status: Order status ('open', 'closed', 'all')
            limit: Maximum number of orders to return

        Returns:
            List of order dictionaries
        """
        try:
            return self.monitor.get_orders(status=status, limit=limit)
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return [{"error": str(e), "status": "failed"}]

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive portfolio overview.

        Returns:
            Dict with account, positions, metrics, and open orders
        """
        try:
            return self.monitor.get_portfolio_summary()
        except Exception as e:
            logger.error(f"Failed to get portfolio summary: {e}")
            return {"error": str(e), "status": "failed"}


class AlpacaOrderTool:
    """
    AutoGen tool wrapper for order management operations.

    Provides order placement, modification, and cancellation capabilities
    for AutoGen agents with enhanced safety rails.
    """

    def __init__(self, mode: str = "paper", risk_limits: Optional[Dict] = None):
        """
        Initialize order tool.

        Args:
            mode: "paper" or "live" trading mode
            risk_limits: Optional risk management limits
        """
        self.manager = AlpacaOrderManager(mode=mode, risk_limits=risk_limits)
        self.name = "alpaca_orders"
        self.description = (
            f"Complete order management for Alpaca {mode} trading account. "
            f"Supports market, limit, stop, trailing stop, and bracket orders. "
            f"Includes safety rails and validation. Mode: {mode.upper()}"
        )

    def place_market_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """
        Place market order.

        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'SPY')
            qty: Number of shares
            side: "buy" or "sell"
            time_in_force: "day", "gtc", "ioc", "fok"

        Returns:
            Dict with order result or error information
        """
        try:
            return self.manager.place_market_order(symbol, qty, side, time_in_force)
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {"symbol": symbol, "qty": qty, "side": side}
            }

    def place_limit_order_gtc(
        self,
        symbol: str,
        qty: int,
        side: str,
        limit_price: float
    ) -> Dict[str, Any]:
        """
        Place GTC limit order.

        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'SPY')
            qty: Number of shares
            side: "buy" or "sell"
            limit_price: Limit price per share

        Returns:
            Dict with order result or error information
        """
        try:
            return self.manager.place_limit_order_gtc(symbol, qty, side, limit_price)
        except Exception as e:
            logger.error(f"Failed to place limit order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "limit_price": limit_price
                }
            }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an existing order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Dict with cancellation result
        """
        try:
            return self.manager.cancel_order(order_id)
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {"status": "error", "message": str(e), "order_id": order_id}

    def close_position(
        self,
        symbol: str,
        qty: Optional[int] = None,
        percentage: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Close position in a symbol.

        Args:
            symbol: Symbol to close
            qty: Specific quantity to close (optional)
            percentage: Percentage of position to close (0-1, optional)

        Returns:
            Dict with closing order result
        """
        try:
            return self.manager.close_position(symbol, qty, percentage)
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return {"status": "error", "message": str(e), "symbol": symbol}

    def place_stop_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        stop_price: float,
        time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """
        Place stop order.

        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'SOXL')
            qty: Number of shares
            side: "buy" or "sell"
            stop_price: Stop price trigger
            time_in_force: "day", "gtc", "ioc", "fok"

        Returns:
            Dict with order result or error information
        """
        try:
            return self.manager.place_stop_order(symbol, qty, side, stop_price, time_in_force)
        except Exception as e:
            logger.error(f"Failed to place stop order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {"symbol": symbol, "qty": qty, "side": side, "stop_price": stop_price}
            }

    def place_trailing_stop_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        trail_percent: Optional[float] = None,
        trail_price: Optional[float] = None,
        time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """
        Place trailing stop order.

        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'SOXL')
            qty: Number of shares
            side: "buy" or "sell"
            trail_percent: Trailing percentage (0.1-1.0, e.g., 0.1 for 10%)
            trail_price: Trailing price amount (alternative to percentage)
            time_in_force: "day", "gtc"

        Returns:
            Dict with order result or error information
        """
        try:
            return self.manager.place_trailing_stop_order(
                symbol, qty, side, trail_percent, trail_price, time_in_force
            )
        except Exception as e:
            logger.error(f"Failed to place trailing stop order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {
                    "symbol": symbol, "qty": qty, "side": side,
                    "trail_percent": trail_percent, "trail_price": trail_price
                }
            }

    def place_bracket_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        entry_limit_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """
        Place bracket order (entry + take profit + stop loss).

        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'SOXL')
            qty: Number of shares
            side: "buy" or "sell"
            entry_limit_price: Entry limit price (None for market entry)
            take_profit_price: Take profit limit price
            stop_loss_price: Stop loss price
            time_in_force: "day", "gtc"

        Returns:
            Dict with order result or error information
        """
        try:
            return self.manager.place_bracket_order(
                symbol, qty, side, entry_limit_price,
                take_profit_price, stop_loss_price, time_in_force
            )
        except Exception as e:
            logger.error(f"Failed to place bracket order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {
                    "symbol": symbol, "qty": qty, "side": side,
                    "entry_limit_price": entry_limit_price,
                    "take_profit_price": take_profit_price,
                    "stop_loss_price": stop_loss_price
                }
            }

    # Inherit all read-only methods from account tool
    def get_account_status(self) -> Dict[str, Any]:
        """Get account status (inherited from account monitor)."""
        return self.manager.get_account_status()

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get positions (inherited from account monitor)."""
        return self.manager.get_positions()

    def get_orders(self, status: str = "open", limit: int = 50) -> List[Dict[str, Any]]:
        """Get orders (inherited from account monitor)."""
        return self.manager.get_orders(status=status, limit=limit)


class AlpacaUnifiedTool:
    """
    Unified AutoGen tool combining both account monitoring and order management.

    This is the recommended tool for most AutoGen agents, providing complete
    trading functionality with mode awareness and safety rails.
    """

    def __init__(self, mode: str = "paper", risk_limits: Optional[Dict] = None):
        """
        Initialize unified trading tool.

        Args:
            mode: "paper" or "live" trading mode
            risk_limits: Optional risk management limits
        """
        self.mode = mode
        self.order_manager = AlpacaOrderManager(mode=mode, risk_limits=risk_limits)
        self.name = f"alpaca_trading_{mode}"
        self.description = (
            f"Complete Alpaca trading tool for {mode} trading. "
            "Includes account monitoring, position tracking, and advanced order management "
            "(market, limit, stop, trailing stop, bracket orders) with safety rails, "
            "market hours checking, and comprehensive validation."
        )

    # Account Operations
    def get_account_status(self) -> Dict[str, Any]:
        """Get comprehensive account status."""
        return self.order_manager.get_account_status()

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all current positions."""
        return self.order_manager.get_positions()

    def get_orders(self, status: str = "open", limit: int = 50) -> List[Dict[str, Any]]:
        """Get orders by status."""
        return self.order_manager.get_orders(status=status, limit=limit)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio overview."""
        return self.order_manager.get_portfolio_summary()

    # Order Operations
    def place_market_order(
        self, symbol: str, qty: int, side: str, time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """Place market order with validation."""
        return self.order_manager.place_market_order(symbol, qty, side, time_in_force)

    def place_limit_order_gtc(
        self, symbol: str, qty: int, side: str, limit_price: float
    ) -> Dict[str, Any]:
        """Place GTC limit order with validation."""
        return self.order_manager.place_limit_order_gtc(symbol, qty, side, limit_price)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel existing order."""
        return self.order_manager.cancel_order(order_id)

    def close_position(
        self, symbol: str, qty: Optional[int] = None, percentage: Optional[float] = None
    ) -> Dict[str, Any]:
        """Close position with flexible quantity options."""
        return self.order_manager.close_position(symbol, qty, percentage)

    def place_stop_order(
        self, symbol: str, qty: int, side: str, stop_price: float, time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """Place stop order with validation."""
        return self.order_manager.place_stop_order(symbol, qty, side, stop_price, time_in_force)

    def place_trailing_stop_order(
        self, symbol: str, qty: int, side: str, trail_percent: Optional[float] = None,
        trail_price: Optional[float] = None, time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """Place trailing stop order with validation."""
        return self.order_manager.place_trailing_stop_order(
            symbol, qty, side, trail_percent, trail_price, time_in_force
        )

    def place_bracket_order(
        self, symbol: str, qty: int, side: str, entry_limit_price: Optional[float] = None,
        take_profit_price: Optional[float] = None, stop_loss_price: Optional[float] = None,
        time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """Place bracket order with entry, take profit, and stop loss."""
        return self.order_manager.place_bracket_order(
            symbol, qty, side, entry_limit_price, take_profit_price, stop_loss_price, time_in_force
        )

    # Utility Methods
    def get_trading_mode(self) -> str:
        """Get current trading mode."""
        return self.mode

    def validate_order_before_placement(
        self, symbol: str, qty: int, side: str, price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Validate order without placing it.

        Args:
            symbol: Stock symbol
            qty: Order quantity
            side: "buy" or "sell"
            price: Optional limit price

        Returns:
            Dict with validation result
        """
        try:
            self.order_manager._validate_order(symbol, qty, side, price)
            return {
                "status": "valid",
                "message": "Order passes all validation checks",
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "price": price
                }
            }
        except Exception as e:
            return {
                "status": "invalid",
                "message": str(e),
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "price": price
                }
            }

    def check_market_hours(self, extended_hours: bool = False) -> Dict[str, Any]:
        """
        Check if market is currently open.

        Args:
            extended_hours: Include pre-market and after-hours

        Returns:
            Dict with market status information
        """
        return self.order_manager._is_market_hours(extended_hours)


# Factory functions for easy tool creation
def create_alpaca_account_tool(mode: str = "paper") -> AlpacaAccountTool:
    """
    Create read-only account monitoring tool for AutoGen agents.

    Args:
        mode: "paper" or "live" trading mode

    Returns:
        AlpacaAccountTool instance
    """
    return AlpacaAccountTool(mode=mode)


def create_alpaca_order_tool(
    mode: str = "paper",
    risk_limits: Optional[Dict] = None
) -> AlpacaOrderTool:
    """
    Create order management tool for AutoGen agents.

    Args:
        mode: "paper" or "live" trading mode
        risk_limits: Optional risk management limits

    Returns:
        AlpacaOrderTool instance
    """
    return AlpacaOrderTool(mode=mode, risk_limits=risk_limits)


def create_alpaca_unified_tool(
    mode: str = "paper",
    risk_limits: Optional[Dict] = None
) -> AlpacaUnifiedTool:
    """
    Create unified trading tool for AutoGen agents.

    This is the recommended approach for most agents.

    Args:
        mode: "paper" or "live" trading mode
        risk_limits: Optional risk management limits

    Returns:
        AlpacaUnifiedTool instance
    """
    return AlpacaUnifiedTool(mode=mode, risk_limits=risk_limits)


# Usage examples for agent integration
if __name__ == "__main__":
    # Example usage for AutoGen agents

    # Read-only account monitoring
    account_tool = create_alpaca_account_tool(mode="paper")
    print("Account Status:", account_tool.get_account_status())

    # Full order management
    trading_tool = create_alpaca_unified_tool(mode="paper")
    print("Portfolio Summary:", trading_tool.get_portfolio_summary())

    # Validate order before placing
    validation = trading_tool.validate_order_before_placement("SPY", 1, "buy", 400.0)
    print("Order Validation:", validation)
