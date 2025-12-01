"""
Trailing Stop CLI Commands

Provides natural language interface for:
- Viewing trailing stop states
- Showing configuration
- Manual stop overrides
- Position tracking

Issue #424: Trailing Stop CLI Commands - Visibility & Control
Depends on: #414 (Advanced Trailing Stop Automation)
"""

import logging
from typing import Dict

from src.utils.safe_print import get_symbol, safe_print

logger = logging.getLogger(__name__)


class TrailingStopCommands:
    """
    Trailing stop management commands for CLI.

    Available commands:
    - show trailing stops / trailing stops status
    - trailing-stop config / show stop settings
    - set trailing-stop SYMBOL PRICE
    - override stop SYMBOL $PRICE
    """

    def __init__(self, trailing_stop_manager=None):
        """
        Initialize trailing stop commands.

        Args:
            trailing_stop_manager: TrailingStopManager instance
        """
        self.stop_manager = trailing_stop_manager
        logger.info("TrailingStopCommands initialized")

    def show_trailing_stops(self) -> Dict:
        """
        Display all positions being tracked with trailing stops.

        Returns:
            Dict with status and position details
        """
        if self.stop_manager is None:
            safe_print(f"{get_symbol('WARNING')} TrailingStopManager not available")
            return {"status": "no_manager", "positions": []}

        safe_print(f"\n{get_symbol('INFO')} Trailing Stops Summary")
        print("=" * 80)

        # Get configuration info
        config = self.stop_manager.trailing_config
        mode_info = self._get_mode_description(config)

        print(f"Mode: {mode_info}")
        print(
            f"Climb Rate: {config.climb_rate} {self._get_climb_rate_description(config.climb_rate)}"
        )
        print(f"Volatility Aware: {'Yes' if config.volatility_aware else 'No'}")

        # Get all positions
        positions = self.stop_manager.stop_states
        profit_zone_count = sum(
            1 for state in positions.values() if getattr(state, "in_profit_zone", False)
        )
        total_adjustments = sum(state.adjustments_count for state in positions.values())

        print(f"Positions Tracked: {len(positions)}")
        print(f"In Profit Zone: {profit_zone_count}")
        print(f"Total Adjustments: {total_adjustments}")
        print()

        if not positions:
            safe_print(f"{get_symbol('INFO')} No positions currently tracked")
            return {"status": "success", "positions": [], "count": 0}

        # Table header
        print(
            f"{'Symbol':<8} {'Entry':>10} {'Current':>10} {'Stop':>10} "
            f"{'Profit':>8} {'Zone':>6} {'Adj':>5}"
        )
        print("─" * 80)

        # Display each position
        position_data = []
        for symbol, state in positions.items():
            # Calculate profit percentage
            if state.entry_price > 0:
                # Assume current price is highest seen
                profit_pct = (
                    (state.highest_price_seen - state.entry_price) / state.entry_price * 100
                )
            else:
                profit_pct = 0.0

            zone_status = "YES" if getattr(state, "in_profit_zone", False) else "NO"

            print(
                f"{symbol:<8} "
                f"${state.entry_price:>9.2f} "
                f"${state.highest_price_seen:>9.2f} "
                f"${state.current_stop:>9.2f} "
                f"{profit_pct:>7.1f}% "
                f"{zone_status:>6} "
                f"{state.adjustments_count:>5}"
            )

            position_data.append(
                {
                    "symbol": symbol,
                    "entry_price": state.entry_price,
                    "highest_price": state.highest_price_seen,
                    "current_stop": state.current_stop,
                    "profit_pct": profit_pct,
                    "in_profit_zone": zone_status == "YES",
                    "adjustments": state.adjustments_count,
                }
            )

        print("=" * 80)
        return {"status": "success", "positions": position_data, "count": len(positions)}

    def show_config(self) -> Dict:
        """
        Display trailing stop configuration settings.

        Returns:
            Dict with status and configuration details
        """
        if self.stop_manager is None:
            safe_print(f"{get_symbol('WARNING')} TrailingStopManager not available")
            return {"status": "no_manager"}

        config = self.stop_manager.trailing_config

        safe_print(f"\n{get_symbol('INFO')} Trailing Stop Configuration")
        print("=" * 80)

        # Mode description
        mode_info = self._get_mode_description(config)
        print(f"Trading Mode: {mode_info}")

        # Climb rate details
        climb_desc = self._get_climb_rate_description(config.climb_rate)
        print(f"Climb Rate: {config.climb_rate} {climb_desc}")

        # Volatility settings
        if config.volatility_aware:
            print(f"Volatility Aware: Yes (ATR multiplier: {config.atr_multiplier}x)")
            print(f"ATR Period: {getattr(config, 'atr_period', 14)} periods")
        else:
            print("Volatility Aware: No")

        # Profit zone threshold
        print(f"Profit Zone Start: {config.profit_zone_start_pct * 100:.1f}%")
        print()

        # Progressive thresholds
        print("Progressive Thresholds:")
        print(f"  Breakeven: {config.progressive_breakeven_pct * 100:.1f}%")
        print(f"  Lock 25%: {config.progressive_lock_25_pct * 100:.1f}%")
        print(f"  Trail 50%: {config.progressive_trail_50_pct * 100:.1f}%+")
        print()

        # Update settings
        print(f"Min Update Interval: {config.min_update_interval_seconds}s")
        print(f"Never Move Stop Down: {config.never_move_stop_down}")

        print("=" * 80)

        return {
            "status": "success",
            "config": {
                "climb_rate": config.climb_rate,
                "volatility_aware": config.volatility_aware,
                "atr_multiplier": config.atr_multiplier if config.volatility_aware else None,
                "profit_zone_start_pct": config.profit_zone_start_pct,
                "progressive_breakeven_pct": config.progressive_breakeven_pct,
                "progressive_lock_25_pct": config.progressive_lock_25_pct,
                "progressive_trail_50_pct": config.progressive_trail_50_pct,
                "min_update_interval_seconds": config.min_update_interval_seconds,
            },
        }

    def set_manual_stop(self, symbol: str, stop_price: float) -> Dict:
        """
        Manually override trailing stop for a position.

        Args:
            symbol: Ticker symbol
            stop_price: New stop price

        Returns:
            Dict with status and details
        """
        if self.stop_manager is None:
            safe_print(f"{get_symbol('WARNING')} TrailingStopManager not available")
            return {"status": "no_manager"}

        # Check if position exists
        if symbol not in self.stop_manager.stop_states:
            safe_print(f"{get_symbol('ERROR')} No trailing stop found for {symbol}")
            return {"status": "not_found", "symbol": symbol}

        state = self.stop_manager.stop_states[symbol]
        old_stop = state.current_stop

        # Validate new stop price
        if stop_price > state.entry_price and stop_price <= state.highest_price_seen:
            # Valid override - update the stop
            state.current_stop = stop_price
            state.adjustments_count += 1

            safe_print(
                f"{get_symbol('SUCCESS')} Manual stop override for {symbol}: "
                f"${old_stop:.2f} → ${stop_price:.2f}"
            )

            # If order_manager available, update broker order
            if self.stop_manager.order_manager and state.stop_order_id:
                try:
                    result = self.stop_manager.order_manager.replace_stop_order(
                        order_id=state.stop_order_id,
                        new_stop_price=stop_price,
                        symbol=symbol,
                        qty=state.quantity,
                    )

                    if "error" in result:
                        safe_print(
                            f"{get_symbol('WARNING')} Stop updated locally "
                            f"but broker update failed: {result['error']}"
                        )
                    else:
                        safe_print(f"{get_symbol('INFO')} Broker stop order updated")
                except Exception as e:
                    logger.error(f"Error updating broker stop: {e}")
                    safe_print(
                        f"{get_symbol('WARNING')} Stop updated locally but broker update failed"
                    )

            return {
                "status": "success",
                "symbol": symbol,
                "old_stop": old_stop,
                "new_stop": stop_price,
            }
        else:
            # Invalid stop price
            safe_print(
                f"{get_symbol('ERROR')} Invalid stop price ${stop_price:.2f} for {symbol}\n"
                f"Must be between entry (${state.entry_price:.2f}) and "
                f"highest (${state.highest_price_seen:.2f})"
            )
            return {"status": "invalid_price", "symbol": symbol, "stop_price": stop_price}

    def _get_mode_description(self, config) -> str:
        """
        Get trading mode description from config.

        Args:
            config: TrailingStopConfig

        Returns:
            Mode description string
        """
        # Try to infer mode from parameters
        if config.progressive_breakeven_pct <= 0.02 and hasattr(config, "stop_loss"):
            if config.stop_loss <= 0.03:
                return "Conservative"
        if config.progressive_breakeven_pct >= 0.03:
            return "Aggressive"
        return "Moderate"

    def _get_climb_rate_description(self, climb_rate: str) -> str:
        """
        Get human-readable climb rate description.

        Args:
            climb_rate: Climb rate setting (slow/medium/fast)

        Returns:
            Description with gain lock percentages
        """
        descriptions = {
            "slow": "(20%/40%/60% gain locks)",
            "medium": "(25%/50%/75% gain locks)",
            "fast": "(33%/60%/80% gain locks)",
        }
        return descriptions.get(climb_rate, "(unknown)")
