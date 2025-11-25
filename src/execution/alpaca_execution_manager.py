"""
AlpacaExecutionManager - Executes trades via Alpaca broker.

Integrates existing OrderManager into the plugin architecture.
"""

import logging
import uuid
from typing import Optional, Tuple

from core.interfaces import ExecutionManager
from core.models import OrderResult, TradeDecision, TradeSuggestion

from src.utils.date_utils import get_datetime_now

# Import message loader for user-facing messages
try:
    from config_defaults.message_loader import MessageLoader

    _MSG = MessageLoader()
    MESSAGE_LOADER_AVAILABLE = True
except ImportError:
    MESSAGE_LOADER_AVAILABLE = False
    logging.warning("MessageLoader not available - using fallback messages")


# Load market hours configuration from YAML
def _load_market_hours_config():
    """Load market hours configuration from config_defaults/market_hours.yaml"""
    try:
        import os

        import yaml

        # Get path to config file
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "config_defaults", "market_hours.yaml")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        return config
    except Exception as e:
        logging.warning(f"Failed to load market_hours.yaml, using defaults: {e}")
        # Fallback to hardcoded defaults
        return {
            "timezone": "America/New_York",
            "regular_hours": {
                "open_hour": 9,
                "open_minute": 30,
                "close_hour": 16,
                "close_minute": 0,
            },
            "weekend": {"saturday": 5, "sunday": 6},
        }


# Load configuration at module level
_MARKET_CONFIG = _load_market_hours_config()

# Extract configuration values (backward compatibility with existing code)
MARKET_TIMEZONE = _MARKET_CONFIG.get("timezone", "America/New_York")
SATURDAY = _MARKET_CONFIG.get("weekend", {}).get("saturday", 5)
SUNDAY = _MARKET_CONFIG.get("weekend", {}).get("sunday", 6)
MARKET_OPEN_HOUR = _MARKET_CONFIG.get("regular_hours", {}).get("open_hour", 9)
MARKET_OPEN_MINUTE = _MARKET_CONFIG.get("regular_hours", {}).get("open_minute", 30)
MARKET_CLOSE_HOUR = _MARKET_CONFIG.get("regular_hours", {}).get("close_hour", 16)
MARKET_CLOSE_MINUTE = _MARKET_CONFIG.get("regular_hours", {}).get("close_minute", 0)
DEFAULT_FALLBACK_PRICE = 100.0  # UnifiedPriceFetcher default when data unavailable

# Try to import pytz for timezone handling
try:
    import pytz

    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False
    logging.warning(
        "pytz not available - market hours detection may fail. " "Install with: pip install pytz"
    )

# Import price fetcher for current market prices
try:
    from src.trading.unified_price_fetcher import UnifiedPriceFetcher

    PRICE_FETCHER_AVAILABLE = True
except ImportError:
    try:
        from trading.unified_price_fetcher import UnifiedPriceFetcher

        PRICE_FETCHER_AVAILABLE = True
    except ImportError:
        PRICE_FETCHER_AVAILABLE = False
        logging.warning("UnifiedPriceFetcher not available - will use suggestion prices")


logger = logging.getLogger(__name__)


class AlpacaExecutionManager(ExecutionManager):
    """
    Execute trades via Alpaca broker.

    Integrates with existing OrderManager to place bracket orders
    with entry, stop-loss, and take-profit levels.

    MVP: Simplified to handle basic execution.
    Full order lifecycle management in OrderManager.
    """

    def __init__(
        self,
        order_manager: Optional[object] = None,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.08,
    ):
        """
        Initialize with existing OrderManager.

        Args:
            order_manager: OrderManager instance (from src/trading/order_manager.py)
            stop_loss_pct: Stop loss percentage (default 5%)
            take_profit_pct: Take profit percentage (default 8%)
        """
        self.order_manager = order_manager
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        if order_manager:
            msg = (
                _MSG.get("execution.init_with_manager")
                if MESSAGE_LOADER_AVAILABLE
                else "AlpacaExecutionManager initialized with OrderManager"
            )
            logger.info(msg)
        else:
            msg = (
                _MSG.get("execution.init_without_manager")
                if MESSAGE_LOADER_AVAILABLE
                else "AlpacaExecutionManager initialized without OrderManager (stub mode)"
            )
            logger.warning(msg)

        msg = (
            _MSG.get(
                "execution.strategy_config",
                stop_loss_pct=stop_loss_pct * 100,
                take_profit_pct=take_profit_pct * 100,
            )
            if MESSAGE_LOADER_AVAILABLE
            else f"Using strategy config: stop_loss={stop_loss_pct*100}%, take_profit={take_profit_pct*100}%"
        )
        logger.info(msg)

        # Log price fetcher availability
        if PRICE_FETCHER_AVAILABLE:
            logger.info(
                "UnifiedPriceFetcher available - will fetch current prices before execution"
            )
        else:
            logger.warning("UnifiedPriceFetcher NOT available - will use suggestion prices")

    def _is_market_hours(self) -> bool:
        """
        Check if current time is during regular market hours (9:30 AM - 4:00 PM ET, Mon-Fri).

        Returns:
            True if during market hours, False otherwise
        """
        if not PYTZ_AVAILABLE:
            logger.warning("pytz not available - cannot determine market hours")
            return False

        try:
            et_tz = pytz.timezone(MARKET_TIMEZONE)
            now_et = get_datetime_now(et_tz)

            # Check if weekend
            if now_et.weekday() >= SATURDAY:  # Saturday or Sunday
                return False

            # Check if within market hours
            market_open = now_et.replace(
                hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0
            )
            market_close = now_et.replace(
                hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0
            )

            return market_open <= now_et <= market_close

        except Exception as e:
            logger.warning(f"Could not determine market hours: {e}")
            return False  # Assume off-hours if we can't determine

    def _is_bracket_validation_error(self, error_data: dict) -> bool:
        """
        Detect if an error is a bracket order validation failure.

        Uses Alpaca API error codes when available, falls back to heuristics.

        Args:
            error_data: Error dict from order_manager (contains status, message, error_code, status_code)

        Returns:
            True if this is a bracket order validation error, False otherwise
        """
        # Method 1: Check Alpaca API error codes (most reliable)
        error_code = error_data.get("error_code")
        status_code = error_data.get("status_code")

        if status_code == 422:  # Unprocessable Entity - validation failed
            # Alpaca returns 422 for bracket order validation failures
            logger.debug(f"Detected HTTP 422 validation error (error_code={error_code})")
            return True

        # Alpaca error code 42210000 series: Invalid order parameters
        if error_code and str(error_code).startswith("4221"):
            logger.debug(f"Detected Alpaca error code {error_code} - bracket order validation")
            return True

        # Method 2: Message-based heuristics (fallback for when error codes unavailable)
        error_msg = error_data.get("message", "").lower()

        # Common bracket order validation error patterns
        bracket_error_keywords = [
            "limit_price",
            "base_price",
            "take_profit",
            "stop_loss",
            "bracket",
            "order_class",
        ]

        matches = sum(1 for keyword in bracket_error_keywords if keyword in error_msg)
        if matches >= 2:  # Multiple keywords suggest bracket order issue
            logger.debug(
                f"Detected bracket validation via message pattern (matched {matches} keywords)"
            )
            return True

        return False

    async def execute_trade(
        self, suggestion: TradeSuggestion, decision: Optional[TradeDecision] = None
    ) -> OrderResult:
        """
        Execute trade based on suggestion and user decision.

        MVP: Places bracket order (entry + stop + target) via OrderManager.

        Args:
            suggestion: The trade suggestion
            decision: User's decision (may contain modifications)

        Returns:
            OrderResult with order IDs and execution details
        """
        ticker = suggestion.ticker
        signal = suggestion.signal.value

        # Apply modifications if present
        if decision:
            quantity = decision.modified_quantity or suggestion.recommended_quantity
            entry_price = decision.modified_entry or suggestion.entry_price
            stop_loss = decision.modified_stop or suggestion.stop_loss
            take_profit = decision.modified_target or suggestion.take_profit
        else:
            quantity = suggestion.recommended_quantity
            entry_price = suggestion.entry_price
            stop_loss = suggestion.stop_loss
            take_profit = suggestion.take_profit

        logger.info(
            f"Executing: {signal.upper()} {quantity} {ticker} "
            f"@ {entry_price:.2f} (stop: {stop_loss:.2f}, target: {take_profit:.2f})"
        )

        try:
            # Fetch current market price for bracket order validation
            # Critical: Alpaca validates bracket prices against their internal quote prices
            # We need to use the same price to avoid validation errors
            current_market_price = None

            # Try to get current price from OrderManager's market data client
            if self.order_manager and hasattr(self.order_manager, "client"):
                try:
                    # Use Alpaca's market data client for most accurate price
                    from src.data_sources.sources.market.alpaca_market_data import (
                        AlpacaMarketData,
                    )

                    market_data = AlpacaMarketData()

                    # Try latest trade first
                    trade = market_data.get_latest_trade(ticker)
                    if trade and "trade" in trade and trade["trade"].get("p"):
                        current_market_price = float(trade["trade"]["p"])
                        logger.info(
                            f"Got latest trade price for {ticker}: ${current_market_price:.2f}"
                        )
                    else:
                        # Fallback to quote mid-price
                        quote = market_data.get_latest_quote(ticker)
                        if quote and "quote" in quote:
                            bid = quote["quote"].get("bp")
                            ask = quote["quote"].get("ap")
                            if bid and ask and bid > 0 and ask > 0:
                                current_market_price = round((float(bid) + float(ask)) / 2, 2)
                                logger.info(
                                    f"Got quote mid-price for {ticker}: ${current_market_price:.2f}"
                                )
                except Exception as e:
                    logger.warning(f"Could not fetch current price from Alpaca market data: {e}")

            # Fallback to UnifiedPriceFetcher if Alpaca failed
            if current_market_price is None and PRICE_FETCHER_AVAILABLE:
                try:
                    price_fetcher = UnifiedPriceFetcher()
                    fetched_price = price_fetcher.get_current_price(ticker, use_cache=False)
                    # Only use if not the fallback default price
                    if fetched_price != DEFAULT_FALLBACK_PRICE:
                        current_market_price = fetched_price
                        logger.info(
                            f"Got price from UnifiedPriceFetcher: ${current_market_price:.2f}"
                        )
                    else:
                        logger.warning(
                            f"UnifiedPriceFetcher returned default fallback price ${fetched_price:.2f} - not using"
                        )
                except Exception as e:
                    logger.error(f"UnifiedPriceFetcher failed with exception: {e}", exc_info=True)

            # Recalculate bracket prices using current market price if available
            if current_market_price and current_market_price > 0 and signal.lower() == "buy":
                entry_price = round(current_market_price, 2)
                stop_loss = round(current_market_price * (1 - self.stop_loss_pct), 2)
                take_profit = round(current_market_price * (1 + self.take_profit_pct), 2)

                logger.info(
                    f"Recalculated bracket prices using current market price ${current_market_price:.2f}: "
                    f"entry=${entry_price:.2f}, stop=${stop_loss:.2f} (-{self.stop_loss_pct*100}%), "
                    f"target=${take_profit:.2f} (+{self.take_profit_pct*100}%)"
                )
            else:
                logger.warning(
                    f"Using suggestion prices for {ticker} (could not fetch current market price) - "
                    f"may cause validation errors during off-hours"
                )

            # Check if SELL signal - need to verify we have a position before allowing
            if signal.lower() == "sell":
                # Check if we have a position in this ticker
                has_position = False
                position_qty = 0

                if self.order_manager and hasattr(self.order_manager, "get_positions"):
                    try:
                        positions = self.order_manager.get_positions()
                        position = next((p for p in positions if p["symbol"] == ticker), None)

                        if position and position["qty"] > 0:
                            has_position = True
                            position_qty = int(position["qty"])
                            logger.info(f"Found position: {position_qty} shares of {ticker}")
                    except Exception as e:
                        logger.warning(f"Could not check positions: {e}")

                # If no position, reject SELL to prevent short selling
                if not has_position:
                    log_msg = f"SELL signal rejected for {ticker} - no position held (prevents short selling)"
                    logger.warning(log_msg)
                    user_msg = (
                        _MSG.get("execution.sell_no_position", ticker=ticker)
                        if MESSAGE_LOADER_AVAILABLE
                        else f"SELL signal rejected: No position in {ticker}. Short selling not supported."
                    )
                    return OrderResult(
                        success=False,
                        entry_order_id=None,
                        stop_order_id=None,
                        target_order_id=None,
                        ticker=ticker,
                        quantity=quantity,
                        filled_price=None,
                        message=user_msg,
                        error="No position - short selling not supported",
                    )

                # Verify quantity doesn't exceed position
                if quantity > position_qty:
                    log_msg = (
                        f"SELL quantity {quantity} exceeds position {position_qty} for {ticker}"
                    )
                    logger.warning(log_msg)
                    user_msg = (
                        _MSG.get(
                            "execution.sell_exceeds_position",
                            qty=quantity,
                            position_qty=position_qty,
                        )
                        if MESSAGE_LOADER_AVAILABLE
                        else f"SELL quantity ({quantity}) exceeds position ({position_qty} shares)"
                    )
                    return OrderResult(
                        success=False,
                        entry_order_id=None,
                        stop_order_id=None,
                        target_order_id=None,
                        ticker=ticker,
                        quantity=quantity,
                        filled_price=None,
                        message=user_msg,
                        error="Insufficient position",
                    )

                logger.info(
                    f"SELL signal approved - have {position_qty} shares of {ticker}, selling {quantity}"
                )

            if not self.order_manager:
                # Stub mode: Return mock order result
                return self._create_stub_result(ticker, quantity, entry_price, signal)

            # Check if we're during market hours
            is_market_hours = self._is_market_hours()

            if not is_market_hours:
                msg = (
                    _MSG.get("execution.market_closed_warning")
                    if MESSAGE_LOADER_AVAILABLE
                    else "⚠️  Market is CLOSED (weekend/off-hours). Bracket orders may fail validation during off-hours."
                )
                logger.warning(msg)

            # Execute via OrderManager (only BUY orders reach here)
            # AlpacaOrderManager.place_bracket_order handles entry + stop + target
            # Note: Uses different parameter names than generic OrderManager
            try:
                order_data = self.order_manager.place_bracket_order(
                    symbol=ticker,
                    qty=quantity,
                    side="buy",  # Always BUY (SELL signals filtered above)
                    entry_limit_price=None,  # Market order
                    take_profit_price=take_profit,
                    stop_loss_price=stop_loss,
                    time_in_force="gtc",  # Good-til-canceled
                )

                # Check for errors (AlpacaOrderManager returns status='error')
                if order_data.get("status") == "error":
                    # Preserve error data for analysis before raising
                    error_data = {
                        "status": "error",
                        "message": order_data.get("message", "Unknown error"),
                        "error_code": order_data.get("error_code"),
                        "status_code": order_data.get("status_code"),
                    }
                    raise Exception(order_data.get("message", "Unknown error"))

            except Exception as e:
                # Check if this is an off-hours bracket validation error using error codes
                # error_data was set above if the error came from order_manager
                # If not set, create minimal error_data for analysis
                if "error_data" not in locals():
                    error_data = {
                        "status": "error",
                        "message": str(e),
                        "error_code": None,
                        "status_code": None,
                    }

                is_bracket_error = self._is_bracket_validation_error(error_data)

                if not is_market_hours and is_bracket_error:
                    msg = (
                        _MSG.get(
                            "execution.bracket_validation_failed",
                            error=str(e),
                            error_code=error_data.get("error_code", "N/A"),
                            status_code=error_data.get("status_code", "N/A"),
                        )
                        if MESSAGE_LOADER_AVAILABLE
                        else f"❌ Bracket order validation failed (off-hours): {e}\nError code: {error_data.get('error_code', 'N/A')}, Status: {error_data.get('status_code', 'N/A')}\n🔄 Attempting fallback: simple market order without brackets..."
                    )
                    logger.warning(msg)

                    # Fallback: Place simple market order for demo/testing purposes
                    try:
                        fallback_order = self.order_manager.place_market_order(
                            symbol=ticker, qty=quantity, side="buy"
                        )

                        if fallback_order.get("status") == "error":
                            raise Exception(fallback_order.get("message", "Unknown error"))

                        fallback_order_id = fallback_order.get("order_id") or fallback_order.get(
                            "id"
                        )

                        msg = (
                            _MSG.get(
                                "execution.fallback_order_success",
                                order_id=fallback_order_id,
                                target=take_profit,
                                stop=stop_loss,
                            )
                            if MESSAGE_LOADER_AVAILABLE
                            else f"✅ Simple market order placed: {fallback_order_id}\n⚠️  NOTE: Stop-loss and take-profit NOT set (bracket order failed).\nManual risk management required!\nTarget: ${take_profit:.2f}, Stop: ${stop_loss:.2f}"
                        )
                        logger.info(msg)

                        user_msg = (
                            _MSG.get(
                                "execution.fallback_order_warning",
                                target=take_profit,
                                stop=stop_loss,
                            )
                            if MESSAGE_LOADER_AVAILABLE
                            else f"⚠️  Market order placed WITHOUT brackets (off-hours fallback). Target: ${take_profit:.2f}, Stop: ${stop_loss:.2f} (NOT automatically set). Manual risk management required!"
                        )
                        return OrderResult(
                            success=True,
                            entry_order_id=fallback_order_id,
                            stop_order_id=None,  # Not set
                            target_order_id=None,  # Not set
                            ticker=ticker,
                            quantity=quantity,
                            filled_price=None,
                            message=user_msg,
                            error=None,
                        )

                    except Exception as fallback_error:
                        logger.error(f"❌ Fallback market order also failed: {fallback_error}")
                        user_msg = (
                            _MSG.get("execution.fallback_order_failed")
                            if MESSAGE_LOADER_AVAILABLE
                            else "Both bracket and fallback market orders failed during off-hours"
                        )
                        return OrderResult(
                            success=False,
                            entry_order_id=None,
                            stop_order_id=None,
                            target_order_id=None,
                            ticker=ticker,
                            quantity=quantity,
                            filled_price=None,
                            message=user_msg,
                            error=f"Bracket error: {e}; Fallback error: {fallback_error}",
                        )
                else:
                    # Re-raise if it's not an off-hours issue
                    raise

            # Extract order IDs (AlpacaOrderManager uses 'order_id' not 'id')
            entry_order_id = order_data.get("order_id")

            # For now, AlpacaOrderManager doesn't return leg IDs separately
            # The bracket order is created but legs managed by Alpaca
            stop_order_id = f"{entry_order_id}_stop" if entry_order_id else None
            target_order_id = f"{entry_order_id}_target" if entry_order_id else None

            result = OrderResult(
                success=True,
                entry_order_id=entry_order_id,
                stop_order_id=stop_order_id,
                target_order_id=target_order_id,
                ticker=ticker,
                quantity=quantity,
                filled_price=None,  # Will be updated when filled
                message=f"Bracket order placed: {signal} {quantity} {ticker} (mode: {order_data.get('mode', 'unknown')})",
            )

            logger.info(
                f"✅ Execution complete: {ticker} "
                f"entry_id={entry_order_id}, stop_id={stop_order_id}, target_id={target_order_id}"
            )

            return result

        except Exception as e:
            # Log full error details at DEBUG level only (not shown to users)
            logger.debug(f"Execution error for {ticker}: {e}", exc_info=True)

            # Translate API errors to user-friendly messages
            user_message, user_error = self._translate_api_error(
                str(e), ticker, entry_price, stop_loss, take_profit
            )

            return OrderResult(
                success=False,
                ticker=ticker,
                quantity=quantity,
                message=user_message,
                error=user_error,
            )

    def _translate_api_error(
        self, error_str: str, ticker: str, entry: float, stop: float, target: float
    ) -> Tuple[str, str]:
        """
        Translate Alpaca API errors into user-friendly messages.

        Args:
            error_str: The raw error string
            ticker: Stock ticker
            entry: Entry price
            stop: Stop loss price
            target: Take profit price

        Returns:
            Tuple of (user_message, user_error)
        """
        import json
        import re

        # Try to parse JSON error from Alpaca
        try:
            # Extract JSON if embedded in error string
            json_match = re.search(r"\{.*\}", error_str)
            if json_match:
                error_data = json.loads(json_match.group())
                code = error_data.get("code")
                base_price = error_data.get("base_price")
                api_message = error_data.get("message", "")

                # Bracket order validation errors (42210000 series)
                if code == 42210000:
                    if "stop_loss" in api_message and "must be <=" in api_message:
                        return (
                            f"Order rejected: Stop loss price (${stop:.2f}) doesn't match market price",
                            f"The market is closed and price data may be stale. "
                            f"Alpaca expects stop=${base_price} but we calculated ${stop:.2f}. "
                            f"Try again during market hours (9:30 AM - 4:00 PM ET) for accurate pricing.",
                        )
                    elif "take_profit" in api_message and "must be >=" in api_message:
                        return (
                            f"Order rejected: Take profit price (${target:.2f}) doesn't match market price",
                            f"The market is closed and price data may be stale. "
                            f"Alpaca expects target>=${base_price} but we calculated ${target:.2f}. "
                            f"Try again during market hours (9:30 AM - 4:00 PM ET) for accurate pricing.",
                        )

                # Insufficient buying power
                if "buying power" in api_message.lower() or "insufficient" in api_message.lower():
                    return (
                        "Order rejected: Not enough cash available",
                        "Check your account balance and reduce the order size.",
                    )

                # Invalid symbol
                if "symbol" in api_message.lower() and (
                    "invalid" in api_message.lower() or "not found" in api_message.lower()
                ):
                    return (
                        f"Order rejected: {ticker} is not a valid or tradeable symbol",
                        "Double-check the ticker symbol. It may be delisted or not supported by Alpaca.",
                    )

                # Market hours
                if "market" in api_message.lower() and "closed" in api_message.lower():
                    return (
                        "Order rejected: Market is closed",
                        "Regular market hours: 9:30 AM - 4:00 PM ET. Your order may execute when the market opens.",
                    )

        except (json.JSONDecodeError, AttributeError):
            pass

        # Generic fallback
        return (
            f"Order failed for {ticker}",
            "Please try again during market hours or contact support if the issue persists.",
        )

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully
        """
        if not self.order_manager:
            msg = (
                _MSG.get("execution.cancel_no_manager")
                if MESSAGE_LOADER_AVAILABLE
                else "Cannot cancel - no OrderManager (stub mode)"
            )
            logger.warning(msg)
            return False

        try:
            # OrderManager should have cancel method
            # (or use broker client directly)
            self.order_manager.broker.cancel_order_by_id(order_id)
            msg = (
                _MSG.get("execution.order_cancelled", order_id=order_id)
                if MESSAGE_LOADER_AVAILABLE
                else f"Order cancelled: {order_id}"
            )
            logger.info(msg)
            return True

        except Exception as e:
            msg = (
                _MSG.get("execution.cancel_failed", order_id=order_id, error=str(e))
                if MESSAGE_LOADER_AVAILABLE
                else f"Failed to cancel order {order_id}: {e}"
            )
            logger.error(msg)
            return False

    async def get_order_status(self, order_id: str) -> dict:
        """
        Get current status of an order.

        Args:
            order_id: Order ID

        Returns:
            Dict with order status details
        """
        if not self.order_manager:
            msg = (
                _MSG.get("execution.status_no_manager")
                if MESSAGE_LOADER_AVAILABLE
                else "Cannot get status - no OrderManager (stub mode)"
            )
            logger.warning(msg)
            return {"status": "unknown", "error": "No OrderManager"}

        try:
            # Query broker for order status
            order = self.order_manager.broker.get_order_by_id(order_id)

            return {
                "id": order.id,
                "status": order.status.value,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0.0,
                "filled_avg_price": (
                    float(order.filled_avg_price) if order.filled_avg_price else None
                ),
            }

        except Exception as e:
            msg = (
                _MSG.get("execution.status_failed", order_id=order_id, error=str(e))
                if MESSAGE_LOADER_AVAILABLE
                else f"Failed to get order status {order_id}: {e}"
            )
            logger.error(msg)
            return {"status": "error", "error": str(e)}

    async def modify_order(
        self, order_id: str, new_quantity: Optional[int] = None, new_price: Optional[float] = None
    ) -> bool:
        """
        Modify an existing order.

        MVP: Not implemented (Alpaca has limited modify support).
        Alternative: Cancel and replace.

        Args:
            order_id: Order ID to modify
            new_quantity: New quantity (if changing)
            new_price: New limit price (if changing)

        Returns:
            True if modified successfully
        """
        logger.warning("Order modification not implemented in MVP - use cancel/replace pattern")
        return False

    def _create_stub_result(
        self, ticker: str, quantity: int, price: float, signal: str
    ) -> OrderResult:
        """
        Create stub order result for testing without OrderManager.

        Args:
            ticker: Stock ticker
            quantity: Number of shares
            price: Entry price
            signal: buy or sell

        Returns:
            Mock OrderResult
        """
        # Generate unique stub ID for each call
        stub_id = str(uuid.uuid4())[:8]

        return OrderResult(
            success=True,
            entry_order_id=f"stub_entry_{stub_id}",
            stop_order_id=f"stub_stop_{stub_id}",
            target_order_id=f"stub_target_{stub_id}",
            ticker=ticker,
            quantity=quantity,
            filled_price=price,
            message=f"[STUB] {signal.upper()} {quantity} {ticker} @ ${price:.2f}",
        )
