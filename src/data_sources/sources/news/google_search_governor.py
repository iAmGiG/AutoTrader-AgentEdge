"""
News Governor-Aware Google Search Tool

Replaces the standard Google Search tool with smart sampling capabilities.
This integrates NewsGovernor directly into the tool layer for transparent
quota management without requiring agent modifications.
"""

import logging
from typing import Optional

import pandas as pd

from src.tools.data_sources.news.google_search_simple import fetch_google_news
from src.tools.news_governor import NewsGovernor, create_balanced_governor
from src.utils.date_utils import get_datetime_now, parse_date_string

logger = logging.getLogger(__name__)

# Global news governor instance (shared across all tool calls)
_news_governor: Optional[NewsGovernor] = None


def initialize_news_governor(governor: NewsGovernor = None):
    """Initialize the global news governor for smart sampling."""
    global _news_governor
    _news_governor = governor or create_balanced_governor()
    logger.info(f"🎯 Initialized news governor: {_news_governor.sampling_strategy} sampling")


def get_news_governor() -> NewsGovernor:
    """Get the current news governor, initializing if needed."""
    global _news_governor
    if _news_governor is None:
        initialize_news_governor()
    return _news_governor


def fetch_google_news_with_governor(
    symbol: str, start_date: str, end_date: str, max_results: int = 10
) -> pd.DataFrame:
    """
    Fetch news using smart sampling via NewsGovernor.

    This function replaces the standard fetch_google_news in agent tools
    to provide transparent quota management and intelligent caching.

    Args:
        symbol: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        max_results: Maximum results to return

    Returns:
        DataFrame with news articles (may be from cache)
    """
    governor = get_news_governor()

    # Convert string date to datetime for governor
    try:
        target_date = parse_date_string(start_date)
    except ValueError:
        logger.warning(f"Invalid date format: {start_date}, using current date")
        target_date = get_datetime_now()

    # Define the actual fetch function for governor
    def actual_fetch(symbol, start_date, end_date):
        return fetch_google_news(symbol, start_date, end_date, max_results)

    # Get news through governor (with smart sampling)
    news_data, source = governor.get_news_for_date(target_date, symbol, actual_fetch)

    # Log the source for transparency
    if source.startswith("fresh"):
        logger.info(f"📰 Fresh news: {len(news_data)} articles for {symbol}")
    elif source.startswith("cached"):
        logger.info(f"📰 Cached news: {len(news_data)} articles for {symbol} ({source})")
    else:
        logger.info(f"📰 News source: {source} for {symbol}")

    return news_data


def get_quota_status():
    """Get current quota status from the news governor."""
    governor = get_news_governor()
    return governor.get_quota_status()


def print_quota_summary():
    """Print a summary of news governor performance."""
    governor = get_news_governor()
    governor.print_quota_summary()


# Convenience function to reset governor (useful for testing)


def reset_news_governor():
    """Reset the global news governor (useful for testing)."""
    global _news_governor
    _news_governor = None
