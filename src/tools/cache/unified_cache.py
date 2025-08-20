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

    def _calculate_market_data_expiration(self, start_date: str, end_date: str) -> datetime:
        """
        Calculate appropriate expiration based on data recency.
        
        Historical data (>2 days old): Long expiration (10 years)
        Recent data (≤2 days): Short expiration (24 hours) for fresh updates
        """
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            today = datetime.now().date()
            
            # Historical data should never practically expire
            if end_dt.date() < today - timedelta(days=2):
                return datetime.now() + timedelta(days=365*10)  # 10 years
            
            # Recent data needs fresh updates
            else:
                return datetime.now() + timedelta(hours=24)
                
        except ValueError:
            # Fallback to short expiration if date parsing fails
            return datetime.now() + timedelta(hours=24)

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
        First tries exact cache key match, then searches for overlapping date ranges.
        """
        cache_key = self._get_market_cache_key(symbol, start, end, source)
        cache_path = self.market_dir / cache_key
        
        # First try exact match
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)

                # Check expiration using date-aware logic
                start_date = cache_data['metadata']['start_date']
                end_date = cache_data['metadata']['end_date']
                expected_expiry = self._calculate_market_data_expiration(start_date, end_date)
                
                # Use stored expiry if available, otherwise calculate
                if 'expires_at' in cache_data['metadata']:
                    expires_at = datetime.fromisoformat(cache_data['metadata']['expires_at'])
                else:
                    expires_at = expected_expiry
                
                if datetime.now() > expires_at:
                    self.logger.debug(f"Market data cache expired: {cache_key}")
                else:
                    # Convert to DataFrame
                    df = pd.DataFrame(cache_data['data'])
                    if not df.empty and 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                        df.set_index('date', inplace=True)
                        
                    self.logger.debug(f"Market data cache hit (exact): {cache_key}")
                    return df

            except Exception as e:
                self.logger.error(f"Error reading market cache {cache_key}: {e}")
        
        # If exact match failed, search for overlapping date ranges
        return self._search_overlapping_cache(symbol, start, end, source)

    def _search_overlapping_cache(self, symbol: str, start: str, end: str, source: str) -> Optional[pd.DataFrame]:
        """
        Search for cached data with overlapping date ranges.
        
        This handles cases where we request a broad date range that spans 
        multiple cached files (e.g., requesting 2024-01-01 to 2024-12-31
        but having quarterly cache files).
        """
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            
            # Look for cache files that might contain our date range
            pattern = f"{symbol}_*_{source}.json"
            matching_files = list(self.market_dir.glob(pattern))
            
            # Collect all overlapping data files
            overlapping_data = []
            
            for cache_file in matching_files:
                try:
                    # Parse filename to extract date range
                    name_parts = cache_file.stem.split('_')
                    if len(name_parts) < 4:
                        continue
                        
                    file_start_str = name_parts[1]
                    file_end_str = name_parts[2]
                    
                    # Skip if not proper date format
                    if len(file_start_str) != 10 or len(file_end_str) != 10:
                        continue
                    
                    file_start_date = datetime.strptime(file_start_str, "%Y-%m-%d")
                    file_end_date = datetime.strptime(file_end_str, "%Y-%m-%d")
                    
                    # Check if cached range overlaps with requested range
                    if file_start_date <= end_date and file_end_date >= start_date:
                        # Found overlapping range, load and filter data
                        with open(cache_file, 'r') as f:
                            cache_data = json.load(f)
                        
                        # Check expiration using date-aware logic
                        file_start_str = cache_data['metadata']['start_date']
                        file_end_str = cache_data['metadata']['end_date']
                        expected_expiry = self._calculate_market_data_expiration(file_start_str, file_end_str)
                        
                        # Use stored expiry if available, otherwise calculate
                        if 'expires_at' in cache_data['metadata']:
                            expires_at = datetime.fromisoformat(cache_data['metadata']['expires_at'])
                        else:
                            expires_at = expected_expiry
                        
                        if datetime.now() > expires_at:
                            continue
                        
                        # Convert to DataFrame  
                        df = pd.DataFrame(cache_data['data'])
                        if df.empty or 'date' not in df.columns:
                            continue
                            
                        df['date'] = pd.to_datetime(df['date'])
                        df.set_index('date', inplace=True)
                        
                        # Add to overlapping data list
                        overlapping_data.append((file_start_date, df, cache_file.name))
                            
                except (ValueError, KeyError) as e:
                    # Skip files with parsing errors
                    continue
            
            # Combine overlapping data if found
            if overlapping_data:
                # Sort by start date to ensure proper chronological order
                overlapping_data.sort(key=lambda x: x[0])
                
                # Combine all DataFrames
                combined_dfs = [df for _, df, _ in overlapping_data]
                combined_df = pd.concat(combined_dfs, axis=0)
                
                # Remove duplicates (in case of overlapping ranges) and sort
                combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
                combined_df = combined_df.sort_index()
                
                # Filter to requested date range
                mask = (combined_df.index >= start_date) & (combined_df.index <= end_date)
                filtered_df = combined_df[mask]
                
                if not filtered_df.empty:
                    file_names = [name for _, _, name in overlapping_data]
                    self.logger.debug(
                        f"Market data cache hit (combined): {', '.join(file_names)} "
                        f"-> {len(filtered_df)} records for {start} to {end}"
                    )
                    return filtered_df
                    
            self.logger.debug(f"No overlapping market data cache found for {symbol} {start} to {end}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error in overlapping cache search: {e}")
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

            # Create standardized cache structure with date-aware expiration
            expires_at = self._calculate_market_data_expiration(start, end)
            cache_data = {
                "metadata": {
                    "symbol": symbol,
                    "start_date": start,
                    "end_date": end,
                    "source": source,
                    "cached_at": datetime.now().isoformat(),
                    "expires_at": expires_at.isoformat()
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