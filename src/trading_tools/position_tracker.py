"""
Position Tracking - Pure Functions and Classes

Track positions with validated exit parameters (8% TP / 5% SL).
Enhanced with exit alerts and dynamic stop integration.
"""

import pandas as pd
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

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
            'alert_id': self.alert_id,
            'position_id': self.position_id,
            'ticker': self.ticker,
            'alert_type': self.alert_type.value,
            'timestamp': self.timestamp.isoformat(),
            'current_price': self.current_price,
            'details': self.details,
            'severity': self.severity
        }

    def format_message(self) -> str:
        """Format alert as human-readable message."""
        severity_emoji = {
            'INFO': '📊',
            'WARNING': '⚠️',
            'CRITICAL': '🚨'
        }
        emoji = severity_emoji.get(self.severity, '📊')

        if self.alert_type == AlertType.APPROACHING_TAKE_PROFIT:
            distance = self.details.get('distance_pct', 0)
            return (f"{emoji} {self.ticker} approaching take profit! "
                   f"Current: ${self.current_price:.2f}, Distance: {distance:.2f}%")

        elif self.alert_type == AlertType.APPROACHING_STOP_LOSS:
            distance = self.details.get('distance_pct', 0)
            return (f"{emoji} {self.ticker} approaching stop loss! "
                   f"Current: ${self.current_price:.2f}, Distance: {distance:.2f}%")

        elif self.alert_type == AlertType.STOP_ADJUSTED:
            old_stop = self.details.get('old_stop', 0)
            new_stop = self.details.get('new_stop', 0)
            return (f"{emoji} {self.ticker} stop adjusted: "
                   f"${old_stop:.2f} → ${new_stop:.2f}")

        elif self.alert_type == AlertType.PROFIT_TARGET_REACHED:
            profit_pct = self.details.get('profit_pct', 0)
            return (f"{emoji} {self.ticker} profit target reached! "
                   f"Current: ${self.current_price:.2f}, Profit: {profit_pct:.1f}%")

        elif self.alert_type == AlertType.LOSS_THRESHOLD_REACHED:
            loss_pct = self.details.get('loss_pct', 0)
            return (f"{emoji} {self.ticker} loss threshold reached! "
                   f"Current: ${self.current_price:.2f}, Loss: {loss_pct:.1f}%")

        return f"{emoji} {self.ticker} alert: {self.alert_type.value}"


@dataclass
class Position:
    """Position data structure with alert tracking."""
    position_id: str
    ticker: str
    entry_date: datetime
    entry_price: float
    quantity: int
    take_profit_price: float
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
            'position_id': self.position_id,
            'ticker': self.ticker,
            'entry_date': self.entry_date.isoformat(),
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'take_profit_price': self.take_profit_price,
            'stop_loss_price': self.stop_loss_price,
            'status': self.status,
            'exit_date': self.exit_date.isoformat() if self.exit_date else None,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason.value if self.exit_reason else None,
            'alert_history': [alert.to_dict() for alert in self.alert_history],
            'last_alert_time': self.last_alert_time.isoformat() if self.last_alert_time else None
        }
    
    def calculate_unrealized_pnl(self, current_price: float) -> Dict[str, float]:
        """Calculate unrealized P&L."""
        if self.status != "ACTIVE":
            return {'unrealized_pnl': 0.0, 'unrealized_pnl_pct': 0.0}
            
        pnl = (current_price - self.entry_price) * self.quantity
        pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
        
        return {
            'unrealized_pnl': pnl,
            'unrealized_pnl_pct': pnl_pct
        }
    
    def calculate_realized_pnl(self) -> Dict[str, float]:
        """Calculate realized P&L (for closed positions)."""
        if self.status == "ACTIVE" or self.exit_price is None:
            return {'realized_pnl': 0.0, 'realized_pnl_pct': 0.0}
            
        pnl = (self.exit_price - self.entry_price) * self.quantity
        pnl_pct = ((self.exit_price - self.entry_price) / self.entry_price) * 100
        
        return {
            'realized_pnl': pnl,
            'realized_pnl_pct': pnl_pct
        }


class PositionTracker:
    """Position tracking with validated exit parameters and enhanced alerts."""

    def __init__(self, take_profit_pct: float = 0.08, stop_loss_pct: float = 0.05,
                 alert_cooldown_seconds: int = 300):
        """
        Initialize with validated exit parameters.

        Args:
            take_profit_pct: Take profit percentage (default 8%)
            stop_loss_pct: Stop loss percentage (default 5%)
            alert_cooldown_seconds: Minimum seconds between repeated alerts (default 300 = 5 minutes)
        """
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.alert_cooldown_seconds = alert_cooldown_seconds
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
        position_id = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Calculate exit levels using validated parameters
        take_profit_price = entry_price * (1 + self.take_profit_pct)
        stop_loss_price = entry_price * (1 - self.stop_loss_pct)
        
        position = Position(
            position_id=position_id,
            ticker=ticker,
            entry_date=datetime.now(),
            entry_price=entry_price,
            quantity=quantity,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price
        )
        
        self.positions[position_id] = position
        return position
    
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

        time_since_last = (datetime.now() - position.last_alert_time).total_seconds()
        return time_since_last >= self.alert_cooldown_seconds

    def _create_alert(self, position: Position, alert_type: AlertType,
                     current_price: float, details: Dict[str, Any],
                     severity: str = "INFO") -> PositionAlert:
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
            timestamp=datetime.now(),
            current_price=current_price,
            details=details,
            severity=severity
        )

        # Add to position history
        position.alert_history.append(alert)
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
        Check if position should be exited with enhanced alert generation.

        Args:
            position_id: Position ID
            current_price: Current market price

        Returns:
            Exit recommendation or None
        """
        position = self.positions.get(position_id)
        if not position or position.status != "ACTIVE":
            return None

        # Check take profit
        if current_price >= position.take_profit_price:
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100

            # Generate critical alert
            if self._should_send_alert(position):
                self._create_alert(
                    position,
                    AlertType.PROFIT_TARGET_REACHED,
                    current_price,
                    {'profit_pct': pnl_pct, 'target_price': position.take_profit_price},
                    severity="CRITICAL"
                )

            return {
                'recommendation': 'EXIT',
                'reason': ExitReason.TAKE_PROFIT,
                'exit_price': current_price,
                'pnl_pct': pnl_pct
            }

        # Check stop loss
        if current_price <= position.stop_loss_price:
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100

            # Generate critical alert
            if self._should_send_alert(position):
                self._create_alert(
                    position,
                    AlertType.LOSS_THRESHOLD_REACHED,
                    current_price,
                    {'loss_pct': pnl_pct, 'stop_price': position.stop_loss_price},
                    severity="CRITICAL"
                )

            return {
                'recommendation': 'EXIT',
                'reason': ExitReason.STOP_LOSS,
                'exit_price': current_price,
                'pnl_pct': pnl_pct
            }

        # Check approaching levels (for alerts)
        tp_distance = (position.take_profit_price - current_price) / position.entry_price
        sl_distance = (current_price - position.stop_loss_price) / position.entry_price

        if tp_distance < 0.02:  # Within 2% of take profit
            if self._should_send_alert(position):
                self._create_alert(
                    position,
                    AlertType.APPROACHING_TAKE_PROFIT,
                    current_price,
                    {
                        'distance_pct': tp_distance * 100,
                        'target_price': position.take_profit_price,
                        'distance_dollars': position.take_profit_price - current_price
                    },
                    severity="WARNING"
                )

            return {
                'recommendation': 'ALERT',
                'reason': 'APPROACHING_TP',
                'distance_pct': tp_distance * 100,
                'distance_dollars': position.take_profit_price - current_price
            }

        if sl_distance < 0.02:  # Within 2% of stop loss
            if self._should_send_alert(position):
                self._create_alert(
                    position,
                    AlertType.APPROACHING_STOP_LOSS,
                    current_price,
                    {
                        'distance_pct': sl_distance * 100,
                        'stop_price': position.stop_loss_price,
                        'distance_dollars': current_price - position.stop_loss_price
                    },
                    severity="WARNING"
                )

            return {
                'recommendation': 'ALERT',
                'reason': 'APPROACHING_SL',
                'distance_pct': sl_distance * 100,
                'distance_dollars': current_price - position.stop_loss_price
            }

        return None
    
    def close_position(self, position_id: str, exit_price: float, exit_reason: ExitReason = ExitReason.MANUAL) -> bool:
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
            
        position.exit_date = datetime.now()
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

    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Get summary of all alerts.

        Returns:
            Dictionary with alert counts and recent alerts
        """
        all_alerts = self.get_all_alerts()

        alert_counts = {
            'total': len(all_alerts),
            'critical': len([a for a in all_alerts if a.severity == "CRITICAL"]),
            'warning': len([a for a in all_alerts if a.severity == "WARNING"]),
            'info': len([a for a in all_alerts if a.severity == "INFO"])
        }

        # Get recent alerts (last 10)
        recent_alerts = all_alerts[:10]

        return {
            'counts': alert_counts,
            'recent_alerts': [alert.to_dict() for alert in recent_alerts],
            'alert_messages': [alert.format_message() for alert in recent_alerts]
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
                total_pnl += pnl_data['unrealized_pnl']
                
                position_details.append({
                    'position_id': position.position_id,
                    'ticker': position.ticker,
                    'quantity': position.quantity,
                    'entry_price': position.entry_price,
                    'current_price': current_price,
                    'position_value': position_value,
                    'unrealized_pnl': pnl_data['unrealized_pnl'],
                    'unrealized_pnl_pct': pnl_data['unrealized_pnl_pct'],
                    'take_profit_price': position.take_profit_price,
                    'stop_loss_price': position.stop_loss_price
                })
        
        return {
            'active_positions': position_count,
            'total_position_value': total_value,
            'total_unrealized_pnl': total_pnl,
            'positions': position_details
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize tracker state including all positions and alert history.

        Returns:
            Dictionary containing tracker configuration and all position data
        """
        return {
            'config': {
                'take_profit_pct': self.take_profit_pct,
                'stop_loss_pct': self.stop_loss_pct,
                'alert_cooldown_seconds': self.alert_cooldown_seconds
            },
            'alert_counter': self.alert_counter,
            'positions': {
                position_id: position.to_dict()
                for position_id, position in self.positions.items()
            }
        }

    def restore_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Restore tracker state from serialized data.

        Args:
            data: Dictionary from to_dict()
        """
        # Restore counter
        self.alert_counter = data.get('alert_counter', 0)

        # Restore positions
        for position_id, pos_data in data.get('positions', {}).items():
            # Reconstruct PositionAlert objects
            alert_history = []
            for alert_data in pos_data.get('alert_history', []):
                alert = PositionAlert(
                    alert_id=alert_data['alert_id'],
                    position_id=alert_data['position_id'],
                    ticker=alert_data['ticker'],
                    alert_type=AlertType(alert_data['alert_type']),
                    timestamp=datetime.fromisoformat(alert_data['timestamp']),
                    current_price=alert_data['current_price'],
                    details=alert_data['details'],
                    severity=alert_data['severity']
                )
                alert_history.append(alert)

            # Reconstruct Position object
            position = Position(
                position_id=pos_data['position_id'],
                ticker=pos_data['ticker'],
                entry_date=datetime.fromisoformat(pos_data['entry_date']),
                entry_price=pos_data['entry_price'],
                quantity=pos_data['quantity'],
                take_profit_price=pos_data['take_profit_price'],
                stop_loss_price=pos_data['stop_loss_price'],
                status=pos_data['status'],
                exit_date=datetime.fromisoformat(pos_data['exit_date']) if pos_data.get('exit_date') else None,
                exit_price=pos_data.get('exit_price'),
                exit_reason=ExitReason(pos_data['exit_reason']) if pos_data.get('exit_reason') else None,
                alert_history=alert_history,
                last_alert_time=datetime.fromisoformat(pos_data['last_alert_time']) if pos_data.get('last_alert_time') else None
            )

            self.positions[position_id] = position

        logger.info(f"Restored {len(self.positions)} positions with alert history from state")