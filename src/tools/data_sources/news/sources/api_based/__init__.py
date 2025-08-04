"""
API-Based News Sources

News sources accessed through REST APIs, webhooks, or other API interfaces.
These sources typically require API keys and have rate limiting.
"""

from .google_search_news_tool import (
    search_google_historical_news,
    google_search_news_tool
)

__all__ = [
    'search_google_historical_news',
    'google_search_news_tool'
]