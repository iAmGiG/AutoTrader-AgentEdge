"""
[DEPRECATED] Tool for fetching market data from Alpha Vantage API.

This file is maintained for backward compatibility but will be removed in a future version.
Please use the specialized versions instead:
- src.tools.data_sources.market.alpha_vantage_market
- src.tools.data_sources.news.alpha_vantage_news
"""

import requests
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from config.config_loader import ConfigLoader
from src.tools.date_utils import get_processed_date_range


class AlphaVantageTool:
    """
    [DEPRECATED] Tool for retrieving market data from Alpha Vantage API.
    
    This class has been split into specialized components:
    - AlphaVantageMarketTool - for market data and fundamentals
    - AlphaVantageNewsTool - for news and sentiment data
    """

    def __init__(self):
        import warnings
        warnings.warn(
            "AlphaVantageTool is deprecated. Use AlphaVantageMarketTool or AlphaVantageNewsTool instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Load API key from config
        config_loader = ConfigLoader()
        self.api_key = config_loader.get("alpha_vantage_key")

        if not self.api_key:
            logging.warning("Alpha Vantage API key not found in config.")

        self.base_url = "https://www.alphavantage.co/query"
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_stock_data(self, symbol: str, start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch daily stock data for a given symbol.

        Args:
            symbol: Stock ticker symbol
            start_date: Optional start date filter (YYYY-MM-DD) or relative date string ("-30d")
                        If None, uses dynamic calculation (last 5 trading days)
            end_date: Optional end date filter (YYYY-MM-DD) or relative date string ("today")
                      If None, uses today's date

        Returns:
            DataFrame with stock price data
        """
        try:
            # Process date parameters, applying dynamic date calculation if needed
            processed_start, processed_end = get_processed_date_range(
                start_date, end_date)

            self.logger.info(
                f"Fetching Alpha Vantage data for {symbol} from {processed_start} to {processed_end}")

            # Determine outputsize based on date range
            days_range = (datetime.now() -
                          datetime.strptime(processed_start, "%Y-%m-%d")).days
            use_full = days_range > 100

            # API parameters for daily time series
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "apikey": self.api_key,
                "outputsize": "full" if use_full else "compact",
                "datatype": "json"
            }

            # Make API request
            response = requests.get(self.base_url, params=params)

            if response.status_code != 200:
                self.logger.error(
                    f"Alpha Vantage API error: {response.status_code} - {response.text}")
                return pd.DataFrame()

            data = response.json()

            # Check for errors in the response
            if "Error Message" in data:
                self.logger.error(
                    f"Alpha Vantage API error: {data['Error Message']}")
                return pd.DataFrame()

            # Extract time series data
            if "Time Series (Daily)" not in data:
                self.logger.warning(f"No time series data found for {symbol}")
                return pd.DataFrame()

            time_series = data["Time Series (Daily)"]

            # Convert to DataFrame
            df = pd.DataFrame.from_dict(time_series, orient="index")

            # Fix column names (removing number prefixes)
            df = df.rename(columns={
                "1. open": "open",
                "2. high": "high",
                "3. low": "low",
                "4. close": "close",
                "5. volume": "volume"
            })

            # Convert index to datetime
            df.index = pd.to_datetime(df.index)

            # Convert values to numeric
            for col in df.columns:
                df[col] = pd.to_numeric(df[col])

            # Apply date filters using processed dates
            df = df[df.index >= processed_start]
            df = df[df.index <= processed_end]

            # Sort by date (newest first)
            df = df.sort_index(ascending=False)

            return df

        except Exception as e:
            self.logger.error(f"Error fetching Alpha Vantage data: {e}")
            return pd.DataFrame()

    def fetch_company_overview(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch company overview data with fundamentals.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with company overview data
        """
        try:
            params = {
                "function": "OVERVIEW",
                "symbol": symbol,
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

            return data

        except Exception as e:
            self.logger.error(f"Error fetching company overview: {e}")
            return {}

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


if __name__ == "__main__":
    # Example usage
    tool = AlphaVantageTool()

    # Example 1: Using default dynamic dates (last 5 trading days)
    print("\nExample 1: Using default dynamic dates (last 5 trading days)")
    stock_df1 = tool.fetch_stock_data("AAPL")
    print("\nStock data with default dates:")
    print(stock_df1.head())

    # Example 2: Using explicit dates
    print("\nExample 2: Using explicit dates")
    stock_df2 = tool.fetch_stock_data("MSFT", "2024-01-01", "2024-01-31")
    print("\nStock data with explicit dates:")
    print(stock_df2.head())

    # Example 3: Using relative dates
    print("\nExample 3: Using relative dates")
    stock_df3 = tool.fetch_stock_data("GOOGL", "-30d", "today")
    print("\nStock data with relative dates:")
    print(stock_df3.head())

    # Fetch news sentiment
    news_df = tool.fetch_news_sentiment("AAPL")
    print("\nNews sentiment data:")
    if not news_df.empty:
        print(news_df[["title", "source", "overall_sentiment_score"]].head())
    else:
        print("No news data returned")
