"""Cache utilities for reducing API calls."""

from .cache_adapter import CacheAdapter, cache_adapter
from .news_cache import NewsCache
from .sqlite_cache import TradingCacheManager

__all__ = [
    "NewsCache",
    "TradingCacheManager",  # SQLite-based cache (production)
    "CacheAdapter",
    "cache_adapter",
]
