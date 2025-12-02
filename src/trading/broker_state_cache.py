"""
BrokerStateCache - Cached broker state with smart TTL management.

Extracted from trading_cycle.py as part of #439 refactoring.
Handles broker state caching to reduce API calls (Issue #337).
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.utils.date_utils import get_datetime_now, now_iso

logger = logging.getLogger(__name__)


class BrokerStateCache:
    """
    Manages cached broker state with TTL-based invalidation.

    Broker is always source of truth. Cache reduces API calls while
    maintaining freshness within TTL window.
    """

    def __init__(
        self,
        account_monitor: Any,
        check_alerts_callback: Optional[Callable[[Dict[str, Any]], List[Any]]] = None,
        cache_ttl_seconds: int = 60,
        alert_refresh_interval: int = 300,
    ):
        """
        Initialize BrokerStateCache.

        Args:
            account_monitor: Alpaca account monitor for API calls
            check_alerts_callback: Optional callback to check position alerts
            cache_ttl_seconds: How long to keep cached data (default: 60s)
            alert_refresh_interval: Time between alert refreshes (default: 300s)
        """
        self.account_monitor = account_monitor
        self.check_alerts_callback = check_alerts_callback
        self.cache_ttl_seconds = cache_ttl_seconds
        self.alert_refresh_interval = alert_refresh_interval

        # Cache state
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None

        # Alert state (Issue #337 Phase 2)
        self._cached_alerts: List[Any] = []
        self._last_alert_check: Optional[datetime] = None

        logger.info(
            f"BrokerStateCache initialized: TTL={cache_ttl_seconds}s, "
            f"alert_interval={alert_refresh_interval}s"
        )

    @property
    def cached_alerts(self) -> List[Any]:
        """Get cached alerts."""
        return self._cached_alerts

    def fetch(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get all positions and orders from broker with smart caching.
        This is the source of truth.

        Issue #337: Added caching to reduce API calls. Cache TTL is configurable.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data from broker

        Returns:
            Dict with positions, orders, account info, and timestamp
        """
        # Check if cached data is still valid
        if not force_refresh and self._cache is not None:
            cache_age = (get_datetime_now() - self._cache_timestamp).total_seconds()
            if cache_age < self.cache_ttl_seconds:
                logger.debug(f"Using cached broker state (age: {cache_age:.1f}s)")
                return self._cache

        logger.debug("Cache miss or force_refresh - fetching from broker")

        try:
            # Get all positions (one API call)
            positions = self.account_monitor.get_positions()

            # Get all orders (one API call)
            # Use 'all' to include pending_new, accepted, and other statuses
            orders = self.account_monitor.get_orders(status="all")

            # Get account info (one API call)
            account = self.account_monitor.get_account_status()

            # Organize into clean structure
            broker_state = {
                "positions": {},
                "orders": {},
                "account": {
                    "buying_power": float(account.get("buying_power", 0)),
                    "portfolio_value": float(account.get("portfolio_value", 0)),
                    "cash": float(account.get("cash", 0)),
                },
                "timestamp": now_iso(),
            }

            # Process positions
            for pos in positions:
                symbol = pos["symbol"]
                broker_state["positions"][symbol] = {
                    "symbol": symbol,
                    "quantity": int(pos["qty"]),
                    "entry_price": float(pos["avg_entry_price"]),
                    "current_price": float(pos["market_value"]) / abs(int(pos["qty"])),
                    "unrealized_pl": float(pos["unrealized_pl"]),
                    "side": pos["side"],  # long/short
                }

            # Process orders (group by symbol)
            # Only include active orders (not filled, cancelled, expired, etc.)
            active_statuses = ["new", "pending_new", "accepted", "partially_filled", "held"]

            for order in orders:
                # Filter to only active orders
                order_status = str(order.get("status", "")).lower()
                if not any(status in order_status for status in active_statuses):
                    continue  # Skip filled, cancelled, expired orders

                symbol = order["symbol"]
                if symbol not in broker_state["orders"]:
                    broker_state["orders"][symbol] = []

                # Convert enums to strings for consistent comparison
                order_entry = {
                    "id": order["id"],
                    "type": str(order["order_type"]),  # Convert enum to string
                    "side": str(order["side"]),  # Convert enum to string
                    "quantity": int(order["qty"]),
                    "limit_price": (
                        float(order.get("limit_price", 0)) if order.get("limit_price") else None
                    ),
                    "stop_price": (
                        float(order.get("stop_price", 0)) if order.get("stop_price") else None
                    ),
                    "status": str(order["status"]),  # Convert enum to string
                    "time_in_force": str(order["time_in_force"]),  # Convert enum to string
                }
                broker_state["orders"][symbol].append(order_entry)
                logger.debug(f"Order {symbol}: {order_entry}")

                # Process bracket order legs (stop-loss and take-profit)
                if "legs" in order and order["legs"]:
                    for leg in order["legs"]:
                        leg_status = str(leg.get("status", "")).lower()
                        if not any(status in leg_status for status in active_statuses):
                            continue  # Skip inactive legs

                        leg_entry = {
                            "id": leg["id"],
                            "type": str(leg["order_type"]),
                            "side": str(leg["side"]),
                            "quantity": int(leg["qty"]),
                            "limit_price": (
                                float(leg.get("limit_price", 0)) if leg.get("limit_price") else None
                            ),
                            "stop_price": (
                                float(leg.get("stop_price", 0)) if leg.get("stop_price") else None
                            ),
                            "status": str(leg["status"]),
                            "time_in_force": str(leg["time_in_force"]),
                            "parent_order_id": order["id"],  # Track parent relationship
                        }
                        broker_state["orders"][symbol].append(leg_entry)
                        logger.debug(f"  Bracket leg {symbol}: {leg_entry}")

            logger.info(
                f"Fetched broker state: {len(broker_state['positions'])} positions, "
                f"{len(broker_state['orders'])} order groups, "
                f"total {len(orders)} orders"
            )

            # Issue #337: Cache the broker state
            self._cache = broker_state
            self._cache_timestamp = get_datetime_now()

            # Issue #337 Phase 2: Piggyback alert check if enough time has passed
            self._maybe_refresh_alerts(broker_state)

            return broker_state

        except Exception as e:
            logger.error(f"Failed to fetch broker state: {e}")
            raise

    def invalidate(self):
        """
        Invalidate the broker state cache.

        Issue #337: Call this after placing/modifying/cancelling orders
        to ensure the next fetch() gets fresh data.
        """
        self._cache = None
        self._cache_timestamp = None
        logger.debug("Broker state cache invalidated")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for debugging/monitoring.

        Returns:
            Dict with cache_valid, cache_age_seconds, ttl_seconds
        """
        if self._cache is None:
            return {
                "cache_valid": False,
                "cache_age_seconds": None,
                "ttl_seconds": self.cache_ttl_seconds,
            }

        cache_age = (get_datetime_now() - self._cache_timestamp).total_seconds()
        return {
            "cache_valid": cache_age < self.cache_ttl_seconds,
            "cache_age_seconds": round(cache_age, 1),
            "ttl_seconds": self.cache_ttl_seconds,
        }

    def _should_refresh_alerts(self) -> bool:
        """
        Check if alerts should be refreshed.

        Returns:
            True if enough time has passed since last alert check
        """
        if self._last_alert_check is None:
            return True
        elapsed = (get_datetime_now() - self._last_alert_check).total_seconds()
        return elapsed >= self.alert_refresh_interval

    def _maybe_refresh_alerts(self, broker_state: Dict[str, Any]):
        """
        Opportunistically refresh alerts if enough time has passed.

        Issue #337 Phase 2: This is called from fetch() to
        "piggyback" alert checks on broker state fetches without additional API calls.

        Args:
            broker_state: Current broker state (already fetched)
        """
        if not self._should_refresh_alerts():
            return

        if self.check_alerts_callback is None:
            return

        try:
            self._cached_alerts = self.check_alerts_callback(broker_state)
            self._last_alert_check = get_datetime_now()
            logger.debug(f"Background alert refresh: {len(self._cached_alerts)} alerts")
        except Exception as e:
            logger.warning(f"Failed to refresh alerts: {e}")

    def get_current_alerts(self) -> List[Any]:
        """
        Get cached alerts without additional API calls.

        Issue #337 Phase 2: Returns cached alerts. If alerts are stale or missing,
        triggers a broker state fetch which will refresh alerts via piggyback.

        Returns:
            List of PositionAlertSummary objects
        """
        if not self._cached_alerts or self._should_refresh_alerts():
            # Trigger broker fetch which will piggyback alert refresh
            self.fetch()

        return self._cached_alerts
