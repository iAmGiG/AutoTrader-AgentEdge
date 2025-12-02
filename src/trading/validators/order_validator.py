"""
Order validation logic extracted from AlpacaOrderManager.

Issue #437: Extract validators from alpaca_trading_client.py for better testability.
"""

import logging
from datetime import timezone
from typing import Any, Dict, List, Optional

import pytz

from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)


class OrderValidator:
    """
    Validates trading orders against risk limits and account constraints.

    Performs pre-trade checks:
    - Parameter validation (symbol, quantity, side)
    - Risk limit enforcement (max order size, daily trade limits)
    - Buying power verification for buys
    - Position availability verification for sells
    """

    def __init__(
        self,
        risk_limits: Optional[Dict[str, Any]] = None,
        account_provider=None,
        position_provider=None,
        order_provider=None,
    ):
        """
        Initialize order validator.

        Args:
            risk_limits: Dictionary with risk parameters:
                - max_order_size: Maximum shares per order (default: 1000)
                - max_daily_trades: Maximum trades per day (default: 100)
            account_provider: Callable that returns account status dict
            position_provider: Callable that returns list of positions
            order_provider: Callable that returns orders (used for daily limit check)
        """
        self.risk_limits = risk_limits or {
            "max_order_size": 1000,
            "max_daily_trades": 100,
        }
        self.account_provider = account_provider
        self.position_provider = position_provider
        self.order_provider = order_provider

    def validate_order(
        self, symbol: str, qty: int, side: str, price: Optional[float] = None
    ) -> bool:
        """
        Validate order parameters before submission.

        Args:
            symbol: Stock symbol
            qty: Order quantity
            side: "buy" or "sell"
            price: Limit price (optional, used for buying power check)

        Returns:
            True if order passes validation

        Raises:
            ValueError: If order fails validation with detailed message
        """
        # Basic parameter validation
        self._validate_parameters(symbol, qty, side)

        # Risk limit checks
        self._validate_order_size(qty)

        # Account-specific checks (require providers)
        if side.lower() == "buy":
            self._validate_buying_power(symbol, qty, price)
        elif side.lower() == "sell":
            self._validate_position_availability(symbol, qty)

        # Daily trade limit check
        self._check_daily_trade_limit()

        return True

    def _validate_parameters(self, symbol: str, qty: int, side: str):
        """Validate basic order parameters."""
        if not symbol or not symbol.strip():
            raise ValueError("Symbol is required")

        if qty <= 0:
            raise ValueError(f"Quantity must be positive, got {qty}")

        if side.lower() not in ["buy", "sell"]:
            raise ValueError(f"Side must be 'buy' or 'sell', got {side}")

    def _validate_order_size(self, qty: int):
        """Validate order quantity against max order size limit."""
        max_size = self.risk_limits.get("max_order_size", 1000)
        if qty > max_size:
            raise ValueError(f"Order size {qty} exceeds limit {max_size}")

    def _validate_buying_power(self, symbol: str, qty: int, price: Optional[float]):
        """Validate sufficient buying power for buy orders."""
        if not self.account_provider:
            logger.warning("No account provider configured, skipping buying power check")
            return

        try:
            account = self.account_provider()
            estimated_cost = qty * (price or 100.0)  # Conservative estimate if no price

            buying_power = account.get("buying_power", 0)
            if estimated_cost > buying_power:
                raise ValueError(
                    f"Estimated cost ${estimated_cost:,.2f} exceeds buying power "
                    f"${buying_power:,.2f}"
                )
        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.error(f"Error checking buying power: {e}")
            # Don't block order if check fails - log and continue
            logger.warning("Proceeding with order despite buying power check failure")

    def _validate_position_availability(self, symbol: str, qty: int):
        """Validate sufficient position for sell orders."""
        if not self.position_provider:
            logger.warning("No position provider configured, skipping position check")
            return

        try:
            positions = self.position_provider()
            position = next((p for p in positions if p["symbol"] == symbol), None)

            if not position or position["qty"] < qty:
                available_qty = position["qty"] if position else 0
                raise ValueError(
                    f"Cannot sell {qty} shares of {symbol}, only {available_qty} available"
                )
        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.error(f"Error checking position availability: {e}")
            # Don't block order if check fails - log and continue
            logger.warning("Proceeding with order despite position check failure")

    def _check_daily_trade_limit(self) -> bool:
        """
        Check if daily trade limit has been reached.

        Returns:
            True if within limits

        Raises:
            ValueError: If daily trade limit exceeded
        """
        if not self.order_provider:
            logger.warning("No order provider configured, skipping daily trade limit check")
            return True

        try:
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
            today_orders = self.order_provider(after=market_start_utc)
            order_count = len(today_orders)

            max_trades = self.risk_limits.get("max_daily_trades", 100)
            logger.info(f"Daily trade count: {order_count}/{max_trades}")

            if order_count >= max_trades:
                raise ValueError(
                    f"Daily trade limit exceeded: {order_count}/{max_trades} orders placed today"
                )

            return True

        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.warning(f"Could not check daily trade limit: {e}")
            return True  # Don't block if check fails

    def validate_sell_signal(self, symbol: str, qty: int) -> bool:
        """
        Specialized validation for sell signals (ensures position exists).

        Args:
            symbol: Stock symbol
            qty: Quantity to sell

        Returns:
            True if valid sell signal

        Raises:
            ValueError: If cannot sell (no position or insufficient quantity)
        """
        self._validate_parameters(symbol, qty, "sell")
        self._validate_position_availability(symbol, qty)
        return True

    def validate_buy_signal(self, symbol: str, qty: int, price: Optional[float] = None) -> bool:
        """
        Specialized validation for buy signals (ensures buying power).

        Args:
            symbol: Stock symbol
            qty: Quantity to buy
            price: Expected entry price

        Returns:
            True if valid buy signal

        Raises:
            ValueError: If cannot buy (insufficient buying power or risk limits)
        """
        self._validate_parameters(symbol, qty, "buy")
        self._validate_order_size(qty)
        self._validate_buying_power(symbol, qty, price)
        self._check_daily_trade_limit()
        return True
