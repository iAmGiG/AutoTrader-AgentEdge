"""
News data sources package for V0-V4 framework.

Simple structure:
- google_search_simple.py: Main interface tool (used by tools.py)
- google_search_api.py: Google Custom Search API implementation

This package provides Google Search-based financial news for sentiment analysis.
"""

from .google_search_simple import fetch_google_news, google_search_simple_tool

__all__ = ["fetch_google_news", "google_search_simple_tool"]
