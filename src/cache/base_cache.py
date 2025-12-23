"""
Base SQLite cache manager with shared connection logic.

Issue #438: Split sqlite_cache.py by data domain.
"""

import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)


class BaseSQLiteCache:
    """
    Base class for SQLite-based cache managers.

    Provides:
    - Shared database connection
    - Thread-safe write operations
    - Common cleanup operations
    - Database initialization hooks
    """

    def __init__(self, db_path: str = ".cache/trading_data.db"):
        """
        Initialize SQLite cache connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._write_lock = threading.Lock()  # Serialize write operations
        self._init_database()

    def _init_database(self):
        """
        Initialize database schema.

        Subclasses should override to create their tables.
        """
        raise NotImplementedError("Subclasses must implement _init_database()")

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a new database connection.

        Returns:
            SQLite connection
        """
        return sqlite3.connect(self.db_path)

    def vacuum(self):
        """
        Optimize database file size.

        Reclaims unused space from deleted rows.
        """
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                self.logger.info(f"Database vacuumed: {self.db_path}")
        except Exception as e:
            self.logger.error(f"Error vacuuming database: {e}")

    def _calculate_expiration(self, start_date: str, end_date: str) -> datetime:
        """
        Calculate expiration time for cached data.

        Historical data (>1 day old) never expires.
        Current/recent data expires after 24 hours.

        Args:
            start_date: Data start date
            end_date: Data end date

        Returns:
            Expiration datetime
        """
        now = get_datetime_now()
        today = now.date()

        # Parse end date
        try:
            if isinstance(end_date, str):
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            else:
                end_dt = end_date
        except Exception:
            # If parse fails, assume current data
            end_dt = today

        # Historical data never expires (set far future)
        if end_dt < today:
            return now + timedelta(days=36500)  # ~100 years

        # Current/recent data expires after 24 hours
        return now + timedelta(hours=24)

    def cleanup_expired(self, table_name: str) -> int:
        """
        Remove expired cache entries from specified table.

        Args:
            table_name: Name of table to clean

        Returns:
            Number of deleted rows
        """
        try:
            with self._write_lock:
                with self.get_connection() as conn:
                    now = get_datetime_now().isoformat()
                    cursor = conn.execute(
                        f"DELETE FROM {table_name} WHERE expires_at < ?", (now,)  # nosec B608
                    )
                    deleted = cursor.rowcount
                    conn.commit()

                    if deleted > 0:
                        self.logger.info(f"Cleaned up {deleted} expired entries from {table_name}")

                    return deleted
        except Exception as e:
            self.logger.error(f"Error cleaning up {table_name}: {e}")
            return 0
