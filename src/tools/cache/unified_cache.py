"""
Unified cache manager for V0-V4 framework.

Provides standardized caching interface for all data sources, ensuring consistent
data formats regardless of source (Polygon.io, Alpha Vantage, Google Search).
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
from datetime import datetime, timedelta
import logging


class UnifiedCacheManager:
    """
    Unified cache manager for market data and news.
    
    Provides consistent caching interface regardless of data source.
    All OHLCV data stored in same format whether from Polygon or Alpha Vantage.
    """

    def __init__(self, base_dir: str = ".cache"):
        """Initialize unified cache manager."""
        self.base_dir = Path(base_dir)
        self.market_dir = self.base_dir / "market_data"
        self.news_dir = self.base_dir / "news"
        self.metadata_dir = self.base_dir / "metadata"
        
        # Create directories
        for dir_path in [self.market_dir, self.news_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_market_cache_key(self, symbol: str, start: str, end: str, source: str) -> str:
        """Generate standardized cache key for market data."""
        return f"{symbol}_{start}_{end}_{source}.json"

    def _get_news_cache_key(self, query: str, start: str, end: str, source: str = "google_search") -> str:
        """Generate standardized cache key for news data."""
        # Clean query for filename
        clean_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).strip()
        clean_query = clean_query.replace(' ', '_')[:50]  # Limit length
        return f"{clean_query}_{start}_{end}_{source}.json"

    def get_market_data(self, symbol: str, start: str, end: str, source: str) -> Optional[pd.DataFrame]:
        """
        Get cached market data.
        
        Returns standardized OHLCV data regardless of original source.
        """
        cache_key = self._get_market_cache_key(symbol, start, end, source)
        cache_path = self.market_dir / cache_key
        
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)

            # Check expiration (24 hours for market data)
            cached_time = datetime.fromisoformat(cache_data['metadata']['cached_at'])
            if datetime.now() - cached_time > timedelta(hours=24):
                self.logger.debug(f"Market data cache expired: {cache_key}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(cache_data['data'])
            if not df.empty and 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
            self.logger.debug(f"Market data cache hit: {cache_key}")
            return df

        except Exception as e:
            self.logger.error(f"Error reading market cache {cache_key}: {e}")
            return None

    def set_market_data(self, symbol: str, start: str, end: str, source: str, data: pd.DataFrame):
        """
        Cache market data in standardized format.
        
        Stores OHLCV data consistently regardless of source.
        """
        if data.empty:
            return

        try:
            # Standardize DataFrame format
            df = data.copy()
            
            # Ensure standard columns exist
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    # Try common variants
                    for variant in [col.title(), col.upper()]:
                        if variant in df.columns:
                            df[col] = df[variant]
                            break
                    else:
                        self.logger.warning(f"Missing column {col} in market data")
                        return

            # Reset index to get date column
            if isinstance(df.index, pd.DatetimeIndex):
                df.reset_index(inplace=True)
                df.rename(columns={'index': 'date'}, inplace=True)
            elif 'date' not in df.columns and 'Date' in df.columns:
                df.rename(columns={'Date': 'date'}, inplace=True)

            # Ensure date is string for JSON serialization
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # Create standardized cache structure
            cache_data = {
                "metadata": {
                    "symbol": symbol,
                    "start_date": start,
                    "end_date": end,
                    "source": source,
                    "cached_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
                },
                "data": df[['date', 'open', 'high', 'low', 'close', 'volume']].to_dict('records')
            }

            cache_key = self._get_market_cache_key(symbol, start, end, source)
            cache_path = self.market_dir / cache_key

            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)

            self.logger.debug(f"Market data cached: {cache_key}")

        except Exception as e:
            self.logger.error(f"Error caching market data: {e}")

    def get_news(self, query: str, start: str, end: str, source: str = "google_search") -> Optional[pd.DataFrame]:
        """Get cached news data."""
        cache_key = self._get_news_cache_key(query, start, end, source)
        cache_path = self.news_dir / source / f"{cache_key}"
        
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)

            # Check expiration (7 days for news)
            cached_time = datetime.fromisoformat(cache_data['metadata']['cached_at'])
            if datetime.now() - cached_time > timedelta(days=7):
                self.logger.debug(f"News cache expired: {cache_key}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(cache_data['data'])
            self.logger.debug(f"News cache hit: {cache_key}")
            return df

        except Exception as e:
            self.logger.error(f"Error reading news cache {cache_key}: {e}")
            return None

    def set_news(self, query: str, start: str, end: str, data: pd.DataFrame, source: str = "google_search"):
        """Cache news data in standardized format."""
        if data.empty:
            return

        try:
            # Create source directory
            source_dir = self.news_dir / source
            source_dir.mkdir(exist_ok=True)

            cache_data = {
                "metadata": {
                    "query": query,
                    "start_date": start,
                    "end_date": end,
                    "source": source,
                    "cached_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(days=7)).isoformat()
                },
                "data": data.to_dict('records')
            }

            cache_key = self._get_news_cache_key(query, start, end, source)
            cache_path = source_dir / cache_key

            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)

            self.logger.debug(f"News data cached: {cache_key}")

        except Exception as e:
            self.logger.error(f"Error caching news data: {e}")

    def cleanup_expired(self):
        """Remove expired cache files."""
        now = datetime.now()
        cleaned_count = 0

        # Clean market data (24h expiry)
        for cache_file in self.market_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                expires_at = datetime.fromisoformat(cache_data['metadata']['expires_at'])
                if now > expires_at:
                    cache_file.unlink()
                    cleaned_count += 1
                    
            except Exception as e:
                self.logger.warning(f"Error checking expiry for {cache_file}: {e}")

        # Clean news data (7d expiry)
        for cache_file in self.news_dir.rglob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                expires_at = datetime.fromisoformat(cache_data['metadata']['expires_at'])
                if now > expires_at:
                    cache_file.unlink()
                    cleaned_count += 1
                    
            except Exception as e:
                self.logger.warning(f"Error checking expiry for {cache_file}: {e}")

        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} expired cache files")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        market_files = list(self.market_dir.glob("*.json"))
        news_files = list(self.news_dir.rglob("*.json"))
        
        total_size = sum(f.stat().st_size for f in market_files + news_files)
        
        return {
            "market_data_files": len(market_files),
            "news_files": len(news_files),
            "total_files": len(market_files) + len(news_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dirs": {
                "market_data": str(self.market_dir),
                "news": str(self.news_dir),
                "metadata": str(self.metadata_dir)
            }
        }