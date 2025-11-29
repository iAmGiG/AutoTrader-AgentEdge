#!/usr/bin/env python3
"""
Trailing Stop Manager - Dynamic Stop Loss Management

Implements progressive trailing stop logic to maximize winning trades
while protecting profits. Integrates with OrderManager for broker operations.

Issue #321: Implement Dynamic Trailing Stop Logic
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from config_defaults.trading_config import TradingConfig

from src.trading.unified_price_fetcher import get_current_price
from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


@dataclass
class StopState:
    """Track stop state for a position."""

    symbol: str
    entry_price: float
    current_stop: float
    quantity: int
    stop_order_id: Optional[str] = None
    last_update_time: Optional[str] = None
    highest_price_seen: float = 0.0
    adjustments_count: int = 0


class TrailingStopManager:
    """
    Manages dynamic trailing stops for open positions.

    Progressive stop adjustment rules (from validated research):
    - Under 2% profit: Don't adjust (avoid whipsaws)
    - 2-4% profit: Move to breakeven (protect capital)
    - 4-6% profit: Lock in 25% of gains
    - Over 6% profit: Trail at 50% of gains

    Key features:
    - Rate-limited updates (default: 60 seconds minimum between updates)
    - Stops only move up, never down (safety)
    - Tracks highest price for proper trailing calculation
    - Integrates with Alpaca via OrderManager.replace_stop_order()
    """

    def __init__(self, order_manager, config: Optional[TradingConfig] = None):
        """
        Initialize trailing stop manager.

        Args:
            order_manager: OrderManager instance for broker operations
            config: TradingConfig instance (loads defaults if None)
        """
        self.order_manager = order_manager
        self.config = config or TradingConfig()
        self.trailing_config = self.config.get_trailing_stop_config()

        # Track stop state for each position
        self.stop_states: Dict[str, StopState] = {}

        # Rate limiting
        self.last_update_times: Dict[str, float] = {}

        logger.info(
            f"TrailingStopManager initialized: "
            f"enabled={self.trailing_config.enabled}, "
            f"progressive={self.trailing_config.progressive_enabled}"
        )

    def register_position(
        self,
        symbol: str,
        entry_price: float,
        initial_stop: float,
        quantity: int,
        stop_order_id: Optional[str] = None,
    ) -> StopState:
        """
        Register a new position for trailing stop management.

        Args:
            symbol: Ticker symbol
            entry_price: Position entry price
            initial_stop: Initial stop loss price
            quantity: Position size
            stop_order_id: ID of the stop order at broker

        Returns:
            StopState for the registered position
        """
        state = StopState(
            symbol=symbol,
            entry_price=entry_price,
            current_stop=initial_stop,
            quantity=quantity,
            stop_order_id=stop_order_id,
            last_update_time=now_iso(),
            highest_price_seen=entry_price,
        )

        self.stop_states[symbol] = state
        logger.info(
            f"Registered {symbol} for trailing stops: "
            f"entry=${entry_price:.2f}, stop=${initial_stop:.2f}"
        )

        return state

    def unregister_position(self, symbol: str) -> bool:
        """
        Remove a position from trailing stop management.

        Args:
            symbol: Ticker symbol to unregister

        Returns:
            True if position was removed
        """
        if symbol in self.stop_states:
            del self.stop_states[symbol]
            self.last_update_times.pop(symbol, None)
            logger.info(f"Unregistered {symbol} from trailing stops")
            return True
        return False

    def calculate_new_stop(self, symbol: str, current_price: float) -> Optional[float]:
        """
        Calculate new stop price based on current price and profit level.

        Uses progressive stop logic:
        - Under 2%: No adjustment
        - 2-4%: Breakeven
        - 4-6%: Lock 25% of gains
        - 6%+: Trail 50% of gains

        Args:
            symbol: Ticker symbol
            current_price: Current market price

        Returns:
            New stop price or None if no adjustment needed
        """
        if symbol not in self.stop_states:
            logger.warning(f"Symbol {symbol} not registered for trailing stops")
            return None

        if not self.trailing_config.enabled:
            return None

        state = self.stop_states[symbol]
        entry_price = state.entry_price
        current_stop = state.current_stop

        # Update highest price seen
        if current_price > state.highest_price_seen:
            state.highest_price_seen = current_price

        # Calculate profit percentage
        profit_pct = (current_price - entry_price) / entry_price

        new_stop = None

        if self.trailing_config.progressive_enabled:
            # Progressive stop logic (proven in backtesting)
            if profit_pct < self.trailing_config.progressive_breakeven_pct:
                # Under breakeven threshold - no adjustment
                logger.debug(
                    f"{symbol}: {profit_pct:.1%} profit < "
                    f"{self.trailing_config.progressive_breakeven_pct:.1%} threshold"
                )
                return None

            elif profit_pct < self.trailing_config.progressive_lock_25_pct:
                # Move to breakeven (2-4% profit zone)
                new_stop = entry_price
                logger.info(f"{symbol}: Moving stop to breakeven at {profit_pct:.1%} profit")

            elif profit_pct < self.trailing_config.progressive_trail_50_pct:
                # Lock 25% of gains (4-6% profit zone)
                gain = current_price - entry_price
                new_stop = entry_price + (gain * 0.25)
                logger.info(
                    f"{symbol}: Locking 25% of gains at {profit_pct:.1%} profit, "
                    f"stop=${new_stop:.2f}"
                )

            else:
                # Trail 50% of gains (6%+ profit zone)
                gain = current_price - entry_price
                new_stop = entry_price + (gain * 0.50)
                logger.info(
                    f"{symbol}: Trailing 50% of gains at {profit_pct:.1%} profit, "
                    f"stop=${new_stop:.2f}"
                )
        else:
            # Simple trailing stop logic
            if profit_pct >= self.trailing_config.trail_start_trigger:
                # Trail by fixed distance below current price
                new_stop = current_price * (1 - self.trailing_config.trail_distance)
                logger.info(
                    f"{symbol}: Simple trail at {profit_pct:.1%} profit, " f"stop=${new_stop:.2f}"
                )
            elif profit_pct >= self.trailing_config.breakeven_trigger:
                # Move to breakeven
                new_stop = entry_price
                logger.info(f"{symbol}: Moving to breakeven at {profit_pct:.1%} profit")

        # Safety: Never move stop down
        if new_stop is not None and self.trailing_config.never_move_stop_down:
            if new_stop <= current_stop:
                logger.debug(
                    f"{symbol}: New stop ${new_stop:.2f} <= current ${current_stop:.2f}, "
                    "not adjusting"
                )
                return None

        return round(new_stop, 2) if new_stop else None

    def should_update_stop(self, symbol: str) -> bool:
        """
        Check if enough time has passed since last update.

        Rate limits stop updates to avoid excessive API calls.

        Args:
            symbol: Ticker symbol

        Returns:
            True if update is allowed
        """
        if symbol not in self.last_update_times:
            return True

        elapsed = time.time() - self.last_update_times[symbol]
        min_interval = self.trailing_config.min_update_interval_seconds

        if elapsed < min_interval:
            logger.debug(f"{symbol}: Rate limited, {min_interval - elapsed:.0f}s until next update")
            return False

        return True

    def update_stop(self, symbol: str, current_price: float, force: bool = False) -> Dict[str, Any]:
        """
        Update trailing stop for a position if conditions are met.

        Args:
            symbol: Ticker symbol
            current_price: Current market price
            force: Skip rate limiting check

        Returns:
            Dict with update result
        """
        if symbol not in self.stop_states:
            return {"status": "error", "message": f"{symbol} not registered"}

        if not self.trailing_config.enabled:
            return {"status": "disabled", "message": "Trailing stops disabled"}

        # Check rate limiting
        if not force and not self.should_update_stop(symbol):
            return {"status": "rate_limited", "message": "Update rate limited"}

        state = self.stop_states[symbol]

        # Calculate new stop
        new_stop = self.calculate_new_stop(symbol, current_price)

        if new_stop is None:
            return {
                "status": "no_change",
                "current_stop": state.current_stop,
                "message": "No adjustment needed",
            }

        # Execute stop replacement at broker
        if state.stop_order_id:
            result = self.order_manager.replace_stop_order(
                order_id=state.stop_order_id,
                new_stop_price=new_stop,
                symbol=symbol,
                qty=state.quantity,
            )

            if "error" in result:
                logger.error(f"Failed to update stop for {symbol}: {result['error']}")
                return {"status": "error", "message": result["error"]}

            # Update state with new order ID
            old_stop = state.current_stop
            state.current_stop = new_stop
            state.stop_order_id = result.get("id")
            state.last_update_time = now_iso()
            state.adjustments_count += 1

            # Update rate limit tracking
            self.last_update_times[symbol] = time.time()

            logger.info(
                f"{symbol}: Stop adjusted ${old_stop:.2f} -> ${new_stop:.2f} "
                f"(adjustment #{state.adjustments_count})"
            )

            return {
                "status": "updated",
                "old_stop": old_stop,
                "new_stop": new_stop,
                "order_id": state.stop_order_id,
                "adjustments_count": state.adjustments_count,
            }
        else:
            # No stop order ID - just update local state
            old_stop = state.current_stop
            state.current_stop = new_stop
            state.last_update_time = now_iso()

            logger.warning(
                f"{symbol}: Stop updated locally (no order ID): "
                f"${old_stop:.2f} -> ${new_stop:.2f}"
            )

            return {
                "status": "local_update",
                "old_stop": old_stop,
                "new_stop": new_stop,
                "message": "No stop order ID - updated locally only",
            }

    def check_all_positions(self, price_fetcher: callable = None) -> Dict[str, Dict[str, Any]]:
        """
        Check and update all registered positions.

        Args:
            price_fetcher: Function to get current price for a symbol
                          Signature: price_fetcher(symbol) -> float

        Returns:
            Dict mapping symbol to update result
        """
        if price_fetcher is None:
            price_fetcher = get_current_price

        results = {}

        for symbol in list(self.stop_states.keys()):
            try:
                current_price = price_fetcher(symbol)
                result = self.update_stop(symbol, current_price)
                results[symbol] = result
            except Exception as e:
                logger.error(f"Error checking {symbol}: {e}")
                results[symbol] = {"status": "error", "message": str(e)}

        return results

    def get_state(self, symbol: str) -> Optional[StopState]:
        """Get current stop state for a symbol."""
        return self.stop_states.get(symbol)

    def get_all_states(self) -> Dict[str, StopState]:
        """Get all registered stop states."""
        return self.stop_states.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of trailing stop management status."""
        total_positions = len(self.stop_states)
        total_adjustments = sum(s.adjustments_count for s in self.stop_states.values())

        return {
            "enabled": self.trailing_config.enabled,
            "progressive_mode": self.trailing_config.progressive_enabled,
            "positions_tracked": total_positions,
            "total_adjustments": total_adjustments,
            "config": {
                "breakeven_trigger": self.trailing_config.progressive_breakeven_pct,
                "lock_25_trigger": self.trailing_config.progressive_lock_25_pct,
                "trail_50_trigger": self.trailing_config.progressive_trail_50_pct,
                "min_update_interval": self.trailing_config.min_update_interval_seconds,
            },
        }
