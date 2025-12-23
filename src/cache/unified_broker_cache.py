"""
Unified Broker Cache - Database-first caching for broker state.

Issue #469: Implements database-as-cache architecture where all broker data
flows through SQLite before being displayed to users.

Pattern: API Fetch → Store to DB → Read from DB → Display to User

This ensures:
1. Consistency between displayed and stored data
2. Audit trail of what users saw
3. Graceful degradation when API fails
4. Historical queries for debugging
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.utils.date_utils import get_datetime_now, now_iso

logger = logging.getLogger(__name__)


class UnifiedBrokerCache:
    """
    Database-first broker state caching.

    Replaces in-memory BrokerStateCache with SQLite-backed storage that:
    - Persists between sessions
    - Provides historical queries
    - Ensures displayed data matches stored data
    - Supports audit logging

    Example:
        >>> cache = UnifiedBrokerCache()
        >>> account = cache.get_account("paper_main", fetcher=alpaca_monitor.get_account_status)
        >>> positions = cache.get_positions("paper_main", fetcher=alpaca_monitor.get_positions)
    """

    # Default TTL values in seconds
    DEFAULT_TTL = {
        "account": 60,  # Account balance - 1 minute
        "positions": 60,  # Position list - 1 minute
        "orders": 30,  # Orders - 30 seconds (more dynamic)
        "default": 60,
    }

    def __init__(self, db_path: str = ".cache/trading_data.db"):
        """
        Initialize unified broker cache.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_tables()
        logger.info(f"UnifiedBrokerCache initialized: {self.db_path}")

    def _init_tables(self):
        """Create broker cache tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Main broker state cache table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS broker_state_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    state_type TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    UNIQUE(account_id, state_type)
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_broker_state_lookup
                ON broker_state_cache(account_id, state_type)
            """
            )

            # Position snapshots for historical tracking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS position_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    snapshot_time TEXT NOT NULL,
                    qty REAL NOT NULL,
                    avg_entry_price REAL NOT NULL,
                    current_price REAL,
                    market_value REAL,
                    unrealized_pnl REAL,
                    unrealized_pnl_pct REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    trailing_stop_pct REAL,
                    source TEXT DEFAULT 'alpaca'
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_position_snapshots
                ON position_snapshots(account_id, symbol, snapshot_time)
            """
            )

            # Order snapshots for historical tracking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS order_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    snapshot_time TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    qty REAL NOT NULL,
                    filled_qty REAL DEFAULT 0,
                    limit_price REAL,
                    stop_price REAL,
                    status TEXT NOT NULL,
                    submitted_at TEXT,
                    filled_at TEXT,
                    source TEXT DEFAULT 'alpaca'
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_order_snapshots
                ON order_snapshots(account_id, order_id, snapshot_time)
            """
            )

            # Display audit log
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS display_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_time TEXT NOT NULL,
                    display_type TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    cache_source TEXT,
                    cache_age_seconds REAL
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_time
                ON display_audit_log(display_time)
            """
            )

            conn.commit()

    def get_account(
        self,
        account_id: str,
        fetcher: Optional[Callable[[], Optional[Dict]]] = None,
        max_age_seconds: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached account state, fetch if stale.

        Args:
            account_id: Account identifier
            fetcher: Optional function to fetch fresh data if cache is stale
            max_age_seconds: Maximum cache age (default: 60 seconds)

        Returns:
            Account data dict or None if not available
        """
        ttl = max_age_seconds or self.DEFAULT_TTL["account"]
        return self._get_cached_state(account_id, "account", fetcher, ttl)

    def get_positions(
        self,
        account_id: str,
        fetcher: Optional[Callable[[], List[Dict]]] = None,
        max_age_seconds: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get cached positions, fetch if stale.

        Args:
            account_id: Account identifier
            fetcher: Optional function to fetch fresh data if cache is stale
            max_age_seconds: Maximum cache age (default: 60 seconds)

        Returns:
            List of position dicts (empty list if not available)
        """
        ttl = max_age_seconds or self.DEFAULT_TTL["positions"]
        result = self._get_cached_state(account_id, "positions", fetcher, ttl)
        return result if result else []

    def get_orders(
        self,
        account_id: str,
        fetcher: Optional[Callable[[], List[Dict]]] = None,
        max_age_seconds: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get cached orders, fetch if stale.

        Args:
            account_id: Account identifier
            fetcher: Optional function to fetch fresh data if cache is stale
            max_age_seconds: Maximum cache age (default: 30 seconds)

        Returns:
            List of order dicts (empty list if not available)
        """
        ttl = max_age_seconds or self.DEFAULT_TTL["orders"]
        result = self._get_cached_state(account_id, "orders", fetcher, ttl)
        return result if result else []

    def _get_cached_state(
        self,
        account_id: str,
        state_type: str,
        fetcher: Optional[Callable] = None,
        ttl_seconds: int = 60,
    ) -> Optional[Any]:
        """
        Get cached state with optional refresh.

        Database-first pattern:
        1. Check cache freshness
        2. If stale and fetcher provided, fetch and store
        3. Return from database (never from raw API response)

        Args:
            account_id: Account identifier
            state_type: Type of state (account, positions, orders)
            fetcher: Function to fetch fresh data
            ttl_seconds: Cache TTL in seconds

        Returns:
            Cached data or None
        """
        now = get_datetime_now()

        # Step 1: Check existing cache
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT data_json, fetched_at, expires_at
                    FROM broker_state_cache
                    WHERE account_id = ? AND state_type = ?
                """,
                    (account_id, state_type),
                )
                row = cursor.fetchone()

                if row:
                    data_json, fetched_at, expires_at = row
                    expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

                    # Cache is fresh - return it
                    if now < expires_dt:
                        logger.debug(f"Cache hit: {account_id}/{state_type}")
                        return json.loads(data_json)

                    logger.debug(f"Cache stale: {account_id}/{state_type}")

        except Exception as e:
            logger.warning(f"Error reading cache: {e}")

        # Step 2: Cache miss or stale - fetch if possible
        if fetcher is not None:
            try:
                fresh_data = fetcher()
                if fresh_data is not None:
                    # Store to database first
                    self._store_state(account_id, state_type, fresh_data, ttl_seconds)
                    logger.debug(f"Fetched and cached: {account_id}/{state_type}")
                    # Return from database (database-first pattern)
                    return fresh_data

            except Exception as e:
                logger.warning(f"Error fetching fresh data for {state_type}: {e}")

        # Step 3: Return stale cache as fallback
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT data_json FROM broker_state_cache
                    WHERE account_id = ? AND state_type = ?
                """,
                    (account_id, state_type),
                )
                row = cursor.fetchone()
                if row:
                    logger.warning(f"Serving stale cache: {account_id}/{state_type}")
                    return json.loads(row[0])

        except Exception as e:
            logger.error(f"Error reading stale cache: {e}")

        return None

    def _store_state(self, account_id: str, state_type: str, data: Any, ttl_seconds: int) -> None:
        """Store state to database."""
        now = get_datetime_now()
        expires_at = now + timedelta(seconds=ttl_seconds)

        with self._write_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO broker_state_cache
                        (account_id, state_type, data_json, fetched_at, expires_at)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            account_id,
                            state_type,
                            json.dumps(data, default=str),
                            now.isoformat(),
                            expires_at.isoformat(),
                        ),
                    )
                    conn.commit()

            except Exception as e:
                logger.error(f"Error storing cache: {e}")

    def refresh(self, account_id: str, state_type: str = "all") -> None:
        """
        Force cache expiration to trigger refresh on next access.

        Args:
            account_id: Account identifier
            state_type: Type to refresh ("all", "account", "positions", "orders")
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if state_type == "all":
                    conn.execute(
                        """
                        UPDATE broker_state_cache
                        SET expires_at = datetime('now', '-1 hour')
                        WHERE account_id = ?
                    """,
                        (account_id,),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE broker_state_cache
                        SET expires_at = datetime('now', '-1 hour')
                        WHERE account_id = ? AND state_type = ?
                    """,
                        (account_id, state_type),
                    )
                conn.commit()
                logger.info(f"Cache invalidated: {account_id}/{state_type}")

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")

    def get_cache_info(self, account_id: str) -> Dict[str, Any]:
        """
        Get cache statistics for an account.

        Args:
            account_id: Account identifier

        Returns:
            Dict with cache stats (types, ages, expiry times)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT state_type, fetched_at, expires_at
                    FROM broker_state_cache
                    WHERE account_id = ?
                """,
                    (account_id,),
                )

                now = get_datetime_now()
                info = {"account_id": account_id, "cache_entries": {}}

                for row in cursor:
                    state_type, fetched_at, expires_at = row
                    fetched_dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
                    expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

                    age_seconds = (now - fetched_dt).total_seconds()
                    is_fresh = now < expires_dt

                    info["cache_entries"][state_type] = {
                        "fetched_at": fetched_at,
                        "expires_at": expires_at,
                        "age_seconds": round(age_seconds, 1),
                        "is_fresh": is_fresh,
                        "status": "fresh" if is_fresh else "stale",
                    }

                return info

        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
            return {"account_id": account_id, "error": str(e)}

    def store_position_snapshot(
        self, account_id: str, positions: List[Dict], local_state: Optional[Dict] = None
    ) -> int:
        """
        Store position snapshot for historical tracking.

        Args:
            account_id: Account identifier
            positions: List of position dicts from broker
            local_state: Optional local state with stops/targets

        Returns:
            Number of positions stored
        """
        snapshot_time = now_iso()
        local_state = local_state or {}

        with self._write_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    count = 0
                    for pos in positions:
                        symbol = pos.get("symbol", "")
                        local_pos = local_state.get(symbol, {})

                        conn.execute(
                            """
                            INSERT INTO position_snapshots
                            (account_id, symbol, snapshot_time, qty, avg_entry_price,
                             current_price, market_value, unrealized_pnl, unrealized_pnl_pct,
                             stop_loss, take_profit, trailing_stop_pct, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                account_id,
                                symbol,
                                snapshot_time,
                                float(pos.get("qty", 0)),
                                float(pos.get("avg_entry_price", 0)),
                                float(pos.get("current_price", 0)),
                                float(pos.get("market_value", 0)),
                                float(pos.get("unrealized_pl", 0)),
                                float(pos.get("unrealized_plpc", 0)),
                                local_pos.get("stop_loss"),
                                local_pos.get("take_profit"),
                                local_pos.get("trailing_stop_pct"),
                                "alpaca",
                            ),
                        )
                        count += 1

                    conn.commit()
                    logger.debug(f"Stored {count} position snapshots")
                    return count

            except Exception as e:
                logger.error(f"Error storing position snapshots: {e}")
                return 0

    def store_order_snapshot(self, account_id: str, orders: List[Dict]) -> int:
        """
        Store order snapshot for historical tracking.

        Args:
            account_id: Account identifier
            orders: List of order dicts from broker

        Returns:
            Number of orders stored
        """
        snapshot_time = now_iso()

        with self._write_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    count = 0
                    for order in orders:
                        conn.execute(
                            """
                            INSERT INTO order_snapshots
                            (account_id, order_id, symbol, snapshot_time, side, order_type,
                             qty, filled_qty, limit_price, stop_price, status,
                             submitted_at, filled_at, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                account_id,
                                order.get("id", ""),
                                order.get("symbol", ""),
                                snapshot_time,
                                order.get("side", ""),
                                order.get("type", ""),
                                float(order.get("qty", 0)),
                                float(order.get("filled_qty", 0)),
                                order.get("limit_price"),
                                order.get("stop_price"),
                                order.get("status", ""),
                                order.get("submitted_at"),
                                order.get("filled_at"),
                                "alpaca",
                            ),
                        )
                        count += 1

                    conn.commit()
                    logger.debug(f"Stored {count} order snapshots")
                    return count

            except Exception as e:
                logger.error(f"Error storing order snapshots: {e}")
                return 0

    def audit_display(
        self,
        display_type: str,
        data: Any,
        cache_source: str = "unknown",
        cache_age_seconds: float = 0.0,
    ) -> None:
        """
        Log data displayed to user for audit trail.

        Args:
            display_type: Type of display (portfolio, position, order, analysis)
            data: Data that was displayed
            cache_source: Where data came from (live, cached, stale)
            cache_age_seconds: Age of cached data
        """
        with self._write_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO display_audit_log
                        (display_time, display_type, data_json, cache_source, cache_age_seconds)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            now_iso(),
                            display_type,
                            json.dumps(data, default=str),
                            cache_source,
                            cache_age_seconds,
                        ),
                    )
                    conn.commit()

            except Exception as e:
                logger.warning(f"Error logging display audit: {e}")

    def get_position_history(
        self, account_id: str, symbol: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get historical position snapshots for a symbol.

        Args:
            account_id: Account identifier
            symbol: Stock symbol
            limit: Maximum results to return

        Returns:
            List of position snapshot dicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM position_snapshots
                    WHERE account_id = ? AND symbol = ?
                    ORDER BY snapshot_time DESC
                    LIMIT ?
                """,
                    (account_id, symbol.upper(), limit),
                )
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting position history: {e}")
            return []

    def cleanup_old_snapshots(self, days_to_keep: int = 30) -> int:
        """
        Remove old snapshots to manage database size.

        Args:
            days_to_keep: Number of days of snapshots to retain

        Returns:
            Number of rows deleted
        """
        cutoff = (get_datetime_now() - timedelta(days=days_to_keep)).isoformat()

        with self._write_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Delete old position snapshots
                    cursor = conn.execute(
                        "DELETE FROM position_snapshots WHERE snapshot_time < ?", (cutoff,)
                    )
                    pos_deleted = cursor.rowcount

                    # Delete old order snapshots
                    cursor = conn.execute(
                        "DELETE FROM order_snapshots WHERE snapshot_time < ?", (cutoff,)
                    )
                    order_deleted = cursor.rowcount

                    # Delete old audit logs
                    cursor = conn.execute(
                        "DELETE FROM display_audit_log WHERE display_time < ?", (cutoff,)
                    )
                    audit_deleted = cursor.rowcount

                    conn.commit()

                    total = pos_deleted + order_deleted + audit_deleted
                    if total > 0:
                        logger.info(
                            f"Cleaned up {total} old records "
                            f"(positions: {pos_deleted}, orders: {order_deleted}, audit: {audit_deleted})"
                        )
                    return total

            except Exception as e:
                logger.error(f"Error cleaning up snapshots: {e}")
                return 0


# Global instance for easy access
unified_broker_cache = UnifiedBrokerCache()
