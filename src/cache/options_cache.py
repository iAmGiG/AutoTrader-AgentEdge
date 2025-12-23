"""
Options Cache Mixin for TradingCacheManager.

Issue #510: Extracted from sqlite_cache.py for modularity.
Contains raw options chain storage and retrieval methods.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


class OptionsCacheMixin:
    """
    Mixin providing options cache functionality.

    Requires:
        - self.db_path: Path to SQLite database
        - self._write_lock: Threading lock for write operations
        - self.logger: Logger instance
    """

    def store_raw_options(
        self,
        symbol: str,
        trading_date: str,
        options_df: pd.DataFrame,
        underlying_price: float = None,
        source: str = "polygon",
        data_quality_score: float = 1.0,
        provider_metadata: dict = None,
    ) -> int:
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
        """
        if options_df is None or options_df.empty:
            self.logger.warning(f"Empty options data for {symbol} {trading_date}")
            return 0

        try:
            records = []
            df = options_df.copy()

            # Normalize option_type column
            if "type" in df.columns and "option_type" not in df.columns:
                df["option_type"] = df["type"]
            elif "option_type" not in df.columns:
                raise ValueError("Options data must have 'type' or 'option_type' column")

            df["option_type"] = df["option_type"].str.lower()

            for _, row in df.iterrows():
                try:
                    expiration = row["expiration"]
                    if hasattr(expiration, "strftime"):
                        expiration_str = expiration.strftime("%Y-%m-%d")
                    else:
                        expiration_str = str(expiration)

                    contract_sym = row.get("contract_symbol") or row.get("contractID")

                    underlying = underlying_price
                    if underlying is None and "underlying_price" in row:
                        underlying = row["underlying_price"]

                    metadata_json = json.dumps(provider_metadata) if provider_metadata else None
                    current_time = now_iso()

                    record = (
                        symbol.upper(),
                        trading_date,
                        float(row["strike"]),
                        str(row["option_type"]),
                        expiration_str,
                        float(row["bid"]) if pd.notna(row.get("bid")) else None,
                        float(row["ask"]) if pd.notna(row.get("ask")) else None,
                        float(row["last"]) if pd.notna(row.get("last")) else None,
                        int(row["volume"]) if pd.notna(row.get("volume")) else None,
                        int(row["open_interest"]) if pd.notna(row.get("open_interest")) else None,
                        (
                            float(row["implied_volatility"])
                            if pd.notna(row.get("implied_volatility"))
                            else None
                        ),
                        float(row["delta"]) if pd.notna(row.get("delta")) else None,
                        float(row["gamma"]) if pd.notna(row.get("gamma")) else None,
                        float(row["theta"]) if pd.notna(row.get("theta")) else None,
                        float(row["vega"]) if pd.notna(row.get("vega")) else None,
                        float(row["rho"]) if pd.notna(row.get("rho")) else None,
                        contract_sym,
                        float(underlying) if underlying is not None else None,
                        source,
                        current_time,
                        current_time,
                        float(data_quality_score),
                        metadata_json,
                    )
                    records.append(record)

                except Exception as e:
                    self.logger.warning(f"Error preparing option record: {e}")
                    continue

            if not records:
                self.logger.warning(f"No valid records prepared for {symbol} {trading_date}")
                return 0

            with self._write_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.executemany(
                        """
                        INSERT OR REPLACE INTO raw_options_chain
                        (symbol, trading_date, strike, option_type, expiration,
                         bid, ask, last, volume, open_interest,
                         implied_volatility, delta, gamma, theta, vega, rho,
                         contract_symbol, underlying_price, source, cached_at,
                         modified_at, data_quality_score, provider_metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        records,
                    )
                    conn.commit()
                    rows_inserted = cursor.rowcount

            self.logger.info(
                f"Stored {rows_inserted} raw options for {symbol} {trading_date} "
                f"from {source} (quality: {data_quality_score:.2f})"
            )
            return rows_inserted

        except Exception as e:
            self.logger.error(
                f"Error storing raw options for {symbol} {trading_date}: {e}", exc_info=True
            )
            return 0

    def get_raw_options(
        self, symbol: str, trading_date: str, source: str = None
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve raw options chain from database with file cache fallback.

        Args:
            symbol: Stock symbol (e.g., "SPY")
            trading_date: Trading date in YYYY-MM-DD format
            source: Data source filter (None = any source)

        Returns:
            DataFrame with raw options data, or None if not found
        """
        try:
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
                self.logger.debug(
                    f"Database hit: {len(df)} raw options for {symbol} {trading_date}"
                )
                return df

            # Fallback to file cache (deprecated)
            self.logger.debug(
                f"Database miss for {symbol} {trading_date}, trying file cache fallback"
            )
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

    def _get_raw_options_from_file_cache(
        self, symbol: str, trading_date: str
    ) -> Optional[pd.DataFrame]:
        """Fallback to file cache for raw options data (deprecated)."""
        try:
            file_cache_paths = [
                Path(f".cache/options/{symbol.upper()}/{trading_date}.pickle"),
                Path(f".cache/options/{symbol.upper()}/{trading_date}.json"),
            ]

            for cache_path in file_cache_paths:
                if cache_path.exists():
                    if cache_path.suffix == ".pickle":
                        df = pd.read_pickle(cache_path)  # nosec B301
                    elif cache_path.suffix == ".json":
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
            Dictionary with options metrics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM raw_options_chain").fetchone()[0]

                unique_symbols = conn.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM raw_options_chain"
                ).fetchone()[0]

                unique_dates = conn.execute(
                    "SELECT COUNT(DISTINCT trading_date) FROM raw_options_chain"
                ).fetchone()[0]

                sources = {}
                for row in conn.execute(
                    "SELECT source, COUNT(*) as count FROM raw_options_chain GROUP BY source"
                ):
                    sources[row[0]] = row[1]

                date_range = conn.execute(
                    "SELECT MIN(trading_date), MAX(trading_date) FROM raw_options_chain"
                ).fetchone()

            return {
                "total_contracts": total,
                "unique_symbols": unique_symbols,
                "trading_dates": unique_dates,
                "sources": sources,
                "date_range": (
                    {"min_date": date_range[0], "max_date": date_range[1]}
                    if date_range[0]
                    else None
                ),
            }

        except Exception as e:
            self.logger.error(f"Error getting options stats: {e}")
            return {}
