"""
News data sources package.

Reorganized modular structure:
- aggregators/: Unifying tools that combine multiple news sources
- sources/: Individual data source implementations (API-based and scrapers)
- utils/: Support utilities (quota managers, batch operations, etc.)

For most use cases, import from aggregators for unified interfaces.
"""

# Import primary aggregator for common use
from .aggregators.hybrid_historical_news_tool import (
    fetch_hybrid_historical_news,
    hybrid_historical_news_tool
)

# Import legacy unified tool for backward compatibility
from .aggregators.legacy.unified_news_tool import (
    UnifiedNewsController,
    fetch_unified_news,
    fetch_unified_news_async
)

__all__ = [
    "fetch_hybrid_historical_news",
    "hybrid_historical_news_tool",
    "UnifiedNewsController", 
    "fetch_unified_news",
    "fetch_unified_news_async"
]