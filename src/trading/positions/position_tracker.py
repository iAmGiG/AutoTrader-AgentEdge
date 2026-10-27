"""
Position Tracking - Pure Functions and Classes

Track open positions against their stop and, where one exists, their target, and raise
alerts when the price nears or crosses either. The routines keep one entry per open
symbol, synced to the live levels on every run (#599).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.utils.config_loader import ConfigLoader
from src.utils.date_utils import get_datetime_now, parse_date_string

logger = logging.getLogger(__name__)


class ExitReason(Enum):
    """Exit reasons for positions."""

    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    MANUAL = "manual"
    TIMEOUT = "timeout"


class AlertType(Enum):
    """Alert types for position monitoring."""

    APPROACHING_TAKE_PROFIT = "approaching_tp"
    APPROACHING_STOP_LOSS = "approaching_sl"
    STOP_ADJUSTED = "stop_adjusted"
    PROFIT_TARGET_REACHED = "profit_target_reached"
    LOSS_THRESHOLD_REACHED = "loss_threshold_reached"


# Alert when the price is within this fraction of a stop or target, measured from the price
WARNING_DISTANCE = 0.02
# Alerts kept per position, so the saved state stays small
MAX_ALERT_HISTORY = 50
SEVERITY_EMOJI = {"INFO": "📊", "WARNING": "⚠️", "CRITICAL": "🚨"}


def position_key(ticker: str) -> str:
    """The tracker's key for a position: one entry per open symbol."""
    return ticker.upper()


def alert_text(ticker: str, alert_type: AlertType, price: float, details: Dict[str, Any]) -> str:
    """One line describing an alert, without its severity marker."""
    distance = details.get("distance_pct", 0)
    stop = details.get("stop_price", 0)
    target = details.get("target_price", 0)
    if alert_type == AlertType.APPROACHING_STOP_LOSS:
        return f"{ticker} is {distance:.2f}% above its stop ${stop:.2f} (price ${price:.2f})"
    if alert_type == AlertType.LOSS_THRESHOLD_REACHED:
        return f"{ticker} is at or below its stop ${stop:.2f} (price ${price:.2f}), still open"
    if alert_type == AlertType.APPROACHING_TAKE_PROFIT:
        return f"{ticker} is {distance:.2f}% below its target ${target:.2f} (price ${price:.2f})"
    if alert_type == AlertType.PROFIT_TARGET_REACHED:
        return f"{ticker} is at or above its target ${target:.2f} (price ${price:.2f}), still open"
    if alert_type == AlertType.STOP_ADJUSTED:
        old_stop = details.get("old_stop", 0)
        new_stop = details.get("new_stop", 0)
        return f"{ticker} stop adjusted: ${old_stop:.2f} → ${new_stop:.2f}"
    return f"{ticker} alert: {alert_type.value}"


@dataclass
class PositionAlert:
    """Alert for position monitoring."""

    alert_id: str
    position_id: str
    ticker: str
    alert_type: AlertType
    timestamp: datetime
    current_price: float
    details: Dict[str, Any]
    severity: str = "INFO"  # INFO, WARNING, CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "position_id": self.position_id,
            "ticker": self.ticker,
            "alert_type": self.alert_type.value,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "details": self.details,
            "severity": self.severity,
        }

    def format_message(self) -> str:
        """Format alert as human-readable message."""
        emoji = SEVERITY_EMOJI.get(self.severity, "📊")
        return (
            f"{emoji} {alert_text(self.ticker, self.alert_type, self.current_price, self.details)}"
        )


@dataclass
class Position:
    """Position data structure with alert tracking."""

    position_id: str
    ticker: str
    entry_date: datetime
    entry_price: float
    quantity: int
    take_profit_price: Optional[float]  # None: no target (trailing-stop-only exits)
    stop_loss_price: float
    status: str = "ACTIVE"
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    alert_history: List[PositionAlert] = field(default_factory=list)
    last_alert_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "position_id": self.position_id,
            "ticker": self.ticker,
            "entry_date": self.entry_date.isoformat(),
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "take_profit_price": self.take_profit_price,
            "stop_loss_price": self.stop_loss_price,
            "status": self.status,
            "exit_date": self.exit_date.isoformat() if self.exit_date else None,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason.value if self.exit_reason else None,
            "alert_history": [alert.to_dict() for alert in self.alert_history],
            "last_alert_time": self.last_alert_time.isoformat() if self.last_alert_time else None,
        }

    def calculate_unrealized_pnl(self, current_price: float) -> Dict[str, float]:
        """Calculate unrealized P&L."""
        if self.status != "ACTIVE":
            return {"unrealized_pnl": 0.0, "unrealized_pnl_pct": 0.0}

        pnl = (current_price - self.entry_price) * self.quantity
        pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100

        return {"unrealized_pnl": pnl, "unrealized_pnl_pct": pnl_pct}

    def calculate_realized_pnl(self) -> Dict[str, float]:
        """Calculate realized P&L (for closed positions)."""
        if self.status == "ACTIVE" or self.exit_price is None:
            return {"realized_pnl": 0.0, "realized_pnl_pct": 0.0}

        pnl = (self.exit_price - self.entry_price) * self.quantity
        pnl_pct = ((self.exit_price - self.entry_price) / self.entry_price) * 100

        return {"realized_pnl": pnl, "realized_pnl_pct": pnl_pct}


class PositionTracker:
    """Position tracking with validated exit parameters and enhanced alerts."""

    def __init__(
        self,
        take_profit_pct: Optional[float] = None,
        stop_loss_pct: Optional[float] = None,
        alert_cooldown_seconds: int = 300,
        warning_pct: float = WARNING_DISTANCE,
    ):
        """
        Initialize with validated exit parameters.

        Args:
            take_profit_pct: Take profit percentage (default 8%)
            stop_loss_pct: Stop loss percentage (default 5%)
            alert_cooldown_seconds: Minimum seconds between repeated alerts (default 300 = 5 minutes)
            warning_pct: Alert when the price is this close to a level, as a fraction of
                the price (default 2%)
        """
        # Config is only read for a percentage not passed in
        config = ConfigLoader() if not (take_profit_pct and stop_loss_pct) else None
        self.take_profit_pct = take_profit_pct or config.get(
            "trading.default_take_profit_pct", 0.08
        )
        self.stop_loss_pct = stop_loss_pct or config.get("trading.default_stop_loss_pct", 0.05)
        self.alert_cooldown_seconds = alert_cooldown_seconds
        self.warning_pct = warning_pct
        self.positions: Dict[str, Position] = {}
        self.alert_counter = 0

    def create_position(self, ticker: str, entry_price: float, quantity: int) -> Position:
        """
        Create a new position with validated exit levels.

        Args:
            ticker: Stock ticker
            entry_price: Entry price
            quantity: Number of shares

        Returns:
            Created position
        """
        position_id = position_key(ticker)

        # Calculate exit levels using validated parameters
        take_profit_price = entry_price * (1 + self.take_profit_pct)
        stop_loss_price = entry_price * (1 - self.stop_loss_pct)

        position = Position(
            position_id=position_id,
            ticker=position_id,
            entry_date=get_datetime_now(),
            entry_price=entry_price,
            quantity=quantity,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
        )

        self.positions[position_id] = position
        return position

    def sync_position(
        self,
        ticker: str,
        entry_price: float,
        quantity: int,
        stop_loss_price: float,
        take_profit_price: Optional[float] = None,
    ) -> Position:
        """
        The entry for an open position, created or updated with the levels in force now
        (the live stop after any raise, and the target if there is one).

        Returns:
            The position, keyed by position_key(ticker)
        """
        key = position_key(ticker)
        position = self.positions.get(key)
        if position is None:
            position = Position(
                position_id=key,
                ticker=key,
                entry_date=get_datetime_now(),
                entry_price=entry_price,
                quantity=quantity,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
            )
            self.positions[key] = position
            return position
        position.entry_price = entry_price
        position.quantity = quantity
        position.stop_loss_price = stop_loss_price
        position.take_profit_price = take_profit_price
        position.status = "ACTIVE"
        position.exit_date = position.exit_price = position.exit_reason = None
        return position

    def prune(self, open_tickers) -> List[str]:
        """
        Drop every entry that isn't keyed to an open position: closed positions, and
        entries saved under the old timestamp keys.

        Returns:
            The keys dropped
        """
        keep = {position_key(ticker) for ticker in open_tickers}
        dropped = [key for key in self.positions if key not in keep]
        for key in dropped:
            del self.positions[key]
        if dropped:
            logger.info("Dropped %d tracker entries with no open position", len(dropped))
        return dropped

    def _should_send_alert(self, position: Position) -> bool:
        """
        Check if enough time has passed since last alert.

        Args:
            position: Position to check

        Returns:
            True if alert should be sent
        """
        if not position.last_alert_time:
            return True

        time_since_last = (get_datetime_now() - position.last_alert_time).total_seconds()
        return time_since_last >= self.alert_cooldown_seconds

    def _create_alert(
        self,
        position: Position,
        alert_type: AlertType,
        current_price: float,
        details: Dict[str, Any],
        severity: str = "INFO",
    ) -> PositionAlert:
        """
        Create and log an alert.

        Args:
            position: Position generating alert
            alert_type: Type of alert
            current_price: Current market price
            details: Alert details
            severity: Alert severity level

        Returns:
            Created alert
        """
        self.alert_counter += 1
        alert = PositionAlert(
            alert_id=f"alert_{position.position_id}_{self.alert_counter}",
            position_id=position.position_id,
            ticker=position.ticker,
            alert_type=alert_type,
            timestamp=get_datetime_now(),
            current_price=current_price,
            details=details,
            severity=severity,
        )

        # Add to position history
        position.alert_history.append(alert)
        del position.alert_history[:-MAX_ALERT_HISTORY]
        position.last_alert_time = alert.timestamp

        # Log the alert
        log_msg = alert.format_message()
        if severity == "CRITICAL":
            logger.critical(log_msg)
        elif severity == "WARNING":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return alert

    def check_exit_conditions(self, position_id: str, current_price: float) -> Optional[Dict]:
        """
        A position's alert condition at this price: through or near its stop, or its
        target if it has one. Distances are fractions of the price, the fall (or rise)
        from here that reaches the level.

        The condition is returned on every call. It is added to the position's alert
        history (and logged) when it differs from the last one recorded, or when the
        cooldown has passed since then.

        Args:
            position_id: Position ID
            current_price: Current market price

        Returns:
            None, or a dict with recommendation ("EXIT" when the price is through a level
            while the position is still open, else "ALERT"), reason, alert_type, severity,
            message, details, and alert (the history entry this call added, or None); plus
            exit_price and pnl_pct for EXIT, distance_pct and distance_dollars for ALERT
        """
        position = self.positions.get(position_id)
        if not position or position.status != "ACTIVE":
            return None

        found = [
            condition
            for condition in (
                self._stop_condition(position, current_price),
                self._target_condition(position, current_price),
            )
            if condition
        ]
        if not found:
            return None
        # The more severe one; the stop's on a tie
        condition = max(found, key=lambda c: c["severity"] == "CRITICAL")
        details = condition["details"]
        # The keys earlier versions returned
        if condition["recommendation"] == "EXIT":
            condition.update(exit_price=current_price, pnl_pct=details["profit_pct"])
        else:
            condition.update(
                distance_pct=details["distance_pct"], distance_dollars=details["distance_dollars"]
            )

        # A new kind of condition (say, near the stop, then through it) is always recorded;
        # the cooldown only spaces out repeats of the same one
        history = position.alert_history
        changed = not history or history[-1].alert_type != condition["alert_type"]
        alert = None
        if changed or self._should_send_alert(position):
            alert = self._create_alert(
                position,
                condition["alert_type"],
                current_price,
                condition["details"],
                severity=condition["severity"],
            )
        text = alert_text(
            position.ticker, condition["alert_type"], current_price, condition["details"]
        )
        condition["message"] = f"{SEVERITY_EMOJI[condition['severity']]} {text}"
        condition["alert"] = alert
        return condition

    def _stop_condition(self, position: Position, price: float) -> Optional[Dict]:
        """Through or near the stop; None without a stop, or with the price well clear."""
        stop = position.stop_loss_price
        if not stop:
            return None
        distance = (price - stop) / price
        details = {
            "stop_price": stop,
            "distance_pct": distance * 100,
            "distance_dollars": price - stop,
            "profit_pct": (price - position.entry_price) / position.entry_price * 100,
        }
        if price <= stop:
            return {
                "recommendation": "EXIT",
                "reason": ExitReason.STOP_LOSS,
                "alert_type": AlertType.LOSS_THRESHOLD_REACHED,
                "severity": "CRITICAL",
                "details": details,
            }
        if distance < self.warning_pct:
            return {
                "recommendation": "ALERT",
                "reason": "APPROACHING_SL",
                "alert_type": AlertType.APPROACHING_STOP_LOSS,
                "severity": "WARNING",
                "details": details,
            }
        return None

    def _target_condition(self, position: Position, price: float) -> Optional[Dict]:
        """Through or near the target; None without a target, or with the price well clear."""
        target = position.take_profit_price
        if not target:
            return None
        distance = (target - price) / price
        details = {
            "target_price": target,
            "distance_pct": distance * 100,
            "distance_dollars": target - price,
            "profit_pct": (price - position.entry_price) / position.entry_price * 100,
        }
        if price >= target:
            return {
                "recommendation": "EXIT",
                "reason": ExitReason.TAKE_PROFIT,
                "alert_type": AlertType.PROFIT_TARGET_REACHED,
                "severity": "CRITICAL",
                "details": details,
            }
        if distance < self.warning_pct:
            return {
                "recommendation": "ALERT",
                "reason": "APPROACHING_TP",
                "alert_type": AlertType.APPROACHING_TAKE_PROFIT,
                "severity": "WARNING",
                "details": details,
            }
        return None

    def close_position(
        self, position_id: str, exit_price: float, exit_reason: ExitReason = ExitReason.MANUAL
    ) -> bool:
        """
        Close a position.

        Args:
            position_id: Position ID
            exit_price: Exit price
            exit_reason: Reason for exit

        Returns:
            True if successful
        """
        position = self.positions.get(position_id)
        if not position or position.status != "ACTIVE":
            return False

        position.exit_date = get_datetime_now()
        position.exit_price = exit_price
        position.exit_reason = exit_reason
        position.status = "CLOSED"

        return True

    def get_active_positions(self) -> List[Position]:
        """Get all active positions."""
        return [p for p in self.positions.values() if p.status == "ACTIVE"]

    def get_all_alerts(self, since: Optional[datetime] = None) -> List[PositionAlert]:
        """
        Get all alerts across all positions.

        Args:
            since: Optional datetime to filter alerts after this time

        Returns:
            List of alerts
        """
        all_alerts = []
        for position in self.positions.values():
            if since:
                alerts = [a for a in position.alert_history if a.timestamp >= since]
            else:
                alerts = position.alert_history
            all_alerts.extend(alerts)

        # Sort by timestamp (most recent first)
        all_alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return all_alerts

    def get_position_alerts(self, position_id: str) -> List[PositionAlert]:
        """
        Get alerts for a specific position.

        Args:
            position_id: Position ID

        Returns:
            List of alerts for this position
        """
        position = self.positions.get(position_id)
        if not position:
            return []
        return position.alert_history

    def get_alert_history(self, limit: int = 10) -> List[PositionAlert]:
        """
        Get recent alert history across all positions.

        Args:
            limit: Maximum number of alerts to return (default 10)

        Returns:
            List of recent alerts, sorted by timestamp (most recent first)
        """
        all_alerts = self.get_all_alerts()
        return all_alerts[:limit]

    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Get summary of all alerts.

        Returns:
            Dictionary with alert counts and recent alerts
        """
        all_alerts = self.get_all_alerts()

        alert_counts = {
            "total": len(all_alerts),
            "critical": len([a for a in all_alerts if a.severity == "CRITICAL"]),
            "warning": len([a for a in all_alerts if a.severity == "WARNING"]),
            "info": len([a for a in all_alerts if a.severity == "INFO"]),
        }

        # Get recent alerts (last 10)
        recent_alerts = all_alerts[:10]

        return {
            "counts": alert_counts,
            "recent_alerts": [alert.to_dict() for alert in recent_alerts],
            "alert_messages": [alert.format_message() for alert in recent_alerts],
        }

    def get_position_summary(self, current_prices: Dict[str, float]) -> Dict:
        """
        Get portfolio position summary.

        Args:
            current_prices: Dictionary of ticker -> current price

        Returns:
            Portfolio summary
        """
        active_positions = self.get_active_positions()

        total_value = 0.0
        total_pnl = 0.0
        position_count = len(active_positions)

        position_details = []

        for position in active_positions:
            current_price = current_prices.get(position.ticker)
            if current_price:
                pnl_data = position.calculate_unrealized_pnl(current_price)
                position_value = current_price * position.quantity

                total_value += position_value
                total_pnl += pnl_data["unrealized_pnl"]

                position_details.append(
                    {
                        "position_id": position.position_id,
                        "ticker": position.ticker,
                        "quantity": position.quantity,
                        "entry_price": position.entry_price,
                        "current_price": current_price,
                        "position_value": position_value,
                        "unrealized_pnl": pnl_data["unrealized_pnl"],
                        "unrealized_pnl_pct": pnl_data["unrealized_pnl_pct"],
                        "take_profit_price": position.take_profit_price,
                        "stop_loss_price": position.stop_loss_price,
                    }
                )

        return {
            "active_positions": position_count,
            "total_position_value": total_value,
            "total_unrealized_pnl": total_pnl,
            "positions": position_details,
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize tracker state including all positions and alert history.

        Returns:
            Dictionary containing tracker configuration and all position data
        """
        return {
            "config": {
                "take_profit_pct": self.take_profit_pct,
                "stop_loss_pct": self.stop_loss_pct,
                "alert_cooldown_seconds": self.alert_cooldown_seconds,
            },
            "alert_counter": self.alert_counter,
            "positions": {
                position_id: position.to_dict() for position_id, position in self.positions.items()
            },
        }

    def restore_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Restore tracker state from serialized data, replacing what the tracker holds.

        Alert types this version doesn't know are skipped, and each position keeps its
        latest MAX_ALERT_HISTORY alerts.

        Args:
            data: Dictionary from to_dict()
        """
        # Restore counter
        self.alert_counter = data.get("alert_counter", 0)

        # Restore positions
        positions: Dict[str, Position] = {}
        for position_id, pos_data in data.get("positions", {}).items():
            # Reconstruct PositionAlert objects
            alert_history = []
            for alert_data in pos_data.get("alert_history", [])[-MAX_ALERT_HISTORY:]:
                try:
                    alert_type = AlertType(alert_data["alert_type"])
                except ValueError:
                    continue
                alert = PositionAlert(
                    alert_id=alert_data["alert_id"],
                    position_id=alert_data["position_id"],
                    ticker=alert_data["ticker"],
                    alert_type=alert_type,
                    timestamp=parse_date_string(alert_data["timestamp"]),
                    current_price=alert_data["current_price"],
                    details=alert_data["details"],
                    severity=alert_data["severity"],
                )
                alert_history.append(alert)

            # Reconstruct Position object
            position = Position(
                position_id=pos_data["position_id"],
                ticker=pos_data["ticker"],
                entry_date=parse_date_string(pos_data["entry_date"]),
                entry_price=pos_data["entry_price"],
                quantity=pos_data["quantity"],
                take_profit_price=pos_data.get("take_profit_price"),
                stop_loss_price=pos_data["stop_loss_price"],
                status=pos_data["status"],
                exit_date=(
                    parse_date_string(pos_data["exit_date"]) if pos_data.get("exit_date") else None
                ),
                exit_price=pos_data.get("exit_price"),
                exit_reason=(
                    ExitReason(pos_data["exit_reason"]) if pos_data.get("exit_reason") else None
                ),
                alert_history=alert_history,
                last_alert_time=(
                    parse_date_string(pos_data["last_alert_time"])
                    if pos_data.get("last_alert_time")
                    else None
                ),
            )

            positions[position_id] = position

        self.positions = positions
        logger.info(f"Restored {len(self.positions)} positions with alert history from state")
