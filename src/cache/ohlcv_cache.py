"""
OHLCV market data cache manager.

Issue #438: Split sqlite_cache.py by data domain.
Handles stock/futures OHLCV price data caching.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from .base_cache import BaseSQLiteCache
from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)


class OHLCVCacheManager(BaseSQLiteCache):
    """
    SQLite-based OHLCV market data cache.

    Features:
    - Efficient range queries for price data
    - Multi-source support (Alpaca, Polygon, Alpha Vantage)
    - Smart expiration (historical data never expires)
    - Futures-ready (asset_type column)

    Example:
        >>> cache = OHLCVCacheManager()
        >>> df = cache.get("SPY", "2024-01-01", "2024-12-31", source="alpaca")
        >>> cache.set("SPY", market_data_df, source="alpaca")
    """

    def _init_database(self):
        """Create market_cache table and indexes."""
        with self.get_connection() as conn:
            # Create main market data table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- Asset identification
                    asset_type TEXT NOT NULL DEFAULT 'stock',
                    symbol TEXT NOT NULL,
                    trading_date TEXT NOT NULL,
                    source TEXT NOT NULL,

                    -- Price data (OHLCV)
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL NOT NULL,
                    volume REAL,

                    -- Extended data (optional, for Polygon)
                    vwap REAL,
                    transactions INTEGER,

                    -- Metadata
                    cached_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    metadata TEXT,

                    -- Unique constraint: one entry per symbol+date+source
                    UNIQUE(asset_type, symbol, trading_date, source)
                )
            """
            )

            # Create indexes for faster queries
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_symbol_date
                ON market_cache(symbol, trading_date)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_expires
                ON market_cache(expires_at)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_asset_type
                ON market_cache(asset_type)
            """
            )

    def get(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        source: Optional[str] = None,
        asset_type: str = "stock",
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve cached OHLCV data for a symbol and date range.

        Args:
            symbol: Stock/futures symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            source: Data source filter (alpaca, polygon, alpha_vantage, None=any)
            asset_type: Asset type (stock, futures)

        Returns:
            DataFrame with OHLCV data, or None if not cached
        """
        try:
            with self.get_connection() as conn:
                now = get_datetime_now().isoformat()

                # Build query with optional source filter
                if source:
                    query = """
                        SELECT trading_date, open, high, low, close, volume, vwap, transactions
                        FROM market_cache
                        WHERE asset_type = ? AND symbol = ? AND trading_date >= ? AND trading_date <= ?
                          AND source = ? AND expires_at > ?
                        ORDER BY trading_date ASC
                    """
                    params = (asset_type, symbol, start_date, end_date, source, now)
                else:
                    query = """
                        SELECT trading_date, open, high, low, close, volume, vwap, transactions
                        FROM market_cache
                        WHERE asset_type = ? AND symbol = ? AND trading_date >= ? AND trading_date <= ?
                          AND expires_at > ?
                        ORDER BY trading_date ASC
                    """
                    params = (asset_type, symbol, start_date, end_date, now)

                df = pd.read_sql_query(query, conn, params=params, parse_dates=["trading_date"])

                if df.empty:
                    return None

                # Set trading_date as index
                df.set_index("trading_date", inplace=True)

                # Capitalize column names for consistency
                df.columns = [col.capitalize() for col in df.columns]

                return df

        except Exception as e:
            self.logger.error(f"Error retrieving cache for {symbol}: {e}")
            return None

    def set(
        self,
        symbol: str,
        data: pd.DataFrame,
        source: str = "auto",
        asset_type: str = "stock",
    ) -> bool:
        """
        Store OHLCV data in cache.

        Args:
            symbol: Stock/futures symbol
            data: DataFrame with OHLCV data (must have DatetimeIndex)
            source: Data source (alpaca, polygon, alpha_vantage, auto)
            asset_type: Asset type (stock, futures)

        Returns:
            True if successful, False otherwise
        """
        if data is None or data.empty:
            return False

        try:
            # Normalize column names (handle both lowercase and capitalized)
            column_mapping = {
                "open": "open",
                "Open": "open",
                "high": "high",
                "High": "high",
                "low": "low",
                "Low": "low",
                "close": "close",
                "Close": "close",
                "volume": "volume",
                "Volume": "volume",
                "vwap": "vwap",
                "Vwap": "vwap",
                "VWAP": "vwap",
                "transactions": "transactions",
                "Transactions": "transactions",
            }

            data_copy = data.copy()

            # Rename columns to lowercase
            data_copy.rename(columns=column_mapping, inplace=True)

            # Extract date range for expiration calculation
            if not isinstance(data_copy.index, pd.DatetimeIndex):
                self.logger.error(f"DataFrame must have DatetimeIndex, got {type(data_copy.index)}")
                return False

            start_date = data_copy.index.min().strftime("%Y-%m-%d")
            end_date = data_copy.index.max().strftime("%Y-%m-%d")

            # Calculate expiration
            expires_at = self._calculate_expiration(start_date, end_date)
            cached_at = get_datetime_now()

            # Prepare rows for insertion
            rows = []
            for trading_date, row in data_copy.iterrows():
                rows.append(
                    (
                        asset_type,
                        symbol,
                        trading_date.strftime("%Y-%m-%d"),
                        source,
                        row.get("open"),
                        row.get("high"),
                        row.get("low"),
                        row["close"],  # Required
                        row.get("volume"),
                        row.get("vwap"),
                        row.get("transactions"),
                        cached_at.isoformat(),
                        expires_at.isoformat(),
                        None,  # metadata
                    )
                )

            # Insert with thread safety
            with self._write_lock:
                with self.get_connection() as conn:
                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO market_cache
                        (asset_type, symbol, trading_date, source, open, high, low, close,
                         volume, vwap, transactions, cached_at, expires_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        rows,
                    )
                    conn.commit()

            self.logger.debug(
                f"Cached {len(rows)} rows for {symbol} ({start_date} to {end_date}, source={source})"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error caching data for {symbol}: {e}")
            return False

    def exists(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        source: Optional[str] = None,
        asset_type: str = "stock",
    ) -> bool:
        """
        Check if data exists in cache for the given parameters.

        Args:
            symbol: Stock/futures symbol
            start_date: Start date
            end_date: End date
            source: Data source filter (optional)
            asset_type: Asset type

        Returns:
            True if data exists and is not expired
        """
        data = self.get(symbol, start_date, end_date, source=source, asset_type=asset_type)
        return data is not None and not data.empty

    def delete(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source: Optional[str] = None,
        asset_type: str = "stock",
    ) -> int:
        """
        Delete cached data.

        Args:
            symbol: Stock/futures symbol
            start_date: Optional start date filter
            end_date: Optional end date filter
            source: Optional source filter
            asset_type: Asset type

        Returns:
            Number of deleted rows
        """
        try:
            with self._write_lock:
                with self.get_connection() as conn:
                    # Build dynamic query based on filters
                    conditions = ["asset_type = ?", "symbol = ?"]
                    params = [asset_type, symbol]

                    if start_date:
                        conditions.append("trading_date >= ?")
                        params.append(start_date)

                    if end_date:
                        conditions.append("trading_date <= ?")
                        params.append(end_date)

                    if source:
                        conditions.append("source = ?")
                        params.append(source)

                    query = (
                        f"DELETE FROM market_cache WHERE {' AND '.join(conditions)}"  # nosec B608
                    )

                    cursor = conn.execute(query, params)
                    deleted = cursor.rowcount
                    conn.commit()

                    self.logger.info(f"Deleted {deleted} cache entries for {symbol}")
                    return deleted

        except Exception as e:
            self.logger.error(f"Error deleting cache for {symbol}: {e}")
            return 0

    def cleanup_expired(self) -> int:
        """
        Remove expired market data cache entries.

        Returns:
            Number of deleted rows
        """
        return super().cleanup_expired("market_cache")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        try:
            with self.get_connection() as conn:
                # Total rows
                total = conn.execute("SELECT COUNT(*) FROM market_cache").fetchone()[0]

                # Unique symbols
                symbols = conn.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM market_cache"
                ).fetchone()[0]

                # Date range
                date_range = conn.execute(
                    "SELECT MIN(trading_date), MAX(trading_date) FROM market_cache"
                ).fetchone()

                # By source
                sources = {}
                for row in conn.execute(
                    "SELECT source, COUNT(*) FROM market_cache GROUP BY source"
                ).fetchall():
                    sources[row[0]] = row[1]

                # By asset type
                asset_types = {}
                for row in conn.execute(
                    "SELECT asset_type, COUNT(*) FROM market_cache GROUP BY asset_type"
                ).fetchall():
                    asset_types[row[0]] = row[1]

                return {
                    "total_rows": total,
                    "unique_symbols": symbols,
                    "date_range": {
                        "min": date_range[0],
                        "max": date_range[1],
                    },
                    "by_source": sources,
                    "by_asset_type": asset_types,
                }

        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {}

    def get_symbols(self, asset_type: str = "stock") -> List[str]:
        """
        Get list of all cached symbols.

        Args:
            asset_type: Asset type filter

        Returns:
            List of symbol strings
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT DISTINCT symbol FROM market_cache WHERE asset_type = ? ORDER BY symbol",
                    (asset_type,),
                )
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting symbols: {e}")
            return []
