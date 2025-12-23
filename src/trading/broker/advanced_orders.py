"""
Advanced Order Management Mixin for AlpacaOrderManager.

Issue #511: Extracted from alpaca_trading_client.py for modularity.
Contains trailing stop, bracket order, and order modification methods.
"""

import logging
from typing import Any, Dict, Optional

from src.trading.broker.market_hours import validate_market_hours
from src.trading.broker.validators import map_side, map_time_in_force

try:
    from alpaca.common.exceptions import APIError
    from alpaca.trading.enums import OrderClass, TimeInForce
    from alpaca.trading.requests import (
        GetOrdersRequest,
        LimitOrderRequest,
        MarketOrderRequest,
        ReplaceOrderRequest,
        StopLossRequest,
        TakeProfitRequest,
        TrailingStopOrderRequest,
    )

    ALPACA_TRADING_AVAILABLE = True
except ImportError:
    APIError = None
    OrderClass = None
    TimeInForce = None
    GetOrdersRequest = None
    LimitOrderRequest = None
    MarketOrderRequest = None
    ReplaceOrderRequest = None
    StopLossRequest = None
    TakeProfitRequest = None
    TrailingStopOrderRequest = None
    ALPACA_TRADING_AVAILABLE = False

logger = logging.getLogger(__name__)


class AdvancedOrdersMixin:
    """
    Mixin providing advanced order functionality.

    Requires:
        - self.client: AlpacaTradingClient instance
        - self._validate_order(): Order validation method
        - self.get_orders(): Method to get orders
    """

    def place_trailing_stop_order(  # noqa: C901
        self,
        symbol: str,
        qty: int,
        side: str,
        trail_percent: Optional[float] = None,
        trail_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """
        Place trailing stop order with mode awareness and validation.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            trail_percent: Trailing percentage (0-1, e.g., 0.05 for 5%)
            trail_price: Trailing price amount (alternative to percentage)
            time_in_force: "day", "gtc"

        Returns:
            Dict with order details or error information
        """
        try:
            # Validate order parameters
            self._validate_order(symbol, qty, side)

            if not trail_percent and not trail_price:
                raise ValueError("Either trail_percent or trail_price must be specified")

            if trail_percent and (trail_percent <= 0 or trail_percent >= 1):
                raise ValueError(f"Trail percent must be between 0 and 1, got {trail_percent}")

            if trail_price and trail_price <= 0:
                raise ValueError(f"Trail price must be positive, got {trail_price}")

            # Validate market hours (warn only for now)
            validate_market_hours(symbol, extended_hours=False, warn_only=True)

            # Mode-aware logging
            trail_desc = f"{trail_percent * 100:.1f}%" if trail_percent else f"${trail_price:.2f}"
            if self.client.mode == "live":
                logger.warning(
                    f"🔥 LIVE TRAILING STOP: {side.upper()} {qty} {symbol} trail {trail_desc}"
                )
            else:
                logger.info(
                    f"📝 PAPER TRAILING STOP: {side.upper()} {qty} {symbol} trail {trail_desc}"
                )

            # Map values to enums
            side_enum = map_side(side)
            tif_enum = map_time_in_force(time_in_force)

            # Create order request
            order_request = TrailingStopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif_enum,
                trail_percent=trail_percent,
                trail_price=trail_price,
            )

            # Safety check for live trading
            order_details = {
                "type": "trailing_stop",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "trail_percent": trail_percent,
                "trail_price": trail_price,
                "time_in_force": time_in_force,
            }

            if self.client.mode == "live":
                if not self.client._safety_check("PLACE TRAILING STOP ORDER", order_details):
                    return {
                        "status": "cancelled",
                        "message": "Order cancelled by user",
                        "order_details": order_details,
                    }

            # Submit order
            order = self.client.trading_client.submit_order(order_data=order_request)

            # Return structured response
            return {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": side.lower(),
                "order_type": "trailing_stop",
                "trail_percent": trail_percent,
                "trail_price": trail_price,
                "time_in_force": time_in_force.upper(),
                "status_detail": str(order.status),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "mode": self.client.mode,
            }

        except Exception as e:
            logger.error(f"Failed to place trailing stop order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "trail_percent": trail_percent,
                    "trail_price": trail_price,
                    "type": "trailing_stop",
                },
            }

    def place_bracket_order(  # noqa: C901
        self,
        symbol: str,
        qty: int,
        side: str,
        entry_limit_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """
        Place bracket order (entry + take profit + stop loss).

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            entry_limit_price: Entry limit price (None for market entry)
            take_profit_price: Take profit limit price
            stop_loss_price: Stop loss price
            time_in_force: "day", "gtc"

        Returns:
            Dict with order details or error information
        """
        try:
            # Validate order parameters
            self._validate_order(symbol, qty, side, entry_limit_price)

            if not take_profit_price and not stop_loss_price:
                raise ValueError(
                    "At least one of take_profit_price or stop_loss_price must be specified"
                )

            if take_profit_price and take_profit_price <= 0:
                raise ValueError(f"Take profit price must be positive, got {take_profit_price}")

            if stop_loss_price and stop_loss_price <= 0:
                raise ValueError(f"Stop loss price must be positive, got {stop_loss_price}")

            # Validate market hours (warn only for now)
            validate_market_hours(symbol, extended_hours=False, warn_only=True)

            # Mode-aware logging
            entry_desc = f"limit ${entry_limit_price:.2f}" if entry_limit_price else "market"
            if self.client.mode == "live":
                logger.warning(
                    f"🔥 LIVE BRACKET ORDER: {side.upper()} {qty} {symbol} @ {entry_desc} "
                    f"TP:{take_profit_price} SL:{stop_loss_price}"
                )
            else:
                logger.info(
                    f"📝 PAPER BRACKET ORDER: {side.upper()} {qty} {symbol} @ {entry_desc} "
                    f"TP:{take_profit_price} SL:{stop_loss_price}"
                )

            # Map values to enums
            side_enum = map_side(side)
            tif_enum = map_time_in_force(time_in_force)

            # Create take profit and stop loss requests
            take_profit = (
                TakeProfitRequest(limit_price=take_profit_price) if take_profit_price else None
            )
            stop_loss = StopLossRequest(stop_price=stop_loss_price) if stop_loss_price else None

            # Create main order request (market or limit entry)
            if entry_limit_price:
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_enum,
                    time_in_force=tif_enum,
                    limit_price=entry_limit_price,
                    order_class=OrderClass.BRACKET,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            else:
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_enum,
                    time_in_force=tif_enum,
                    order_class=OrderClass.BRACKET,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )

            # Safety check for live trading
            order_details = {
                "type": "bracket",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "entry_limit_price": entry_limit_price,
                "take_profit_price": take_profit_price,
                "stop_loss_price": stop_loss_price,
                "time_in_force": time_in_force,
            }

            if self.client.mode == "live":
                if not self.client._safety_check("PLACE BRACKET ORDER", order_details):
                    return {
                        "status": "cancelled",
                        "message": "Order cancelled by user",
                        "order_details": order_details,
                    }

            # Submit order
            order = self.client.trading_client.submit_order(order_data=order_request)

            # Return structured response
            return {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": side.lower(),
                "order_type": "bracket",
                "entry_limit_price": entry_limit_price,
                "take_profit_price": take_profit_price,
                "stop_loss_price": stop_loss_price,
                "order_class": "bracket",
                "time_in_force": time_in_force.upper(),
                "status_detail": str(order.status),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "mode": self.client.mode,
            }

        except Exception as e:
            # Don't log error here - it will be logged and translated by execution manager
            logger.debug(f"Bracket order error details: {e}", exc_info=True)

            # Extract Alpaca API error details if available
            error_code = None
            status_code = None

            # Try to extract error code from Alpaca APIError
            try:
                if isinstance(e, APIError):
                    status_code = getattr(e, "status_code", None)
                    error_code = getattr(e, "code", None)
                    logger.debug(f"Alpaca API error: status={status_code}, code={error_code}")
            except ImportError:
                # alpaca-py not available or doesn't have APIError
                pass
            except Exception:
                # Failed to extract error details
                pass

            return {
                "status": "error",
                "message": str(e),
                "error_code": error_code,
                "status_code": status_code,
                "order_details": {
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "entry_limit_price": entry_limit_price,
                    "take_profit_price": take_profit_price,
                    "stop_loss_price": stop_loss_price,
                    "type": "bracket",
                },
            }

    def modify_order(  # noqa: C901
        self,
        order_id: str,
        qty: Optional[int] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Modify an existing order.

        Args:
            order_id: ID of the order to modify
            qty: New quantity (optional)
            limit_price: New limit price (optional)
            stop_price: New stop price (optional)
            time_in_force: New time in force (optional)

        Returns:
            Dict with modified order details or error information
        """
        try:
            # Get current order to validate it exists
            try:
                self.client.trading_client.get_order_by_id(order_id)
            except Exception:
                return {
                    "status": "error",
                    "message": f"Order {order_id} not found",
                    "order_id": order_id,
                }

            # Build replacement order request
            # Start with current order values
            replace_request_params = {}

            if qty is not None:
                if qty <= 0:
                    raise ValueError(f"Quantity must be positive, got {qty}")
                replace_request_params["qty"] = qty

            if limit_price is not None:
                if limit_price <= 0:
                    raise ValueError(f"Limit price must be positive, got {limit_price}")
                replace_request_params["limit_price"] = limit_price

            if stop_price is not None:
                if stop_price <= 0:
                    raise ValueError(f"Stop price must be positive, got {stop_price}")
                replace_request_params["stop_price"] = stop_price

            if time_in_force is not None:
                replace_request_params["time_in_force"] = map_time_in_force(time_in_force)

            # Create replacement request
            replace_request = ReplaceOrderRequest(**replace_request_params)

            # Mode-aware logging
            if self.client.mode == "live":
                logger.warning(f"🔥 LIVE ORDER MODIFICATION: {order_id}")
                if self.client.require_confirmation:
                    confirmation = input(
                        f"Confirm LIVE order modification for {order_id}? (yes/no): "
                    )
                    if confirmation.lower() != "yes":
                        return {
                            "status": "cancelled",
                            "message": "Order modification cancelled by user",
                            "order_id": order_id,
                        }
            else:
                logger.info(f"📝 PAPER ORDER MODIFICATION: {order_id}")

            # Replace the order
            updated_order = self.client.trading_client.replace_order_by_id(
                order_id, replace_request
            )

            return {
                "status": "submitted",
                "message": "Order modified successfully",
                "order_id": str(updated_order.id),
                "symbol": str(updated_order.symbol),
                "qty": float(updated_order.qty),
                "side": str(updated_order.side),
                "order_type": str(updated_order.order_type),
                "time_in_force": str(updated_order.time_in_force),
                "limit_price": (
                    float(updated_order.limit_price) if updated_order.limit_price else None
                ),
                "stop_price": float(updated_order.stop_price) if updated_order.stop_price else None,
                "status_detail": str(updated_order.status),
                "submitted_at": (
                    updated_order.submitted_at.isoformat() if updated_order.submitted_at else None
                ),
                "mode": self.client.mode,
            }

        except Exception as e:
            logger.error(f"Failed to modify order {order_id}: {e}")
            return {"status": "error", "message": str(e), "order_id": order_id}

    def modify_stop_order(self, order_id: str, new_stop_price: float, symbol: str) -> bool:
        """
        Modify stop price on an existing stop order (convenience wrapper).

        Used for dynamic trailing stop adjustments.

        Args:
            order_id: ID of the stop order to modify
            new_stop_price: New stop price level
            symbol: Stock symbol (for logging)

        Returns:
            True if modification successful, False otherwise
        """
        logger.info(f"Modifying stop order {order_id} for {symbol} to ${new_stop_price:.2f}")

        result = self.modify_order(order_id=order_id, stop_price=new_stop_price)

        if result.get("status") == "submitted":
            logger.info(f"✅ Stop order {order_id} updated successfully")
            return True
        else:
            error_msg = result.get("message", "Unknown error")
            logger.error(f"❌ Failed to modify stop order {order_id}: {error_msg}")
            return False

    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:  # noqa: C901
        """
        Cancel all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter orders (cancels all if None)

        Returns:
            Dict with cancellation results
        """
        try:
            # Import OrderStatus here to avoid circular imports
            try:
                from alpaca.trading.enums import OrderStatus as AlpacaOrderStatus

                order_status_open = AlpacaOrderStatus.OPEN
            except ImportError:
                order_status_open = None

            # Get open orders
            if symbol:
                request = GetOrdersRequest(status=order_status_open, symbols=[symbol])
                orders = self.client.trading_client.get_orders(request)
            else:
                orders = self.get_orders(status="open")
                # Convert to alpaca order objects if needed
                if orders and isinstance(orders[0], dict):
                    # These are our formatted orders, we need the raw ones
                    request = GetOrdersRequest(status=order_status_open)
                    orders = self.client.trading_client.get_orders(request)

            if not orders:
                return {
                    "status": "success",
                    "message": f'No open orders found{" for " + symbol if symbol else ""}',
                    "cancelled_orders": [],
                    "mode": self.client.mode,
                }

            # Mode-aware logging and confirmation
            order_count = len(orders)
            symbol_desc = f" for {symbol}" if symbol else ""

            if self.client.mode == "live":
                logger.warning(f"🔥 LIVE BULK CANCELLATION: {order_count} orders{symbol_desc}")
                if self.client.require_confirmation:
                    confirmation = input(
                        f"Confirm cancelling {order_count} LIVE orders{symbol_desc}? (yes/no): "
                    )
                    if confirmation.lower() != "yes":
                        return {
                            "status": "cancelled",
                            "message": "Bulk cancellation cancelled by user",
                            "cancelled_orders": [],
                            "mode": self.client.mode,
                        }
            else:
                logger.info(f"📝 PAPER BULK CANCELLATION: {order_count} orders{symbol_desc}")

            # Cancel all orders
            cancelled_orders = []
            errors = []

            for order in orders:
                try:
                    self.client.trading_client.cancel_order_by_id(order.id)
                    cancelled_orders.append(str(order.id))
                except Exception as e:
                    errors.append(f"Failed to cancel {order.id}: {str(e)}")

            result = {
                "status": "success" if not errors else "partial",
                "message": f"Cancelled {len(cancelled_orders)} orders{symbol_desc}",
                "cancelled_orders": cancelled_orders,
                "mode": self.client.mode,
            }

            if errors:
                result["errors"] = errors

            return result

        except Exception as e:
            logger.error(f"Failed to cancel orders{' for ' + symbol if symbol else ''}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "cancelled_orders": [],
                "mode": self.client.mode,
            }
