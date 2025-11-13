"""
SQLite-based cache for market data.

Replaces file-based caching with efficient relational storage.
Provides drop-in replacement for UnifiedCacheManager with better performance.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
import json


logger = logging.getLogger(__name__)


class TradingCacheManager:
    """
    SQLite-based market data cache.

    Features:
    - Efficient range queries (no file loading overhead)
    - ACID transactions for data integrity
    - Concurrent read/write safety
    - Futures-ready schema (asset_type column)
    - Smart expiration (historical data never expires)

    Example:
        >>> cache = TradingCacheManager()
        >>> df = cache.get("SPY", "2024-01-01", "2024-12-31", source="alpaca")
        >>> cache.set("SPY", market_data_df, source="alpaca")
    """

    def __init__(self, db_path: str = ".cache/trading_data.db"):
        """
        Initialize SQLite cache.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_database()

    def _init_database(self):
        """Create tables and indexes if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Create main table
            conn.execute("""
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
            """)

            # Create indexes for fast lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_lookup
                ON market_cache(asset_type, symbol, trading_date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_range
                ON market_cache(symbol, trading_date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expiry
                ON market_cache(expires_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol
                ON market_cache(symbol)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source
                ON market_cache(source)
            """)
            conn.commit()

        self.logger.debug(f"SQLite cache initialized: {self.db_path}")

    def get(self, symbol: str, start: str, end: str,
            source: str = None, asset_type: str = "stock") -> Optional[pd.DataFrame]:
        """
        Get cached data for date range.

        Automatically filters out expired data. Returns None if no valid cache found.

        Args:
            symbol: Ticker symbol (e.g., "SPY")
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format
            source: Data source filter (None = any source)
            asset_type: Asset type (default: "stock")

        Returns:
            DataFrame with OHLCV data, or None if not found/expired

        Example:
            >>> df = cache.get("SPY", "2024-01-01", "2024-03-31", source="alpaca")
            >>> if df is not None:
            ...     print(f"Loaded {len(df)} days of data")
        """
        try:
            # Build query with optional source filter
            query = """
                SELECT trading_date, open, high, low, close, volume, vwap, transactions
                FROM market_cache
                WHERE asset_type = ?
                  AND symbol = ?
                  AND trading_date >= ?
                  AND trading_date <= ?
                  AND datetime(expires_at) > datetime('now')
            """
            params = [asset_type, symbol, start, end]

            if source:
                query += " AND source = ?"
                params.append(source)

            query += " ORDER BY trading_date ASC"

            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn, params=params)

            if df.empty:
                self.logger.debug(f"Cache miss: {symbol} ({start} to {end})")
                return None

            # Convert date column to datetime and set as index
            df['trading_date'] = pd.to_datetime(df['trading_date'])
            df.set_index('trading_date', inplace=True)
            df.index.name = 'date'  # Rename index to match expected format

            # Drop columns that are all NULL (e.g., vwap/transactions from Alpha Vantage)
            df = df.dropna(axis=1, how='all')

            self.logger.debug(
                f"Cache hit: {symbol} ({start} to {end}) - {len(df)} days from {source or 'any source'}"
            )
            return df

        except Exception as e:
            self.logger.error(f"Error reading cache for {symbol}: {e}")
            return None

    def set(self, symbol: str, data: pd.DataFrame, source: str,
            asset_type: str = "stock", ttl_hours: int = None):
        """
        Cache market data.

        Stores OHLCV data with smart expiration:
        - Historical data (>2 days old): 10 years (effectively never expires)
        - Recent data (≤2 days): 24 hours (needs fresh updates)

        Args:
            symbol: Ticker symbol
            data: DataFrame with OHLCV data (must have 'date' column or DatetimeIndex)
            source: Data source ("alpaca", "polygon", "alpha_vantage")
            asset_type: Asset type (default: "stock")
            ttl_hours: Custom TTL in hours (None = auto-calculate)

        Raises:
            ValueError: If data has no date column/index

        Example:
            >>> df = pd.DataFrame({
            ...     'date': ['2024-01-01', '2024-01-02'],
            ...     'close': [100.0, 101.0],
            ...     'volume': [1000, 1100]
            ... })
            >>> cache.set("SPY", df, source="alpaca")
        """
        if data.empty:
            self.logger.debug(f"Skipping empty data for {symbol}")
            return

        try:
            # Prepare DataFrame
            df = data.copy()

            # Ensure we have a date column
            if isinstance(df.index, pd.DatetimeIndex):
                df.reset_index(inplace=True)
                if 'index' in df.columns:
                    df.rename(columns={'index': 'date'}, inplace=True)
            elif 'date' not in df.columns:
                raise ValueError("Data must have 'date' column or DatetimeIndex")

            # Convert date to string format
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # Add metadata columns
            df['asset_type'] = asset_type
            df['symbol'] = symbol
            df['source'] = source
            df['cached_at'] = datetime.now().isoformat()

            # Calculate smart expiration for each row
            if ttl_hours:
                # Custom TTL
                expires_at = datetime.now() + timedelta(hours=ttl_hours)
                df['expires_at'] = expires_at.isoformat()
            else:
                # Smart TTL based on data recency
                df['expires_at'] = df['date'].apply(lambda d: self._calculate_expiration(d, d).isoformat())

            # Rename date column to trading_date for DB
            df.rename(columns={'date': 'trading_date'}, inplace=True)

            # Select columns that exist in schema
            base_columns = ['asset_type', 'symbol', 'trading_date', 'source',
                          'cached_at', 'expires_at']
            price_columns = ['open', 'high', 'low', 'close', 'volume', 'vwap', 'transactions']

            # Include only columns that exist in the data
            columns_to_save = base_columns + [col for col in price_columns if col in df.columns]
            df_to_save = df[columns_to_save]

            # Ensure close column exists (required)
            if 'close' not in df_to_save.columns:
                raise ValueError("Data must have 'close' column")

            # Bulk insert using pandas to_sql (much faster than row-by-row)
            with sqlite3.connect(self.db_path) as conn:
                # Use INSERT OR REPLACE for idempotent caching
                df_to_save.to_sql(
                    'market_cache_temp',
                    conn,
                    if_exists='replace',
                    index=False
                )

                # Build column list for INSERT (exclude id which is auto-increment)
                columns_list = ', '.join(columns_to_save)

                # Copy to main table with INSERT OR REPLACE
                conn.execute(f"""
                    INSERT OR REPLACE INTO market_cache
                    ({columns_list})
                    SELECT {columns_list} FROM market_cache_temp
                """)

                # Drop temp table
                conn.execute("DROP TABLE market_cache_temp")
                conn.commit()

            self.logger.debug(
                f"Cached {len(df_to_save)} days for {symbol} ({df_to_save['trading_date'].min()} to {df_to_save['trading_date'].max()}) from {source}"
            )

        except Exception as e:
            self.logger.error(f"Error caching data for {symbol}: {e}", exc_info=True)
            raise

    def exists(self, symbol: str, start: str, end: str,
               source: str = None, asset_type: str = "stock") -> bool:
        """
        Check if data exists (even if expired).

        Args:
            symbol: Ticker symbol
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            source: Data source filter (None = any source)
            asset_type: Asset type (default: "stock")

        Returns:
            True if any data exists for the range (expired or not)
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM market_cache
                WHERE asset_type = ?
                  AND symbol = ?
                  AND trading_date >= ?
                  AND trading_date <= ?
            """
            params = [asset_type, symbol, start, end]

            if source:
                query += " AND source = ?"
                params.append(source)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                count = cursor.fetchone()[0]

            return count > 0

        except Exception as e:
            self.logger.error(f"Error checking existence for {symbol}: {e}")
            return False

    def delete(self, symbol: str, start: str = None, end: str = None,
               source: str = None, asset_type: str = "stock") -> int:
        """
        Delete cached data.

        Args:
            symbol: Ticker symbol
            start: Start date (None = all dates)
            end: End date (None = all dates)
            source: Data source filter (None = all sources)
            asset_type: Asset type (default: "stock")

        Returns:
            Number of rows deleted
        """
        try:
            query = "DELETE FROM market_cache WHERE asset_type = ? AND symbol = ?"
            params = [asset_type, symbol]

            if start:
                query += " AND trading_date >= ?"
                params.append(start)

            if end:
                query += " AND trading_date <= ?"
                params.append(end)

            if source:
                query += " AND source = ?"
                params.append(source)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                deleted = cursor.rowcount
                conn.commit()

            self.logger.debug(f"Deleted {deleted} rows for {symbol}")
            return deleted

        except Exception as e:
            self.logger.error(f"Error deleting data for {symbol}: {e}")
            return 0

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of rows deleted
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM market_cache
                    WHERE datetime(expires_at) <= datetime('now')
                """)
                deleted = cursor.rowcount
                conn.commit()

            if deleted > 0:
                self.logger.info(f"Cleaned up {deleted} expired cache entries")

            return deleted

        except Exception as e:
            self.logger.error(f"Error cleaning up expired cache: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache metrics:
            - total_entries: Total number of cached days
            - unique_symbols: Number of unique symbols
            - sources: Breakdown by data source
            - asset_types: Breakdown by asset type
            - date_range: Min and max dates
            - db_size_mb: Database file size in MB
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total entries
                total = conn.execute("SELECT COUNT(*) FROM market_cache").fetchone()[0]

                # Unique symbols
                unique_symbols = conn.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM market_cache"
                ).fetchone()[0]

                # Breakdown by source
                sources = {}
                for row in conn.execute(
                    "SELECT source, COUNT(*) as count FROM market_cache GROUP BY source"
                ):
                    sources[row[0]] = row[1]

                # Breakdown by asset type
                asset_types = {}
                for row in conn.execute(
                    "SELECT asset_type, COUNT(*) as count FROM market_cache GROUP BY asset_type"
                ):
                    asset_types[row[0]] = row[1]

                # Date range
                date_range = conn.execute(
                    "SELECT MIN(trading_date), MAX(trading_date) FROM market_cache"
                ).fetchone()

                # Expired entries
                expired = conn.execute("""
                    SELECT COUNT(*) FROM market_cache
                    WHERE datetime(expires_at) <= datetime('now')
                """).fetchone()[0]

            # Database file size
            db_size_mb = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0

            return {
                "total_entries": total,
                "unique_symbols": unique_symbols,
                "sources": sources,
                "asset_types": asset_types,
                "date_range": {
                    "min_date": date_range[0],
                    "max_date": date_range[1]
                } if date_range[0] else None,
                "expired_entries": expired,
                "db_size_mb": round(db_size_mb, 2),
                "db_path": str(self.db_path)
            }

        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {}

    def _calculate_expiration(self, start_date: str, end_date: str) -> datetime:
        """
        Calculate smart expiration based on data recency.

        Historical data (>2 days old): 10 years (effectively never expires)
        Recent data (≤2 days): 24 hours (needs fresh updates)

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Expiration datetime
        """
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            today = datetime.now().date()

            # Historical data should never practically expire
            if end_dt.date() < today - timedelta(days=2):
                return datetime.now() + timedelta(days=365 * 10)  # 10 years

            # Recent data needs fresh updates
            else:
                return datetime.now() + timedelta(hours=24)

        except ValueError:
            # Fallback to short expiration if date parsing fails
            return datetime.now() + timedelta(hours=24)

    def get_symbols(self, asset_type: str = "stock") -> List[str]:
        """
        Get list of all cached symbols.

        Args:
            asset_type: Asset type filter (default: "stock")

        Returns:
            List of unique symbols
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT DISTINCT symbol FROM market_cache WHERE asset_type = ? ORDER BY symbol",
                    [asset_type]
                )
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting symbols: {e}")
            return []

    def vacuum(self):
        """
        Optimize database (reclaim space after deletions).

        Run this after cleanup_expired() or large deletions.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("VACUUM")

            self.logger.info("Database optimized (VACUUM completed)")

        except Exception as e:
            self.logger.error(f"Error vacuuming database: {e}")
