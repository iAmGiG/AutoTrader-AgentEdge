"""Cache utilities for reducing API calls."""

from .market_data_cache import MarketDataCache
from .news_cache import NewsCache
from .unified_cache import UnifiedCacheManager
from .sqlite_cache import TradingCacheManager
from .cache_adapter import CacheAdapter, cache_adapter

__all__ = [
    'MarketDataCache',
    'NewsCache',
    'UnifiedCacheManager',
    'TradingCacheManager',  # New SQLite-based cache (recommended)
    'CacheAdapter',
    'cache_adapter'
]
