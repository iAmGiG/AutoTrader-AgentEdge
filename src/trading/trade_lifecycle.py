"""
Trade Lifecycle State Machine - Foundation for Trade Management

Implements conservative stop logic and state persistence for individual trades.
Built on existing Order Management (#313) and validated MACD+RSI signals.
Uses unified PositionManager and OrderManager for proper state tracking.
"""

import json
import logging
import os
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Dict, Optional

from config_defaults.trading_config import TradingConfig

from src.trading.order_manager import OrderManager
from src.trading.position_manager import PositionManager
from src.trading.unified_price_fetcher import get_current_price

logger = logging.getLogger(__name__)


# CRITICAL FIX: Rate limiting to prevent API throttling
class SimpleRateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 180):
        self.calls_per_minute = calls_per_minute
        self.calls = deque()
        self.lock = Lock()

    def wait_if_needed(self):
        """Wait if we're approaching rate limits."""
        with self.lock:
            now = time.time()

            # Remove calls older than 1 minute
            while self.calls and self.calls[0] < now - 60:
                self.calls.popleft()

            # If at limit, wait
            if len(self.calls) >= self.calls_per_minute:
                sleep_time = 61 - (now - self.calls[0])  # Wait until oldest call expires
                if sleep_time > 0:
                    logger.warning(f"Rate limit hit, waiting {sleep_time:.1f}s")
                    time.sleep(sleep_time)

            # Record this call
            self.calls.append(now)


# Global rate limiter
rate_limiter = SimpleRateLimiter()


class TradeState(Enum):
    """Trade lifecycle states"""
    SIGNAL_GENERATED = "signal"     # MACD+RSI voting generates signal
    ORDER_PENDING = "pending"       # Entry order placed, waiting for fill
    POSITION_OPEN = "open"          # Position filled, stop/target active
    STOP_ADJUSTED = "adjusted"      # Trailing stop or manual adjustment
    EXIT_TRIGGERED = "exiting"      # Exit signal received, closing position
    POSITION_CLOSED = "closed"      # Trade complete, P&L realized


@dataclass
class TradeData:
    """Trade data for JSON persistence"""
    symbol: str
    state: str
    entry_price: Optional[float] = None
    current_stop: Optional[float] = None
    target_price: Optional[float] = None
    quantity: int = 0
    entry_time: Optional[str] = None
    last_adjustment: Optional[str] = None
    signal_strength: str = "NEUTRAL"
    confidence: float = 0.0
    # {'entry': 'order_123', 'stop': 'order_456', 'target': 'order_789'}
    order_ids: Dict[str, str] = None

    def __post_init__(self):
        if self.order_ids is None:
            self.order_ids = {}


@dataclass
class OpportunityData:
    """New trading opportunity for comparison"""
    symbol: str
    signal_strength: str
    confidence: float
    current_price: float
    expected_entry: float
    expected_target: float
    expected_profit: float = None

    def __post_init__(self):
        if self.expected_profit is None:
            self.expected_profit = self.expected_target - self.expected_entry


class TradeCycle:
    """
    Single trade from signal to close with conservative stop logic.

    Implements proven position sizing and progressive stop adjustments.
    Uses JSON files for state persistence (no database complexity).
    """

    def __init__(self, symbol: str, signal_strength: str = "BULLISH", confidence: float = 0.7,
                 broker_client=None, config: Optional[TradingConfig] = None):
        """
        Initialize trade cycle.

        Args:
            symbol: Stock symbol (e.g., 'TQQQ')
            signal_strength: 'BULLISH', 'NEUTRAL', or 'BEARISH'
            confidence: Signal confidence 0.0-1.0
            broker_client: Alpaca broker client (optional, will use paper mode if None)
            config: Trading configuration (loads defaults if None)
        """
        self.symbol = symbol
        self.data = TradeData(
            symbol=symbol,
            state=TradeState.SIGNAL_GENERATED.value,
            signal_strength=signal_strength,
            confidence=confidence
        )

        # Initialize unified components
        if broker_client is None:
            # Use paper mode by default
            from src.trading.alpaca_trading_client import AlpacaOrderManager
            old_manager = AlpacaOrderManager(mode="paper")
            broker_client = old_manager.client.trading_client

        self.position_manager = PositionManager(broker_client)
        self.order_manager = OrderManager(broker_client, self.position_manager)

        # Load trading configuration with fallback
        try:
            self.config = config or TradingConfig()
        except Exception as e:
            logger.warning(f"Could not load trading config: {e}. Using hardcoded defaults.")
            self.config = self._create_fallback_config()

        # CRITICAL FIX: Fill monitoring system
        self.last_fill_check = 0

        # State file paths
        self.state_dir = "state"
        self.positions_file = os.path.join(self.state_dir, "positions.json")
        os.makedirs(self.state_dir, exist_ok=True)

        logger.info(
            f"TradeCycle initialized: {symbol} {signal_strength} (confidence: {confidence:.2f})")

    def _create_fallback_config(self):
        """Create hardcoded fallback config when file loading fails."""
        class FallbackConfig:
            def get_exit_config(self):
                class ExitConfig:
                    stop_loss = 0.05  # 5%
                    take_profit = 0.08  # 8%
                    description = "Hardcoded fallback: 8% TP / 5% SL"
                return ExitConfig()
        return FallbackConfig()

    # Price fetching now handled by unified_price_fetcher.get_current_price()

    def check_order_fills(self) -> bool:
        """
        CRITICAL FIX: Check if pending orders have filled.

        This is the missing piece that transitions ORDER_PENDING -> POSITION_OPEN
        when broker confirms the order was filled.

        Returns:
            True if any orders filled and state was updated
        """
        if self.data.state != TradeState.ORDER_PENDING.value:
            return False

        return self.monitor_fills_simple()

    def monitor_fills_simple(self) -> bool:
        """Check for filled orders by polling Alpaca."""
        try:
            if not self.data.order_ids.get('parent'):
                logger.warning("No parent order ID to check")
                return False
            
            # Rate limit API calls
            rate_limiter.wait_if_needed()
            
            # Get recent filled orders for this symbol
            from datetime import timedelta
            recent_cutoff = datetime.now() - timedelta(minutes=5)
            
            # Use the broker client directly (avoid circular dependencies)
            orders = self.position_manager.broker.get_orders(
                status='filled',
                limit=50,
                after=recent_cutoff.isoformat()
            )
            
            for order in orders:
                if order.symbol == self.symbol and order.id == self.data.order_ids['parent']:
                    # Found our filled order!
                    fill_data = {
                        'symbol': self.symbol,
                        'side': order.side,
                        'qty': float(order.filled_qty),
                        'filled_price': float(order.filled_avg_price),
                        'filled_at': (order.filled_at.isoformat() 
                                    if order.filled_at 
                                    else datetime.now().isoformat())
                    }
                    self._handle_order_fill(fill_data)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Fill monitoring failed: {e}")
            return False

    def _handle_order_fill(self, filled_order: Dict[str, Any]):
        """
        Handle a filled order by updating trade state.

        Args:
            filled_order: Fill notification from OrderManager
        """
        try:
            # Update trade data with fill information
            self.data.actual_entry_price = filled_order['filled_price']
            self.data.actual_quantity = filled_order['qty']
            self.data.entry_time = filled_order['filled_at']

            # Transition state: ORDER_PENDING -> POSITION_OPEN
            self.data.state = TradeState.POSITION_OPEN.value

            # Save updated state
            self.save_state()

            logger.info(
                f"Order filled: {self.symbol} - {filled_order['side']} "
                f"{filled_order['qty']} @ ${filled_order['filled_price']}")
            logger.info(
                f"Trade state: {TradeState.ORDER_PENDING.value} -> "
                f"{TradeState.POSITION_OPEN.value}")
            
            return True  # Success

        except Exception as e:
            logger.error(f"Error handling order fill for {self.symbol}: {e}")
            return False  # Failure

    def parse_bracket_response(self, bracket_response: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract order IDs from bracket order response.

        Alpaca bracket orders return:
        - Parent order (entry)
        - Two attached orders (stop-loss and take-profit)

        Args:
            bracket_response: Response from place_bracket_order

        Returns:
            Dictionary with order IDs for entry, stop, and target
        """
        try:
            order_ids = {}

            # Handle different response formats
            if 'order_id' in bracket_response:
                # Simple format - single order ID (might be parent)
                order_ids['entry'] = bracket_response['order_id']
                logger.warning("Simple order ID format - may need bracket order tracking")

            elif 'parent' in bracket_response:
                # Complex bracket format
                order_ids['entry'] = bracket_response['parent']['id']

                # Alpaca doesn't return legs in the initial response
                # The OCO orders are created asynchronously
                # We'll need to query for them separately
                logger.info(f"Bracket order placed with parent ID: {order_ids['entry']}")
                logger.info("OCO orders will be created automatically by Alpaca")

            else:
                # Fallback - use whatever ID we have
                for key in ['id', 'order_id', 'orderid']:
                    if key in bracket_response:
                        order_ids['entry'] = bracket_response[key]
                        break

            logger.info(f"Parsed order IDs: {order_ids}")
            return order_ids

        except Exception as e:
            logger.error(f"Error parsing bracket response: {e}")
            # Return basic structure to prevent crashes
            return {
                'entry': bracket_response.get('order_id', 'unknown'),
                'stop': 'pending',
                'target': 'pending'
            }

    def calculate_position_size(self, account_balance: float, current_price: float) -> int:
        """
        Calculate position size based on conservative rules.

        Small account best practices:
        - Never more than 20% in one position
        - Position size = min(20% of account, $5000) to start
        - Keep 20% cash reserve always

        Args:
            account_balance: Current account balance
            current_price: Current stock price

        Returns:
            Number of shares to buy
        """
        # Conservative position sizing
        max_position_value = min(account_balance * 0.20, 5000)  # 20% or $5K max

        # Calculate shares (round down to avoid over-allocation)
        shares = int(max_position_value / current_price)

        logger.info(f"Position sizing: ${account_balance:,.2f} account, ${current_price:.2f} price")
        logger.info(f"Max position: ${max_position_value:,.2f}, Shares: {shares}")

        return shares

    def adjust_stop(self, current_price: float) -> Optional[float]:
        """
        Progressive stop adjustment - only moves up, never down.
        Conservative approach that prevents giving back gains.

        Rules:
        - Under 2% profit: Don't adjust
        - 2-4% profit: Move to breakeven  
        - 4-6% profit: Lock in 25% of gains
        - Over 6% profit: Trail at 50% of gains

        Args:
            current_price: Current stock price

        Returns:
            New stop price or None if no adjustment needed
        """
        if not self.data.entry_price or not self.data.current_stop:
            return None

        entry_price = self.data.entry_price
        current_stop = self.data.current_stop

        # Calculate profit percentage
        profit_percent = (current_price - entry_price) / entry_price

        new_stop = None

        if profit_percent < 0.02:  # Under 2% profit
            new_stop = current_stop  # Don't adjust
            logger.debug(f"Stop unchanged: {profit_percent:.1%} profit < 2% threshold")

        elif profit_percent < 0.04:  # 2-4% profit
            new_stop = entry_price  # Move to breakeven
            logger.info(f"Stop to breakeven: {profit_percent:.1%} profit, stop ${new_stop:.2f}")

        elif profit_percent < 0.06:  # 4-6% profit
            new_stop = entry_price + (current_price - entry_price) * 0.25  # Lock 25%
            logger.info(f"Stop locks 25%: {profit_percent:.1%} profit, stop ${new_stop:.2f}")

        else:  # Over 6% profit
            new_stop = entry_price + (current_price - entry_price) * 0.50  # Trail 50%
            logger.info(f"Trailing 50%: {profit_percent:.1%} profit, stop ${new_stop:.2f}")

        # Only return new stop if it's higher than current (never move down)
        if new_stop and new_stop > current_stop:
            return round(new_stop, 2)
        else:
            return None

    def place_entry_order(self, current_price: Optional[float] = None) -> bool:
        """
        Place bracket order (entry + stop + target).

        Uses existing AlpacaOrderManager for order placement.
        Conservative stops at 5%, targets at 8% (validated ratios).

        Args:
            current_price: Current market price

        Returns:
            True if order placed successfully
        """
        try:
            # Rate limit API calls
            rate_limiter.wait_if_needed()

            # Get real market price if not provided
            if current_price is None:
                current_price = get_current_price(self.symbol)

            # Get account info for position sizing
            account = self.position_manager.get_account_info()
            account_balance = float(account['buying_power'])

            # Calculate position size
            quantity = self.calculate_position_size(account_balance, current_price)

            if quantity <= 0:
                logger.error(f"Invalid position size: {quantity} shares")
                return False

            # Use configured exit levels (default: balanced 8% TP / 5% SL)
            exit_config = self.config.get_exit_config()
            stop_loss_price = current_price * (1 - exit_config.stop_loss)
            take_profit_price = current_price * (1 + exit_config.take_profit)

            # Rate limit the order placement call
            rate_limiter.wait_if_needed()

            # Place simple bracket order directly with Alpaca
            result = self.place_bracket_order_simple(
                symbol=self.symbol,
                qty=quantity,
                stop_price=stop_loss_price,
                target_price=take_profit_price
            )

            if 'error' not in result and result.get('status') in ['submitted', 'pending_new']:
                # Order confirmed successful - safe to update state
                self.data.quantity = quantity
                self.data.entry_price = current_price
                self.data.current_stop = stop_loss_price
                self.data.target_price = take_profit_price
                self.data.entry_time = datetime.now(timezone.utc).isoformat()
                self.data.state = TradeState.ORDER_PENDING.value

                # Store bracket order ID from simplified response
                self.data.order_ids = {'parent': result.get('id', 'unknown')}
                    
                # Note: Alpaca creates OCO orders asynchronously, not in initial response
                logger.info("Bracket order submitted - OCO orders will be created by Alpaca")

                # Save state only after all validations pass
                self.save_state()

                logger.info(f"Bracket order confirmed: {quantity} shares {self.symbol}")
                logger.info(
                    f"Entry: ${current_price:.2f}, Stop: ${stop_loss_price:.2f} "
                    f"({exit_config.stop_loss:.1%}), Target: ${take_profit_price:.2f} "
                    f"({exit_config.take_profit:.1%})")
                logger.info(f"Exit Strategy: {exit_config.description}")
                logger.info(f"Order IDs: {self.data.order_ids}")
                return True
            else:
                # Order failed - don't modify state
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Order placement failed: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"Error placing entry order: {e}")
            return False

    def place_bracket_order_simple(self, symbol: str, qty: int, 
                                   stop_price: float, target_price: float) -> Dict[str, Any]:
        """
        CRITICAL FIX: Simple bracket order placement with retry logic.
        
        Args:
            symbol: Stock symbol
            qty: Number of shares
            stop_price: Stop loss price
            target_price: Take profit price
            
        Returns:
            Dictionary with order response and status
        """
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Rate limit the call
                rate_limiter.wait_if_needed()
                
                # Place single order with attached bracket using Alpaca SDK
                order_request = {
                    'symbol': symbol,
                    'qty': qty,
                    'side': 'buy',
                    'type': 'market',
                    'time_in_force': 'gtc',
                    'order_class': 'bracket',
                    'stop_loss': {'stop_price': str(stop_price)},
                    'take_profit': {'limit_price': str(target_price)}
                }
                
                # Submit order through position manager's broker client
                order_response = self.position_manager.broker.submit_order(**order_request)
                
                # Alpaca returns OrderData object - extract what we need
                result = {
                    'id': order_response.id,
                    'status': order_response.status,
                    'symbol': order_response.symbol,
                    'qty': order_response.qty,
                    'order_class': order_response.order_class,
                    'submitted_at': (order_response.submitted_at.isoformat() 
                                   if order_response.submitted_at else None)
                }
                
                logger.info(f"Bracket order submitted successfully on attempt {attempt + 1}")
                logger.info(f"Order ID: {result['id']}, Status: {result['status']}")
                
                return result
                
            except Exception as e:
                logger.warning(f"Bracket order attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + (time.time() % 1)
                    logger.info(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} bracket order attempts failed")
                    return {'error': str(e), 'status': 'failed'}
        
        return {'error': 'Max retries exceeded', 'status': 'failed'}

    def sync_with_broker(self) -> bool:
        """
        Reconcile local state with actual broker positions and orders.

        Prevents drift between JSON state and actual Alpaca positions.

        Returns:
            True if sync completed successfully
        """
        try:
            logger.info(f"Syncing {self.symbol} state with broker...")

            # Get actual broker positions
            positions = self.order_manager.get_positions()
            broker_position = None

            for pos in positions:
                if pos['symbol'] == self.symbol:
                    broker_position = pos
                    break

            # Get actual broker orders
            orders = self.order_manager.get_orders(status='all')
            broker_orders = []

            for order in orders:
                if order['symbol'] == self.symbol:
                    broker_orders.append(order)

            # Sync position data
            if broker_position:
                broker_qty = int(broker_position['qty'])
                if broker_qty > 0:
                    # We have a position - update state if needed
                    if self.data.state == TradeState.ORDER_PENDING.value:
                        # Order was filled
                        self.data.state = TradeState.POSITION_OPEN.value
                        self.data.quantity = broker_qty
                        logger.info(f"Position filled: {broker_qty} shares")

                    elif self.data.quantity != broker_qty:
                        # Quantity mismatch - update to broker reality
                        logger.warning(
                            f"Quantity mismatch: local {self.data.quantity}, broker {broker_qty}")
                        self.data.quantity = broker_qty

                else:
                    # No position at broker but we think we have one
                    if self.data.state in [TradeState.POSITION_OPEN.value, TradeState.STOP_ADJUSTED.value]:
                        logger.info("Position closed at broker - updating local state")
                        self.data.state = TradeState.POSITION_CLOSED.value

            else:
                # No position at broker
                if self.data.state in [TradeState.POSITION_OPEN.value, TradeState.STOP_ADJUSTED.value]:
                    logger.info("No position at broker - updating local state")
                    self.data.state = TradeState.POSITION_CLOSED.value

            # Sync order status
            active_order_ids = set(self.data.order_ids.values())
            {order['order_id'] for order in broker_orders}

            # Check for filled/cancelled orders
            for order in broker_orders:
                order_id = order['order_id']
                order_status = order.get('status', 'unknown')

                if order_id in active_order_ids:
                    if order_status in ['filled', 'partially_filled']:
                        logger.info(f"Order {order_id} filled")
                    elif order_status in ['cancelled', 'expired', 'rejected']:
                        logger.info(f"Order {order_id} cancelled/expired")

            # Save updated state
            self.save_state()

            logger.info("Broker sync completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error syncing with broker: {e}")
            return False

    def update_stop(self, new_stop_price: float) -> bool:
        """
        Update stop loss order with new price.

        Args:
            new_stop_price: New stop loss price

        Returns:
            True if stop updated successfully
        """
        try:
            # Get the current stop order ID (simplified - would need order tracking)
            stop_order_id = self.data.order_ids.get('stop')

            if not stop_order_id:
                logger.error("No stop order ID found")
                return False

            # Modify the stop order
            result = self.order_manager.modify_order(
                order_id=stop_order_id,
                stop_price=new_stop_price
            )

            if result['status'] == 'submitted':
                self.data.current_stop = new_stop_price
                self.data.last_adjustment = datetime.now(timezone.utc).isoformat()
                self.data.state = TradeState.STOP_ADJUSTED.value

                # Save state
                self.save_state()

                logger.info(f"Stop updated to ${new_stop_price:.2f}")
                return True
            else:
                logger.error(f"Stop update failed: {result['message']}")
                return False

        except Exception as e:
            logger.error(f"Error updating stop: {e}")
            return False

    def check_and_adjust_stop(self, current_price: float) -> bool:
        """
        Check if stop should be adjusted and update if needed.

        Args:
            current_price: Current market price

        Returns:
            True if stop was adjusted
        """
        new_stop = self.adjust_stop(current_price)

        if new_stop and new_stop != self.data.current_stop:
            return self.update_stop(new_stop)

        return False

    def should_exit_for_new_opportunity(self, current_price: float, new_opportunity: OpportunityData) -> bool:
        """
        Determine if current position should be exited for a better opportunity.

        Conservative rules:
        - New opportunity must be 2x better than current unrealized profit
        - Current position must be profitable (no exit at loss for new trades)
        - Only consider if we're in an open position

        Args:
            current_price: Current market price for this position
            new_opportunity: New trading opportunity to compare

        Returns:
            True if should exit current position for new opportunity
        """
        # Only consider if we have an open position
        if self.data.state not in [TradeState.POSITION_OPEN.value, TradeState.STOP_ADJUSTED.value]:
            return False

        if not self.data.entry_price or not self.data.entry_time:
            return False

        # Calculate current unrealized profit/loss
        current_unrealized = current_price - self.data.entry_price

        # Calculate time held (for additional context)
        entry_time = datetime.fromisoformat(self.data.entry_time.replace('Z', '+00:00'))
        current_time_held = datetime.now(timezone.utc) - entry_time

        # New opportunity expected profit
        new_expected_profit = new_opportunity.expected_profit

        # Decision logic: Exit current if new opportunity is 2x better AND current is profitable
        should_exit = (
            new_expected_profit > current_unrealized * 2 and  # 2x better opportunity
            current_unrealized > 0                            # Current position profitable
        )

        if should_exit:
            logger.info(f"Exit recommendation for {self.symbol}:")
            logger.info(f"  Current unrealized: ${current_unrealized:.2f}")
            logger.info(f"  Time held: {current_time_held}")
            logger.info(
                f"  New opportunity: {new_opportunity.symbol} (${new_expected_profit:.2f} expected)")
            logger.info(f"  New is {new_expected_profit/current_unrealized:.1f}x better")
        else:
            logger.debug(
                f"No exit needed: Current ${current_unrealized:.2f}, New ${new_expected_profit:.2f}")

        return should_exit

    def close_position(self, reason: str = "Manual close") -> bool:
        """
        Close current position by canceling stop/target and placing market sell order.

        Args:
            reason: Reason for closing position

        Returns:
            True if position closed successfully
        """
        try:
            if self.data.state not in [TradeState.POSITION_OPEN.value, TradeState.STOP_ADJUSTED.value]:
                logger.warning(f"Cannot close position: current state is {self.data.state}")
                return False

            logger.info(f"Closing position {self.symbol}: {reason}")

            # Cancel existing stop and target orders
            for order_type, order_id in self.data.order_ids.items():
                if order_id and order_type in ['stop', 'target']:
                    cancel_result = self.order_manager.cancel_order(order_id)
                    if cancel_result['status'] == 'cancelled':
                        logger.info(f"Cancelled {order_type} order {order_id}")

            # Place market sell order to close position
            if self.data.quantity > 0:
                close_result = self.order_manager.place_market_order(
                    symbol=self.symbol,
                    qty=self.data.quantity,
                    side="sell"
                )

                if close_result['status'] == 'submitted':
                    self.data.state = TradeState.EXIT_TRIGGERED.value
                    self.save_state()
                    logger.info(f"Market sell order placed for {self.data.quantity} shares")
                    return True
                else:
                    logger.error(f"Failed to place close order: {close_result['message']}")
                    return False
            else:
                logger.error("No position to close (quantity = 0)")
                return False

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False

    def save_state(self):
        """Save trade state to JSON file."""
        try:
            # Load existing positions
            positions = self.load_positions()

            # Update our position
            positions[self.symbol] = asdict(self.data)

            # Save positions file
            with open(self.positions_file, 'w') as f:
                json.dump(positions, f, indent=2, default=str)

            logger.debug(f"State saved for {self.symbol}")

        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def load_positions(self) -> Dict[str, Any]:
        """Load all positions from JSON file."""
        try:
            if os.path.exists(self.positions_file):
                with open(self.positions_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading positions: {e}")
            return {}

    def execute_lifecycle(self) -> bool:
        """
        Execute complete trade lifecycle (for testing).

        This is a simplified version for testing with hardcoded signal.
        Production version would be event-driven with market data updates.

        Returns:
            True if lifecycle executed successfully
        """
        try:
            logger.info(f"Executing trade lifecycle for {self.symbol}")

            # 1. Get real current market price
            try:
                current_price = self.get_current_price(self.symbol)
            except Exception as e:
                logger.error(f"Failed to get current price: {e}")
                return False

            # 2. Place entry order with bracket (stop + target)
            if self.data.state == TradeState.SIGNAL_GENERATED.value:
                success = self.place_entry_order(current_price)
                if success:
                    logger.info("Trade lifecycle: Entry order placed")
                    return True
                else:
                    logger.error("Trade lifecycle: Entry order failed")
                    return False

            # 3. Check for stop adjustments (would be called periodically)
            elif self.data.state in [TradeState.POSITION_OPEN.value, TradeState.STOP_ADJUSTED.value]:
                # Simulate price movement for testing
                test_price = current_price * 1.03  # 3% profit
                adjusted = self.check_and_adjust_stop(test_price)
                if adjusted:
                    logger.info("Trade lifecycle: Stop adjusted")
                return True

            else:
                logger.info(f"Trade lifecycle: No action for state {self.data.state}")
                return True

        except Exception as e:
            logger.error(f"Error in trade lifecycle: {e}")
            return False


class TradeManager:
    """
    Manages multiple positions with opportunity comparison.

    Enforces position limits and handles trade-offs between current and new opportunities.
    """

    def __init__(self, max_positions: int = 3):
        """
        Initialize trade manager.

        Args:
            max_positions: Maximum concurrent positions (default 3 for PDT compliance)
        """
        self.max_positions = max_positions
        self.active_trades: Dict[str, TradeCycle] = {}

        logger.info(f"TradeManager initialized with max {max_positions} positions")

    def load_active_trades(self) -> Dict[str, TradeCycle]:
        """
        Load active trades from JSON state files.

        Returns:
            Dictionary of active trades by symbol
        """
        try:
            positions_file = os.path.join("state", "positions.json")
            if not os.path.exists(positions_file):
                return {}

            with open(positions_file, 'r') as f:
                positions_data = json.load(f)

            active_trades = {}
            for symbol, data in positions_data.items():
                if data['state'] in ['pending', 'open', 'adjusted', 'exiting']:
                    # Create TradeCycle from saved data
                    trade = TradeCycle(symbol, data['signal_strength'], data['confidence'])
                    trade.data = TradeData(**data)
                    active_trades[symbol] = trade

            logger.info(f"Loaded {len(active_trades)} active trades")
            return active_trades

        except Exception as e:
            logger.error(f"Error loading active trades: {e}")
            return {}

    def get_position_count(self) -> int:
        """Get current number of active positions."""
        self.active_trades = self.load_active_trades()
        return len(self.active_trades)

    def can_add_position(self) -> bool:
        """Check if we can add a new position."""
        return self.get_position_count() < self.max_positions

    def evaluate_new_opportunity(self, opportunity: OpportunityData) -> Dict[str, Any]:
        """
        Evaluate a new trading opportunity against current positions.

        Args:
            opportunity: New trading opportunity

        Returns:
            Dictionary with recommendation and actions
        """
        self.active_trades = self.load_active_trades()

        # If we have room, just take the new position
        if self.can_add_position():
            return {
                'action': 'TAKE_NEW',
                'reason': f'Available slot ({len(self.active_trades)}/{self.max_positions})',
                'symbol': opportunity.symbol,
                'exit_symbol': None
            }

        # If positions are full, evaluate against current holdings
        best_exit_candidate = None
        best_improvement_ratio = 0

        for symbol, trade in self.active_trades.items():
            if trade.should_exit_for_new_opportunity(opportunity.current_price, opportunity):
                # Calculate improvement ratio
                current_unrealized = opportunity.current_price - trade.data.entry_price
                improvement_ratio = opportunity.expected_profit / current_unrealized

                if improvement_ratio > best_improvement_ratio:
                    best_improvement_ratio = improvement_ratio
                    best_exit_candidate = symbol

        if best_exit_candidate:
            return {
                'action': 'REPLACE_POSITION',
                'reason': f'New opportunity {best_improvement_ratio:.1f}x better',
                'symbol': opportunity.symbol,
                'exit_symbol': best_exit_candidate,
                'improvement_ratio': best_improvement_ratio
            }
        else:
            return {
                'action': 'REJECT',
                'reason': 'No profitable exits for new opportunity',
                'symbol': opportunity.symbol,
                'exit_symbol': None
            }

    def execute_trade_decision(self, opportunity: OpportunityData) -> bool:
        """
        Execute trade decision based on opportunity evaluation.

        Args:
            opportunity: New trading opportunity

        Returns:
            True if trade executed successfully
        """
        try:
            decision = self.evaluate_new_opportunity(opportunity)

            logger.info(f"Trade decision: {decision['action']} - {decision['reason']}")

            if decision['action'] == 'TAKE_NEW':
                # Create and execute new trade
                new_trade = TradeCycle(
                    opportunity.symbol,
                    opportunity.signal_strength,
                    opportunity.confidence
                )
                success = new_trade.place_entry_order(opportunity.current_price)
                if success:
                    self.active_trades[opportunity.symbol] = new_trade
                return success

            elif decision['action'] == 'REPLACE_POSITION':
                # Close existing position and open new one
                exit_symbol = decision['exit_symbol']
                exit_trade = self.active_trades[exit_symbol]

                # Close existing position
                close_success = exit_trade.close_position(
                    f"Replacing with {opportunity.symbol} ({decision['improvement_ratio']:.1f}x better)"
                )

                if close_success:
                    # Remove from active trades
                    del self.active_trades[exit_symbol]

                    # Create new position
                    new_trade = TradeCycle(
                        opportunity.symbol,
                        opportunity.signal_strength,
                        opportunity.confidence
                    )
                    success = new_trade.place_entry_order(opportunity.current_price)
                    if success:
                        self.active_trades[opportunity.symbol] = new_trade
                    return success

                return False

            else:  # REJECT
                logger.info(f"Rejecting {opportunity.symbol}: {decision['reason']}")
                return False

        except Exception as e:
            logger.error(f"Error executing trade decision: {e}")
            return False


# Convenience functions for testing
def test_trade_cycle():
    """Test the trade cycle with hardcoded TQQQ signal."""
    print("=== Trade Cycle Test ===")

    # Create trade cycle with bullish signal
    trade = TradeCycle("TQQQ", "BULLISH", 0.75)

    # Execute lifecycle (will place bracket order)
    success = trade.execute_lifecycle()

    if success:
        print("✅ Trade cycle executed successfully")
        print(f"   State: {trade.data.state}")
        print(f"   Entry: ${trade.data.entry_price}")
        print(f"   Stop: ${trade.data.current_stop}")
        print(f"   Target: ${trade.data.target_price}")
    else:
        print("❌ Trade cycle failed")

    return success


def test_opportunity_comparison():
    """Test opportunity comparison logic."""
    print("=== Opportunity Comparison Test ===")

    # Create existing position (TQQQ at $50, now at $52 = $2 profit)
    trade = TradeCycle("TQQQ", "BULLISH", 0.75)
    trade.data.entry_price = 50.0
    trade.data.current_stop = 47.5
    trade.data.target_price = 54.0
    trade.data.quantity = 100
    trade.data.state = TradeState.POSITION_OPEN.value
    trade.data.entry_time = datetime.now(timezone.utc).isoformat()

    # Create new opportunities
    opportunities = [
        # Weak opportunity: only $1 expected profit vs $2 current
        OpportunityData("NVDA", "BULLISH", 0.6, 100.0, 100.0, 101.0),
        # Strong opportunity: $5 expected profit vs $2 current (2.5x better)
        OpportunityData("AAPL", "BULLISH", 0.8, 150.0, 150.0, 155.0),
    ]

    current_price = 52.0  # TQQQ current price ($2 profit)

    for opp in opportunities:
        should_exit = trade.should_exit_for_new_opportunity(current_price, opp)
        print(f"   {opp.symbol}: Expected ${opp.expected_profit:.2f} profit")
        print(f"   Should exit TQQQ: {'✅ YES' if should_exit else '❌ NO'}")

    return True


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Run test
    test_trade_cycle()
