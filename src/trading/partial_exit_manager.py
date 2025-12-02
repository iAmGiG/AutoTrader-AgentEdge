#!/usr/bin/env python3
"""
Partial Exit Manager - Multi-Target Position Exits

Issue #248: Implement Partial Position Exits

Manages positions with multiple exit targets:
- Target 1: Partial profit-taking at fixed profit level (e.g., 4-6%)
- Target 2: Trailing stop for remaining position (integrates with #414)

Design:
- Default 50/50 split between targets
- Target 1 uses limit order at profit percentage
- Target 2 leverages TrailingStopManager for dynamic stops
- Per-mode configuration via trading_modes.yaml
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


@dataclass
class ExitTarget:
    """Represents a single exit target within a partial exit strategy."""

    target_number: int  # 1, 2, 3, etc.
    quantity: int  # Shares for this target
    ratio: float  # Percentage of total position (0.0 - 1.0)
    exit_type: str  # "limit" or "trailing"
    exit_price: Optional[float] = None  # For limit orders
    order_id: Optional[str] = None  # Broker order ID
    filled: bool = False  # Whether this target has been hit
    filled_at: Optional[str] = None  # ISO timestamp of fill


@dataclass
class PartialExitState:
    """Track partial exit state for a position."""

    symbol: str
    entry_price: float
    total_quantity: int  # Original position size
    targets: List[ExitTarget]
    stop_price: float  # Initial stop price
    stop_order_id: Optional[str] = None  # Stop order for remaining position
    registered_at: str = None  # ISO timestamp
    last_updated: str = None

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.registered_at is None:
            self.registered_at = now_iso()
        if self.last_updated is None:
            self.last_updated = now_iso()

    def get_remaining_quantity(self) -> int:
        """Calculate quantity remaining after filled targets."""
        filled_qty = sum(target.quantity for target in self.targets if target.filled)
        return self.total_quantity - filled_qty

    def get_filled_targets(self) -> List[ExitTarget]:
        """Get list of targets that have been filled."""
        return [target for target in self.targets if target.filled]

    def get_active_targets(self) -> List[ExitTarget]:
        """Get list of targets that are still active."""
        return [target for target in self.targets if not target.filled]


class PartialExitManager:
    """
    Manages multi-target position exits.

    Issue #248: Implement Partial Position Exits

    Coordinates with TrailingStopManager to provide:
    - Partial profit-taking at fixed levels
    - Trailing stops for remaining position
    - Position state tracking across partial fills
    """

    def __init__(
        self,
        order_manager,
        trailing_stop_manager=None,
        partial_exit_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize partial exit manager.

        Args:
            order_manager: OrderManager instance for broker operations
            trailing_stop_manager: TrailingStopManager for dynamic stops
            partial_exit_config: Configuration dict for partial exits
        """
        self.order_manager = order_manager
        self.trailing_stop_manager = trailing_stop_manager

        # Default configuration if not provided
        self.config = partial_exit_config or {
            "enabled": True,
            "targets": 2,
            "split": [0.5, 0.5],
            "target_1_pct": 0.04,  # 4% profit
            "target_2": "trailing",
        }

        # Track exit states for each position
        self.exit_states: Dict[str, PartialExitState] = {}

        logger.info(
            f"PartialExitManager initialized: enabled={self.config.get('enabled')}, "
            f"targets={self.config.get('targets')}, split={self.config.get('split')}"
        )

    def register_position(
        self,
        symbol: str,
        entry_price: float,
        total_quantity: int,
        stop_price: float,
        stop_order_id: Optional[str] = None,
    ) -> Optional[PartialExitState]:
        """
        Register a new position for partial exit management.

        Args:
            symbol: Ticker symbol
            entry_price: Position entry price
            total_quantity: Total shares/quantity
            stop_price: Initial stop loss price
            stop_order_id: ID of initial stop order (will be replaced)

        Returns:
            PartialExitState if registered, None if disabled/error
        """
        if not self.config.get("enabled", False):
            logger.debug(f"Partial exits disabled, skipping registration for {symbol}")
            return None

        if total_quantity < 2:
            logger.warning(
                f"Position {symbol} too small for partial exits (qty={total_quantity}), "
                "requires minimum 2 shares"
            )
            return None

        # Calculate exit targets
        targets = self._calculate_targets(symbol, entry_price, total_quantity, stop_price)

        # Create exit state
        state = PartialExitState(
            symbol=symbol,
            entry_price=entry_price,
            total_quantity=total_quantity,
            targets=targets,
            stop_price=stop_price,
            stop_order_id=stop_order_id,
        )

        self.exit_states[symbol] = state

        # Place orders for targets
        self._place_target_orders(state)

        logger.info(
            f"Registered {symbol} for partial exits: "
            f"{len(targets)} targets, total_qty={total_quantity}"
        )

        return state

    def _calculate_targets(
        self, symbol: str, entry_price: float, total_quantity: int, stop_price: float
    ) -> List[ExitTarget]:
        """
        Calculate exit targets based on configuration.

        Args:
            symbol: Ticker symbol
            entry_price: Position entry price
            total_quantity: Total shares
            stop_price: Initial stop price

        Returns:
            List of ExitTarget objects
        """
        targets = []
        split_ratios = self.config.get("split", [0.5, 0.5])

        # Calculate quantities for each target
        remaining_qty = total_quantity
        for i, ratio in enumerate(split_ratios, start=1):
            # Last target gets all remaining shares (handles rounding)
            if i == len(split_ratios):
                qty = remaining_qty
            else:
                qty = int(total_quantity * ratio)
                remaining_qty -= qty

            # Determine exit type and price
            if i == 1:
                # Target 1: Limit order at profit percentage
                target_pct = self.config.get("target_1_pct", 0.04)
                exit_price = entry_price * (1 + target_pct)
                exit_type = "limit"
            else:
                # Target 2+: Trailing stop (no fixed price)
                exit_price = None
                exit_type = "trailing"

            target = ExitTarget(
                target_number=i,
                quantity=qty,
                ratio=ratio,
                exit_type=exit_type,
                exit_price=exit_price,
            )

            targets.append(target)

        logger.debug(
            f"Calculated targets for {symbol}: "
            f"{[(t.target_number, t.quantity, t.exit_type) for t in targets]}"
        )

        return targets

    def _place_target_orders(self, state: PartialExitState) -> None:
        """
        Place orders for all exit targets.

        Args:
            state: PartialExitState for the position
        """
        for target in state.targets:
            if target.exit_type == "limit":
                # Place limit order for partial profit-taking
                self._place_limit_exit(state, target)
            elif target.exit_type == "trailing":
                # Register with TrailingStopManager
                self._register_trailing_target(state, target)

    def _place_limit_exit(self, state: PartialExitState, target: ExitTarget) -> None:
        """
        Place limit order for a profit target.

        Args:
            state: PartialExitState for the position
            target: ExitTarget to place order for
        """
        try:
            # Use order_manager to place limit sell order
            result = self.order_manager.place_limit_order(
                symbol=state.symbol,
                qty=target.quantity,
                side="sell",
                limit_price=target.exit_price,
            )

            if "error" not in result:
                target.order_id = result.get("id")
                logger.info(
                    f"Placed limit exit for {state.symbol} target {target.target_number}: "
                    f"{target.quantity} @ ${target.exit_price:.2f} (ID: {target.order_id})"
                )
            else:
                logger.error(
                    f"Failed to place limit exit for {state.symbol} "
                    f"target {target.target_number}: {result['error']}"
                )

        except Exception as e:
            logger.error(
                f"Error placing limit exit for {state.symbol} target {target.target_number}: {e}"
            )

    def _register_trailing_target(self, state: PartialExitState, target: ExitTarget) -> None:
        """
        Register trailing stop target with TrailingStopManager.

        Args:
            state: PartialExitState for the position
            target: ExitTarget for trailing stop
        """
        if self.trailing_stop_manager is None:
            logger.warning(
                f"TrailingStopManager not available for {state.symbol} "
                f"target {target.target_number}, using fixed stop"
            )
            return

        try:
            # Register with trailing stop manager
            self.trailing_stop_manager.register_position(
                symbol=state.symbol,
                entry_price=state.entry_price,
                initial_stop=state.stop_price,
                quantity=target.quantity,
                stop_order_id=state.stop_order_id,  # Will replace with partial qty
            )

            logger.info(
                f"Registered trailing target for {state.symbol} target {target.target_number}: "
                f"{target.quantity} shares with dynamic stops"
            )

        except Exception as e:
            logger.error(
                f"Error registering trailing target for {state.symbol} "
                f"target {target.target_number}: {e}"
            )

    def update_position_fills(self, symbol: str) -> bool:
        """
        Check if any targets have been filled and update state.

        Args:
            symbol: Ticker symbol to check

        Returns:
            True if any targets were filled, False otherwise
        """
        if symbol not in self.exit_states:
            return False

        state = self.exit_states[symbol]
        updated = False

        for target in state.get_active_targets():
            if target.order_id is None:
                continue

            # Check order status from broker
            order_status = self._check_order_status(target.order_id)

            if order_status == "filled":
                target.filled = True
                target.filled_at = now_iso()
                updated = True

                logger.info(
                    f"Target {target.target_number} filled for {symbol}: "
                    f"{target.quantity} @ ${target.exit_price:.2f}"
                )

        if updated:
            state.last_updated = now_iso()

        return updated

    def _check_order_status(self, order_id: str) -> str:
        """
        Check order status from broker.

        Args:
            order_id: Order ID to check

        Returns:
            Order status string ("filled", "open", "cancelled", etc.)
        """
        try:
            # Use position_manager to get order details
            order = self.order_manager.position_manager.get_order(order_id)
            if order:
                return order.get("status", "unknown")
            return "unknown"
        except Exception as e:
            logger.error(f"Error checking order status for {order_id}: {e}")
            return "error"

    def get_position_summary(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of partial exit state for a position.

        Args:
            symbol: Ticker symbol

        Returns:
            Dict with exit state summary, None if not found
        """
        if symbol not in self.exit_states:
            return None

        state = self.exit_states[symbol]

        return {
            "symbol": symbol,
            "entry_price": state.entry_price,
            "total_quantity": state.total_quantity,
            "remaining_quantity": state.get_remaining_quantity(),
            "targets": [
                {
                    "number": t.target_number,
                    "quantity": t.quantity,
                    "type": t.exit_type,
                    "price": t.exit_price,
                    "filled": t.filled,
                    "filled_at": t.filled_at,
                }
                for t in state.targets
            ],
            "filled_targets": len(state.get_filled_targets()),
            "active_targets": len(state.get_active_targets()),
            "registered_at": state.registered_at,
            "last_updated": state.last_updated,
        }

    def remove_position(self, symbol: str) -> bool:
        """
        Remove position from partial exit tracking (fully closed).

        Args:
            symbol: Ticker symbol

        Returns:
            True if removed, False if not found
        """
        if symbol in self.exit_states:
            del self.exit_states[symbol]
            logger.info(f"Removed {symbol} from partial exit tracking")
            return True
        return False

    @classmethod
    def from_mode_manager(
        cls, order_manager, trailing_stop_manager, mode_manager, mode=None
    ) -> "PartialExitManager":
        """
        Create PartialExitManager from TradingModeManager configuration.

        Args:
            order_manager: OrderManager instance
            trailing_stop_manager: TrailingStopManager instance
            mode_manager: TradingModeManager instance
            mode: TradingMode to use (default: current mode)

        Returns:
            PartialExitManager instance configured for the mode
        """
        params = mode_manager.get_parameters(mode)

        # Extract partial exit config from mode parameters
        # This would need to be added to ModeParameters dataclass
        # For now, use a default structure
        partial_exit_config = {
            "enabled": True,
            "targets": 2,
            "split": [0.5, 0.5],
            "target_1_pct": 0.04,  # Could vary by mode
            "target_2": "trailing",
        }

        logger.info(
            f"Creating PartialExitManager from mode: {params.mode.value}, "
            f"config={partial_exit_config}"
        )

        return cls(
            order_manager=order_manager,
            trailing_stop_manager=trailing_stop_manager,
            partial_exit_config=partial_exit_config,
        )
