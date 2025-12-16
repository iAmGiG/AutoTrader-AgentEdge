#!/usr/bin/env python3
"""
Trailing Stop Manager - Dynamic Stop Loss Management

Implements progressive trailing stop logic to maximize winning trades
while protecting profits. Integrates with OrderManager for broker operations.

Issue #321: Implement Dynamic Trailing Stop Logic
Issue #414: Advanced Trailing Stop Automation (KILLER FEATURE)

Enhanced with:
- Configurable climb rates (slow/medium/fast)
- Volatility-aware adjustments via ATR
- Per-mode configuration integration
- Profit-zone awareness
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from config_defaults.trading_config import TradingConfig, TrailingStopConfig

from src.trading.utils.unified_price_fetcher import get_current_price
from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


@dataclass
class StopState:
    """
    Track stop state for a position.

    Issue #414: Extended with ATR tracking for volatility-aware stops,
    voter signal integration, and support/resistance awareness.
    """

    symbol: str
    entry_price: float
    current_stop: float
    quantity: int
    stop_order_id: Optional[str] = None
    last_update_time: Optional[str] = None
    highest_price_seen: float = 0.0
    adjustments_count: int = 0
    # Issue #414: ATR tracking for volatility-aware stops
    current_atr: Optional[float] = None
    in_profit_zone: bool = False
    # Issue #414: Voter signal integration (KILLER FEATURE)
    voter_signal: Optional[str] = None  # "BUY", "SELL", "HOLD"
    voter_confidence: float = 0.0
    voter_tightening_active: bool = False
    # Issue #414: Support/Resistance awareness
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None


class TrailingStopManager:
    """
    Manages dynamic trailing stops for open positions.

    Issue #321: Base trailing stop logic
    Issue #414: Advanced Trailing Stop Automation (KILLER FEATURE)

    Progressive stop adjustment rules (configurable via climb_rate):
    - Under profit_zone: Don't adjust (avoid whipsaws)
    - In profit zone: Lock gains based on climb_rate (slow/medium/fast)
    - Volatility-aware: Adjust trail distance based on ATR

    Key features:
    - Rate-limited updates (default: 60 seconds minimum between updates)
    - Stops only move up, never down (safety)
    - Tracks highest price for proper trailing calculation
    - Integrates with Alpaca via OrderManager.replace_stop_order()
    - Configurable climb rates for different trading modes
    - ATR-based volatility adjustments
    """

    def __init__(
        self,
        order_manager,
        config: Optional[TradingConfig] = None,
        trailing_config: Optional[TrailingStopConfig] = None,
        atr_fetcher: Optional[Callable[[str, int], float]] = None,
    ):
        """
        Initialize trailing stop manager.

        Args:
            order_manager: OrderManager instance for broker operations
            config: TradingConfig instance (loads defaults if None)
            trailing_config: Direct TrailingStopConfig (overrides config)
            atr_fetcher: Function to get ATR for a symbol: atr_fetcher(symbol, period) -> float
        """
        self.order_manager = order_manager
        self.config = config or TradingConfig()

        # Use direct trailing_config if provided, otherwise load from config
        if trailing_config is not None:
            self.trailing_config = trailing_config
        else:
            self.trailing_config = self.config.get_trailing_stop_config()

        # ATR fetcher for volatility-aware stops
        self.atr_fetcher = atr_fetcher

        # Track stop state for each position
        self.stop_states: Dict[str, StopState] = {}

        # Rate limiting
        self.last_update_times: Dict[str, float] = {}

        # Cache gain lock percentages from climb rate
        self._gain_locks = self.trailing_config.get_gain_lock_percentages()

        logger.info(
            "TrailingStopManager initialized: enabled=%s, progressive=%s, climb_rate=%s",
            self.trailing_config.enabled,
            self.trailing_config.progressive_enabled,
            self.trailing_config.climb_rate,
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
            logger.info("Unregistered %s from trailing stops", symbol)
            return True
        return False

    def _get_atr(self, symbol: str) -> Optional[float]:
        """
        Get ATR for a symbol using the configured fetcher.

        Issue #414: ATR-based volatility awareness.

        Args:
            symbol: Ticker symbol

        Returns:
            ATR value or None if not available
        """
        if self.atr_fetcher is None:
            return None

        try:
            atr = self.atr_fetcher(symbol, self.trailing_config.atr_period)
            return atr
        except Exception as e:
            logger.warning("Failed to get ATR for %s: %s", symbol, e)
            return None

    def _calculate_volatility_adjusted_stop(
        self,
        current_price: float,
        base_stop: float,
        atr: float,
    ) -> float:
        """
        Adjust stop price based on volatility (ATR).

        Issue #414: Volatility-aware trailing stops.

        Higher volatility = wider stop to avoid whipsaws.

        Args:
            current_price: Current market price
            base_stop: Base stop price before adjustment
            atr: Average True Range value

        Returns:
            Volatility-adjusted stop price
        """
        if atr <= 0:
            return base_stop

        # Calculate ATR-based buffer
        atr_buffer = atr * self.trailing_config.atr_multiplier

        # Stop should be at least ATR buffer below current price
        volatility_stop = current_price - atr_buffer

        # Use the lower of the two (more conservative)
        adjusted_stop = min(base_stop, volatility_stop)

        logger.debug(
            "Volatility adjustment: base=%.2f, atr_buffer=%.2f, adjusted=%.2f",
            base_stop,
            atr_buffer,
            adjusted_stop,
        )

        return adjusted_stop

    def calculate_new_stop(  # noqa: C901 - complexity justified by profit zone logic
        self, symbol: str, current_price: float
    ) -> Optional[float]:
        """
        Calculate new stop price based on current price and profit level.

        Issue #414: Enhanced with configurable climb rates and volatility awareness.

        Uses progressive stop logic based on climb_rate:
        - slow: Lock 20%/40%/60% of gains
        - medium: Lock 25%/50%/75% of gains
        - fast: Lock 33%/60%/80% of gains

        Args:
            symbol: Ticker symbol
            current_price: Current market price

        Returns:
            New stop price or None if no adjustment needed
        """
        if symbol not in self.stop_states:
            logger.warning("Symbol %s not registered for trailing stops", symbol)
            return None

        if not self.trailing_config.enabled:
            return None

        state = self.stop_states[symbol]
        entry_price = state.entry_price
        current_stop = state.current_stop

        # Update highest price seen
        state.highest_price_seen = max(state.highest_price_seen, current_price)

        # Calculate profit percentage
        profit_pct = (current_price - entry_price) / entry_price

        # Issue #414: Check if we've entered the profit zone
        profit_zone_threshold = self.trailing_config.profit_zone_start_pct
        if profit_pct >= profit_zone_threshold and not state.in_profit_zone:
            state.in_profit_zone = True
            logger.info(
                "%s: Entered profit zone at %.1f%% (threshold: %.1f%%)",
                symbol,
                profit_pct * 100,
                profit_zone_threshold * 100,
            )

        # Issue #414: Update ATR for volatility-aware stops
        if self.trailing_config.volatility_aware and state.current_atr is None:
            state.current_atr = self._get_atr(symbol)

        new_stop = None

        if self.trailing_config.progressive_enabled:
            # Progressive stop logic with configurable climb rates
            # Gain lock percentages from climb_rate: (breakeven, zone1, zone2, zone3)
            _, lock_zone1, lock_zone2, lock_zone3 = self._gain_locks

            if profit_pct < self.trailing_config.progressive_breakeven_pct:
                # Under breakeven threshold - no adjustment
                logger.debug(
                    "%s: %.1f%% profit < %.1f%% threshold",
                    symbol,
                    profit_pct * 100,
                    self.trailing_config.progressive_breakeven_pct * 100,
                )
                return None

            if profit_pct < self.trailing_config.progressive_lock_25_pct:
                # Move to breakeven (first profit zone)
                new_stop = entry_price
                logger.info(
                    "%s: Moving stop to breakeven at %.1f%% profit", symbol, profit_pct * 100
                )

            elif profit_pct < self.trailing_config.progressive_trail_50_pct:
                # Lock gains based on climb_rate zone 1
                gain = current_price - entry_price
                new_stop = entry_price + (gain * lock_zone1)
                logger.info(
                    "%s: Locking %.0f%% of gains at %.1f%% profit, stop=$%.2f",
                    symbol,
                    lock_zone1 * 100,
                    profit_pct * 100,
                    new_stop,
                )

            else:
                # Trail gains based on climb_rate zone 2/3
                gain = current_price - entry_price
                # Use higher lock percentage for larger profits
                lock_pct = lock_zone2 if profit_pct < 0.10 else lock_zone3
                new_stop = entry_price + (gain * lock_pct)
                logger.info(
                    "%s: Trailing %.0f%% of gains at %.1f%% profit, stop=$%.2f",
                    symbol,
                    lock_pct * 100,
                    profit_pct * 100,
                    new_stop,
                )
        else:
            # Simple trailing stop logic
            if profit_pct >= self.trailing_config.trail_start_trigger:
                # Trail by fixed distance below current price
                new_stop = current_price * (1 - self.trailing_config.trail_distance)
                logger.info(
                    "%s: Simple trail at %.1f%% profit, stop=$%.2f",
                    symbol,
                    profit_pct * 100,
                    new_stop,
                )
            elif profit_pct >= self.trailing_config.breakeven_trigger:
                # Move to breakeven
                new_stop = entry_price
                logger.info("%s: Moving to breakeven at %.1f%% profit", symbol, profit_pct * 100)

        # Issue #414: Apply volatility adjustment if enabled and ATR available
        if (
            new_stop is not None
            and self.trailing_config.volatility_aware
            and state.current_atr is not None
        ):
            new_stop = self._calculate_volatility_adjusted_stop(
                current_price, new_stop, state.current_atr
            )

        # Issue #414: Apply voter-influenced tightening (KILLER FEATURE)
        if new_stop is not None and state.voter_tightening_active:
            new_stop = self._apply_voter_tightening(new_stop, state)

        # Issue #414: Avoid S/R levels
        if new_stop is not None:
            new_stop = self._avoid_sr_levels(new_stop, state)

        # Safety: Never move stop down
        if new_stop is not None and self.trailing_config.never_move_stop_down:
            if new_stop <= current_stop:
                logger.debug(
                    "%s: New stop $%.2f <= current $%.2f, not adjusting",
                    symbol,
                    new_stop,
                    current_stop,
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
        positions_in_profit = sum(1 for s in self.stop_states.values() if s.in_profit_zone)
        # Issue #414: Track voter tightening and S/R awareness status
        positions_with_tightening = sum(
            1 for s in self.stop_states.values() if s.voter_tightening_active
        )
        positions_with_sr = sum(1 for s in self.stop_states.values() if s.support_level is not None)

        return {
            "enabled": self.trailing_config.enabled,
            "progressive_mode": self.trailing_config.progressive_enabled,
            "positions_tracked": total_positions,
            "positions_in_profit_zone": positions_in_profit,
            "total_adjustments": total_adjustments,
            # Issue #414: Voter and S/R status
            "positions_with_voter_tightening": positions_with_tightening,
            "positions_with_sr_levels": positions_with_sr,
            "config": {
                "breakeven_trigger": self.trailing_config.progressive_breakeven_pct,
                "lock_25_trigger": self.trailing_config.progressive_lock_25_pct,
                "trail_50_trigger": self.trailing_config.progressive_trail_50_pct,
                "min_update_interval": self.trailing_config.min_update_interval_seconds,
                # Issue #414: Advanced features
                "climb_rate": self.trailing_config.climb_rate,
                "gain_lock_percentages": self._gain_locks,
                "volatility_aware": self.trailing_config.volatility_aware,
                "atr_multiplier": self.trailing_config.atr_multiplier,
                "profit_zone_start": self.trailing_config.profit_zone_start_pct,
                # Issue #414: Voter signal integration
                "voter_influenced": self.trailing_config.voter_influenced,
                "voter_tighten_multiplier": self.trailing_config.voter_tighten_multiplier,
                "voter_min_confidence": self.trailing_config.voter_min_confidence,
                # Issue #414: S/R awareness
                "sr_awareness_enabled": self.trailing_config.sr_awareness_enabled,
                "sr_buffer_pct": self.trailing_config.sr_buffer_pct,
            },
        }

    # === Issue #414: Voter Signal Integration (KILLER FEATURE) ===

    def update_voter_signal(self, symbol: str, signal: str, confidence: float) -> Dict[str, Any]:
        """
        Update voter signal for a position - triggers stop tightening on SELL.

        Issue #414: When voters signal SELL, don't force exit - instead,
        aggressively tighten stops to protect profits.

        Args:
            symbol: Ticker symbol
            signal: Voter signal ("BUY", "SELL", "HOLD")
            confidence: Confidence level (0.0 - 1.0)

        Returns:
            Dict with update status and any stop adjustments made
        """
        if symbol not in self.stop_states:
            return {"status": "error", "message": f"{symbol} not registered"}

        if not self.trailing_config.voter_influenced:
            return {"status": "disabled", "message": "Voter influence disabled"}

        state = self.stop_states[symbol]
        old_signal = state.voter_signal

        # Update voter signal
        state.voter_signal = signal
        state.voter_confidence = confidence

        # Check if we should activate tightening
        if (
            signal == "SELL"
            and confidence >= self.trailing_config.voter_min_confidence
            and state.in_profit_zone
        ):
            state.voter_tightening_active = True
            logger.info(
                "%s: Voter signaling SELL (%.0f%% conf) - activating stop tightening",
                symbol,
                confidence * 100,
            )
            return {
                "status": "tightening_activated",
                "signal": signal,
                "confidence": confidence,
                "message": "Stop tightening activated due to SELL signal",
            }
        elif signal != "SELL" and state.voter_tightening_active:
            state.voter_tightening_active = False
            logger.info(
                "%s: Voter signal changed to %s - deactivating stop tightening",
                symbol,
                signal,
            )

        return {
            "status": "updated",
            "old_signal": old_signal,
            "new_signal": signal,
            "confidence": confidence,
            "tightening_active": state.voter_tightening_active,
        }

    def _apply_voter_tightening(self, stop_price: float, state: StopState) -> float:
        """
        Apply voter-influenced stop tightening.

        Issue #414: When voters signal SELL, tighten the trailing distance.

        Args:
            stop_price: Base stop price
            state: Current stop state

        Returns:
            Tightened stop price (higher = tighter protection)
        """
        if not state.voter_tightening_active:
            return stop_price

        if not self.trailing_config.voter_influenced:
            return stop_price

        # Calculate tighter stop (move it up closer to current price)
        # The tighten_multiplier reduces the distance from price to stop
        current_distance = state.highest_price_seen - stop_price
        tightened_distance = current_distance * self.trailing_config.voter_tighten_multiplier
        tightened_stop = state.highest_price_seen - tightened_distance

        # Only tighten, never loosen
        new_stop = max(stop_price, tightened_stop)

        if new_stop > stop_price:
            logger.info(
                "%s: Voter tightening applied: $%.2f -> $%.2f (%.1f%% tighter)",
                state.symbol,
                stop_price,
                new_stop,
                (1 - self.trailing_config.voter_tighten_multiplier) * 100,
            )

        return new_stop

    # === Issue #414: Support/Resistance Awareness ===

    def set_support_resistance(
        self, symbol: str, support: Optional[float], resistance: Optional[float]
    ) -> Dict[str, Any]:
        """
        Set support/resistance levels for a position.

        Issue #414: Avoid placing stops exactly at S/R levels (obvious
        liquidation targets for market makers).

        Args:
            symbol: Ticker symbol
            support: Support price level
            resistance: Resistance price level

        Returns:
            Dict with update status
        """
        if symbol not in self.stop_states:
            return {"status": "error", "message": f"{symbol} not registered"}

        state = self.stop_states[symbol]
        state.support_level = support
        state.resistance_level = resistance

        logger.info(
            "%s: S/R levels set - Support: $%.2f, Resistance: $%.2f",
            symbol,
            support or 0,
            resistance or 0,
        )

        return {
            "status": "updated",
            "support": support,
            "resistance": resistance,
        }

    def _avoid_sr_levels(self, stop_price: float, state: StopState) -> float:
        """
        Adjust stop price to avoid support/resistance levels.

        Issue #414: Don't place stops exactly at S/R levels where
        market makers target liquidity.

        Args:
            stop_price: Proposed stop price
            state: Current stop state

        Returns:
            Adjusted stop price avoiding S/R levels
        """
        if not self.trailing_config.sr_awareness_enabled:
            return stop_price

        if state.support_level is None:
            return stop_price

        support = state.support_level
        buffer_pct = self.trailing_config.sr_buffer_pct

        # Calculate buffer zone around support
        support_upper = support * (1 + buffer_pct)
        support_lower = support * (1 - buffer_pct)

        # If stop is too close to support, move it below the support zone
        if support_lower <= stop_price <= support_upper:
            adjusted_stop = support_lower - 0.01  # Place just below buffer
            logger.info(
                "%s: Stop $%.2f too close to support $%.2f, adjusting to $%.2f",
                state.symbol,
                stop_price,
                support,
                adjusted_stop,
            )
            return round(adjusted_stop, 2)

        return stop_price

    @classmethod
    def from_mode_manager(
        cls,
        order_manager,
        mode_manager,
        atr_fetcher: Optional[Callable[[str, int], float]] = None,
    ) -> "TrailingStopManager":
        """
        Create TrailingStopManager from a TradingModeManager.

        Issue #414: Integration with trading modes.

        Args:
            order_manager: OrderManager instance for broker operations
            mode_manager: TradingModeManager instance
            atr_fetcher: Function to get ATR for a symbol

        Returns:
            TrailingStopManager configured with mode-specific settings
        """
        # Get trailing config dict from mode manager
        config_dict = mode_manager.get_trailing_stop_config_dict()

        # Create TrailingStopConfig from dict
        trailing_config = TrailingStopConfig(
            enabled=config_dict.get("enabled", True),
            progressive_enabled=config_dict.get("progressive_enabled", True),
            progressive_breakeven_pct=config_dict.get("progressive_breakeven_pct", 0.02),
            progressive_lock_25_pct=config_dict.get("progressive_lock_25_pct", 0.04),
            progressive_trail_50_pct=config_dict.get("progressive_trail_50_pct", 0.06),
            min_update_interval_seconds=config_dict.get("min_update_interval_seconds", 60),
            never_move_stop_down=config_dict.get("never_move_stop_down", True),
            climb_rate=config_dict.get("climb_rate", "medium"),
            volatility_aware=config_dict.get("volatility_aware", False),
            atr_multiplier=config_dict.get("atr_multiplier", 1.5),
            profit_zone_start_pct=config_dict.get("profit_zone_start_pct", 0.02),
            # Issue #414: Voter signal integration
            voter_influenced=config_dict.get("voter_influenced", True),
            voter_tighten_multiplier=config_dict.get("voter_tighten_multiplier", 0.6),
            voter_min_confidence=config_dict.get("voter_min_confidence", 0.60),
            # Issue #414: S/R awareness
            sr_awareness_enabled=config_dict.get("sr_awareness_enabled", True),
            sr_buffer_pct=config_dict.get("sr_buffer_pct", 0.005),
        )

        return cls(
            order_manager=order_manager,
            trailing_config=trailing_config,
            atr_fetcher=atr_fetcher,
        )
