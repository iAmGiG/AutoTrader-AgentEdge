"""
Alpaca Trading Client with unified live/paper functionality and safety rails.

This implementation provides a unified interface for both paper and live trading
with explicit safety confirmations for live trades and comprehensive read/write operations.

Phase 1: Read-only operations (account status, positions, orders)
Phase 2: Write operations (order placement, modification, cancellation)
"""

import logging
from datetime import time as dt_time
from datetime import timezone
from typing import Any, Dict, List, Optional

import pytz

from src.utils.date_utils import get_datetime_now, get_default_timezone

try:
    from alpaca.common.exceptions import APIError
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import (
        OrderClass,
        OrderSide,
        OrderStatus,
        OrderType,
        QueryOrderStatus,
        TimeInForce,
    )
    from alpaca.trading.requests import (
        ClosePositionRequest,
        GetOrdersRequest,
        LimitOrderRequest,
        MarketOrderRequest,
        ReplaceOrderRequest,
        StopLimitOrderRequest,
        StopLossRequest,
        StopOrderRequest,
        TakeProfitRequest,
        TrailingStopOrderRequest,
    )

    ALPACA_TRADING_AVAILABLE = True
except ImportError:
    APIError = None
    TradingClient = None
    GetOrdersRequest = None
    MarketOrderRequest = None
    LimitOrderRequest = None
    StopOrderRequest = None
    StopLimitOrderRequest = None
    TrailingStopOrderRequest = None
    ClosePositionRequest = None
    TakeProfitRequest = None
    StopLossRequest = None
    ReplaceOrderRequest = None
    OrderSide = None
    OrderStatus = None
    OrderType = None
    TimeInForce = None
    QueryOrderStatus = None
    OrderClass = None
    ALPACA_TRADING_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(
        "alpaca-py SDK not installed. Alpaca trading client will be unavailable. "
        "Install with: pip install alpaca-py"
    )

from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class AlpacaTradingClient:
    """
    Unified trading client that handles both paper and live trading.

    Features:
    - Explicit mode selection (paper/live)
    - Safety confirmations for live trades
    - Unified API for both modes
    - Comprehensive error handling
    - Singleton pattern per mode (prevents duplicate initialization messages)
    """

    # Class-level singleton instances (one per mode)
    _instances = {}

    def __new__(cls, mode: str = "paper", require_confirmation: bool = True):
        """
        Singleton pattern - return existing instance for this mode if available.

        Args:
            mode: "paper" or "live"
            require_confirmation: Extra confirmation for live trades

        Returns:
            Singleton instance for this mode
        """
        # Create unique key for this mode
        key = mode

        if key not in cls._instances:
            # Create new instance
            instance = super(AlpacaTradingClient, cls).__new__(cls)
            cls._instances[key] = instance
            # Mark that this instance needs initialization
            instance._initialized = False

        return cls._instances[key]

    def __init__(self, mode: str = "paper", require_confirmation: bool = True):
        """
        Initialize trading client.

        Args:
            mode: "paper" or "live" - explicitly required
            require_confirmation: Extra confirmation for live trades

        Raises:
            ValueError: If mode is not "paper" or "live"
        """
        # Skip initialization if already done (singleton pattern)
        if getattr(self, "_initialized", False):
            return

        if not ALPACA_TRADING_AVAILABLE:
            raise ImportError(
                "alpaca-py SDK is required for AlpacaTradingClient. "
                "Install with: pip install alpaca-py"
            )

        if mode not in ["paper", "live"]:
            raise ValueError("Mode must be explicitly 'paper' or 'live'")

        self.mode = mode
        self.require_confirmation = require_confirmation and (mode == "live")

        # Use different credentials based on mode
        config = ConfigLoader()
        if mode == "paper":
            api_key = config.get("ALPACA_PAPER_API_KEY")
            secret = config.get("ALPACA_PAPER_SECRET")
            self.base_url = "https://paper-api.alpaca.markets"
        else:
            # For live trading - these keys would need to be added to config
            api_key = config.get("ALPACA_LIVE_API_KEY")
            secret = config.get("ALPACA_LIVE_SECRET")
            self.base_url = "https://api.alpaca.markets"

        if not api_key or not secret:
            raise ValueError(
                f"Alpaca {mode} API credentials required. Check config.json for "
                f"ALPACA_{mode.upper()}_API_KEY and ALPACA_{mode.upper()}_SECRET"
            )

        # Initialize the official SDK client
        self.trading_client = TradingClient(
            api_key=api_key, secret_key=secret, paper=(mode == "paper")
        )

        # Log the mode prominently for safety
        logger.warning(f"🔥 Alpaca client initialized in {mode.upper()} mode")
        if mode == "live":
            logger.warning("⚠️  LIVE TRADING MODE - Real money at risk!")

        # Mark as initialized
        self._initialized = True

    def _safety_check(self, action: str, details: Dict[str, Any]) -> bool:
        """
        Safety confirmation for live trading operations.

        Args:
            action: Description of the action being performed
            details: Dict with action details

        Returns:
            bool: True if confirmed, False if cancelled
        """
        if not self.require_confirmation:
            return True

        print(f"\n⚠️  LIVE TRADING ACTION: {action}")
        print(f"Mode: {self.mode.upper()}")
        print(f"Details: {details}")
        print("🚨 This will execute with real money!")

        response = input("Type 'CONFIRM' to proceed (any other input cancels): ")
        confirmed = response.strip().upper() == "CONFIRM"

        if confirmed:
            logger.warning(f"Live trading action CONFIRMED: {action}")
        else:
            logger.info(f"Live trading action CANCELLED: {action}")

        return confirmed


class AlpacaAccountMonitor:
    """
    Read-only account and position monitoring for both paper and live accounts.

    This class provides safe, read-only access to account information, positions,
    and order history without any ability to place or modify trades.
    """

    def __init__(self, mode: str = "paper"):
        """
        Initialize account monitor.

        Args:
            mode: "paper" or "live" trading mode
        """
        self.client = AlpacaTradingClient(mode=mode, require_confirmation=False)
        logger.info(f"Account monitor initialized for {mode} trading")

    def get_account_status(self) -> Dict[str, Any]:
        """
        Get comprehensive account overview.

        Returns:
            Dict with account status including buying power, cash, portfolio value, etc.

        Example:
            {
                'mode': 'paper',
                'buying_power': 100000.0,
                'cash': 100000.0,
                'portfolio_value': 100000.0,
                'pattern_day_trader': False,
                'trading_blocked': False,
                'account_number': '...'
            }
        """
        try:
            account = self.client.trading_client.get_account()

            return {
                "mode": self.client.mode,  # Always show which mode we're in
                "buying_power": float(account.buying_power) if account.buying_power else 0.0,
                "cash": float(account.cash) if account.cash else 0.0,
                "portfolio_value": (
                    float(account.portfolio_value) if account.portfolio_value else 0.0
                ),
                "pattern_day_trader": account.pattern_day_trader,
                "trading_blocked": account.trading_blocked,
                "account_blocked": account.account_blocked,
                "account_number": str(account.account_number),
                "status": str(account.status),
                "crypto_status": (
                    str(account.crypto_status) if hasattr(account, "crypto_status") else "N/A"
                ),
                "multiplier": str(account.multiplier) if hasattr(account, "multiplier") else "N/A",
                "equity": float(account.equity) if account.equity else 0.0,
                "last_equity": float(account.last_equity) if account.last_equity else 0.0,
            }

        except Exception as e:
            logger.error(f"Failed to get account status: {e}")
            raise

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all current positions.

        Returns:
            List of position dictionaries with symbol, quantity, P&L, etc.

        Example:
            [
                {
                    'symbol': 'AAPL',
                    'qty': 10.0,
                    'side': 'long',
                    'avg_entry_price': 150.00,
                    'market_value': 1520.00,
                    'unrealized_pl': 20.00,
                    'unrealized_plpc': 0.0131
                }
            ]
        """
        try:
            positions = self.client.trading_client.get_all_positions()

            return [
                {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty) if pos.qty else 0.0,
                    "side": str(pos.side),
                    "avg_entry_price": float(pos.avg_entry_price) if pos.avg_entry_price else 0.0,
                    "market_value": float(pos.market_value) if pos.market_value else 0.0,
                    "unrealized_pl": float(pos.unrealized_pl) if pos.unrealized_pl else 0.0,
                    "unrealized_plpc": float(pos.unrealized_plpc) if pos.unrealized_plpc else 0.0,
                    "cost_basis": float(pos.cost_basis) if pos.cost_basis else 0.0,
                    "change_today": float(pos.change_today) if pos.change_today else 0.0,
                }
                for pos in positions
            ]

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    def get_orders(
        self, status: str = "open", limit: int = 100, symbols: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders filtered by status.

        Args:
            status: Order status ('open', 'closed', 'all')
            limit: Maximum number of orders to return
            symbols: Optional list of symbols to filter by

        Returns:
            List of order dictionaries

        Example:
            [
                {
                    'id': 'order-123',
                    'symbol': 'AAPL',
                    'side': 'buy',
                    'qty': 10,
                    'status': 'filled',
                    'order_type': 'market',
                    'submitted_at': '2024-01-15T10:30:00Z',
                    'filled_at': '2024-01-15T10:30:05Z'
                }
            ]
        """
        try:
            # Create request with filters
            # IMPORTANT: nested=True includes bracket order legs (stop-loss, take-profit)
            if status == "all":
                request = GetOrdersRequest(limit=limit, symbols=symbols, nested=True)
            else:
                # Map status string to enum
                status_enum = None
                if status == "open":
                    status_enum = QueryOrderStatus.OPEN
                elif status == "closed":
                    status_enum = QueryOrderStatus.CLOSED

                request = GetOrdersRequest(
                    status=status_enum, limit=limit, symbols=symbols, nested=True
                )

            orders = self.client.trading_client.get_orders(filter=request)

            # First pass: collect all orders with their metadata
            result = []
            leg_ids = set()  # Track leg order IDs
            parent_map = {}  # Map leg IDs to parent order IDs

            for order in orders:
                order_dict = {
                    "id": str(order.id),
                    "symbol": order.symbol,
                    "side": order.side.value if hasattr(order.side, "value") else str(order.side),
                    "qty": float(order.qty) if order.qty else 0.0,
                    "filled_qty": float(order.filled_qty) if order.filled_qty else 0.0,
                    "status": (
                        order.status.value if hasattr(order.status, "value") else str(order.status)
                    ),
                    "order_type": (
                        order.order_type.value
                        if hasattr(order.order_type, "value")
                        else str(order.order_type)
                    ),
                    "time_in_force": (
                        order.time_in_force.value
                        if hasattr(order.time_in_force, "value")
                        else str(order.time_in_force)
                    ),
                    "limit_price": float(order.limit_price) if order.limit_price else None,
                    "stop_price": float(order.stop_price) if order.stop_price else None,
                    "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                    "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                    "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None,
                    "filled_avg_price": (
                        float(order.filled_avg_price) if order.filled_avg_price else None
                    ),
                    "order_class": (
                        order.order_class.value
                        if hasattr(order, "order_class") and hasattr(order.order_class, "value")
                        else (str(order.order_class) if hasattr(order, "order_class") else None)
                    ),
                    "legs": [],  # Will be populated in second pass
                }

                # Track leg IDs from bracket orders
                if hasattr(order, "legs") and order.legs:
                    # order.legs is a list of UUIDs for the leg orders
                    for leg_id in order.legs:
                        leg_id_str = str(leg_id)
                        leg_ids.add(leg_id_str)
                        parent_map[leg_id_str] = str(order.id)
                    logger.info(
                        f"Bracket order {order.id} has leg IDs: {[str(leg_id) for leg_id in order.legs]}"
                    )

                result.append(order_dict)

            # Second pass: match leg orders to their parents
            legs_found = 0
            for order_dict in result:
                order_id = order_dict["id"]

                # If this order is a leg of another order
                if order_id in leg_ids:
                    parent_id = parent_map.get(order_id)
                    if parent_id:
                        # Find parent and add this as a leg
                        for parent_order in result:
                            if parent_order["id"] == parent_id:
                                parent_order["legs"].append(order_dict)
                                legs_found += 1
                                logger.info(f"Matched leg {order_id} to parent {parent_id}")
                                break

            # Third pass: For bracket orders with empty legs, try fetching by ID to get held orders
            # Alpaca's get_orders() doesn't return "held" orders, but get_order_by_id() might
            for order_dict in result:
                if order_dict.get("order_class") == "OrderClass.BRACKET" and not order_dict.get(
                    "legs"
                ):
                    try:
                        # Fetch this specific order by ID to see if it includes held legs
                        full_order = self.client.trading_client.get_order_by_id(order_dict["id"])

                        if hasattr(full_order, "legs") and full_order.legs:
                            logger.info(
                                f"Found {len(full_order.legs)} legs for bracket order {order_dict['id']} via get_order_by_id"
                            )

                            # Fetch each leg order individually
                            for leg_id in full_order.legs:
                                try:
                                    leg_order = self.client.trading_client.get_order_by_id(
                                        str(leg_id)
                                    )
                                    leg_dict = {
                                        "id": str(leg_order.id),
                                        "symbol": leg_order.symbol,
                                        "side": str(leg_order.side),
                                        "qty": float(leg_order.qty) if leg_order.qty else 0.0,
                                        "status": str(leg_order.status),
                                        "order_type": str(leg_order.order_type),
                                        "time_in_force": str(leg_order.time_in_force),
                                        "limit_price": (
                                            float(leg_order.limit_price)
                                            if leg_order.limit_price
                                            else None
                                        ),
                                        "stop_price": (
                                            float(leg_order.stop_price)
                                            if leg_order.stop_price
                                            else None
                                        ),
                                    }
                                    order_dict["legs"].append(leg_dict)
                                    legs_found += 1
                                    logger.info(
                                        f"  Fetched leg {leg_order.id}: {leg_order.order_type} status={leg_order.status}"
                                    )
                                except Exception as e:
                                    # Don't spam users with leg fetch errors (common for bracket orders)
                                    logger.debug(f"  Failed to fetch leg {leg_id}: {e}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch bracket order {order_dict['id']} by ID: {e}"
                        )

            logger.info(f"Processed {len(result)} orders, found {legs_found} bracket legs")

            return result

        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            raise

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get combined portfolio summary with account and positions.

        Returns:
            Dict with comprehensive portfolio overview
        """
        try:
            account_status = self.get_account_status()
            positions = self.get_positions()
            open_orders = self.get_orders(status="open")

            # Calculate portfolio metrics
            total_unrealized_pl = float(sum(pos["unrealized_pl"] for pos in positions))
            total_positions_value = float(sum(pos["market_value"] for pos in positions))
            position_count = len(positions)
            open_order_count = len(open_orders)

            return {
                "account": account_status,
                "portfolio_metrics": {
                    "position_count": position_count,
                    "open_order_count": open_order_count,
                    "total_unrealized_pl": total_unrealized_pl,
                    "total_positions_value": total_positions_value,
                    "cash_utilization": (
                        (total_positions_value / account_status["portfolio_value"]) * 100
                        if account_status["portfolio_value"] > 0
                        else 0
                    ),
                },
                "positions": positions,
                "open_orders": open_orders,
            }

        except Exception as e:
            logger.error(f"Failed to get portfolio summary: {e}")
            raise


# Convenience functions for quick access
def get_account_status(mode: str = "paper") -> Dict[str, Any]:
    """
    Quick access to account status.

    Args:
        mode: "paper" or "live"

    Returns:
        Account status dictionary
    """
    monitor = AlpacaAccountMonitor(mode=mode)
    return monitor.get_account_status()


def get_positions(mode: str = "paper") -> List[Dict[str, Any]]:
    """
    Quick access to current positions.

    Args:
        mode: "paper" or "live"

    Returns:
        List of position dictionaries
    """
    monitor = AlpacaAccountMonitor(mode=mode)
    return monitor.get_positions()


def get_orders(mode: str = "paper", status: str = "open") -> List[Dict[str, Any]]:
    """
    Quick access to orders.

    Args:
        mode: "paper" or "live"
        status: Order status filter

    Returns:
        List of order dictionaries
    """
    monitor = AlpacaAccountMonitor(mode=mode)
    return monitor.get_orders(status=status)


class AlpacaOrderManager(AlpacaAccountMonitor):
    """
    Extends AlpacaAccountMonitor with order placement capabilities.

    Provides write operations (order management) while maintaining all
    read-only functionality from the parent class with enhanced safety rails.
    """

    def __init__(self, mode: str = "paper", risk_limits: Optional[Dict] = None):
        """
        Initialize order manager.

        Args:
            mode: "paper" or "live" trading mode
            risk_limits: Optional risk management limits
        """
        # Don't call super().__init__() to avoid creating client twice
        # Instead, create client directly with write permissions
        self.client = AlpacaTradingClient(mode=mode, require_confirmation=(mode == "live"))

        # Risk limits for order validation
        self.risk_limits = risk_limits or {
            "max_position_percent": 0.10,  # 10% max position size
            "max_daily_trades": 50,  # Max trades per day
            "max_order_size": 1000,  # Max shares per order
        }

        logger.info(f"Order manager initialized for {mode} trading with safety rails")

    def _validate_order(
        self, symbol: str, qty: int, side: str, price: Optional[float] = None
    ) -> bool:
        """
        Validate order parameters before submission.

        Args:
            symbol: Stock symbol
            qty: Order quantity
            side: "buy" or "sell"
            price: Limit price (optional)

        Returns:
            bool: True if order passes validation

        Raises:
            ValueError: If order fails validation
        """
        # Basic parameter validation
        if not symbol or not symbol.strip():
            raise ValueError("Symbol is required")

        if qty <= 0:
            raise ValueError(f"Quantity must be positive, got {qty}")

        if side.lower() not in ["buy", "sell"]:
            raise ValueError(f"Side must be 'buy' or 'sell', got {side}")

        # Risk limit checks
        if qty > self.risk_limits["max_order_size"]:
            raise ValueError(f"Order size {qty} exceeds limit {self.risk_limits['max_order_size']}")

        # Check buying power for buy orders
        if side.lower() == "buy":
            account = self.get_account_status()
            estimated_cost = qty * (price or 100.0)  # Conservative estimate if no price

            if estimated_cost > account["buying_power"]:
                raise ValueError(
                    f"Estimated cost ${estimated_cost:,.2f} exceeds buying power "
                    f"${account['buying_power']:,.2f}"
                )

        # Check if we have the position for sell orders
        if side.lower() == "sell":
            positions = self.get_positions()
            position = next((p for p in positions if p["symbol"] == symbol), None)

            if not position or position["qty"] < qty:
                available_qty = position["qty"] if position else 0
                raise ValueError(
                    f"Cannot sell {qty} shares of {symbol}, only {available_qty} available"
                )

        # Check daily trade limit
        self._check_daily_trade_limit()

        return True

    def _is_market_hours(self, extended_hours: bool = False) -> Dict[str, Any]:
        """
        Check if market is currently open.

        Args:
            extended_hours: Include pre-market and after-hours

        Returns:
            Dict with market status information
        """
        try:
            # Get current time in Eastern timezone (market timezone)
            # Use the configured timezone from date_utils, defaulting to NY (market timezone)
            market_tz = get_default_timezone()  # Should be "America/New_York"
            et = pytz.timezone(market_tz)
            current_et = get_datetime_now(et)
            current_time = current_et.time()
            current_weekday = current_et.weekday()  # 0=Monday, 6=Sunday

            # Market hours: 9:30 AM - 4:00 PM ET (Monday-Friday)
            market_open = dt_time(9, 30)
            market_close = dt_time(16, 0)

            # Extended hours: 4:00 AM - 8:00 PM ET
            extended_open = dt_time(4, 0)
            extended_close = dt_time(20, 0)

            # Check if it's a weekday (Monday=0, Friday=4)
            is_weekday = current_weekday < 5

            # Check market hours
            if extended_hours:
                is_open = is_weekday and extended_open <= current_time <= extended_close
                session = "extended"
                hours_desc = "4:00 AM - 8:00 PM ET"
            else:
                is_open = is_weekday and market_open <= current_time <= market_close
                session = "regular"
                hours_desc = "9:30 AM - 4:00 PM ET"

            # Determine current session
            if is_weekday:
                if current_time < dt_time(9, 30):
                    current_session = "pre-market"
                elif current_time <= dt_time(16, 0):
                    current_session = "market"
                elif current_time <= dt_time(20, 0):
                    current_session = "after-hours"
                else:
                    current_session = "closed"
            else:
                current_session = "weekend"

            return {
                "is_open": is_open,
                "session": session,
                "current_session": current_session,
                "current_time_et": current_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "is_weekday": is_weekday,
                "hours_desc": hours_desc,
                "extended_hours": extended_hours,
            }

        except Exception as e:
            logger.error(f"Failed to check market hours: {e}")
            return {
                "is_open": True,  # Default to open to avoid blocking trades
                "session": "unknown",
                "current_session": "unknown",
                "error": str(e),
            }

    def _validate_market_hours(
        self, _symbol: str, extended_hours: bool = False, warn_only: bool = True
    ) -> bool:
        """
        Validate that market is open for trading.

        Args:
            symbol: Stock symbol
            extended_hours: Allow extended hours trading
            warn_only: If True, warn but don't block; if False, block order

        Returns:
            bool: True if should proceed with order

        Raises:
            ValueError: If market is closed and warn_only=False
        """
        market_status = self._is_market_hours(extended_hours)

        if not market_status["is_open"]:
            message = (
                f"Market is currently {market_status['current_session']} "
                f"({market_status.get('current_time_et', 'unknown time')}). "
                f"Regular hours: {market_status.get('hours_desc', 'unknown')}"
            )

            if warn_only:
                # Note: We submit immediately to Alpaca - THEY queue it, not us
                # If validation fails, order is rejected (no local queue/retry)
                logger.warning(f"⚠️  {message} - Order will be sent to broker (may fail validation)")
                return True
            else:
                logger.error(f"❌ {message} - Order blocked")
                raise ValueError(message)

        return True

    def _check_daily_trade_limit(self) -> bool:
        """
        Check if daily trade limit has been reached.

        Returns:
            bool: True if within limits, False if limit exceeded

        Raises:
            ValueError: If daily trade limit exceeded
        """
        try:
            # Get today's orders
            # Get ET timezone for market day calculation
            et_tz = pytz.timezone("America/New_York")
            now_et = get_datetime_now(et_tz)

            # Market day starts at market open (usually 4:00 AM ET for pre-market)
            market_start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
            if now_et < market_start:
                # Before 4 AM, consider it previous market day
                market_start = market_start.replace(day=market_start.day - 1)

            # Convert to UTC for API call
            market_start_utc = market_start.astimezone(timezone.utc)

            # Get orders from market start of today
            # Note: Not specifying status parameter returns all orders (open, closed, filled, etc.)
            request = GetOrdersRequest(after=market_start_utc)
            # AlpacaOrderManager has self.client (AlpacaTradingClient), which has trading_client
            today_orders = self.client.trading_client.get_orders(request)

            order_count = len(today_orders)
            max_trades = self.risk_limits.get("max_daily_trades", 100)  # Default 100

            logger.info(f"Daily trade count: {order_count}/{max_trades}")

            if order_count >= max_trades:
                raise ValueError(
                    f"Daily trade limit exceeded: {order_count}/{max_trades} orders placed today"
                )

            return True

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            # Log but don't block for other errors
            logger.warning(f"Could not check daily trade limit: {e}")
            return True

    def place_market_order(
        self, symbol: str, qty: int, side: str, time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """
        Place market order with mode awareness and validation.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            time_in_force: "day", "gtc", "ioc", "fok"

        Returns:
            Dict with order details or error information
        """
        try:
            # Validate order parameters
            self._validate_order(symbol, qty, side)

            # Validate market hours (warn only for now)
            self._validate_market_hours(symbol, extended_hours=False, warn_only=True)

            # Mode-aware logging
            if self.client.mode == "live":
                logger.warning(f"🔥 LIVE MARKET ORDER: {side.upper()} {qty} {symbol}")
            else:
                logger.info(f"📝 PAPER MARKET ORDER: {side.upper()} {qty} {symbol}")

            # Map string values to enums
            side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif_map = {
                "day": TimeInForce.DAY,
                "gtc": TimeInForce.GTC,
                "ioc": TimeInForce.IOC,
                "fok": TimeInForce.FOK,
            }
            tif_enum = tif_map.get(time_in_force.lower(), TimeInForce.DAY)

            # Create order request
            order_request = MarketOrderRequest(
                symbol=symbol, qty=qty, side=side_enum, time_in_force=tif_enum
            )

            # Safety check for live trading
            order_details = {
                "type": "market",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "time_in_force": time_in_force,
            }

            if self.client.mode == "live":
                if not self.client._safety_check("PLACE MARKET ORDER", order_details):
                    return {
                        "status": "cancelled",
                        "message": "Order cancelled by user",
                        "order_details": order_details,
                    }

            # Submit order
            order = self.client.trading_client.submit_order(order_data=order_request)

            # Return structured response
            return {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": side.lower(),  # Use original string parameter
                "order_type": str(order.order_type),
                "status_detail": str(order.status),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "mode": self.client.mode,
            }

        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {"symbol": symbol, "qty": qty, "side": side, "type": "market"},
            }

    def place_limit_order_gtc(
        self, symbol: str, qty: int, side: str, limit_price: float
    ) -> Dict[str, Any]:
        """
        Place GTC limit order with mode awareness and validation.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            limit_price: Limit price per share

        Returns:
            Dict with order details or error information
        """
        try:
            # Validate order parameters
            self._validate_order(symbol, qty, side, limit_price)

            if limit_price <= 0:
                raise ValueError(f"Limit price must be positive, got {limit_price}")

            # Validate market hours (warn only for now)
            self._validate_market_hours(symbol, extended_hours=False, warn_only=True)

            # Mode-aware logging
            if self.client.mode == "live":
                logger.warning(
                    f"🔥 LIVE LIMIT ORDER: {side.upper()} {qty} {symbol} @ ${limit_price:.2f}"
                )
            else:
                logger.info(
                    f"📝 PAPER LIMIT ORDER: {side.upper()} {qty} {symbol} @ ${limit_price:.2f}"
                )

            # Map side to enum
            side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            # Create order request
            order_request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=TimeInForce.GTC,  # Good Till Cancelled
                limit_price=limit_price,
            )

            # Safety check for live trading
            order_details = {
                "type": "limit",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "limit_price": limit_price,
                "time_in_force": "GTC",
                "estimated_cost": qty * limit_price if side.lower() == "buy" else 0,
            }

            if self.client.mode == "live":
                if not self.client._safety_check("PLACE LIMIT ORDER", order_details):
                    return {
                        "status": "cancelled",
                        "message": "Order cancelled by user",
                        "order_details": order_details,
                    }

            # Submit order
            order = self.client.trading_client.submit_order(order_data=order_request)

            # Return structured response
            return {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": side.lower(),  # Use original string parameter
                "order_type": str(order.order_type),
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "time_in_force": "GTC",  # We know this is GTC from the method name
                "status_detail": str(order.status),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "mode": self.client.mode,
            }

        except Exception as e:
            logger.error(f"Failed to place limit order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "limit_price": limit_price,
                    "type": "limit",
                },
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
            # Mode-aware logging
            if self.client.mode == "live":
                logger.warning(f"🔥 LIVE ORDER CANCELLATION: {order_id}")

            # Safety check for live trading
            if self.client.mode == "live":
                if not self.client._safety_check("CANCEL ORDER", {"order_id": order_id}):
                    return {
                        "status": "cancelled",
                        "message": "Cancellation cancelled by user",
                        "order_id": order_id,
                    }

            # Cancel the order
            self.client.trading_client.cancel_order_by_id(order_id)

            return {
                "status": "cancelled",
                "order_id": order_id,
                "message": "Order cancellation submitted",
                "mode": self.client.mode,
            }

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return {"status": "error", "message": str(e), "order_id": order_id}

    def close_position(
        self, symbol: str, qty: Optional[int] = None, percentage: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Close position (or partial position) in a symbol.

        Args:
            symbol: Symbol to close
            qty: Specific quantity to close (optional)
            percentage: Percentage of position to close (optional, 0-1)

        Returns:
            Dict with closing order result
        """
        try:
            # Get current position
            positions = self.get_positions()
            position = next((p for p in positions if p["symbol"] == symbol), None)

            if not position:
                return {
                    "status": "error",
                    "message": f"No position found for {symbol}",
                    "symbol": symbol,
                }

            current_qty = int(position["qty"])
            if current_qty == 0:
                return {
                    "status": "error",
                    "message": f"No shares to close for {symbol}",
                    "symbol": symbol,
                }

            # Calculate quantity to close
            close_qty = current_qty
            if qty is not None:
                close_qty = min(qty, current_qty)
            elif percentage is not None:
                if not 0 < percentage <= 1:
                    raise ValueError("Percentage must be between 0 and 1")
                close_qty = int(current_qty * percentage)

            # Determine side (close long = sell, close short = buy)
            close_side = "sell" if position["side"] == "long" else "buy"

            # Mode-aware logging
            if self.client.mode == "live":
                logger.warning(f"🔥 LIVE POSITION CLOSE: {close_side.upper()} {close_qty} {symbol}")

            # Use market order to close position quickly
            return self.place_market_order(symbol, close_qty, close_side)

        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            return {"status": "error", "message": str(e), "symbol": symbol}

    def place_stop_order(
        self, symbol: str, qty: int, side: str, stop_price: float, time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """
        Place stop order with mode awareness and validation.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            stop_price: Stop price trigger
            time_in_force: "day", "gtc", "ioc", "fok"

        Returns:
            Dict with order details or error information
        """
        try:
            # Validate order parameters
            self._validate_order(symbol, qty, side, stop_price)

            if stop_price <= 0:
                raise ValueError(f"Stop price must be positive, got {stop_price}")

            # Validate market hours (warn only for now)
            self._validate_market_hours(symbol, extended_hours=False, warn_only=True)

            # Mode-aware logging
            if self.client.mode == "live":
                logger.warning(
                    f"🔥 LIVE STOP ORDER: {side.upper()} {qty} {symbol} @ stop ${stop_price:.2f}"
                )
            else:
                logger.info(
                    f"📝 PAPER STOP ORDER: {side.upper()} {qty} {symbol} @ stop ${stop_price:.2f}"
                )

            # Map values to enums
            side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif_map = {
                "day": TimeInForce.DAY,
                "gtc": TimeInForce.GTC,
                "ioc": TimeInForce.IOC,
                "fok": TimeInForce.FOK,
            }
            tif_enum = tif_map.get(time_in_force.lower(), TimeInForce.DAY)

            # Create order request
            order_request = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif_enum,
                stop_price=stop_price,
            )

            # Safety check for live trading
            order_details = {
                "type": "stop",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "stop_price": stop_price,
                "time_in_force": time_in_force,
            }

            if self.client.mode == "live":
                if not self.client._safety_check("PLACE STOP ORDER", order_details):
                    return {
                        "status": "cancelled",
                        "message": "Order cancelled by user",
                        "order_details": order_details,
                    }

            # Submit order
            order = self.client.trading_client.submit_order(order_data=order_request)

            # Return structured response
            return {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": side.lower(),
                "order_type": "stop",
                "stop_price": stop_price,
                "time_in_force": time_in_force.upper(),
                "status_detail": str(order.status),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "mode": self.client.mode,
            }

        except Exception as e:
            logger.error(f"Failed to place stop order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "stop_price": stop_price,
                    "type": "stop",
                },
            }

    def place_trailing_stop_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        trail_percent: Optional[float] = None,
        trail_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """
        Place trailing stop order with mode awareness and validation.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            trail_percent: Trailing percentage (0-1, e.g., 0.05 for 5%)
            trail_price: Trailing price amount (alternative to percentage)
            time_in_force: "day", "gtc"

        Returns:
            Dict with order details or error information
        """
        try:
            # Validate order parameters
            self._validate_order(symbol, qty, side)

            if not trail_percent and not trail_price:
                raise ValueError("Either trail_percent or trail_price must be specified")

            if trail_percent and (trail_percent <= 0 or trail_percent >= 1):
                raise ValueError(f"Trail percent must be between 0 and 1, got {trail_percent}")

            if trail_price and trail_price <= 0:
                raise ValueError(f"Trail price must be positive, got {trail_price}")

            # Validate market hours (warn only for now)
            self._validate_market_hours(symbol, extended_hours=False, warn_only=True)

            # Mode-aware logging
            trail_desc = f"{trail_percent*100:.1f}%" if trail_percent else f"${trail_price:.2f}"
            if self.client.mode == "live":
                logger.warning(
                    f"🔥 LIVE TRAILING STOP: {side.upper()} {qty} {symbol} trail {trail_desc}"
                )
            else:
                logger.info(
                    f"📝 PAPER TRAILING STOP: {side.upper()} {qty} {symbol} trail {trail_desc}"
                )

            # Map values to enums
            side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif_enum = TimeInForce.GTC if time_in_force.lower() == "gtc" else TimeInForce.DAY

            # Create order request
            order_request = TrailingStopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif_enum,
                trail_percent=trail_percent,
                trail_price=trail_price,
            )

            # Safety check for live trading
            order_details = {
                "type": "trailing_stop",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "trail_percent": trail_percent,
                "trail_price": trail_price,
                "time_in_force": time_in_force,
            }

            if self.client.mode == "live":
                if not self.client._safety_check("PLACE TRAILING STOP ORDER", order_details):
                    return {
                        "status": "cancelled",
                        "message": "Order cancelled by user",
                        "order_details": order_details,
                    }

            # Submit order
            order = self.client.trading_client.submit_order(order_data=order_request)

            # Return structured response
            return {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": side.lower(),
                "order_type": "trailing_stop",
                "trail_percent": trail_percent,
                "trail_price": trail_price,
                "time_in_force": time_in_force.upper(),
                "status_detail": str(order.status),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "mode": self.client.mode,
            }

        except Exception as e:
            logger.error(f"Failed to place trailing stop order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "trail_percent": trail_percent,
                    "trail_price": trail_price,
                    "type": "trailing_stop",
                },
            }

    def place_bracket_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        entry_limit_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """
        Place bracket order (entry + take profit + stop loss).

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            entry_limit_price: Entry limit price (None for market entry)
            take_profit_price: Take profit limit price
            stop_loss_price: Stop loss price
            time_in_force: "day", "gtc"

        Returns:
            Dict with order details or error information
        """
        try:
            # Validate order parameters
            self._validate_order(symbol, qty, side, entry_limit_price)

            if not take_profit_price and not stop_loss_price:
                raise ValueError(
                    "At least one of take_profit_price or stop_loss_price must be specified"
                )

            if take_profit_price and take_profit_price <= 0:
                raise ValueError(f"Take profit price must be positive, got {take_profit_price}")

            if stop_loss_price and stop_loss_price <= 0:
                raise ValueError(f"Stop loss price must be positive, got {stop_loss_price}")

            # Validate market hours (warn only for now)
            self._validate_market_hours(symbol, extended_hours=False, warn_only=True)

            # Mode-aware logging
            entry_desc = f"limit ${entry_limit_price:.2f}" if entry_limit_price else "market"
            if self.client.mode == "live":
                logger.warning(
                    f"🔥 LIVE BRACKET ORDER: {side.upper()} {qty} {symbol} @ {entry_desc} "
                    f"TP:{take_profit_price} SL:{stop_loss_price}"
                )
            else:
                logger.info(
                    f"📝 PAPER BRACKET ORDER: {side.upper()} {qty} {symbol} @ {entry_desc} "
                    f"TP:{take_profit_price} SL:{stop_loss_price}"
                )

            # Map values to enums
            side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif_enum = TimeInForce.GTC if time_in_force.lower() == "gtc" else TimeInForce.DAY

            # Create take profit and stop loss requests
            take_profit = (
                TakeProfitRequest(limit_price=take_profit_price) if take_profit_price else None
            )
            stop_loss = StopLossRequest(stop_price=stop_loss_price) if stop_loss_price else None

            # Create main order request (market or limit entry)
            if entry_limit_price:
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_enum,
                    time_in_force=tif_enum,
                    limit_price=entry_limit_price,
                    order_class=OrderClass.BRACKET,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            else:
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_enum,
                    time_in_force=tif_enum,
                    order_class=OrderClass.BRACKET,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )

            # Safety check for live trading
            order_details = {
                "type": "bracket",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "entry_limit_price": entry_limit_price,
                "take_profit_price": take_profit_price,
                "stop_loss_price": stop_loss_price,
                "time_in_force": time_in_force,
            }

            if self.client.mode == "live":
                if not self.client._safety_check("PLACE BRACKET ORDER", order_details):
                    return {
                        "status": "cancelled",
                        "message": "Order cancelled by user",
                        "order_details": order_details,
                    }

            # Submit order
            order = self.client.trading_client.submit_order(order_data=order_request)

            # Return structured response
            return {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": side.lower(),
                "order_type": "bracket",
                "entry_limit_price": entry_limit_price,
                "take_profit_price": take_profit_price,
                "stop_loss_price": stop_loss_price,
                "order_class": "bracket",
                "time_in_force": time_in_force.upper(),
                "status_detail": str(order.status),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "mode": self.client.mode,
            }

        except Exception as e:
            # Don't log error here - it will be logged and translated by execution manager
            logger.debug(f"Bracket order error details: {e}", exc_info=True)

            # Extract Alpaca API error details if available
            error_code = None
            status_code = None

            # Try to extract error code from Alpaca APIError
            try:
                if isinstance(e, APIError):
                    status_code = getattr(e, "status_code", None)
                    error_code = getattr(e, "code", None)
                    logger.debug(f"Alpaca API error: status={status_code}, code={error_code}")
            except ImportError:
                # alpaca-py not available or doesn't have APIError
                pass
            except Exception:
                # Failed to extract error details
                pass

            return {
                "status": "error",
                "message": str(e),
                "error_code": error_code,
                "status_code": status_code,
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "entry_limit_price": entry_limit_price,
                    "take_profit_price": take_profit_price,
                    "stop_loss_price": stop_loss_price,
                    "type": "bracket",
                },
            }

    def modify_order(
        self,
        order_id: str,
        qty: Optional[int] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Modify an existing order.

        Args:
            order_id: ID of the order to modify
            qty: New quantity (optional)
            limit_price: New limit price (optional)
            stop_price: New stop price (optional)
            time_in_force: New time in force (optional)

        Returns:
            Dict with modified order details or error information
        """
        try:
            # Get current order to validate it exists
            try:
                self.client.trading_client.get_order_by_id(order_id)
            except Exception:
                return {
                    "status": "error",
                    "message": f"Order {order_id} not found",
                    "order_id": order_id,
                }

            # Build replacement order request
            # Start with current order values
            replace_request_params = {}

            if qty is not None:
                if qty <= 0:
                    raise ValueError(f"Quantity must be positive, got {qty}")
                replace_request_params["qty"] = qty

            if limit_price is not None:
                if limit_price <= 0:
                    raise ValueError(f"Limit price must be positive, got {limit_price}")
                replace_request_params["limit_price"] = limit_price

            if stop_price is not None:
                if stop_price <= 0:
                    raise ValueError(f"Stop price must be positive, got {stop_price}")
                replace_request_params["stop_price"] = stop_price

            if time_in_force is not None:
                tif_map = {
                    "day": TimeInForce.DAY,
                    "gtc": TimeInForce.GTC,
                    "ioc": TimeInForce.IOC,
                    "fok": TimeInForce.FOK,
                }
                if time_in_force.lower() not in tif_map:
                    raise ValueError(f"Invalid time in force: {time_in_force}")
                replace_request_params["time_in_force"] = tif_map[time_in_force.lower()]

            # Create replacement request
            replace_request = ReplaceOrderRequest(**replace_request_params)

            # Mode-aware logging
            if self.client.mode == "live":
                logger.warning(f"🔥 LIVE ORDER MODIFICATION: {order_id}")
                if self.client.require_confirmation:
                    confirmation = input(
                        f"Confirm LIVE order modification for {order_id}? (yes/no): "
                    )
                    if confirmation.lower() != "yes":
                        return {
                            "status": "cancelled",
                            "message": "Order modification cancelled by user",
                            "order_id": order_id,
                        }
            else:
                logger.info(f"📝 PAPER ORDER MODIFICATION: {order_id}")

            # Replace the order
            updated_order = self.client.trading.replace_order_by_id(  # pylint: disable=no-member
                order_id, replace_request
            )

            return {
                "status": "submitted",
                "message": "Order modified successfully",
                "order_id": str(updated_order.id),
                "symbol": str(updated_order.symbol),
                "qty": float(updated_order.qty),
                "side": str(updated_order.side),
                "order_type": str(updated_order.order_type),
                "time_in_force": str(updated_order.time_in_force),
                "limit_price": (
                    float(updated_order.limit_price) if updated_order.limit_price else None
                ),
                "stop_price": float(updated_order.stop_price) if updated_order.stop_price else None,
                "status_detail": str(updated_order.status),
                "submitted_at": (
                    updated_order.submitted_at.isoformat() if updated_order.submitted_at else None
                ),
                "mode": self.client.mode,
            }

        except Exception as e:
            logger.error(f"Failed to modify order {order_id}: {e}")
            return {"status": "error", "message": str(e), "order_id": order_id}

    def modify_stop_order(self, order_id: str, new_stop_price: float, symbol: str) -> bool:
        """
        Modify stop price on an existing stop order (convenience wrapper).

        Used for dynamic trailing stop adjustments.

        Args:
            order_id: ID of the stop order to modify
            new_stop_price: New stop price level
            symbol: Stock symbol (for logging)

        Returns:
            True if modification successful, False otherwise
        """
        logger.info(f"Modifying stop order {order_id} for {symbol} to ${new_stop_price:.2f}")

        result = self.modify_order(order_id=order_id, stop_price=new_stop_price)

        if result.get("status") == "submitted":
            logger.info(f"✅ Stop order {order_id} updated successfully")
            return True
        else:
            error_msg = result.get("message", "Unknown error")
            logger.error(f"❌ Failed to modify stop order {order_id}: {error_msg}")
            return False

    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter orders (cancels all if None)

        Returns:
            Dict with cancellation results
        """
        try:
            # Get open orders
            if symbol:
                request = (
                    GetOrdersRequest(  # pylint: disable=possibly-used-before-assignment,no-member
                        status=OrderStatus.OPEN, symbols=[symbol]  # pylint: disable=no-member
                    )
                )
                orders = self.client.trading_client.get_orders(request)
            else:
                orders = self.get_orders(status="open")
                # Convert to alpaca order objects if needed
                if orders and isinstance(orders[0], dict):
                    # These are our formatted orders, we need the raw ones
                    request = GetOrdersRequest(  # pylint: disable=possibly-used-before-assignment
                        status=OrderStatus.OPEN  # pylint: disable=no-member
                    )
                    orders = self.client.trading.get_orders(request)  # pylint: disable=no-member

            if not orders:
                return {
                    "status": "success",
                    "message": f'No open orders found{" for " + symbol if symbol else ""}',
                    "cancelled_orders": [],
                    "mode": self.client.mode,
                }

            # Mode-aware logging and confirmation
            order_count = len(orders)
            symbol_desc = f" for {symbol}" if symbol else ""

            if self.client.mode == "live":
                logger.warning(f"🔥 LIVE BULK CANCELLATION: {order_count} orders{symbol_desc}")
                if self.client.require_confirmation:
                    confirmation = input(
                        f"Confirm cancelling {order_count} LIVE orders{symbol_desc}? (yes/no): "
                    )
                    if confirmation.lower() != "yes":
                        return {
                            "status": "cancelled",
                            "message": "Bulk cancellation cancelled by user",
                            "cancelled_orders": [],
                            "mode": self.client.mode,
                        }
            else:
                logger.info(f"📝 PAPER BULK CANCELLATION: {order_count} orders{symbol_desc}")

            # Cancel all orders
            cancelled_orders = []
            errors = []

            for order in orders:
                try:
                    self.client.trading.cancel_order_by_id(order.id)  # pylint: disable=no-member
                    cancelled_orders.append(str(order.id))
                except Exception as e:
                    errors.append(f"Failed to cancel {order.id}: {str(e)}")

            result = {
                "status": "success" if not errors else "partial",
                "message": f"Cancelled {len(cancelled_orders)} orders{symbol_desc}",
                "cancelled_orders": cancelled_orders,
                "mode": self.client.mode,
            }

            if errors:
                result["errors"] = errors

            return result

        except Exception as e:
            logger.error(f"Failed to cancel orders{' for ' + symbol if symbol else ''}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "cancelled_orders": [],
                "mode": self.client.mode,
            }


# Convenience functions for Phase 2
def place_market_order(symbol: str, qty: int, side: str, mode: str = "paper") -> Dict[str, Any]:
    """
    Quick market order placement.

    Args:
        symbol: Stock symbol
        qty: Number of shares
        side: "buy" or "sell"
        mode: "paper" or "live"

    Returns:
        Order result dictionary
    """
    manager = AlpacaOrderManager(mode=mode)
    return manager.place_market_order(symbol, qty, side)


def place_limit_order(
    symbol: str, qty: int, side: str, limit_price: float, mode: str = "paper"
) -> Dict[str, Any]:
    """
    Quick GTC limit order placement.

    Args:
        symbol: Stock symbol
        qty: Number of shares
        side: "buy" or "sell"
        limit_price: Limit price per share
        mode: "paper" or "live"

    Returns:
        Order result dictionary
    """
    manager = AlpacaOrderManager(mode=mode)
    return manager.place_limit_order_gtc(symbol, qty, side, limit_price)
