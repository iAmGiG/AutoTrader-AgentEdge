"""
Simplified Google Search News Tool for Sentiment Agent
Direct access to Google Custom Search API with caching
"""

import pandas as pd
import logging
from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)

# Import the Google Search API implementation
from .google_search_api import GoogleSearchNewsTool


def fetch_google_news(
    symbol: str,
    start_date: str,
    end_date: str,
    max_results: int = 10
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
            max_results=max_results
        )

        if not results.empty:
            logger.info(
                f"Google Search found {len(results)} articles for {symbol} from {start_date} to {end_date}")
            # Ensure standard columns
            if 'Data_Source' not in results.columns:
                results['Data_Source'] = 'Google_Search'
            if 'sentiment_ready' not in results.columns:
                results['sentiment_ready'] = True
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
                "This is the primary news source for sentiment analysis."
)

# Export
__all__ = ['fetch_google_news', 'google_search_simple_tool']
