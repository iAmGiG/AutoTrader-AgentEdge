"""
Tool for fetching news data from Alpha Vantage API.

This module specializes in retrieving news and sentiment data from Alpha Vantage.
It's part of the specialized data sources organization that separates different
types of financial data.
"""

from typing import Dict, Any, Optional, List
import logging
import requests
import pandas as pd
import os


class AlphaVantageNewsTool:
    """
    Tool for retrieving news and sentiment data from Alpha Vantage API.

    This class focuses on news-specific data including:
    - Company news
    - Sentiment analysis
    """

    def __init__(self):
        # Load API key from environment
        self.api_key = os.getenv("ALPHA_VANTAGE_KEY")

        if not self.api_key:
            logging.warning("Alpha Vantage API key not found in config.")

        self.base_url = "https://www.alphavantage.co/query"
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_news_sentiment(self, symbol: Optional[str] = None, topics: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch news sentiment data from Alpha Vantage.

        Args:
            symbol: Optional stock ticker symbol to filter news by
            topics: Optional topics to filter by (comma separated)

        Returns:
            DataFrame with news and sentiment data
        """
        try:
            params = {
                "function": "NEWS_SENTIMENT",
                "apikey": self.api_key,
            }

            if symbol:
                params["tickers"] = symbol
            if topics:
                params["topics"] = topics

            response = requests.get(self.base_url, params=params)

            if response.status_code != 200:
                self.logger.error(
                    f"Alpha Vantage API error: {response.status_code} - {response.text}")
                return pd.DataFrame()

            data = response.json()

            if "Error Message" in data:
                self.logger.error(
                    f"Alpha Vantage API error: {data['Error Message']}")
                return pd.DataFrame()

            if "feed" not in data:
                self.logger.warning(
                    "No news feed found in Alpha Vantage response")
                return pd.DataFrame()

            # Extract feed items and convert to DataFrame
            news_items = data.get("feed", [])

            # Convert news items to DataFrame
            news_df = pd.DataFrame(news_items)

            # Add timestamp column
            if "time_published" in news_df.columns:
                news_df["timestamp"] = pd.to_datetime(
                    news_df["time_published"], format="%Y%m%dT%H%M%S")

            return news_df

        except Exception as e:
            self.logger.error(f"Error fetching news sentiment: {e}")
            return pd.DataFrame()

    def fetch_top_gainers_losers(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch top gainers and losers in the market.

        Returns:
            Dictionary with top gainers, losers, and most active stocks
        """
        try:
            params = {
                "function": "TOP_GAINERS_LOSERS",
                "apikey": self.api_key
            }

            response = requests.get(self.base_url, params=params)

            if response.status_code != 200:
                self.logger.error(
                    f"Alpha Vantage API error: {response.status_code} - {response.text}")
                return {}

            data = response.json()

            # Check for errors
            if "Error Message" in data:
                self.logger.error(
                    f"Alpha Vantage API error: {data['Error Message']}")
                return {}

            return {
                "top_gainers": data.get("top_gainers", []),
                "top_losers": data.get("top_losers", []),
                "most_actively_traded": data.get("most_actively_traded", [])
            }

        except Exception as e:
            self.logger.error(f"Error fetching top gainers/losers: {e}")
            return {}

    def fetch_news_by_sentiment(self, symbol: Optional[str] = None, min_sentiment: float = 0.2) -> pd.DataFrame:
        """
        Fetch news filtered by sentiment score.

        Args:
            symbol: Optional stock ticker symbol to filter news by
            min_sentiment: Minimum sentiment score to include (positive values for positive sentiment)

        Returns:
            DataFrame with filtered news by sentiment
        """
        try:
            # First get all news
            news_df = self.fetch_news_sentiment(symbol)

            if news_df.empty:
                return news_df

            # Filter by sentiment if overall_sentiment_score exists
            if "overall_sentiment_score" in news_df.columns:
                if min_sentiment > 0:
                    # Filter for positive sentiment above threshold
                    filtered_df = news_df[news_df["overall_sentiment_score"]
                                          >= min_sentiment]
                elif min_sentiment < 0:
                    # Filter for negative sentiment below threshold
                    filtered_df = news_df[news_df["overall_sentiment_score"]
                                          <= min_sentiment]
                else:
                    # Return all news
                    filtered_df = news_df

                return filtered_df
            else:
                self.logger.warning("No sentiment scores found in news data")
                return news_df

        except Exception as e:
            self.logger.error(f"Error filtering news by sentiment: {e}")
            return pd.DataFrame()

    def fetch_sector_news(self, sector: str) -> pd.DataFrame:
        """
        Fetch news related to a specific market sector.

        Args:
            sector: Market sector name (e.g., "technology", "healthcare")

        Returns:
            DataFrame with sector-related news
        """
        # For sector news, we can use the topics parameter
        return self.fetch_news_sentiment(topics=sector)
