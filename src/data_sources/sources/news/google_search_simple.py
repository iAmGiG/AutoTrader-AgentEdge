"""
Simplified Google Search News Tool for Sentiment Agent
Direct access to Google Custom Search API with caching and smart sampling
"""

import logging

import pandas as pd
from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)

# Import the Google Search API implementation
from .google_search_api import GoogleSearchNewsTool


def fetch_google_news(
    symbol: str, start_date: str, end_date: str, max_results: int = 10
) -> pd.DataFrame:
    """
    Fetch news using Google Custom Search API with caching.

    This is a simplified interface that directly uses Google Search
    for financial news from premium sources (WSJ, Bloomberg, Barrons, etc.)

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        max_results: Maximum number of results to return

    Returns:
        DataFrame with columns: title, summary, url, published_date, source
        Returns empty DataFrame if no results found
    """
    try:
        # Initialize the Google Search tool
        google_tool = GoogleSearchNewsTool()

        # Check if API credentials are configured
        if not google_tool.api_key or not google_tool.search_engine_id:
            logger.warning("Google Search API credentials not configured")
            return pd.DataFrame()

        # Fetch news using the existing tool's search method
        results = google_tool.search_historical_news(
            ticker=symbol,  # Changed from 'symbol' to 'ticker'
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
        )

        if not results.empty:
            logger.info(
                f"Google Search found {len(results)} articles for {symbol} from {start_date} to {end_date}"
            )
            # Ensure standard columns
            if "Data_Source" not in results.columns:
                results["Data_Source"] = "Google_Search"
            if "sentiment_ready" not in results.columns:
                results["sentiment_ready"] = True
        else:
            logger.info(f"No news found for {symbol} from {start_date} to {end_date}")

        return results

    except Exception as e:
        logger.error(f"Error fetching Google news: {e}")
        return pd.DataFrame()


# Create the FunctionTool for AutoGen integration
google_search_simple_tool = FunctionTool(
    func=fetch_google_news,
    name="fetch_google_news",
    description="Fetch financial news using Google Custom Search API. "
    "Searches premium financial sources (WSJ, Bloomberg, Barrons, Reuters, CNBC) "
    "with automatic caching. Returns news articles with title, summary, URL, and date. "
    "This is the primary news source for sentiment analysis.",
)

from datetime import datetime

# Smart sampling with NewsGovernor

# Global news governor (optional, for smart sampling)
_news_governor = None


def set_news_governor(governor):
    """Set a global news governor for smart sampling."""
    global _news_governor
    _news_governor = governor
    if governor is not None:
        logger.info(f"📰 NewsGovernor enabled: {governor.sampling_strategy} sampling")
    else:
        logger.info("📰 NewsGovernor disabled")


def fetch_google_news_smart(
    symbol: str, start_date: str, end_date: str, max_results: int = 10
) -> pd.DataFrame:
    """
    Fetch news with optional smart sampling via NewsGovernor.

    If a NewsGovernor is set globally, this will use smart sampling.
    Otherwise, it falls back to direct API calls.
    """
    global _news_governor

    if _news_governor is not None:
        # Use smart sampling
        try:
            target_date = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            target_date = datetime.now()

        # Define fetch function for governor
        def actual_fetch(symbol, start_date, end_date):
            return fetch_google_news(symbol, start_date, end_date, max_results)

        # Get news through governor
        news_data, source = _news_governor.get_news_for_date(target_date, symbol, actual_fetch)

        logger.debug(f"📰 Smart sampling: {len(news_data)} articles ({source})")
        return news_data

    else:
        # Direct API call (original behavior)
        return fetch_google_news(symbol, start_date, end_date, max_results)


# Create smart sampling tool
google_search_smart_tool = FunctionTool(
    func=fetch_google_news_smart,
    name="fetch_google_news",  # Same name for compatibility
    description="Fetch financial news using Google Custom Search API with smart sampling. "
    "Automatically reduces API quota usage while maintaining data quality. "
    "Searches premium financial sources (WSJ, Bloomberg, Barrons, Reuters, CNBC) "
    "with intelligent caching. Returns news articles with title, summary, URL, and date.",
)

# Export both versions
__all__ = [
    "fetch_google_news",
    "fetch_google_news_smart",
    "google_search_simple_tool",
    "google_search_smart_tool",
    "set_news_governor",
]
