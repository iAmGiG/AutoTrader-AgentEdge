#!/usr/bin/env python3
"""
Unified Position Manager

Single source of truth for all position tracking across the system.
Fetches directly from broker to eliminate state synchronization issues.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.utils.date_utils import get_datetime_now, now_iso

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Unified position management that serves as single source of truth.

    CRITICAL: This class ALWAYS fetches from broker first, then caches
    for the session to avoid constant API calls.
    """

    def __init__(self, broker_client):
        """
        Initialize with broker client connection.

        Args:
            broker_client: Alpaca trading client instance
        """
        # Load paths configuration
        paths_config_file = "config_defaults/paths_config.yaml"
        try:
            with open(paths_config_file) as f:
                paths_config = yaml.safe_load(f)
                logger.info(f"Loaded paths config from {paths_config_file}")
        except FileNotFoundError:
            logger.warning(
                f"Paths config not found at {paths_config_file}, using hardcoded defaults"
            )
            paths_config = {"state_files": {"positions": "state/positions.json"}}

        self.broker = broker_client
        self._session_cache = {}
        self._cache_timestamp = None
        self._cache_ttl_seconds = 60  # Cache for 1 minute

        # Backup state file for persistence across restarts
        state_file_path = paths_config.get("state_files", {}).get(
            "positions", "state/positions.json"
        )
        self.state_file = Path(state_file_path)
        self.state_file.parent.mkdir(exist_ok=True)

    def get_positions(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Get all current positions from broker.

        Args:
            force_refresh: Skip cache and fetch fresh from broker

        Returns:
            Dict mapping symbol -> position data
        """
        now = get_datetime_now()

        # Check if we can use cached data
        if not force_refresh and self._cache_timestamp:
            cache_age = (now - self._cache_timestamp).total_seconds()
            if cache_age < self._cache_ttl_seconds:
                return self._session_cache

        try:
            # Fetch fresh positions from broker
            broker_positions = self.broker.get_all_positions()

            # Convert to our standard format
            positions = {}
            for pos in broker_positions:
                positions[pos.symbol] = {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "side": "long" if float(pos.qty) > 0 else "short",
                    "avg_entry_price": float(pos.avg_cost),
                    "current_price": (
                        float(pos.market_value) / float(pos.qty) if float(pos.qty) != 0 else 0
                    ),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_pl_percent": float(pos.unrealized_plpc),
                    "cost_basis": float(pos.cost_basis),
                    "last_updated": now.isoformat(),
                }

            # Update cache
            self._session_cache = positions
            self._cache_timestamp = now

            # Backup to file
            self._save_positions_backup(positions)

            logger.info(f"Fetched {len(positions)} positions from broker")
            return positions

        except Exception as e:
            logger.error(f"Failed to fetch positions from broker: {e}")

            # Fallback to cached data if available
            if self._session_cache:
                logger.warning("Using cached position data due to broker error")
                return self._session_cache

            # Last resort: try to load from backup file
            return self._load_positions_backup()

    def get_position(self, symbol: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get position for specific symbol.

        Args:
            symbol: Ticker symbol
            force_refresh: Skip cache and fetch fresh from broker

        Returns:
            Position data dict or None if no position
        """
        positions = self.get_positions(force_refresh=force_refresh)
        return positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """Check if we currently have a position in this symbol."""
        position = self.get_position(symbol)
        return position is not None and abs(position["qty"]) > 0

    def get_position_value(self, symbol: str) -> float:
        """Get current market value of position."""
        position = self.get_position(symbol)
        if position:
            return position["market_value"]
        return 0.0

    def get_unrealized_pl(self, symbol: str) -> float:
        """Get unrealized P&L for position."""
        position = self.get_position(symbol)
        if position:
            return position["unrealized_pl"]
        return 0.0

    def get_portfolio_value(self) -> float:
        """Get total portfolio market value."""
        positions = self.get_positions()
        return sum(pos["market_value"] for pos in positions.values())

    def get_portfolio_pl(self) -> float:
        """Get total unrealized P&L across all positions."""
        positions = self.get_positions()
        return sum(pos["unrealized_pl"] for pos in positions.values())

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information from broker.

        Returns:
            Account data including buying power, cash, etc.
        """
        try:
            account = self.broker.get_account()
            return {
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "equity": float(account.equity),
                "day_trade_count": (
                    int(account.daytrade_buying_power)
                    if hasattr(account, "daytrade_buying_power")
                    else 0
                ),
                "status": account.status,
                "last_updated": now_iso(),
            }
        except Exception as e:
            logger.error(f"Failed to fetch account info: {e}")
            return {}

    def _save_positions_backup(self, positions: Dict[str, Any]):
        """Save positions to backup file."""
        try:
            with open(self.state_file, "w") as f:
                json.dump({"positions": positions, "saved_at": now_iso()}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save positions backup: {e}")

    def _load_positions_backup(self) -> Dict[str, Any]:
        """Load positions from backup file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    positions = data.get("positions", {})
                    logger.warning(f"Loaded {len(positions)} positions from backup file")
                    return positions
        except Exception as e:
            logger.error(f"Failed to load positions backup: {e}")

        return {}

    def get_orders(self, status: str = "open", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get orders from broker.

        Args:
            status: Order status filter ('open', 'closed', 'all')
            limit: Maximum number of orders to return

        Returns:
            List of order data dicts
        """
        try:
            orders = self.broker.get_orders(status=status, limit=limit)

            order_list = []
            for order in orders:
                order_data = {
                    "id": order.id,
                    "symbol": order.symbol,
                    "qty": float(order.qty),
                    "side": order.side,
                    "order_type": order.order_type,
                    "status": order.status,
                    "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                    "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                    "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                    "filled_avg_price": (
                        float(order.filled_avg_price) if order.filled_avg_price else 0
                    ),
                    "limit_price": float(order.limit_price) if order.limit_price else None,
                    "stop_price": float(order.stop_price) if order.stop_price else None,
                    "time_in_force": order.time_in_force,
                    "order_class": order.order_class,
                }
                order_list.append(order_data)

            return order_list

        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            return []

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific order by ID.

        Args:
            order_id: Order ID from broker

        Returns:
            Order data dict or None if not found
        """
        try:
            order = self.broker.get_order(order_id)

            return {
                "id": order.id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side,
                "order_type": order.order_type,
                "status": order.status,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else 0,
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "stop_price": float(order.stop_price) if order.stop_price else None,
                "time_in_force": order.time_in_force,
                "order_class": order.order_class,
                "legs": [leg.id for leg in order.legs] if order.legs else [],
            }

        except Exception as e:
            logger.error(f"Failed to fetch order {order_id}: {e}")
            return None

    def refresh_cache(self):
        """Force refresh the position cache."""
        self.get_positions(force_refresh=True)

    def clear_cache(self):
        """Clear the session cache."""
        self._session_cache = {}
        self._cache_timestamp = None
