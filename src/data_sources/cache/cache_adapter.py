"""
Cache adapter to route all market data through TradingCacheManager (SQLite).

Simple approach: Instead of complex consolidation, just ensure all tools
use the same SQLite cache system with set-based union operations.

Updated to use TradingCacheManager for better performance and futures support.
"""

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from .sqlite_cache import TradingCacheManager


class CacheAdapter:
    """
    Adapter to ensure all market data tools use SQLite caching.

    Provides a single interface that:
    1. Checks existing cache (SQLite database)
    2. Routes all new data through TradingCacheManager
    3. Handles set-based union operations for overlapping data

    Note: UnifiedCacheManager (file-based) is deprecated in favor of SQLite.
    """

    def __init__(self):
        self.cache = TradingCacheManager()  # SQLite-based cache
        self.legacy_locations = [Path(".cache/polygon/prices"), Path(".cache/market_data")]

    def get_market_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        source: str = "any",
        timeframe: str = "1Day",
    ) -> Optional[pd.DataFrame]:
        """
        Get market data from SQLite cache, falling back to legacy file cache.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            source: Data source preference ("any", "alpaca", "polygon", "alpha_vantage", "auto")
            timeframe: Bar timeframe (e.g., "1Min", "5Min", "1Hour", "1Day")

        Returns:
            DataFrame with OHLCV data, or None if not found
        """
        # Combine source with timeframe to create unique cache key
        # This ensures different timeframes are cached separately
        # Must match the logic in set_market_data() for consistency
        if source in ("any", "auto"):
            # No source filter for generic requests
            cache_source = None if timeframe == "1Day" else f"any_{timeframe}"
        else:
            # Specific source: use {source}_{timeframe} for non-daily, just source for daily
            cache_source = f"{source}_{timeframe}" if timeframe != "1Day" else source

        # First try SQLite cache
        data = self.cache.get(symbol, start_date, end_date, source=cache_source)
        if data is not None:
            return data

        # Fallback: check legacy file-based locations (for migration)
        # Note: Legacy cache doesn't support timeframes, only check for daily data
        if timeframe == "1Day":
            for location in self.legacy_locations:
                if not location.exists():
                    continue

                legacy_data = self._check_legacy_cache(location, symbol, start_date, end_date)
                if legacy_data is not None:
                    # Found in legacy cache - migrate to SQLite cache
                    detected_source = source if source not in ("any", "auto") else "migrated"
                    self.cache.set(symbol, legacy_data, source=detected_source)
                    return legacy_data

        return None

    def set_market_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        source: str,
        data: pd.DataFrame,
        timeframe: str = "1Day",
    ) -> None:
        """
        Store market data using SQLite cache (with set-based union logic).

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            source: Data source ("alpaca", "polygon", "alpha_vantage", "auto")
            data: OHLCV DataFrame
            timeframe: Bar timeframe (e.g., "1Min", "5Min", "1Hour", "1Day")

        Note: TradingCacheManager handles duplicates with INSERT OR REPLACE,
        so we don't need explicit union logic. The database will automatically
        prefer the most recent cached_at timestamp.
        """
        if data is None or data.empty:
            return

        # Combine source with timeframe to create unique cache key
        cache_source = f"{source}_{timeframe}" if timeframe != "1Day" else source

        # TradingCacheManager.set() extracts date range from DataFrame,
        # no need to pass start/end explicitly
        self.cache.set(symbol, data, source=cache_source)

    def _check_legacy_cache(
        self, cache_dir: Path, symbol: str, start_date: str, end_date: str
    ) -> Optional[pd.DataFrame]:
        """Check legacy cache locations for matching data."""
        if not cache_dir.exists():
            return None

        # Try different filename patterns
        patterns = [
            f"{symbol}_{start_date}_{end_date}_*.json",
            f"{symbol}_{start_date}_to_{end_date}_*.json",
        ]

        for pattern in patterns:
            for file_path in cache_dir.glob(pattern):
                try:
                    data = self._load_legacy_file(file_path)
                    if data is not None:
                        return data
                except Exception as e:
                    print(f"Warning: Error loading legacy cache file {file_path}: {e}")

        return None

    def _load_legacy_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Load data from legacy cache file format."""
        try:
            with open(file_path, "r") as f:
                cache_data = json.load(f)

            # Handle different legacy formats
            if isinstance(cache_data, dict):
                if "data" in cache_data:
                    data = cache_data["data"]
                    if isinstance(data, dict) and "values" in data:
                        # New format
                        df = pd.DataFrame(data["values"])
                        if "index" in data and not df.empty:
                            df.index = pd.to_datetime(data["index"])
                        return df
                    elif isinstance(data, list):
                        # List format
                        return pd.DataFrame(data)
            elif isinstance(cache_data, list):
                # Direct list format
                return pd.DataFrame(cache_data)

        except Exception as e:
            print(f"Error loading legacy file {file_path}: {e}")

        return None

    def _union_data(self, existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        """
        Perform set-based union of two DataFrames.

        Combines data and removes duplicates by index (date).
        Prefers newer data for overlapping dates.
        """
        if existing.empty:
            return new
        if new.empty:
            return existing

        # Combine DataFrames
        combined = pd.concat([existing, new])

        # Remove duplicates, keeping last occurrence (newer data)
        combined = combined[~combined.index.duplicated(keep="last")]

        # Sort by index
        combined = combined.sort_index()

        return combined

    def clear_legacy_caches(self) -> None:
        """
        Optional: Clear legacy cache locations after migration.
        Use with caution - only after confirming SQLite cache works.
        """
        print("⚠️  This will permanently delete legacy JSON cache files!")
        print("   Make sure you've backed up and migrated to SQLite first!")
        if input("Continue? (y/N): ").lower().startswith("y"):
            count = 0
            for location in self.legacy_locations:
                if location.exists():
                    for file in location.glob("*.json"):
                        file.unlink()
                        count += 1
                    print(f"Cleared {count} files from {location}")
            print(f"✅ Deleted {count} legacy cache files")

    def get_cache_stats(self):
        """
        Get statistics about the cache.

        Returns:
            Dictionary with cache statistics from TradingCacheManager
        """
        return self.cache.get_stats()

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries deleted
        """
        return self.cache.cleanup_expired()


# Global instance for easy access
cache_adapter = CacheAdapter()
