"""
SQLite-based cache for market data.

Replaces file-based caching with efficient relational storage.
Provides drop-in replacement for UnifiedCacheManager with better performance.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta  # TODO utilze @date_utils.py
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
import threading
import uuid
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
        self._write_lock = threading.Lock()  # Serialize write operations
        self._init_database()

    def _init_database(self):
        """Create tables and indexes if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Create main market data table
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

            # Create raw options chain table (Issue #373)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw_options_chain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- Asset identification
                    symbol TEXT NOT NULL,
                    trading_date TEXT NOT NULL,

                    -- Option contract details
                    strike REAL NOT NULL,
                    option_type TEXT NOT NULL CHECK(option_type IN ('call', 'put')),
                    expiration TEXT NOT NULL,

                    -- Pricing data
                    bid REAL,
                    ask REAL,
                    last REAL,
                    volume INTEGER,
                    open_interest INTEGER,

                    -- Greeks
                    implied_volatility REAL,
                    delta REAL,
                    gamma REAL,
                    theta REAL,
                    vega REAL,
                    rho REAL,

                    -- Metadata
                    contract_symbol TEXT,
                    underlying_price REAL,
                    source TEXT NOT NULL DEFAULT 'polygon',
                    cached_at TEXT NOT NULL,
                    modified_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    -- Provider tracking & data quality
                    data_quality_score REAL DEFAULT 1.0,
                    provider_metadata TEXT,

                    -- Unique constraint
                    UNIQUE(symbol, trading_date, strike, option_type, expiration, source)
                )
            """)

            # Create indexes for market_cache
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

            # Create indexes for raw_options_chain (Issue #373)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_options_symbol_date
                ON raw_options_chain(symbol, trading_date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_options_expiration
                ON raw_options_chain(expiration)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_options_strike
                ON raw_options_chain(symbol, trading_date, strike)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_options_source
                ON raw_options_chain(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_options_quality
                ON raw_options_chain(data_quality_score)
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
                df['expires_at'] = df['date'].apply(
                    lambda d: self._calculate_expiration(d, d).isoformat())

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
            # Use lock to prevent concurrent write conflicts with temp table
            with self._write_lock:
                # Use unique temp table name to avoid conflicts
                temp_table = f'market_cache_temp_{uuid.uuid4().hex[:8]}'

                with sqlite3.connect(self.db_path) as conn:
                    # Use INSERT OR REPLACE for idempotent caching
                    df_to_save.to_sql(
                        temp_table,
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
                        SELECT {columns_list} FROM {temp_table}
                    """)

                    # Drop temp table
                    conn.execute(f"DROP TABLE {temp_table}")
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

    # === RAW OPTIONS CHAIN METHODS (Issue #373) ===

    def store_raw_options(self, symbol: str, trading_date: str, options_df: pd.DataFrame,
                          underlying_price: float = None, source: str = "polygon",
                          data_quality_score: float = 1.0, provider_metadata: dict = None) -> int:
        """
        Store raw options chain data to database with multi-provider support.

        Args:
            symbol: Stock symbol (e.g., "SPY")
            trading_date: Trading date in YYYY-MM-DD format
            options_df: DataFrame with raw options data
            underlying_price: Spot price of underlying (optional)
            source: Data source ("polygon", "alpha_vantage", "alpaca", etc.)
            data_quality_score: Data quality score 0.0-1.0 (default: 1.0)
            provider_metadata: Optional dict with provider-specific metadata

        Returns:
            Number of options contracts stored

        Expected DataFrame columns:
            - strike (required)
            - option_type or type (required): 'call' or 'put'
            - expiration (required)
            - bid, ask, last, volume, open_interest (optional)
            - implied_volatility, delta, gamma, theta, vega, rho (optional)
            - contract_symbol (optional)

        Example:
            >>> options_df = pd.DataFrame({
            ...     'strike': [400, 405, 410],
            ...     'type': ['call', 'call', 'put'],
            ...     'expiration': ['2024-12-20', '2024-12-20', '2024-12-20'],
            ...     'last': [10.5, 8.2, 3.1]
            ... })
            >>> metadata = {'api_version': '2.0', 'rate_limit': 5}
            >>> count = cache.store_raw_options("SPY", "2024-01-15", options_df,
            ...                                  underlying_price=412.50,
            ...                                  source="polygon",
            ...                                  data_quality_score=0.95,
            ...                                  provider_metadata=metadata)
        """
        if options_df is None or options_df.empty:
            self.logger.warning(f"Empty options data for {symbol} {trading_date}")
            return 0

        try:
            # Prepare records for batch insert
            records = []
            df = options_df.copy()

            # Normalize option_type column (handle both 'type' and 'option_type')
            if 'type' in df.columns and 'option_type' not in df.columns:
                df['option_type'] = df['type']
            elif 'option_type' not in df.columns:
                raise ValueError("Options data must have 'type' or 'option_type' column")

            # Normalize option_type values to lowercase
            df['option_type'] = df['option_type'].str.lower()

            for _, row in df.iterrows():
                try:
                    # Handle expiration date conversion
                    expiration = row['expiration']
                    if hasattr(expiration, 'strftime'):
                        expiration_str = expiration.strftime('%Y-%m-%d')
                    else:
                        expiration_str = str(expiration)

                    # Handle contract_symbol (may be missing)
                    contract_sym = row.get('contract_symbol') or row.get('contractID')

                    # Use provided underlying_price or try to get from row
                    underlying = underlying_price
                    if underlying is None and 'underlying_price' in row:
                        underlying = row['underlying_price']

                    # Serialize provider metadata to JSON if provided
                    metadata_json = json.dumps(provider_metadata) if provider_metadata else None

                    current_time = datetime.now().isoformat()

                    record = (
                        symbol.upper(),
                        trading_date,
                        float(row['strike']),
                        str(row['option_type']),
                        expiration_str,
                        float(row['bid']) if pd.notna(row.get('bid')) else None,
                        float(row['ask']) if pd.notna(row.get('ask')) else None,
                        float(row['last']) if pd.notna(row.get('last')) else None,
                        int(row['volume']) if pd.notna(row.get('volume')) else None,
                        int(row['open_interest']) if pd.notna(row.get('open_interest')) else None,
                        float(row['implied_volatility']) if pd.notna(row.get('implied_volatility')) else None,
                        float(row['delta']) if pd.notna(row.get('delta')) else None,
                        float(row['gamma']) if pd.notna(row.get('gamma')) else None,
                        float(row['theta']) if pd.notna(row.get('theta')) else None,
                        float(row['vega']) if pd.notna(row.get('vega')) else None,
                        float(row['rho']) if pd.notna(row.get('rho')) else None,
                        contract_sym,
                        float(underlying) if underlying is not None else None,
                        source,
                        current_time,  # cached_at
                        current_time,  # modified_at
                        float(data_quality_score),  # data_quality_score
                        metadata_json  # provider_metadata
                    )
                    records.append(record)

                except Exception as e:
                    self.logger.warning(f"Error preparing option record: {e}")
                    continue

            if not records:
                self.logger.warning(f"No valid records prepared for {symbol} {trading_date}")
                return 0

            # Bulk insert with write lock
            with self._write_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.executemany('''
                        INSERT OR REPLACE INTO raw_options_chain
                        (symbol, trading_date, strike, option_type, expiration,
                         bid, ask, last, volume, open_interest,
                         implied_volatility, delta, gamma, theta, vega, rho,
                         contract_symbol, underlying_price, source, cached_at,
                         modified_at, data_quality_score, provider_metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', records)
                    conn.commit()
                    rows_inserted = cursor.rowcount

            self.logger.info(
                f"Stored {rows_inserted} raw options for {symbol} {trading_date} "
                f"from {source} (quality: {data_quality_score:.2f})"
            )
            return rows_inserted

        except Exception as e:
            self.logger.error(f"Error storing raw options for {symbol} {trading_date}: {e}", exc_info=True)
            return 0

    def get_raw_options(self, symbol: str, trading_date: str,
                       source: str = None) -> Optional[pd.DataFrame]:
        """
        Retrieve raw options chain from database with file cache fallback.

        This implements the database-first architecture from Issue #373.
        Falls back to file cache if database is empty (for backward compatibility).

        Args:
            symbol: Stock symbol (e.g., "SPY")
            trading_date: Trading date in YYYY-MM-DD format
            source: Data source filter (None = any source)

        Returns:
            DataFrame with raw options data, or None if not found

        Example:
            >>> options = cache.get_raw_options("SPY", "2024-01-15")
            >>> if options is not None:
            ...     calls = options[options['option_type'] == 'call']
            ...     puts = options[options['option_type'] == 'put']
        """
        try:
            # Try database first (primary source as of Issue #373)
            query = """
                SELECT
                    strike, option_type, expiration,
                    bid, ask, last, volume, open_interest,
                    implied_volatility, delta, gamma, theta, vega, rho,
                    contract_symbol, underlying_price
                FROM raw_options_chain
                WHERE symbol = ? AND trading_date = ?
            """
            params = [symbol.upper(), trading_date]

            if source:
                query += " AND source = ?"
                params.append(source)

            query += " ORDER BY strike, option_type"

            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn, params=params)

            if not df.empty:
                self.logger.debug(f"Database hit: {len(df)} raw options for {symbol} {trading_date}")
                return df

            # Fallback to file cache (deprecated, for backward compatibility)
            self.logger.debug(f"Database miss for {symbol} {trading_date}, trying file cache fallback")
            file_cache_df = self._get_raw_options_from_file_cache(symbol, trading_date)

            if file_cache_df is not None:
                self.logger.warning(
                    f"Using deprecated file cache for {symbol} {trading_date}. "
                    f"Consider migrating to database with store_raw_options()"
                )
                return file_cache_df

            self.logger.debug(f"No raw options found for {symbol} {trading_date}")
            return None

        except Exception as e:
            self.logger.error(f"Error retrieving raw options for {symbol} {trading_date}: {e}")
            return None

    def _get_raw_options_from_file_cache(self, symbol: str, trading_date: str) -> Optional[pd.DataFrame]:
        """
        Fallback to file cache for raw options data (deprecated).

        This provides backward compatibility during migration to database storage.

        Args:
            symbol: Stock symbol
            trading_date: Trading date in YYYY-MM-DD format

        Returns:
            DataFrame from file cache, or None if not found
        """
        try:
            # Try common file cache locations
            file_cache_paths = [
                Path(f".cache/options/{symbol.upper()}/{trading_date}.pickle"),
                Path(f".cache/options/{symbol.upper()}/{trading_date}.json"),
            ]

            for cache_path in file_cache_paths:
                if cache_path.exists():
                    if cache_path.suffix == '.pickle':
                        df = pd.read_pickle(cache_path)
                    elif cache_path.suffix == '.json':
                        df = pd.read_json(cache_path)
                    else:
                        continue

                    if not df.empty:
                        self.logger.debug(f"File cache hit: {cache_path}")
                        return df

            return None

        except Exception as e:
            self.logger.warning(f"Error reading file cache: {e}")
            return None

    def delete_raw_options(self, symbol: str, trading_date: str = None, source: str = None) -> int:
        """
        Delete raw options data.

        Args:
            symbol: Stock symbol
            trading_date: Trading date (None = all dates)
            source: Data source filter (None = all sources)

        Returns:
            Number of rows deleted
        """
        try:
            query = "DELETE FROM raw_options_chain WHERE symbol = ?"
            params = [symbol.upper()]

            if trading_date:
                query += " AND trading_date = ?"
                params.append(trading_date)

            if source:
                query += " AND source = ?"
                params.append(source)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                deleted = cursor.rowcount
                conn.commit()

            self.logger.debug(f"Deleted {deleted} raw options for {symbol}")
            return deleted

        except Exception as e:
            self.logger.error(f"Error deleting raw options for {symbol}: {e}")
            return 0

    def get_options_stats(self) -> Dict[str, Any]:
        """
        Get raw options cache statistics.

        Returns:
            Dictionary with options metrics:
            - total_contracts: Total number of option contracts
            - unique_symbols: Number of unique underlying symbols
            - trading_dates: Number of unique trading dates
            - sources: Breakdown by data source
            - date_range: Min and max trading dates
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total contracts
                total = conn.execute("SELECT COUNT(*) FROM raw_options_chain").fetchone()[0]

                # Unique symbols
                unique_symbols = conn.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM raw_options_chain"
                ).fetchone()[0]

                # Unique trading dates
                unique_dates = conn.execute(
                    "SELECT COUNT(DISTINCT trading_date) FROM raw_options_chain"
                ).fetchone()[0]

                # Breakdown by source
                sources = {}
                for row in conn.execute(
                    "SELECT source, COUNT(*) as count FROM raw_options_chain GROUP BY source"
                ):
                    sources[row[0]] = row[1]

                # Date range
                date_range = conn.execute(
                    "SELECT MIN(trading_date), MAX(trading_date) FROM raw_options_chain"
                ).fetchone()

            return {
                "total_contracts": total,
                "unique_symbols": unique_symbols,
                "trading_dates": unique_dates,
                "sources": sources,
                "date_range": {
                    "min_date": date_range[0],
                    "max_date": date_range[1]
                } if date_range[0] else None
            }

        except Exception as e:
            self.logger.error(f"Error getting options stats: {e}")
            return {}
