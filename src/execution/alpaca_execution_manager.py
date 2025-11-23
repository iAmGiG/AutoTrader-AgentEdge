"""
AlpacaExecutionManager - Executes trades via Alpaca broker.

Integrates existing OrderManager into the plugin architecture.
"""

import logging
from typing import Optional

from core.interfaces import ExecutionManager
from core.models import TradeSuggestion, OrderResult, TradeDecision, TimeInForce

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

    def __init__(self, order_manager: Optional[object] = None,
                 stop_loss_pct: float = 0.05, take_profit_pct: float = 0.08):
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
            logger.info("AlpacaExecutionManager initialized with OrderManager")
        else:
            logger.warning("AlpacaExecutionManager initialized without OrderManager (stub mode)")

        logger.info(f"Using strategy config: stop_loss={stop_loss_pct*100}%, take_profit={take_profit_pct*100}%")

        # Log price fetcher availability
        if PRICE_FETCHER_AVAILABLE:
            logger.info("UnifiedPriceFetcher available - will fetch current prices before execution")
        else:
            logger.warning("UnifiedPriceFetcher NOT available - will use suggestion prices")

    def _is_market_hours(self) -> bool:
        """
        Check if current time is during regular market hours (9:30 AM - 4:00 PM ET, Mon-Fri).

        Returns:
            True if during market hours, False otherwise
        """
        try:
            from datetime import datetime
            import pytz

            et_tz = pytz.timezone('America/New_York')
            now_et = datetime.now(et_tz)

            # Check if weekend
            if now_et.weekday() >= 5:  # 5=Saturday, 6=Sunday
                return False

            # Check if within market hours (9:30 AM - 4:00 PM ET)
            market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

            return market_open <= now_et <= market_close

        except Exception as e:
            logger.warning(f"Could not determine market hours: {e}")
            return False  # Assume off-hours if we can't determine

    async def execute_trade(
        self,
        suggestion: TradeSuggestion,
        decision: Optional[TradeDecision] = None
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
            if self.order_manager and hasattr(self.order_manager, 'client'):
                try:
                    # Use Alpaca's market data client for most accurate price
                    from src.data_sources.sources.market.alpaca_market_data import AlpacaMarketData
                    market_data = AlpacaMarketData()

                    # Try latest trade first
                    trade = market_data.get_latest_trade(ticker)
                    if trade and 'price' in trade and trade['price'] > 0:
                        current_market_price = float(trade['price'])
                        logger.info(
                            f"Got latest trade price for {ticker}: ${current_market_price:.2f}")
                    else:
                        # Fallback to quote mid-price
                        quote = market_data.get_latest_quote(ticker)
                        if quote and 'bid_price' in quote and 'ask_price' in quote:
                            bid = float(quote['bid_price'])
                            ask = float(quote['ask_price'])
                            if bid > 0 and ask > 0:
                                current_market_price = round((bid + ask) / 2, 2)
                                logger.info(
                                    f"Got quote mid-price for {ticker}: ${current_market_price:.2f}")
                except Exception as e:
                    logger.warning(f"Could not fetch current price from Alpaca market data: {e}")

            # Fallback to UnifiedPriceFetcher if Alpaca failed
            if current_market_price is None and PRICE_FETCHER_AVAILABLE:
                try:
                    price_fetcher = UnifiedPriceFetcher()
                    fetched_price = price_fetcher.get_current_price(ticker, use_cache=False)
                    # Only use if not the fallback default price
                    if fetched_price != 100.0:
                        current_market_price = fetched_price
                        logger.info(
                            f"Got price from UnifiedPriceFetcher: ${current_market_price:.2f}")
                except Exception as e:
                    logger.warning(f"UnifiedPriceFetcher failed: {e}")

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

                if self.order_manager and hasattr(self.order_manager, 'get_positions'):
                    try:
                        positions = self.order_manager.get_positions()
                        position = next((p for p in positions if p['symbol'] == ticker), None)

                        if position and position['qty'] > 0:
                            has_position = True
                            position_qty = int(position['qty'])
                            logger.info(f"Found position: {position_qty} shares of {ticker}")
                    except Exception as e:
                        logger.warning(f"Could not check positions: {e}")

                # If no position, reject SELL to prevent short selling
                if not has_position:
                    logger.warning(
                        f"SELL signal rejected for {ticker} - no position held (prevents short selling)")
                    return OrderResult(
                        success=False,
                        entry_order_id=None,
                        stop_order_id=None,
                        target_order_id=None,
                        ticker=ticker,
                        quantity=quantity,
                        filled_price=None,
                        message=f"SELL signal rejected: No position in {ticker}. Short selling not supported.",
                        error="No position - short selling not supported"
                    )

                # Verify quantity doesn't exceed position
                if quantity > position_qty:
                    logger.warning(
                        f"SELL quantity {quantity} exceeds position {position_qty} for {ticker}")
                    return OrderResult(
                        success=False,
                        entry_order_id=None,
                        stop_order_id=None,
                        target_order_id=None,
                        ticker=ticker,
                        quantity=quantity,
                        filled_price=None,
                        message=f"SELL quantity ({quantity}) exceeds position ({position_qty} shares)",
                        error="Insufficient position"
                    )

                logger.info(
                    f"SELL signal approved - have {position_qty} shares of {ticker}, selling {quantity}")

            if not self.order_manager:
                # Stub mode: Return mock order result
                return self._create_stub_result(ticker, quantity, entry_price, signal)

            # Check if we're during market hours
            is_market_hours = self._is_market_hours()

            if not is_market_hours:
                logger.warning(
                    f"⚠️  Market is CLOSED (weekend/off-hours). "
                    f"Bracket orders may fail validation during off-hours."
                )

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
                    time_in_force="gtc"  # Good-til-canceled
                )

                # Check for errors (AlpacaOrderManager returns status='error')
                if order_data.get('status') == 'error':
                    raise Exception(order_data.get('message', 'Unknown error'))

            except Exception as e:
                error_msg = str(e).lower()

                # Check if this is an off-hours validation error
                if not is_market_hours and ('limit_price' in error_msg or 'base_price' in error_msg or 'take_profit' in error_msg):
                    logger.warning(
                        f"❌ Bracket order validation failed (off-hours): {e}\n"
                        f"   🔄 Attempting fallback: simple market order without brackets..."
                    )

                    # Fallback: Place simple market order for demo/testing purposes
                    try:
                        fallback_order = self.order_manager.place_market_order(
                            symbol=ticker,
                            qty=quantity,
                            side="buy"
                        )

                        if fallback_order.get('status') == 'error':
                            raise Exception(fallback_order.get('message', 'Unknown error'))

                        fallback_order_id = fallback_order.get('order_id') or fallback_order.get('id')

                        logger.info(
                            f"✅ Simple market order placed: {fallback_order_id}\n"
                            f"   ⚠️  NOTE: Stop-loss and take-profit NOT set (bracket order failed).\n"
                            f"   Manual risk management required!\n"
                            f"   Target: ${take_profit:.2f}, Stop: ${stop_loss:.2f}"
                        )

                        return OrderResult(
                            success=True,
                            entry_order_id=fallback_order_id,
                            stop_order_id=None,  # Not set
                            target_order_id=None,  # Not set
                            ticker=ticker,
                            quantity=quantity,
                            filled_price=None,
                            message=(
                                f"⚠️  Market order placed WITHOUT brackets (off-hours fallback). "
                                f"Target: ${take_profit:.2f}, Stop: ${stop_loss:.2f} (NOT automatically set). "
                                f"Manual risk management required!"
                            ),
                            error=None
                        )

                    except Exception as fallback_error:
                        logger.error(f"❌ Fallback market order also failed: {fallback_error}")
                        return OrderResult(
                            success=False,
                            entry_order_id=None,
                            stop_order_id=None,
                            target_order_id=None,
                            ticker=ticker,
                            quantity=quantity,
                            filled_price=None,
                            message=f"Both bracket and fallback market orders failed during off-hours",
                            error=f"Bracket error: {e}; Fallback error: {fallback_error}"
                        )
                else:
                    # Re-raise if it's not an off-hours issue
                    raise

            # Extract order IDs (AlpacaOrderManager uses 'order_id' not 'id')
            entry_order_id = order_data.get('order_id')

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
                message=f"Bracket order placed: {signal} {quantity} {ticker} (mode: {order_data.get('mode', 'unknown')})"
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
                str(e), ticker, entry_price, stop_loss, take_profit)

            return OrderResult(
                success=False,
                ticker=ticker,
                quantity=quantity,
                message=user_message,
                error=user_error
            )

    def _translate_api_error(self, error_str: str, ticker: str, entry: float, stop: float, target: float) -> tuple:
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
            json_match = re.search(r'\{.*\}', error_str)
            if json_match:
                error_data = json.loads(json_match.group())
                code = error_data.get('code')
                base_price = error_data.get('base_price')
                api_message = error_data.get('message', '')

                # Bracket order validation errors (42210000 series)
                if code == 42210000:
                    if 'stop_loss' in api_message and 'must be <=' in api_message:
                        return (
                            f"Order rejected: Stop loss price (${stop:.2f}) doesn't match market price",
                            f"The market is closed and price data may be stale. "
                            f"Alpaca expects stop=${base_price} but we calculated ${stop:.2f}. "
                            f"Try again during market hours (9:30 AM - 4:00 PM ET) for accurate pricing."
                        )
                    elif 'take_profit' in api_message and 'must be >=' in api_message:
                        return (
                            f"Order rejected: Take profit price (${target:.2f}) doesn't match market price",
                            f"The market is closed and price data may be stale. "
                            f"Alpaca expects target>=${base_price} but we calculated ${target:.2f}. "
                            f"Try again during market hours (9:30 AM - 4:00 PM ET) for accurate pricing."
                        )

                # Insufficient buying power
                if 'buying power' in api_message.lower() or 'insufficient' in api_message.lower():
                    return (
                        f"Order rejected: Not enough cash available",
                        f"Check your account balance and reduce the order size."
                    )

                # Invalid symbol
                if 'symbol' in api_message.lower() and ('invalid' in api_message.lower() or 'not found' in api_message.lower()):
                    return (
                        f"Order rejected: {ticker} is not a valid or tradeable symbol",
                        f"Double-check the ticker symbol. It may be delisted or not supported by Alpaca."
                    )

                # Market hours
                if 'market' in api_message.lower() and 'closed' in api_message.lower():
                    return (
                        f"Order rejected: Market is closed",
                        f"Regular market hours: 9:30 AM - 4:00 PM ET. Your order may execute when the market opens."
                    )

        except (json.JSONDecodeError, AttributeError):
            pass

        # Generic fallback
        return (
            f"Order failed for {ticker}",
            f"Please try again during market hours or contact support if the issue persists."
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
            logger.warning("Cannot cancel - no OrderManager (stub mode)")
            return False

        try:
            # OrderManager should have cancel method
            # (or use broker client directly)
            self.order_manager.broker.cancel_order_by_id(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
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
            logger.warning("Cannot get status - no OrderManager (stub mode)")
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
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            }

        except Exception as e:
            logger.error(f"Failed to get order status {order_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def modify_order(
        self,
        order_id: str,
        new_quantity: Optional[int] = None,
        new_price: Optional[float] = None
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
        self,
        ticker: str,
        quantity: int,
        price: float,
        signal: str
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
        return OrderResult(
            success=True,
            entry_order_id="stub_entry_123",
            stop_order_id="stub_stop_123",
            target_order_id="stub_target_123",
            ticker=ticker,
            quantity=quantity,
            filled_price=price,
            message=f"[STUB] {signal.upper()} {quantity} {ticker} @ ${price:.2f}"
        )
