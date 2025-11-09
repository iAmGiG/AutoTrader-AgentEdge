"""
AlpacaExecutionManager - Executes trades via Alpaca broker.

Integrates existing OrderManager into the plugin architecture.
"""

import logging
from typing import Optional

from core.interfaces import ExecutionManager
from core.models import TradeSuggestion, OrderResult, TradeDecision, TimeInForce


logger = logging.getLogger(__name__)


class AlpacaExecutionManager(ExecutionManager):
    """
    Execute trades via Alpaca broker.

    Integrates with existing OrderManager to place bracket orders
    with entry, stop-loss, and take-profit levels.

    MVP: Simplified to handle basic execution.
    Full order lifecycle management in OrderManager.
    """

    def __init__(self, order_manager: Optional[object] = None):
        """
        Initialize with existing OrderManager.

        Args:
            order_manager: OrderManager instance (from src/trading/order_manager.py)
        """
        self.order_manager = order_manager

        if order_manager:
            logger.info("AlpacaExecutionManager initialized with OrderManager")
        else:
            logger.warning("AlpacaExecutionManager initialized without OrderManager (stub mode)")

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
            if not self.order_manager:
                # Stub mode: Return mock order result
                return self._create_stub_result(ticker, quantity, entry_price, signal)

            # Execute via OrderManager
            # AlpacaOrderManager.place_bracket_order handles entry + stop + target
            # Note: Uses different parameter names than generic OrderManager
            order_data = self.order_manager.place_bracket_order(
                symbol=ticker,
                qty=quantity,
                side="buy" if signal.lower() == "buy" else "sell",
                entry_limit_price=None,  # Market order
                take_profit_price=take_profit,
                stop_loss_price=stop_loss,
                time_in_force="gtc"  # Good-til-canceled
            )

            # Check for errors (AlpacaOrderManager returns status='error')
            if order_data.get('status') == 'error':
                raise Exception(order_data.get('message', 'Unknown error'))

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
            logger.error(f"Execution error for {ticker}: {e}", exc_info=True)

            return OrderResult(
                success=False,
                ticker=ticker,
                quantity=quantity,
                message=f"Execution failed: {e}",
                error=str(e)
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
