#!/usr/bin/env python3
"""
Unified Order Manager

Handles all order placement, tracking, and fill monitoring using
Alpaca's actual response structure and proper order lifecycle.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from alpaca.trading.requests import (
    LimitOrderRequest,
    MarketOrderRequest,
    OrderClass,
    OrderSide,
    StopLossRequest,
    TakeProfitRequest,
    TimeInForce,
)

from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Unified order management using Alpaca's actual API structure.

    CRITICAL: Uses actual Alpaca response objects and proper order classes.
    Handles bracket orders, OCO orders, and fill monitoring correctly.
    """

    def __init__(self, broker_client, position_manager):
        """
        Initialize with broker client and position manager.

        Args:
            broker_client: Alpaca trading client
            position_manager: PositionManager instance for state tracking
        """
        self.broker = broker_client
        self.position_manager = position_manager
        self.pending_orders = {}  # Track orders waiting for fills
        self.last_fill_check = 0
        self.fill_check_interval = 30  # Check every 30 seconds

    def place_market_order(self, symbol: str, qty: int, side: str) -> Dict[str, Any]:
        """
        Place a simple market order.

        Args:
            symbol: Ticker symbol
            qty: Quantity (positive integer)
            side: 'buy' or 'sell'

        Returns:
            Order response dict with actual Alpaca structure
        """
        try:
            # Create market order request
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )

            # Submit to broker
            order = self.broker.submit_order(order_data=order_request)

            # Convert to our standard format
            order_data = {
                "id": order.id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side.value,
                "order_type": order.order_type.value,
                "status": order.status.value,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "time_in_force": order.time_in_force.value,
                "order_class": order.order_class.value if order.order_class else "simple",
                "legs": [],
            }

            # Track for fill monitoring
            self.pending_orders[order.id] = order_data

            logger.info(f"Market order placed: {side} {qty} {symbol} (ID: {order.id})")
            return order_data

        except Exception as e:
            logger.error(f"Failed to place market order {side} {qty} {symbol}: {e}")
            return {"error": str(e)}

    def place_bracket_order(
        self, symbol: str, qty: int, stop_price: float, target_price: float
    ) -> Dict[str, Any]:
        """
        Place a bracket order with stop loss and take profit.

        Uses Alpaca's actual bracket order structure:
        - Entry order (market)
        - Stop loss (attached)
        - Take profit (attached)

        Args:
            symbol: Ticker symbol
            qty: Quantity
            stop_price: Stop loss price
            target_price: Take profit price

        Returns:
            Order response with entry_id and bracket details
        """
        try:
            # Create bracket order request with stop loss and take profit
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                stop_loss=StopLossRequest(stop_price=stop_price),
                take_profit=TakeProfitRequest(limit_price=target_price),
            )

            # Submit bracket order
            order = self.broker.submit_order(order_data=order_request)

            # Extract bracket components from Alpaca response
            entry_order = {
                "id": order.id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side.value,
                "order_type": order.order_type.value,
                "status": order.status.value,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "order_class": "bracket",
                "stop_price": stop_price,
                "target_price": target_price,
                "legs": [leg.id for leg in order.legs] if order.legs else [],
            }

            # Track main order for fill monitoring
            self.pending_orders[order.id] = entry_order

            logger.info(
                f"Bracket order placed: BUY {qty} {symbol} "
                f"@ Stop:{stop_price} Target:{target_price} (ID: {order.id})"
            )

            return {
                "entry_id": order.id,
                "stop_price": stop_price,
                "target_price": target_price,
                "legs": entry_order["legs"],
                "status": "submitted",
            }

        except Exception as e:
            logger.error(f"Failed to place bracket order {symbol}: {e}")
            return {"error": str(e)}

    def place_limit_order(
        self, symbol: str, qty: int, side: str, limit_price: float
    ) -> Dict[str, Any]:
        """
        Place a limit order.

        Args:
            symbol: Ticker symbol
            qty: Quantity
            side: 'buy' or 'sell'
            limit_price: Limit price

        Returns:
            Order response dict
        """
        try:
            order_request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                limit_price=limit_price,
                time_in_force=TimeInForce.DAY,
            )

            order = self.broker.submit_order(order_data=order_request)

            order_data = {
                "id": order.id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side.value,
                "order_type": order.order_type.value,
                "status": order.status.value,
                "limit_price": float(order.limit_price),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "time_in_force": order.time_in_force.value,
            }

            self.pending_orders[order.id] = order_data

            logger.info(
                f"Limit order placed: {side} {qty} {symbol} @ ${limit_price} (ID: {order.id})"
            )
            return order_data

        except Exception as e:
            logger.error(f"Failed to place limit order {side} {qty} {symbol} @ ${limit_price}: {e}")
            return {"error": str(e)}

    def monitor_order_fills(self) -> List[Dict[str, Any]]:
        """
        Monitor pending orders for fills.

        This is the CRITICAL missing piece that transitions:
        ORDER_PENDING -> POSITION_OPEN when fills occur.

        Returns:
            List of newly filled orders
        """
        now = time.time()

        # Rate limit fill checks
        if now - self.last_fill_check < self.fill_check_interval:
            return []

        self.last_fill_check = now
        filled_orders = []

        # Check each pending order
        orders_to_remove = []
        for order_id, order_data in self.pending_orders.items():
            try:
                # Get current order status from broker
                current_order = self.position_manager.get_order(order_id)

                if not current_order:
                    # Order not found, might be filled or cancelled
                    orders_to_remove.append(order_id)
                    continue

                status = current_order["status"].lower()

                if status == "filled":
                    # Order is filled!
                    filled_order = {
                        "id": order_id,
                        "symbol": current_order["symbol"],
                        "qty": current_order["filled_qty"],
                        "side": current_order["side"],
                        "filled_price": current_order["filled_avg_price"],
                        "filled_at": current_order["filled_at"],
                        "original_order": order_data,
                    }

                    filled_orders.append(filled_order)
                    orders_to_remove.append(order_id)

                    logger.info(
                        f"Order filled: {current_order['side']} "
                        f"{current_order['filled_qty']} {current_order['symbol']} "
                        f"@ ${current_order['filled_avg_price']}"
                    )

                elif status in ["cancelled", "expired", "rejected"]:
                    # Order is done but not filled
                    orders_to_remove.append(order_id)
                    logger.info(f"Order {status}: {order_id}")

                # Update pending order data with current status
                else:
                    self.pending_orders[order_id].update(
                        {"status": status, "filled_qty": current_order["filled_qty"]}
                    )

            except Exception as e:
                logger.error(f"Error checking order {order_id}: {e}")
                # Remove problematic orders after 1 hour
                if now - order_data.get("submitted_timestamp", now) > 3600:
                    orders_to_remove.append(order_id)

        # Clean up completed orders
        for order_id in orders_to_remove:
            self.pending_orders.pop(order_id, None)

        return filled_orders

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        try:
            self.broker.cancel_order_by_id(order_id)
            self.pending_orders.pop(order_id, None)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def replace_stop_order(
        self, order_id: str, new_stop_price: float, symbol: str = None, qty: int = None
    ) -> Dict[str, Any]:
        """
        Replace an existing stop order with a new stop price.

        Alpaca doesn't support modifying stop orders directly - we must cancel and replace.
        This implements the cancel-replace pattern for trailing stop updates.

        Args:
            order_id: ID of the stop order to replace
            new_stop_price: New stop price (must be higher than current for long positions)
            symbol: Symbol (required if not in pending_orders cache)
            qty: Quantity (required if not in pending_orders cache)

        Returns:
            Dict with new order details or error
        """
        from alpaca.trading.requests import StopOrderRequest

        try:
            # Get existing order details if not provided
            if symbol is None or qty is None:
                existing_order = self.position_manager.get_order(order_id)
                if existing_order:
                    symbol = symbol or existing_order.get("symbol")
                    qty = qty or int(existing_order.get("qty", 0))
                else:
                    return {"error": f"Order {order_id} not found and symbol/qty not provided"}

            if not symbol or not qty:
                return {"error": "Missing symbol or quantity for stop order replacement"}

            # Step 1: Cancel existing stop order
            logger.info(f"Replacing stop order {order_id}: cancelling old order...")
            cancel_success = self.cancel_order(order_id)
            if not cancel_success:
                return {"error": f"Failed to cancel existing stop order {order_id}"}

            # Small delay to ensure cancellation is processed
            import time

            time.sleep(0.5)

            # Step 2: Place new stop order at updated price
            logger.info(f"Placing new stop order for {symbol} at ${new_stop_price:.2f}")
            order_request = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                stop_price=new_stop_price,
                time_in_force=TimeInForce.GTC,
            )

            order = self.broker.submit_order(order_data=order_request)

            order_data = {
                "id": order.id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side.value,
                "order_type": order.order_type.value,
                "stop_price": float(order.stop_price) if order.stop_price else new_stop_price,
                "status": order.status.value,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "replaced_order_id": order_id,
            }

            # Track new order
            self.pending_orders[order.id] = order_data

            logger.info(f"Stop order replaced: {order_id} -> {order.id} at ${new_stop_price:.2f}")
            return order_data

        except Exception as e:
            logger.error(f"Failed to replace stop order {order_id}: {e}")
            return {"error": str(e)}

    def cancel_all_orders(self) -> int:
        """Cancel all pending orders."""
        try:
            cancelled_orders = self.broker.cancel_orders()
            count = len(cancelled_orders) if cancelled_orders else 0
            self.pending_orders.clear()
            logger.info(f"Cancelled {count} orders")
            return count
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return 0

    def get_pending_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get all pending orders being tracked."""
        return self.pending_orders.copy()

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of an order."""
        return self.position_manager.get_order(order_id)

    def handle_fill_notification(self, filled_order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a filled order notification.

        This updates the trading system state when an order fills.
        Called by the fill monitoring system.

        Args:
            filled_order: Fill notification data

        Returns:
            State update information
        """
        symbol = filled_order["symbol"]
        side = filled_order["side"]
        qty = filled_order["qty"]
        price = filled_order["filled_price"]

        # Refresh position cache since we have a new fill
        self.position_manager.refresh_cache()

        # Get updated position
        position = self.position_manager.get_position(symbol)

        state_update = {
            "symbol": symbol,
            "action": "position_opened" if side == "buy" else "position_closed",
            "fill_price": price,
            "fill_qty": qty,
            "fill_time": filled_order["filled_at"],
            "position": position,
            "timestamp": now_iso(),
        }

        logger.info(f"Fill handled: {side} {qty} {symbol} @ ${price}")
        return state_update
