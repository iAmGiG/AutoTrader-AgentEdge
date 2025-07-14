"""
Finnhub data source tool for retrieving financial news headlines.

This tool provides access to the Finnhub API to fetch financial news headlines across
various categories including general business, economic, and market news. It focuses
on features available in the free tier API plan, specifically optimized for headline
retrieval for sentiment analysis.
"""

import requests
import logging
from config.config_loader import ConfigLoader
import pandas as pd
from typing import Optional, List
import os
from src.utils.date_utils import get_processed_date_range

# Define news categories supported by Finnhub
NEWS_CATEGORIES = {
    "general": "General news",
    "forex": "Forex news",
    "crypto": "Cryptocurrency news",
    "merger": "Merger & Acquisitions news",
    "business": "Business news",
    "technology": "Technology news",
    "economic": "Economic news",
    "stock": "Stock-specific news"
}


class FinnHubTool:
    """
    A tool for accessing financial news headlines from Finnhub.

    Designed to work with Finnhub's free tier API to retrieve news headlines
    across various categories (business, economic, forex, etc.). This tool
    focuses specifically on headline retrieval for sentiment analysis
    without requiring premium features.
    """

    def __init__(self, api_key: Optional[str] = None, verbose: bool = False):
        """
        Initialize the Finnhub data tool.

        Args:
            api_key: Optional API key for Finnhub. If not provided, will load from config.
            verbose: Whether to enable verbose logging.
        """
        # Set up logger
        self.logger = logging.getLogger(self.__class__.__name__)
        if verbose:
            logging.basicConfig(level=logging.INFO)

        # Load API key from environment if not provided
        if api_key is None:
            config_loader = ConfigLoader()
            api_key = os.getenv(
                "FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

            if not api_key:
                self.logger.error("No Finnhub API key provided in environment")
                raise ValueError(
                    "Finnhub API key is required. Set the FINNHUB_KEY environment variable."
                )

        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
        self.logger.info("Finnhub API client initialized successfully")

        # Store the news categories for reference
        self.news_categories = NEWS_CATEGORIES

    def fetch_news(self,
                   category: str = "general",
                   tickers: Optional[List[str]] = None,
                   count: int = 10) -> pd.DataFrame:
        """
        Fetch news headlines from Finnhub free tier API.

        Args:
            category: News category ('general', 'forex', 'crypto', 'business', 'economic', etc.)
            tickers: List of ticker symbols to filter by (optional, may not work in free tier)
            count: Number of news articles to retrieve

        Returns:
            DataFrame with news headlines optimized for sentiment analysis
        """
        try:
            # Validate the category
            if category not in self.news_categories:
                self.logger.warning(
                    f"Unknown category: {category}, defaulting to 'general'")
                category = "general"

            # Build the URL
            url = f"{self.base_url}/news"
            params = {
                "category": category,
                "token": self.api_key
            }

            # Note: The minId parameter can be used to paginate, but we'll just fetch latest
            # Note: Ticker filtering may not work in free tier

            self.logger.info(
                f"Fetching {category} news headlines from Finnhub...")

            # Make the request
            response = requests.get(url, params=params)

            if response.status_code == 200:
                news_data = response.json()

                if not news_data:
                    self.logger.warning(
                        f"No news data returned for category: {category}")
                    return pd.DataFrame()

                # Convert to DataFrame
                df = pd.DataFrame(news_data[:count])

                # Ensure we have the necessary columns for sentiment analysis
                if 'headline' not in df.columns:
                    self.logger.error(
                        "Response missing 'headline' field required for sentiment analysis")
                    return pd.DataFrame()

                # Rename columns to match expected format
                df = df.rename(columns={
                    'headline': 'title',
                    'summary': 'content',
                    'datetime': 'published_at'
                })

                # Convert datetime if present
                if 'published_at' in df.columns:
                    df['published_at'] = pd.to_datetime(
                        df['published_at'], unit='s')
                    df['published_at'] = df['published_at'].dt.strftime(
                        '%Y-%m-%d %H:%M:%S')

                # Add category column
                df['category'] = category

                # Ensure we have required columns
                if 'content' not in df.columns:
                    df['content'] = df['title']  # Use title as content if no summary

                self.logger.info(
                    f"Successfully fetched {len(df)} news headlines")
                return df

            else:
                self.logger.error(
                    f"Finnhub API error: {response.status_code} - {response.text}")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Error fetching news from Finnhub: {e}")
            return pd.DataFrame()

    def fetch_company_news(self,
                           symbol: str,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch company-specific news headlines from Finnhub.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD format or relative like '-7d')
            end_date: End date (YYYY-MM-DD format or 'today')

        Returns:
            DataFrame with company news headlines
        """
        try:
            # Process date parameters
            start_date, end_date = get_processed_date_range(
                start_date, end_date)

            # Build the URL for company news
            url = f"{self.base_url}/company-news"
            params = {
                "symbol": symbol.upper(),
                "from": start_date,
                "to": end_date,
                "token": self.api_key
            }

            self.logger.info(
                f"Fetching news for {symbol} from {start_date} to {end_date}...")

            # Make the request
            response = requests.get(url, params=params)

            if response.status_code == 200:
                news_data = response.json()

                if not news_data:
                    self.logger.warning(f"No news data returned for {symbol}")
                    return pd.DataFrame()

                # Convert to DataFrame
                df = pd.DataFrame(news_data)

                # Rename columns to match expected format
                df = df.rename(columns={
                    'headline': 'title',
                    'summary': 'content',
                    'datetime': 'published_at'
                })

                # Convert datetime
                if 'published_at' in df.columns:
                    df['published_at'] = pd.to_datetime(
                        df['published_at'], unit='s')
                    df['published_at'] = df['published_at'].dt.strftime(
                        '%Y-%m-%d %H:%M:%S')

                # Add metadata
                df['symbol'] = symbol.upper()
                df['category'] = 'company'

                # Ensure we have content
                if 'content' not in df.columns:
                    df['content'] = df['title']

                self.logger.info(
                    f"Successfully fetched {len(df)} news items for {symbol}")
                return df

            else:
                self.logger.error(
                    f"Finnhub API error: {response.status_code} - {response.text}")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(
                f"Error fetching company news from Finnhub: {e}")
            return pd.DataFrame()

    def fetch_market_news(self, category: str = "general") -> pd.DataFrame:
        """
        Convenience method that wraps fetch_news for backward compatibility.

        Args:
            category: News category to fetch

        Returns:
            DataFrame with market news headlines
        """
        return self.fetch_news(category=category, count=20)

    def test_connection(self) -> bool:
        """
        Test the Finnhub API connection.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to fetch a small amount of general news
            df = self.fetch_news(category="general", count=1)
            return not df.empty
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False


if __name__ == "__main__":
    # Example usage
    tool = FinnHubTool()

    # Test connection
    print("Testing Finnhub connection...")
    if tool.test_connection():
        print("✓ Connection successful!")
    else:
        print("✗ Connection failed!")

    # Fetch general news
    print("\nFetching general market news...")
    general_news = tool.fetch_news(category="general", count=5)
    if not general_news.empty:
        print(f"Found {len(general_news)} articles")
        print(general_news[['title', 'published_at']].head())
    else:
        print("No general news found")

    # Fetch business news
    print("\nFetching business news...")
    business_news = tool.fetch_news(category="business", count=5)
    if not business_news.empty:
        print(f"Found {len(business_news)} articles")
        print(business_news[['title', 'published_at']].head())
    else:
        print("No business news found")

    # Fetch company-specific news
    print("\nFetching Apple news...")
    apple_news = tool.fetch_company_news("AAPL", "-7d", "today")
    if not apple_news.empty:
        print(f"Found {len(apple_news)} articles")
        print(apple_news[['title', 'published_at']].head())
    else:
        print("No Apple news found")

    # Print available categories
    print("\nAvailable news categories:")
    for key, description in tool.news_categories.items():
        print(f"  - {key}: {description}")
