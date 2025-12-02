"""
Response parsers for Alpaca trading API responses.

Issue #437: Extract response parsing logic from alpaca_trading_client.py
Handles complex parsing of bracket orders, positions, and account data.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OrderResponseParser:
    """
    Parses Alpaca order API responses, handling bracket order complexity.

    Bracket orders return nested structures with parent and leg orders.
    This parser normalizes them into a flat list of orders with metadata.
    """

    @staticmethod
    def parse_order_response(order_obj: Any) -> Dict[str, Any]:
        """
        Parse a single Alpaca order object into a standard dict.

        Args:
            order_obj: Alpaca Order object from API

        Returns:
            Normalized order dict with all fields
        """
        return {
            "order_id": str(order_obj.id),
            "symbol": str(order_obj.symbol),
            "qty": float(order_obj.qty) if order_obj.qty else 0.0,
            "filled_qty": float(order_obj.filled_qty) if order_obj.filled_qty else 0.0,
            "side": order_obj.side.value if hasattr(order_obj.side, "value") else str(order_obj.side),
            "order_type": (
                order_obj.order_type.value
                if hasattr(order_obj.order_type, "value")
                else str(order_obj.order_type)
            ),
            "time_in_force": (
                order_obj.time_in_force.value
                if hasattr(order_obj.time_in_force, "value")
                else str(order_obj.time_in_force)
            ),
            "limit_price": float(order_obj.limit_price) if order_obj.limit_price else None,
            "stop_price": float(order_obj.stop_price) if order_obj.stop_price else None,
            "trail_price": float(order_obj.trail_price) if order_obj.trail_price else None,
            "trail_percent": float(order_obj.trail_percent) if order_obj.trail_percent else None,
            "average_fill_price": (
                float(order_obj.average_fill_price) if order_obj.average_fill_price else None
            ),
            "status": order_obj.status.value if hasattr(order_obj.status, "value") else str(order_obj.status),
            "created_at": order_obj.created_at.isoformat() if order_obj.created_at else None,
            "updated_at": order_obj.updated_at.isoformat() if order_obj.updated_at else None,
            "submitted_at": order_obj.submitted_at.isoformat() if order_obj.submitted_at else None,
            "filled_at": order_obj.filled_at.isoformat() if order_obj.filled_at else None,
            "expired_at": order_obj.expired_at.isoformat() if order_obj.expired_at else None,
            "cancelled_at": order_obj.cancelled_at.isoformat() if order_obj.cancelled_at else None,
            "failed_at": order_obj.failed_at.isoformat() if order_obj.failed_at else None,
            "replaced_at": order_obj.replaced_at.isoformat() if order_obj.replaced_at else None,
            "replaced_by": str(order_obj.replaced_by) if order_obj.replaced_by else None,
            "replaces": str(order_obj.replaces) if order_obj.replaces else None,
            "order_class": (
                order_obj.order_class.value
                if hasattr(order_obj.order_class, "value")
                else str(order_obj.order_class)
            ),
            "legs": [],  # Will be populated for bracket orders
        }

    @staticmethod
    def parse_bracket_order_response(orders: List[Any]) -> Dict[str, Any]:
        """
        Parse a bracket order response with parent and leg orders.

        Handles 3-pass parsing logic:
        1. Collect all orders and track parent/leg relationships
        2. Match legs to parent orders via order_class
        3. Fetch missing leg details if needed

        Args:
            orders: List of Alpaca Order objects from get_orders()

        Returns:
            Normalized bracket order with legs attached
        """
        if not orders:
            return {}

        # Track orders by ID and find bracket parents
        orders_by_id = {}
        bracket_parents = []
        order_legs = {}  # Maps parent_id -> list of leg_ids

        # First pass: Index all orders and identify brackets
        for order in orders:
            order_dict = OrderResponseParser.parse_order_response(order)
            orders_by_id[str(order.id)] = order_dict

            is_bracket = (
                hasattr(order, "order_class")
                and order.order_class
                and hasattr(order.order_class, "value")
                and order.order_class.value == "bracket"
            )

            if is_bracket:
                bracket_parents.append(str(order.id))
                order_legs[str(order.id)] = []

        # Second pass: Match legs to parents
        # Legs have order_class = None but their parent_id points to the parent
        for order in orders:
            order_id = str(order.id)
            if order_id in orders_by_id:
                # Check if this order belongs to a bracket as a leg
                if hasattr(order, "parent_order_id") and order.parent_order_id:
                    parent_id = str(order.parent_order_id)
                    if parent_id in order_legs:
                        order_legs[parent_id].append(order_id)

        # Attach legs to bracket orders
        for parent_id in bracket_parents:
            if parent_id in orders_by_id:
                leg_ids = order_legs.get(parent_id, [])
                orders_by_id[parent_id]["legs"] = [
                    orders_by_id[leg_id] for leg_id in leg_ids if leg_id in orders_by_id
                ]

        # Return the first bracket parent (or first order if not a bracket)
        if bracket_parents:
            return orders_by_id[bracket_parents[0]]
        elif orders_by_id:
            # Return first order if no brackets
            first_id = list(orders_by_id.keys())[0]
            return orders_by_id[first_id]

        return {}

    @staticmethod
    def parse_orders_list(orders: List[Any]) -> List[Dict[str, Any]]:
        """
        Parse a list of Alpaca order objects into normalized dicts.

        Args:
            orders: List of Alpaca Order objects

        Returns:
            List of normalized order dicts
        """
        parsed_orders = []
        for order in orders:
            try:
                parsed_order = OrderResponseParser.parse_order_response(order)
                parsed_orders.append(parsed_order)
            except Exception as e:
                logger.warning(f"Failed to parse order {getattr(order, 'id', 'unknown')}: {e}")
                continue

        return parsed_orders


class AccountResponseParser:
    """Parses Alpaca account API responses."""

    @staticmethod
    def parse_account_response(account_obj: Any) -> Dict[str, Any]:
        """
        Parse account status response.

        Args:
            account_obj: Alpaca Account object from API

        Returns:
            Normalized account dict
        """
        return {
            "account_number": str(account_obj.account_number) if account_obj.account_number else None,
            "buying_power": float(account_obj.buying_power) if account_obj.buying_power else 0.0,
            "cash": float(account_obj.cash) if account_obj.cash else 0.0,
            "portfolio_value": float(account_obj.portfolio_value) if account_obj.portfolio_value else 0.0,
            "long_market_value": (
                float(account_obj.long_market_value) if account_obj.long_market_value else 0.0
            ),
            "short_market_value": (
                float(account_obj.short_market_value) if account_obj.short_market_value else 0.0
            ),
            "daytrading_buying_power": (
                float(account_obj.daytrading_buying_power)
                if account_obj.daytrading_buying_power
                else 0.0
            ),
            "trade_suspended_by_user": bool(account_obj.trade_suspended_by_user)
            if hasattr(account_obj, "trade_suspended_by_user")
            else False,
            "trading_blocked": bool(account_obj.trading_blocked)
            if hasattr(account_obj, "trading_blocked")
            else False,
            "transfers_blocked": bool(account_obj.transfers_blocked)
            if hasattr(account_obj, "transfers_blocked")
            else False,
            "account_blocked": bool(account_obj.account_blocked)
            if hasattr(account_obj, "account_blocked")
            else False,
            "created_at": account_obj.created_at.isoformat() if account_obj.created_at else None,
            "updated_at": account_obj.updated_at.isoformat() if account_obj.updated_at else None,
            "multiplier": int(account_obj.multiplier) if account_obj.multiplier else None,
            "status": str(account_obj.status) if account_obj.status else None,
        }


class PositionResponseParser:
    """Parses Alpaca position API responses."""

    @staticmethod
    def parse_position_response(position_obj: Any) -> Dict[str, Any]:
        """
        Parse position response.

        Args:
            position_obj: Alpaca Position object from API

        Returns:
            Normalized position dict
        """
        return {
            "symbol": str(position_obj.symbol),
            "qty": float(position_obj.qty) if position_obj.qty else 0.0,
            "avg_fill_price": float(position_obj.avg_fill_price) if position_obj.avg_fill_price else 0.0,
            "side": position_obj.side.value if hasattr(position_obj.side, "value") else str(position_obj.side),
            "market_value": float(position_obj.market_value) if position_obj.market_value else 0.0,
            "cost_basis": float(position_obj.cost_basis) if position_obj.cost_basis else 0.0,
            "unrealized_pl": float(position_obj.unrealized_pl) if position_obj.unrealized_pl else 0.0,
            "unrealized_plpc": float(position_obj.unrealized_plpc) if position_obj.unrealized_plpc else 0.0,
            "current_price": float(position_obj.current_price) if position_obj.current_price else 0.0,
            "lastday_price": float(position_obj.lastday_price) if position_obj.lastday_price else 0.0,
            "change_today": float(position_obj.change_today) if position_obj.change_today else 0.0,
            "asset_id": str(position_obj.asset_id) if position_obj.asset_id else None,
            "asset_class": str(position_obj.asset_class) if position_obj.asset_class else None,
        }

    @staticmethod
    def parse_positions_list(positions: List[Any]) -> List[Dict[str, Any]]:
        """
        Parse list of positions.

        Args:
            positions: List of Alpaca Position objects

        Returns:
            List of normalized position dicts
        """
        parsed_positions = []
        for position in positions:
            try:
                parsed_position = PositionResponseParser.parse_position_response(position)
                parsed_positions.append(parsed_position)
            except Exception as e:
                logger.warning(f"Failed to parse position {getattr(position, 'symbol', 'unknown')}: {e}")
                continue

        return parsed_positions
