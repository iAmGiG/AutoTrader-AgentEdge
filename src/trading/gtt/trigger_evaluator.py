"""
GTT Trigger Evaluator - Condition checking logic.

Issue #340: Evaluate GTT trigger conditions against current prices.

Phase 1 Supports:
- Price above/below conditions
- Percentage gain/loss conditions
- Trailing stop conditions

Phase 2 Supports:
- Time window conditions (active during specific hours)
- Volume-based conditions (volume threshold/spike)
"""

import logging
from datetime import datetime, time
from typing import Dict, List, Optional

from src.trading.gtt.gtt_manager import ConditionType, GTTTrigger, get_gtt_manager

logger = logging.getLogger(__name__)


class TriggerEvaluator:
    """
    Evaluates GTT trigger conditions.

    Used by scheduler to check which triggers should fire.
    """

    def __init__(self):
        self.gtt_manager = get_gtt_manager()

    def evaluate_trigger(  # noqa: C901
        self,
        trigger: GTTTrigger,
        current_price: float,
        reference_price: Optional[float] = None,
    ) -> bool:
        """
        Evaluate if a trigger condition is met.

        Args:
            trigger: GTT trigger to evaluate
            current_price: Current market price
            reference_price: Reference price for percentage conditions

        Returns:
            True if condition is met
        """
        if not trigger.is_active:
            return False

        condition = trigger.condition_type

        if condition == ConditionType.PRICE_ABOVE.value:
            return self._check_price_above(current_price, trigger.trigger_value)

        elif condition == ConditionType.PRICE_BELOW.value:
            return self._check_price_below(current_price, trigger.trigger_value)

        elif condition == ConditionType.PCT_GAIN.value:
            if reference_price is None:
                reference_price = trigger.action_config.get("reference_price")
            if reference_price:
                return self._check_pct_gain(current_price, reference_price, trigger.trigger_value)
            return False

        elif condition == ConditionType.PCT_LOSS.value:
            if reference_price is None:
                reference_price = trigger.action_config.get("reference_price")
            if reference_price:
                return self._check_pct_loss(current_price, reference_price, trigger.trigger_value)
            return False

        elif condition == ConditionType.TRAILING_STOP.value:
            return self._check_trailing_stop(trigger, current_price)

        # Phase 2: Time-based conditions
        elif condition == ConditionType.TIME_WINDOW.value:
            return self._check_time_window(trigger)

        # Phase 2: Volume-based conditions
        elif condition == ConditionType.VOLUME_ABOVE.value:
            return self._check_volume_above(trigger)

        elif condition == ConditionType.VOLUME_SPIKE.value:
            return self._check_volume_spike(trigger)

        else:
            logger.warning(f"Unknown condition type: {condition}")
            return False

    def evaluate_triggers_batch(
        self,
        prices: Dict[str, float],
        reference_prices: Optional[Dict[str, float]] = None,
    ) -> List[GTTTrigger]:
        """
        Evaluate all active triggers against current prices.

        Args:
            prices: Dict mapping symbol -> current price
            reference_prices: Dict mapping symbol -> reference price (for pct conditions)

        Returns:
            List of triggers that should fire
        """
        triggers_to_fire: List[GTTTrigger] = []
        reference_prices = reference_prices or {}

        # Get all active triggers
        active_triggers = self.gtt_manager.get_triggers(active_only=True)

        for trigger in active_triggers:
            if trigger.symbol not in prices:
                continue

            current_price = prices[trigger.symbol]
            ref_price = reference_prices.get(trigger.symbol)

            # Update trailing stops (track highest price)
            if trigger.condition_type == ConditionType.TRAILING_STOP.value:
                self._update_trailing_highest(trigger, current_price)

            # Evaluate condition
            if self.evaluate_trigger(trigger, current_price, ref_price):
                triggers_to_fire.append(trigger)
                logger.info(
                    f"GTT trigger {trigger.id} fired: "
                    f"{trigger.symbol} {trigger.condition_type} @ {trigger.trigger_value} "
                    f"(current: {current_price})"
                )

        return triggers_to_fire

    # =========================================================================
    # Condition Checkers
    # =========================================================================

    def _check_price_above(self, current: float, target: float) -> bool:
        """Check if price is above target."""
        return current >= target

    def _check_price_below(self, current: float, target: float) -> bool:
        """Check if price is below target."""
        return current <= target

    def _check_pct_gain(self, current: float, reference: float, target_pct: float) -> bool:
        """Check if gain percentage is reached."""
        if reference <= 0:
            return False
        gain_pct = ((current - reference) / reference) * 100
        return gain_pct >= target_pct

    def _check_pct_loss(self, current: float, reference: float, target_pct: float) -> bool:
        """Check if loss percentage is reached."""
        if reference <= 0:
            return False
        loss_pct = ((reference - current) / reference) * 100
        return loss_pct >= target_pct

    def _check_trailing_stop(self, trigger: GTTTrigger, current_price: float) -> bool:
        """
        Check if trailing stop is triggered.

        Trailing stop triggers when price drops X% from highest recorded price.
        """
        config = trigger.action_config or {}
        highest_price = config.get("highest_price", current_price)
        trail_pct = trigger.trigger_value  # e.g., 0.05 for 5%

        if highest_price <= 0:
            return False

        # Calculate stop level
        stop_level = highest_price * (1 - trail_pct)

        # Check if current price has fallen below stop
        return current_price <= stop_level

    def _update_trailing_highest(self, trigger: GTTTrigger, current_price: float) -> None:
        """
        Update trailing stop with new highest price if applicable.

        Called on each evaluation to track the peak price.
        """
        config = trigger.action_config or {}
        highest_price = config.get("highest_price", 0)

        if current_price > highest_price:
            # New high - update the trigger
            trail_pct = trigger.trigger_value
            new_stop = current_price * (1 - trail_pct)

            self.gtt_manager.update_trailing_stop(
                trigger.id, new_highest=current_price, new_stop=new_stop
            )

            logger.info(
                f"Trailing stop {trigger.id} updated: "
                f"highest={current_price:.2f}, stop={new_stop:.2f}"
            )

    # =========================================================================
    # Phase 2: Time-Based Condition Checkers
    # =========================================================================

    def _check_time_window(self, trigger: GTTTrigger) -> bool:
        """
        Check if current time is within the specified time window.

        action_config expected keys:
            - start_time: str "HH:MM" in 24h format (e.g., "09:30")
            - end_time: str "HH:MM" in 24h format (e.g., "16:00")
            - timezone: str timezone (default: US/Eastern)
            - days_of_week: list[int] days to check (0=Mon, 6=Sun, default: [0,1,2,3,4])
        """
        config = trigger.action_config or {}

        start_str = config.get("start_time", "09:30")
        end_str = config.get("end_time", "16:00")
        days_of_week = config.get("days_of_week", [0, 1, 2, 3, 4])  # Mon-Fri

        try:
            # Parse times
            start_parts = start_str.split(":")
            end_parts = end_str.split(":")
            start_time = time(int(start_parts[0]), int(start_parts[1]))
            end_time = time(int(end_parts[0]), int(end_parts[1]))

            # Get current time (would use pytz for timezone in production)
            now = datetime.now()
            current_time = now.time()
            current_day = now.weekday()

            # Check day of week
            if current_day not in days_of_week:
                return False

            # Check time window
            if start_time <= end_time:
                # Normal window (e.g., 09:30 - 16:00)
                return start_time <= current_time <= end_time
            else:
                # Overnight window (e.g., 22:00 - 06:00)
                return current_time >= start_time or current_time <= end_time

        except Exception as e:
            logger.error(f"Time window check failed for trigger {trigger.id}: {e}")
            return False

    # =========================================================================
    # Phase 2: Volume-Based Condition Checkers
    # =========================================================================

    def _check_volume_above(self, trigger: GTTTrigger) -> bool:
        """
        Check if current volume exceeds threshold.

        action_config expected keys:
            - current_volume: int current session volume (injected during evaluation)
            - threshold: int volume threshold (or use trigger_value)
        """
        config = trigger.action_config or {}

        current_volume = config.get("current_volume", 0)
        threshold = config.get("threshold", trigger.trigger_value)

        if not current_volume:
            logger.debug(f"No volume data for trigger {trigger.id}")
            return False

        return current_volume >= threshold

    def _check_volume_spike(self, trigger: GTTTrigger) -> bool:
        """
        Check if volume spike detected (current vs average).

        action_config expected keys:
            - current_volume: int current session volume
            - average_volume: int average daily volume
            - spike_multiplier: float spike threshold (or use trigger_value, e.g., 2.0 for 2x)
        """
        config = trigger.action_config or {}

        current_volume = config.get("current_volume", 0)
        average_volume = config.get("average_volume", 0)
        spike_mult = config.get("spike_multiplier", trigger.trigger_value)

        if not current_volume or not average_volume:
            logger.debug(f"Missing volume data for spike check on trigger {trigger.id}")
            return False

        # Check if current volume exceeds spike threshold
        return current_volume >= (average_volume * spike_mult)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_triggers_for_symbols(self, symbols: List[str]) -> List[GTTTrigger]:
        """Get active triggers for specific symbols."""
        all_triggers = self.gtt_manager.get_triggers(active_only=True)
        return [t for t in all_triggers if t.symbol in symbols]

    def describe_trigger_condition(self, trigger: GTTTrigger) -> str:
        """Generate human-readable description of trigger condition."""
        condition = trigger.condition_type
        value = trigger.trigger_value
        symbol = trigger.symbol

        if condition == ConditionType.PRICE_ABOVE.value:
            return f"{symbol} price >= ${value:.2f}"

        elif condition == ConditionType.PRICE_BELOW.value:
            return f"{symbol} price <= ${value:.2f}"

        elif condition == ConditionType.PCT_GAIN.value:
            return f"{symbol} gains {value:.1f}% from reference"

        elif condition == ConditionType.PCT_LOSS.value:
            return f"{symbol} loses {value:.1f}% from reference"

        elif condition == ConditionType.TRAILING_STOP.value:
            config = trigger.action_config or {}
            highest = config.get("highest_price", 0)
            stop = config.get("current_stop", highest * (1 - value))
            return f"{symbol} drops {value*100:.1f}% from peak (highest=${highest:.2f}, stop=${stop:.2f})"

        # Phase 2: Time-based conditions
        elif condition == ConditionType.TIME_WINDOW.value:
            config = trigger.action_config or {}
            start = config.get("start_time", "09:30")
            end = config.get("end_time", "16:00")
            return f"{symbol} active between {start}-{end}"

        # Phase 2: Volume-based conditions
        elif condition == ConditionType.VOLUME_ABOVE.value:
            return f"{symbol} volume >= {value:,.0f}"

        elif condition == ConditionType.VOLUME_SPIKE.value:
            return f"{symbol} volume spike >= {value:.1f}x average"

        return f"{symbol} {condition} {value}"


# Module-level instance
_evaluator: Optional[TriggerEvaluator] = None


def get_trigger_evaluator() -> TriggerEvaluator:
    """Get global trigger evaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = TriggerEvaluator()
    return _evaluator
