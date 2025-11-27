"""Cache utilities for reducing API calls."""

from .cache_adapter import CacheAdapter, cache_adapter
from .market_data_cache import MarketDataCache
from .news_cache import NewsCache
from .sqlite_cache import TradingCacheManager
from .unified_cache import UnifiedCacheManager

__all__ = [
    "MarketDataCache",
    "NewsCache",
    "UnifiedCacheManager",
    "TradingCacheManager",  # New SQLite-based cache (recommended)
    "CacheAdapter",
    "cache_adapter",
]
