"""
StateReconciler - Reconcile local state with broker reality.

Extracted from trading_cycle.py as part of #439 refactoring.
Handles state reconciliation, stop adjustments, and position alerts.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


@dataclass
class Discrepancy:
    """Represents a mismatch between local state and broker reality."""

    type: str  # UNKNOWN_POSITION, GHOST_POSITION, ORDER_MISMATCH, QUANTITY_MISMATCH
    symbol: str
    details: Dict[str, Any]
    action: str  # NEEDS_HUMAN_REVIEW, AUTO_FIXED, REMOVED_FROM_JSON
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH


@dataclass
class StopAdjustment:
    """Represents a stop order modification needed."""

    symbol: str
    order_id: str
    current_stop: float
    new_stop: float
    reason: str
    profit_percent: float


@dataclass
class PositionAlertSummary:
    """Summary of position alerts for reporting."""

    symbol: str
    alert_type: str
    severity: str
    message: str
    timestamp: str
    current_price: float
    details: Dict[str, Any]


class StateReconciler:
    """
    Reconciles local JSON state with broker reality.

    Broker is always source of truth. Local JSON is for human reference.
    """

    def __init__(
        self,
        config: Any,
        trailing_stop_manager: Optional[Any] = None,
        position_tracker: Optional[Any] = None,
    ):
        """
        Initialize StateReconciler.

        Args:
            config: TradingConfig for risk parameters
            trailing_stop_manager: TrailingStopManager for stop calculations
            position_tracker: PositionTracker for alert checking
        """
        self.config = config
        self.trailing_stop_manager = trailing_stop_manager
        self.position_tracker = position_tracker

        logger.info("StateReconciler initialized")

    def reconcile(
        self,
        broker_state: Dict[str, Any],
        local_state: Dict[str, Any],
    ) -> tuple[List[Discrepancy], Dict[str, Any]]:
        """
        Reconcile local JSON with broker reality.
        JSON is for humans, broker is truth.

        Args:
            broker_state: Current state from broker
            local_state: Current local JSON state

        Returns:
            Tuple of (discrepancies list, updated local_state)
        """
        discrepancies = []
        positions = local_state.get("positions", {})

        # Check for unknown positions (at broker but not in local JSON)
        for symbol, broker_pos in broker_state["positions"].items():
            if symbol not in positions:
                discrepancies.append(
                    Discrepancy(
                        type="UNKNOWN_POSITION",
                        symbol=symbol,
                        details={
                            "broker_quantity": broker_pos["quantity"],
                            "broker_entry": broker_pos["entry_price"],
                            "current_price": broker_pos["current_price"],
                        },
                        action="NEEDS_HUMAN_REVIEW",
                        severity="HIGH",
                    )
                )

                # Extract stop/target prices from broker's open orders
                entry_price = broker_pos["entry_price"]
                stop_price, target_price, _ = self._extract_stop_target_from_orders(
                    symbol, broker_state, entry_price=entry_price, local_state=local_state
                )

                # Auto-add to local state for tracking
                positions[symbol] = {
                    "entry_price": broker_pos["entry_price"],
                    "quantity": broker_pos["quantity"],
                    "entry_time": now_iso(),
                    "source": "AUTO_DISCOVERED",
                    "stop_price": stop_price,
                    "target_price": target_price,
                }

        # Check for ghost positions (in local JSON but not at broker)
        for symbol in list(positions.keys()):
            if symbol not in broker_state["positions"]:
                local_pos = positions[symbol]
                discrepancies.append(
                    Discrepancy(
                        type="GHOST_POSITION",
                        symbol=symbol,
                        details={
                            "local_quantity": local_pos.get("quantity", 0),
                            "local_entry": local_pos.get("entry_price", 0),
                        },
                        action="REMOVED_FROM_JSON",
                        severity="MEDIUM",
                    )
                )

                # Remove ghost position
                del positions[symbol]

        # Check quantity mismatches
        for symbol in broker_state["positions"]:
            if symbol in positions:
                broker_qty = broker_state["positions"][symbol]["quantity"]
                local_qty = positions[symbol].get("quantity", 0)

                if broker_qty != local_qty:
                    discrepancies.append(
                        Discrepancy(
                            type="QUANTITY_MISMATCH",
                            symbol=symbol,
                            details={
                                "broker_quantity": broker_qty,
                                "local_quantity": local_qty,
                                "difference": broker_qty - local_qty,
                            },
                            action="AUTO_FIXED",
                            severity="LOW",
                        )
                    )

                    # Fix quantity
                    positions[symbol]["quantity"] = broker_qty

        # Sync stop/target prices from broker orders for all positions
        for symbol in broker_state["positions"]:
            if symbol in positions:
                entry_price = positions[symbol].get("entry_price")
                stop_price, target_price, _ = self._extract_stop_target_from_orders(
                    symbol, broker_state, entry_price=entry_price, local_state=local_state
                )

                # Update local state with broker's stop/target prices
                local_pos = positions[symbol]
                local_stop = local_pos.get("stop_price")
                local_target = local_pos.get("target_price")

                # Only log discrepancy if there was a change
                if stop_price != local_stop or target_price != local_target:
                    logger.info(
                        f"{symbol}: Syncing stop/target from orders - "
                        f"stop: {local_stop} -> {stop_price}, "
                        f"target: {local_target} -> {target_price}"
                    )
                    local_pos["stop_price"] = stop_price
                    local_pos["target_price"] = target_price

        local_state["positions"] = positions
        logger.info(f"Reconciliation found {len(discrepancies)} discrepancies")
        return discrepancies, local_state

    def _extract_stop_target_from_orders(
        self,
        symbol: str,
        broker_state: Dict[str, Any],
        entry_price: float = None,
        local_state: Dict[str, Any] = None,
    ) -> tuple:
        """
        Extract stop_price and target_price from broker's open orders for a symbol.

        If orders can't be found (Alpaca hides "held" stop orders), calculate expected
        stop from entry price and strategy config.

        Args:
            symbol: Ticker symbol
            broker_state: Current broker state with orders
            entry_price: Position entry price (for calculating expected stop if not found)
            local_state: Local state for saved stop values

        Returns:
            (stop_price, target_price, stop_verified) tuple
            - stop_verified: True if stop found in API, False if calculated
        """
        stop_price = None
        target_price = None
        stop_verified = False

        if symbol in broker_state.get("orders", {}):
            logger.debug(f"{symbol}: Found {len(broker_state['orders'][symbol])} orders")
            for order in broker_state["orders"][symbol]:
                order_type = order.get("type", "")
                side = order.get("side", "")

                # Convert enums to strings for comparison
                side_str = str(side).lower() if side else ""
                order_type_str = str(order_type).lower() if order_type else ""

                logger.debug(
                    f"  Order: type={order_type_str}, side={side_str}, "
                    f"stop={order.get('stop_price')}, limit={order.get('limit_price')}"
                )

                # Stop-loss order: sell order with stop_price set (for long positions)
                if "sell" in side_str and order.get("stop_price"):
                    stop_price = order["stop_price"]
                    stop_verified = True
                    logger.debug(f"  -> Found stop_price: {stop_price}")

                # Take-profit order: sell order with limit_price set (for long positions)
                elif "sell" in side_str and order.get("limit_price"):
                    target_price = order["limit_price"]
                    logger.debug(f"  -> Found target_price: {target_price}")
        else:
            logger.debug(f"{symbol}: No orders found in broker_state")

        # If stop not found via API, try to use saved value from local state first
        if not stop_price and local_state:
            positions = local_state.get("positions", {})
            if symbol in positions:
                saved_stop = positions[symbol].get("stop_price")
                if saved_stop:
                    stop_price = saved_stop
                    logger.info(f"{symbol}: Using saved stop price from local state: ${stop_price}")

        # Last resort: calculate from entry price if we have no saved value
        if not stop_price and entry_price:
            stop_loss_pct = self.config.get_risk_config("stop_loss")
            calculated_stop = round(entry_price * (1 - stop_loss_pct), 2)
            stop_price = calculated_stop
            logger.warning(
                f"{symbol}: Stop order hidden by Alpaca API, no saved value found. "
                f"Calculated from entry: ${calculated_stop}. "
                f"Verify actual stop on Alpaca dashboard."
            )

        logger.info(
            f"{symbol}: Extracted stop=${stop_price} (verified={stop_verified}), "
            f"target=${target_price}"
        )

        return stop_price, target_price, stop_verified

    def calculate_stop_adjustments(
        self,
        broker_state: Dict[str, Any],
        local_state: Dict[str, Any],
    ) -> tuple[List[StopAdjustment], Dict[str, Any]]:
        """
        Calculate which stops need adjustment based on current prices.

        Uses TrailingStopManager for progressive stop logic calculation.

        Args:
            broker_state: Current broker state
            local_state: Current local state

        Returns:
            Tuple of (adjustments list, updated local_state)
        """
        if self.trailing_stop_manager is None:
            logger.warning("No trailing stop manager configured")
            return [], local_state

        adjustments = []
        positions = local_state.get("positions", {})

        for symbol, broker_pos in broker_state["positions"].items():
            if symbol not in positions:
                continue  # Skip unknown positions

            local_pos = positions[symbol]
            entry_price = float(local_pos.get("entry_price", 0))
            current_price = broker_pos["current_price"]
            current_stop = local_pos.get("stop_price")
            quantity = int(broker_pos.get("quantity", 0))

            if not entry_price or not current_stop:
                continue  # No entry price or stop to adjust

            # Register position with TrailingStopManager if not already tracked
            if symbol not in self.trailing_stop_manager.stop_states:
                self.trailing_stop_manager.register_position(
                    symbol=symbol,
                    entry_price=entry_price,
                    initial_stop=current_stop,
                    quantity=quantity,
                    stop_order_id=None,
                )

            # Use TrailingStopManager to calculate new stop price
            new_stop = self.trailing_stop_manager.calculate_new_stop(symbol, current_price)

            if new_stop is None:
                continue  # No adjustment needed

            # Calculate profit percentage for reporting
            profit_percent = (current_price - entry_price) / entry_price

            # Determine reason based on profit level (for reporting)
            if profit_percent < 0.04:
                reason = f"Move to breakeven ({profit_percent:.1%} profit)"
            elif profit_percent < 0.06:
                reason = f"Lock 25% gains ({profit_percent:.1%} profit)"
            else:
                reason = f"Trail 50% gains ({profit_percent:.1%} profit)"

            logger.info(f"{symbol}: Stop adjustment recommended - {reason}")

            # Only adjust if new stop is higher than current stop
            if new_stop > current_stop + 0.01:  # $0.01 minimum move
                # Find the stop order ID from broker orders
                stop_order_id = None
                if symbol in broker_state.get("orders", {}):
                    for order in broker_state["orders"][symbol]:
                        if order["type"] in ["stop", "stop_loss"] and order["side"] == "sell":
                            stop_order_id = order["id"]
                            logger.debug(f"{symbol}: Found stop order ID {stop_order_id}")
                            break

                if stop_order_id:
                    adjustment_amount = new_stop - current_stop
                    adjustment_pct = (adjustment_amount / current_stop) * 100
                    logger.info(
                        f"{symbol}: Creating stop adjustment - "
                        f"${current_stop:.2f} → ${new_stop:.2f} "
                        f"(+${adjustment_amount:.2f}, +{adjustment_pct:.1f}%)"
                    )

                    adjustments.append(
                        StopAdjustment(
                            symbol=symbol,
                            order_id=stop_order_id,
                            current_stop=current_stop,
                            new_stop=new_stop,
                            reason=reason,
                            profit_percent=profit_percent,
                        )
                    )

                    # Update local state
                    positions[symbol]["stop_price"] = new_stop

                    # Update TrailingStopManager state to stay in sync
                    if symbol in self.trailing_stop_manager.stop_states:
                        self.trailing_stop_manager.stop_states[symbol].current_stop = new_stop
                else:
                    logger.warning(
                        f"{symbol}: Stop adjustment needed but no stop order found in broker orders"
                    )
            else:
                logger.debug(
                    f"{symbol}: New stop ${new_stop:.2f} not significantly higher "
                    f"than current ${current_stop:.2f}"
                )

        local_state["positions"] = positions
        logger.info(f"Found {len(adjustments)} stop adjustments needed")
        return adjustments, local_state

    def check_position_alerts(
        self,
        broker_state: Dict[str, Any],
        local_state: Dict[str, Any],
    ) -> List[PositionAlertSummary]:
        """
        Check all positions for exit alerts (approaching TP/SL).

        Args:
            broker_state: Current broker state with positions
            local_state: Current local state

        Returns:
            List of position alerts
        """
        if self.position_tracker is None:
            logger.warning("No position tracker configured")
            return []

        alerts = []
        positions = local_state.get("positions", {})

        for symbol, broker_pos in broker_state["positions"].items():
            if symbol not in positions:
                continue  # Skip unknown positions

            local_pos = positions[symbol]
            entry_price = float(local_pos.get("entry_price", 0))
            current_price = broker_pos["current_price"]
            take_profit_price = local_pos.get("target_price")
            stop_loss_price = local_pos.get("stop_price")

            if not entry_price or not take_profit_price or not stop_loss_price:
                continue  # Skip positions without complete data

            # Create or update position in tracker
            position_id = f"{symbol}_{entry_price}"
            try:
                if position_id not in self.position_tracker.positions:
                    # Create position for tracking
                    self.position_tracker.create_position(
                        ticker=symbol, entry_price=entry_price, quantity=broker_pos["quantity"]
                    )
                    # Manually set TP/SL prices to match configured values
                    if position_id in self.position_tracker.positions:
                        position = self.position_tracker.positions[position_id]
                        position.take_profit_price = take_profit_price
                        position.stop_loss_price = stop_loss_price

                # Check for exit conditions/alerts
                exit_check = self.position_tracker.check_exit_conditions(position_id, current_price)

                if exit_check and exit_check.get("recommendation") == "ALERT":
                    # Get the most recent alert for this position
                    if position_id in self.position_tracker.positions:
                        position = self.position_tracker.positions[position_id]
                        if position.alert_history:
                            recent_alert = position.alert_history[-1]
                            alerts.append(
                                PositionAlertSummary(
                                    symbol=symbol,
                                    alert_type=recent_alert.alert_type.value,
                                    severity=recent_alert.severity,
                                    message=recent_alert.format_message(),
                                    timestamp=recent_alert.timestamp.isoformat(),
                                    current_price=current_price,
                                    details=recent_alert.details,
                                )
                            )
            except (KeyError, Exception) as e:
                logger.warning(f"Position tracker error for {symbol}: {e}")

        logger.info(f"Found {len(alerts)} position alerts")
        return alerts
