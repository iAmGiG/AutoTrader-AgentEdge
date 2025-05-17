"""
Enhanced market data tool that uses Alpha Vantage or other sources based on configuration.
"""

import os
import logging
from typing import Any, Dict, Optional
from config.config_loader import ConfigLoader
from src.tools.data_sources.alpha_vantage_tool import AlphaVantageTool
from src.tools.data_sources.market.yahoo_finance_tool import YahooFinanceTool
from src.tools.date_utils import get_processed_date_range


class MarketDataTool:
    """
    A tool responsible for retrieving and pre-processing historical market data.
    This can fetch data from various sources like Alpha Vantage, Yahoo Finance,
    or local CSV files based on configuration.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize market data tool with optional configuration.

        Args:
            config: Configuration dictionary for data paths, credentials, etc.
                   Example keys include:
                     - 'data_source' (e.g. 'alpha_vantage', 'yahoo', 'csv', 'sql')
                     - 'csv_dir' or 'db_uri'
                     - 'default_symbol'
                     - 'default_date_range'
        """
        # Set up logger
        self.logger = logging.getLogger(self.__class__.__name__)

        # Load from config if not provided
        if config is None:
            config_loader = ConfigLoader()

            # Get default date range from config or use dynamic calculation
            default_days_back = config_loader.get("default_days_back", 5)
            default_date_range = get_processed_date_range(
                default_days_back=default_days_back)

            self.config = {
                "data_source": config_loader.get("market_data_source", "alpha_vantage"),
                "default_symbol": config_loader.get("default_symbol", "AAPL"),
                "default_date_range": default_date_range,
                "default_days_back": default_days_back
            }
        else:
            self.config = config

        # Set configuration values
        self.data_source = self.config.get("data_source", "alpha_vantage")
        self.default_symbol = self.config.get("default_symbol", "AAPL")
        self.default_days_back = self.config.get("default_days_back", 5)
        self.default_date_range = self.config.get("default_date_range",
                                                  get_processed_date_range(default_days_back=self.default_days_back))

        # Initialize specific data source tools
        self.alpha_vantage_tool = None
        self.yahoo_finance_tool = None

        self.logger.info(
            f"MarketDataTool initialized with data_source={self.data_source}")

    def fetch_market_data(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Main entry point for fetching historical market data.

        Args:
            symbol: Stock symbol/ticker to fetch data for.
            start_date: Start of date range (YYYY-MM-DD).
            end_date: End of date range (YYYY-MM-DD).
            filters: Additional filters (e.g., 'intervals', 'indicators').

        Returns:
            A pandas DataFrame containing the requested market data.
        """
        # Use defaults if not provided
        if symbol is None:
            symbol = self.default_symbol

        # Process date parameters, applying dynamic date calculation if needed
        start_date, end_date = get_processed_date_range(
            start_date, end_date, self.default_days_back)

        self.logger.info(
            f"Fetching market data for {symbol} from {start_date} to {end_date} "
            f"using data_source={self.data_source}"
        )

        # Route to the appropriate data source
        if self.data_source == "alpha_vantage":
            return self._fetch_from_alpha_vantage(symbol, start_date, end_date, filters)
        elif self.data_source == "yahoo":
            return self._fetch_from_yahoo(symbol, start_date, end_date, filters)
        elif self.data_source == "csv":
            return self._fetch_from_csv(symbol, start_date, end_date, filters)
        else:
            self.logger.error(f"Unsupported data_source: {self.data_source}")
            return pd.DataFrame()

    def _fetch_from_alpha_vantage(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Fetch market data from Alpha Vantage API.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            filters: Additional filters

        Returns:
            DataFrame with market data
        """
        # Initialize Alpha Vantage tool if needed
        if self.alpha_vantage_tool is None:
            self.alpha_vantage_tool = AlphaVantageTool()

        # Fetch data
        return self.alpha_vantage_tool.fetch_stock_data(symbol, start_date, end_date)

    def _fetch_from_yahoo(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Fetch market data from Yahoo Finance.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            filters: Additional filters

        Returns:
            DataFrame with market data
        """
        # Initialize Yahoo Finance tool if needed
        if self.yahoo_finance_tool is None:
            self.yahoo_finance_tool = YahooFinanceTool()

        # Fetch data
        return self.yahoo_finance_tool.fetch_stock_data(symbol, start_date, end_date)

    def _fetch_from_csv(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Fetch market data from a local CSV file.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            filters: Additional filters

        Returns:
            DataFrame with market data
        """
        # Get CSV directory from config
        csv_dir = self.config.get("csv_dir", "./data")

        # Construct CSV file path
        file_path = os.path.join(csv_dir, f"{symbol}.csv")

        # Check if file exists
        if not os.path.exists(file_path):
            self.logger.error(f"CSV file not found: {file_path}")
            return pd.DataFrame()

        try:
            # Read CSV file
            df = pd.read_csv(file_path, parse_dates=['Date'])

            # Set date as index if it's a column
            if 'Date' in df.columns:
                df.set_index('Date', inplace=True)

            # Apply date filters
            if start_date:
                df = df[df.index >= start_date]
            if end_date:
                df = df[df.index <= end_date]

            return df

        except Exception as e:
            self.logger.error(f"Error reading CSV file: {e}")
            return pd.DataFrame()

    def fetch_news_sentiment(
        self,
        symbol: Optional[str] = None,
        topics: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch news and sentiment data.

        Args:
            symbol: Optional stock symbol to filter news by
            topics: Optional topics to filter by

        Returns:
            DataFrame with news and sentiment data
        """
        # Use default symbol if not provided
        if symbol is None:
            symbol = self.default_symbol

        # Route to the appropriate data source for news
        if self.data_source == "alpha_vantage":
            # Initialize Alpha Vantage tool if needed
            if self.alpha_vantage_tool is None:
                self.alpha_vantage_tool = AlphaVantageTool()

            return self.alpha_vantage_tool.fetch_news_sentiment(symbol, topics)
        else:
            self.logger.warning(
                f"News sentiment not supported for data source: {self.data_source}")
            return pd.DataFrame()
