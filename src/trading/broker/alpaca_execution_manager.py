"""
AlpacaExecutionManager - Executes trades via Alpaca broker.

Integrates existing OrderManager into the plugin architecture.
Refactored to use extracted components (Issue #441).
"""

import logging
import uuid
from typing import Optional

# Import extracted components
from .api_error_translator import APIErrorTranslator
from .validators.bracket_validator import BracketOrderValidator
from src.core.interfaces import ExecutionManager
from src.core.models import OrderResult, OrderType, TradeDecision, TradeSuggestion
from src.utils.market_hours import is_market_hours

# Import message loader for user-facing messages
try:
    from config_defaults.message_loader import MessageLoader

    _MSG = MessageLoader()
    MESSAGE_LOADER_AVAILABLE = True
except ImportError:
    MESSAGE_LOADER_AVAILABLE = False
    logging.warning("MessageLoader not available - using fallback messages")

# Import price fetcher for current market prices
try:
    from src.trading.utils.unified_price_fetcher import UnifiedPriceFetcher

    PRICE_FETCHER_AVAILABLE = True
except ImportError:
    try:
        from ..utils.unified_price_fetcher import UnifiedPriceFetcher

        PRICE_FETCHER_AVAILABLE = True
    except ImportError:
        PRICE_FETCHER_AVAILABLE = False
        logging.warning("UnifiedPriceFetcher not available - will use suggestion prices")

# Default fallback price when data unavailable
DEFAULT_FALLBACK_PRICE = 100.0

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
            else (
                f"Using strategy config: stop_loss={stop_loss_pct * 100}%, "
                f"take_profit={take_profit_pct * 100}%"
            )
        )
        logger.info(msg)

        # Log price fetcher availability
        if PRICE_FETCHER_AVAILABLE:
            logger.info(
                "UnifiedPriceFetcher available - will fetch current prices before execution"
            )
        else:
            logger.warning("UnifiedPriceFetcher NOT available - will use suggestion prices")

    async def execute_trade(
        self, suggestion: TradeSuggestion, decision: Optional[TradeDecision] = None
    ) -> OrderResult:
        """
        Execute trade based on suggestion and user decision.

        High-level orchestration method that delegates to focused helper methods
        for better testability and maintainability.

        Args:
            suggestion: The trade suggestion
            decision: User's decision (may contain modifications)

        Returns:
            OrderResult with order IDs and execution details
        """
        try:
            # Step 1: Prepare trade parameters
            ticker, signal, quantity, entry_price, stop_loss, take_profit = self._prepare_trade(
                suggestion, decision
            )

            # Step 2: Fetch current market price
            current_market_price = await self._fetch_current_price(ticker)

            # Step 3: Recalculate bracket prices if needed
            entry_price, stop_loss, take_profit = self._recalculate_bracket_prices(
                signal,
                suggestion.order_type,
                current_market_price,
                entry_price,
                stop_loss,
                take_profit,
            )

            # Step 4: Validate SELL signal if applicable
            if signal.lower() == "sell":
                validation_result = self._validate_sell_signal(ticker, quantity)
                if not validation_result["success"]:
                    return validation_result["order_result"]

            # Step 5: Place the order
            return await self._place_order(
                ticker, quantity, signal, entry_price, stop_loss, take_profit, suggestion.order_type
            )

        except Exception as e:
            # Log full error details at DEBUG level only
            logger.debug(f"Execution error for {suggestion.ticker}: {e}", exc_info=True)

            # Translate API errors to user-friendly messages
            user_message, user_error = APIErrorTranslator.translate(
                str(e),
                suggestion.ticker,
                suggestion.entry_price,
                suggestion.stop_loss,
                suggestion.take_profit,
            )

            return OrderResult(
                success=False,
                ticker=suggestion.ticker,
                quantity=suggestion.recommended_quantity,
                message=user_message,
                error=user_error,
            )

    def _prepare_trade(
        self, suggestion: TradeSuggestion, decision: Optional[TradeDecision] = None
    ) -> tuple:
        """
        Extract and prepare trade parameters from suggestion and user decision.

        Args:
            suggestion: The trade suggestion
            decision: Optional user modifications

        Returns:
            Tuple of (ticker, signal, quantity, entry_price, stop_loss, take_profit)
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

        return ticker, signal, quantity, entry_price, stop_loss, take_profit

    async def _fetch_current_price(self, ticker: str) -> Optional[float]:
        """
        Fetch current market price using UnifiedPriceFetcher.

        Args:
            ticker: Stock symbol

        Returns:
            Current market price or None if unavailable
        """
        current_market_price = None

        # Try to get current price from OrderManager's market data client
        if self.order_manager and hasattr(self.order_manager, "client"):
            try:
                from src.data_sources.sources.market.alpaca_market_data import AlpacaMarketData

                market_data = AlpacaMarketData()

                # Try latest trade first
                trade = market_data.get_latest_trade(ticker)
                if trade and "trade" in trade and trade["trade"].get("p"):
                    current_market_price = float(trade["trade"]["p"])
                    logger.info(f"Got latest trade price for {ticker}: ${current_market_price:.2f}")
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
                    logger.info(f"Got price from UnifiedPriceFetcher: ${current_market_price:.2f}")
                else:
                    logger.warning(
                        f"UnifiedPriceFetcher returned default fallback price "
                        f"${fetched_price:.2f} - not using"
                    )
            except Exception as e:
                logger.error(f"UnifiedPriceFetcher failed with exception: {e}", exc_info=True)

        return current_market_price

    def _recalculate_bracket_prices(
        self,
        signal: str,
        order_type,
        current_market_price: Optional[float],
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> tuple:
        """
        Recalculate bracket prices based on signal and market price.

        For LIMIT orders (pullback/breakout), preserves calculated prices.
        For MARKET orders, recalculates based on current market price.

        Args:
            signal: BUY or SELL
            order_type: OrderType enum value
            current_market_price: Current market price if available
            entry_price: Original entry price
            stop_loss: Original stop loss
            take_profit: Original take profit

        Returns:
            Tuple of (entry_price, stop_loss, take_profit)
        """
        is_limit_order = order_type == OrderType.LIMIT

        # For LIMIT orders (pullback/breakout), preserve the calculated entry price
        # For MARKET orders, recalculate based on current market price
        if is_limit_order:
            # Preserve pullback/breakout entry price - don't recalculate
            logger.info(
                f"LIMIT order: Using pullback/breakout entry price "
                f"${entry_price:.2f} (stop=${stop_loss:.2f}, "
                f"target=${take_profit:.2f})"
            )
        elif current_market_price and current_market_price > 0 and signal.lower() == "buy":
            # MARKET order: recalculate bracket prices using current market price
            entry_price = round(current_market_price, 2)
            stop_loss = round(current_market_price * (1 - self.stop_loss_pct), 2)
            take_profit = round(current_market_price * (1 + self.take_profit_pct), 2)

            sl_pct = self.stop_loss_pct * 100
            tp_pct = self.take_profit_pct * 100
            logger.info(
                f"MARKET order: Recalculated bracket prices using "
                f"${current_market_price:.2f}: entry=${entry_price:.2f}, "
                f"stop=${stop_loss:.2f} (-{sl_pct}%), "
                f"target=${take_profit:.2f} (+{tp_pct}%)"
            )
        else:
            logger.warning(
                "Using suggestion prices "
                "(could not fetch current market price) - "
                "may cause validation errors during off-hours"
            )

        return entry_price, stop_loss, take_profit

    def _validate_sell_signal(self, ticker: str, quantity: int) -> dict:
        """
        Validate SELL signal to prevent short selling.

        Checks if we have a position and sufficient quantity.

        Args:
            ticker: Stock symbol
            quantity: Quantity to sell

        Returns:
            Dict with keys:
            - success: bool
            - order_result: OrderResult if validation failed
        """
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
            log_msg = (
                f"SELL signal rejected for {ticker} - no position held " "(prevents short selling)"
            )
            logger.warning(log_msg)
            user_msg = (
                _MSG.get("execution.sell_no_position", ticker=ticker)
                if MESSAGE_LOADER_AVAILABLE
                else (
                    f"SELL signal rejected: No position in {ticker}. "
                    "Short selling not supported."
                )
            )
            return {
                "success": False,
                "order_result": OrderResult(
                    success=False,
                    entry_order_id=None,
                    stop_order_id=None,
                    target_order_id=None,
                    ticker=ticker,
                    quantity=quantity,
                    filled_price=None,
                    message=user_msg,
                    error="No position - short selling not supported",
                ),
            }

        # Verify quantity doesn't exceed position
        if quantity > position_qty:
            log_msg = f"SELL quantity {quantity} exceeds position {position_qty} for {ticker}"
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
            return {
                "success": False,
                "order_result": OrderResult(
                    success=False,
                    entry_order_id=None,
                    stop_order_id=None,
                    target_order_id=None,
                    ticker=ticker,
                    quantity=quantity,
                    filled_price=None,
                    message=user_msg,
                    error="Insufficient position",
                ),
            }

        logger.info(
            f"SELL signal approved - have {position_qty} shares of {ticker}, " f"selling {quantity}"
        )
        return {"success": True}

    async def _place_order(
        self,
        ticker: str,
        quantity: int,
        signal: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        order_type,
    ) -> OrderResult:
        """
        Place the actual order via OrderManager.

        Handles bracket orders with fallback to simple market orders during off-hours.

        Args:
            ticker: Stock symbol
            quantity: Quantity to order
            signal: BUY or SELL
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            order_type: OrderType enum value

        Returns:
            OrderResult with order details
        """
        is_limit_order = order_type == OrderType.LIMIT

        if not self.order_manager:
            # Stub mode: Return mock order result
            return self._create_stub_result(ticker, quantity, entry_price, signal)

        # Check if we're during market hours (using centralized utility)
        market_open = is_market_hours()

        if not market_open:
            msg = (
                _MSG.get("execution.market_closed_warning")
                if MESSAGE_LOADER_AVAILABLE
                else (
                    "⚠️  Market is CLOSED (weekend/off-hours). "
                    "Bracket orders may fail validation during off-hours."
                )
            )
            logger.warning(msg)

        # Execute via OrderManager (only BUY orders reach here)
        error_data = None
        try:
            # Issue #344: Use limit entry for pullback/breakout orders
            limit_price = entry_price if is_limit_order else None

            if is_limit_order:
                logger.info(
                    f"Placing LIMIT bracket order: {ticker} @ ${entry_price:.2f} "
                    "(waiting for pullback/breakout price)"
                )
            else:
                logger.info(f"Placing MARKET bracket order: {ticker} (immediate fill)")

            order_data = self.order_manager.place_bracket_order(
                symbol=ticker,
                qty=quantity,
                side="buy",
                entry_limit_price=limit_price,
                take_profit_price=take_profit,
                stop_loss_price=stop_loss,
                time_in_force="gtc",
            )

            # Check for errors
            if order_data.get("status") == "error":
                error_data = {
                    "status": "error",
                    "message": order_data.get("message", "Unknown error"),
                    "error_code": order_data.get("error_code"),
                    "status_code": order_data.get("status_code"),
                }
                raise Exception(order_data.get("message", "Unknown error"))

        except Exception as e:
            if error_data is None:
                error_data = {
                    "status": "error",
                    "message": str(e),
                    "error_code": None,
                    "status_code": None,
                }

            # Use extracted BracketOrderValidator
            is_bracket_error = BracketOrderValidator.is_bracket_validation_error(error_data)

            if not market_open and is_bracket_error:
                # Fallback to simple market order
                return await self._handle_bracket_fallback(
                    ticker, quantity, stop_loss, take_profit, e, error_data
                )
            else:
                # Re-raise if not an off-hours issue
                raise

        # Extract order IDs
        entry_order_id = order_data.get("order_id")
        stop_order_id = f"{entry_order_id}_stop" if entry_order_id else None
        target_order_id = f"{entry_order_id}_target" if entry_order_id else None

        # Issue #344: Include order type and entry price in message
        order_type_str = "LIMIT" if is_limit_order else "MARKET"
        entry_info = f"@ ${entry_price:.2f}" if is_limit_order else "(market)"

        result = OrderResult(
            success=True,
            entry_order_id=entry_order_id,
            stop_order_id=stop_order_id,
            target_order_id=target_order_id,
            ticker=ticker,
            quantity=quantity,
            filled_price=None,
            message=(
                f"{order_type_str} bracket order placed: "
                f"{signal} {quantity} {ticker} {entry_info}"
            ),
        )

        logger.info(
            f"✅ Execution complete: {ticker} "
            f"entry_id={entry_order_id}, stop_id={stop_order_id}, "
            f"target_id={target_order_id}"
        )

        return result

    async def _handle_bracket_fallback(
        self,
        ticker: str,
        quantity: int,
        stop_loss: float,
        take_profit: float,
        original_error: Exception,
        error_data: dict,
    ) -> OrderResult:
        """
        Handle fallback to simple market order when bracket fails off-hours.

        Args:
            ticker: Stock symbol
            quantity: Quantity to order
            stop_loss: Stop loss price (for warning message)
            take_profit: Take profit price (for warning message)
            original_error: The original bracket order error
            error_data: Error data dict

        Returns:
            OrderResult from fallback attempt
        """
        msg = (
            _MSG.get(
                "execution.bracket_validation_failed",
                error=str(original_error),
                error_code=error_data.get("error_code", "N/A"),
                status_code=error_data.get("status_code", "N/A"),
            )
            if MESSAGE_LOADER_AVAILABLE
            else (
                f"❌ Bracket order validation failed (off-hours): {original_error}\n"
                f"Error code: {error_data.get('error_code', 'N/A')}, "
                f"Status: {error_data.get('status_code', 'N/A')}\n"
                "🔄 Attempting fallback: simple market order without brackets..."
            )
        )
        logger.warning(msg)

        try:
            fallback_order = self.order_manager.place_market_order(
                symbol=ticker, qty=quantity, side="buy"
            )

            if fallback_order.get("status") == "error":
                raise Exception(fallback_order.get("message", "Unknown error"))

            fallback_order_id = fallback_order.get("order_id") or fallback_order.get("id")

            user_msg = (
                _MSG.get(
                    "execution.fallback_order_warning",
                    target=take_profit,
                    stop=stop_loss,
                )
                if MESSAGE_LOADER_AVAILABLE
                else (
                    f"⚠️  Market order placed WITHOUT brackets (off-hours fallback). "
                    f"Target: ${take_profit:.2f}, Stop: ${stop_loss:.2f} "
                    "(NOT automatically set). Manual risk management required!"
                )
            )
            return OrderResult(
                success=True,
                entry_order_id=fallback_order_id,
                stop_order_id=None,
                target_order_id=None,
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
                error=f"Bracket error: {original_error}; Fallback error: {fallback_error}",
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
