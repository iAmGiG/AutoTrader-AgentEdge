"""
Position Tracking - Pure Functions and Classes

Track positions with validated exit parameters (8% TP / 5% SL).
"""

import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class ExitReason(Enum):
    """Exit reasons for positions."""
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    MANUAL = "manual"
    TIMEOUT = "timeout"


@dataclass
class Position:
    """Position data structure."""
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
            'exit_reason': self.exit_reason.value if self.exit_reason else None
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
    """Position tracking with validated exit parameters."""
    
    def __init__(self, take_profit_pct: float = 0.08, stop_loss_pct: float = 0.05):
        """
        Initialize with validated exit parameters.
        
        Args:
            take_profit_pct: Take profit percentage (default 8%)
            stop_loss_pct: Stop loss percentage (default 5%)
        """
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.positions: Dict[str, Position] = {}
        
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
    
    def check_exit_conditions(self, position_id: str, current_price: float) -> Optional[Dict]:
        """
        Check if position should be exited.
        
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
            return {
                'recommendation': 'EXIT',
                'reason': ExitReason.TAKE_PROFIT,
                'exit_price': current_price,
                'pnl_pct': ((current_price - position.entry_price) / position.entry_price) * 100
            }
        
        # Check stop loss  
        if current_price <= position.stop_loss_price:
            return {
                'recommendation': 'EXIT',
                'reason': ExitReason.STOP_LOSS,
                'exit_price': current_price,
                'pnl_pct': ((current_price - position.entry_price) / position.entry_price) * 100
            }
        
        # Check approaching levels (for alerts)
        tp_distance = (position.take_profit_price - current_price) / position.entry_price
        sl_distance = (current_price - position.stop_loss_price) / position.entry_price
        
        if tp_distance < 0.02:  # Within 2% of take profit
            return {
                'recommendation': 'ALERT',
                'reason': 'APPROACHING_TP',
                'distance_pct': tp_distance * 100
            }
            
        if sl_distance < 0.02:  # Within 2% of stop loss
            return {
                'recommendation': 'ALERT', 
                'reason': 'APPROACHING_SL',
                'distance_pct': sl_distance * 100
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