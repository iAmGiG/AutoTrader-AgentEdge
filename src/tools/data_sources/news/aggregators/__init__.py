"""
News Aggregators Module

Unifying tools that combine multiple news sources into coherent interfaces.
These tools abstract away the complexity of managing multiple data sources.
"""

from .hybrid_historical_news_tool import (
    fetch_hybrid_historical_news,
    hybrid_historical_news_tool
)

__all__ = [
    'fetch_hybrid_historical_news',
    'hybrid_historical_news_tool'
]