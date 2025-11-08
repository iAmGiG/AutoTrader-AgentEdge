"""
ExecutionManager interface.

Defines the contract for executing trades and managing order lifecycle.
Integrates with existing OrderManager and broker APIs.
"""

from abc import ABC, abstractmethod
from typing import Optional
from ..models import TradeSuggestion, OrderResult, TradeDecision


class ExecutionManager(ABC):
    """
    Abstract interface for trade execution.

    Responsibilities:
    - Place orders (market, limit, stop, bracket)
    - Track order lifecycle (pending, filled, cancelled)
    - Integrate with existing OrderManager
    - Enforce order type (GTC by default)
    """

    @abstractmethod
    async def execute_trade(
        self,
        suggestion: TradeSuggestion,
        decision: Optional[TradeDecision] = None
    ) -> OrderResult:
        """
        Execute a trade based on suggestion and user decision.

        Args:
            suggestion: The trade suggestion
            decision: User's decision (may contain modifications)

        Returns:
            OrderResult with order IDs and execution details

        This should:
        1. Apply any modifications from decision
        2. Create bracket order (entry + stop + target)
        3. Enforce GTC time in force
        4. Place orders via broker API
        5. Return order IDs for tracking
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully, False otherwise
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict:
        """
        Get current status of an order.

        Args:
            order_id: Order ID

        Returns:
            Dict with order status details
        """
        pass

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        new_quantity: Optional[int] = None,
        new_price: Optional[float] = None
    ) -> bool:
        """
        Modify an existing order.

        Args:
            order_id: Order ID to modify
            new_quantity: New quantity (if changing)
            new_price: New limit price (if changing)

        Returns:
            True if modified successfully, False otherwise
        """
        pass
