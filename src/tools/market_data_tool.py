# market_data_tool.py

import pandas as pd
import os
import logging
from typing import Any, Dict, Optional


class MarketDataTool:
    """
    A tool responsible for retrieving and pre-processing historical market data.
    This can be extended to fetch data from local CSV, SQL databases, or 
    remote APIs (e.g., OptionMetrics, Yahoo Finance).
    """

    def __init__(self, config: Dict[str, Any]):
        """
        :param config: Configuration dictionary for data paths, credentials, etc.
                       Example keys might include:
                         - 'data_source' (e.g. 'csv', 'sql', 'api')
                         - 'csv_dir' or 'db_uri'
                         - 'api_key'
                         - 'default_symbol'
                         - 'default_date_range'
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        # Example usage of config
        self.data_source = config.get("data_source", "csv")
        self.csv_dir = config.get("csv_dir", "./data")
        self.api_key = config.get("api_key")
        self.default_symbol = config.get("default_symbol", "AAPL")
        self.default_date_range = config.get(
            "default_date_range", ("2021-01-01", "2021-01-31"))

        # (Optional) set up any DB connections or API sessions here
        # Example:
        # if self.data_source == "sql":
        #     self.db_uri = config.get("db_uri")
        #     self.connection = self._init_db_connection(self.db_uri)

        self.logger.info(
            f"MarketDataTool initialized with data_source={self.data_source}")

    def fetch_options_data(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Main entry point for fetching historical options or market data.

        :param symbol: Stock or option symbol/ticker to fetch data for.
        :param start_date: Start of date range (YYYY-MM-DD).
        :param end_date: End of date range (YYYY-MM-DD).
        :param filters: Additional filters, e.g. 'call/put', 'strike range', 'min open interest'.
        :return: A pandas DataFrame containing the requested data.
        """
        if symbol is None:
            symbol = self.default_symbol
        if not start_date or not end_date:
            start_date, end_date = self.default_date_range

        self.logger.info(
            f"Fetching market data for {symbol} from {start_date} to {end_date} "
            f"using data_source={self.data_source}"
        )

        # Route to the appropriate retrieval method based on data_source
        if self.data_source == "csv":
            return self._fetch_from_csv(symbol, start_date, end_date, filters)
        elif self.data_source == "sql":
            return self._fetch_from_sql(symbol, start_date, end_date, filters)
        elif self.data_source == "api":
            return self._fetch_from_api(symbol, start_date, end_date, filters)
        else:
            self.logger.error(f"Unsupported data_source: {self.data_source}")
            return pd.DataFrame()  # return empty if unsupported
