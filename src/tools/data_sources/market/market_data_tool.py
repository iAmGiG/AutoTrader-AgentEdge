"""
Enhanced market data tool that uses Alpha Vantage or other sources based on configuration.
"""

import os
import logging
from typing import Any, Dict, Optional
import pandas as pd
from config.config_loader import ConfigLoader
from src.tools.data_sources.alpha_vantage_tool import AlphaVantageTool
from src.utils.date_utils import (
    get_processed_date_range,
    localize_df,
    get_default_timezone,
)

# Lazy imports for optional dependencies
YahooFinanceTool = None
FMPTool = None
NasdaqDataLinkTool = None

try:
    from src.tools.data_sources.market.yahoo_finance_tool import YahooFinanceTool
except ImportError:
    pass

try:
    from src.tools.data_sources.market.fmp_tool import FMPTool
except ImportError:
    pass

try:
    from src.tools.data_sources.market.nasdaq_data_link_tool import NasdaqDataLinkTool
except ImportError:
    pass


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

        # Load from environment if config not provided
        if config is None:
            config_loader = ConfigLoader()
            default_days_back = int(
                os.getenv("DEFAULT_DAYS_BACK", config_loader.get(
                    "DEFAULT_DAYS_BACK", 5))
            )
            default_date_range = get_processed_date_range(
                default_days_back=default_days_back)

            self.config = {
                "data_source": os.getenv(
                    "MARKET_DATA_SOURCE",
                    config_loader.get("MARKET_DATA_SOURCE", "alpha_vantage"),
                ),
                "default_symbol": os.getenv(
                    "DEFAULT_SYMBOL", config_loader.get(
                        "DEFAULT_SYMBOL", "AAPL")
                ),
                "default_date_range": default_date_range,
                "default_days_back": default_days_back,
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
        self.fmp_tool = None
        self.nasdaq_dl_tool = None

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
            df = self._fetch_from_alpha_vantage(
                symbol, start_date, end_date, filters)
        elif self.data_source == "yahoo":
            df = self._fetch_from_yahoo(symbol, start_date, end_date, filters)
        elif self.data_source == "fmp":
            df = self._fetch_from_fmp(symbol, start_date, end_date, filters)
        elif self.data_source == "nasdaq":
            df = self._fetch_from_nasdaq(symbol, start_date, end_date, filters)
        elif self.data_source == "csv":
            df = self._fetch_from_csv(symbol, start_date, end_date, filters)
        else:
            self.logger.error(f"Unsupported data_source: {self.data_source}")
            return pd.DataFrame()

        if not df.empty:
            df = localize_df(df, get_default_timezone())
        return df

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

        try:
            df = self.alpha_vantage_tool.fetch_stock_data(
                symbol, start_date, end_date)
            if df is None or df.empty:
                self.logger.warning(
                    "Alpha Vantage returned no data, attempting FMP fallback")
                return self._fetch_from_fmp(symbol, start_date, end_date, filters)
        except Exception as e:
            self.logger.warning(
                f"Alpha Vantage error for {symbol}: {e}. Using FMP fallback")
            return self._fetch_from_fmp(symbol, start_date, end_date, filters)

        col_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
        df = df.rename(
            columns={k: v for k, v in col_map.items() if k in df.columns})

        return df

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
        # Check if Yahoo Finance is available
        if YahooFinanceTool is None:
            self.logger.warning(
                "YahooFinanceTool not available (missing yfinance), falling back to Alpha Vantage")
            return self._fetch_from_alpha_vantage(symbol, start_date, end_date, filters)

        # Initialize Yahoo Finance tool if needed
        if self.yahoo_finance_tool is None:
            self.yahoo_finance_tool = YahooFinanceTool()

        # Fetch data with fallback to Alpha Vantage on failure or empty result
        try:
            df = self.yahoo_finance_tool.fetch_stock_data(
                symbol, start_date, end_date)
            if df is None or df.empty:
                self.logger.warning(
                    "Yahoo Finance returned no data, attempting Alpha Vantage fallback")
                return self._fetch_from_alpha_vantage(
                    symbol, start_date, end_date, filters)
            return df
        except Exception as e:
            self.logger.warning(
                f"Yahoo Finance error for {symbol}: {e}. Using Alpha Vantage fallback")
            return self._fetch_from_alpha_vantage(symbol, start_date, end_date, filters)

    def _fetch_from_fmp(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Fetch market data from Financial Modeling Prep."""
        # Check if FMP is available
        if FMPTool is None:
            self.logger.warning(
                "FMPTool not available, falling back to Nasdaq Data Link")
            return self._fetch_from_nasdaq_dl(symbol, start_date, end_date, filters)

        if self.fmp_tool is None:
            self.fmp_tool = FMPTool()

        try:
            df = self.fmp_tool.fetch_stock_data(symbol, start_date, end_date)
            if df is None or df.empty:
                self.logger.warning(
                    "FMP returned no data, attempting Nasdaq Data Link fallback")
                return self._fetch_from_nasdaq_dl(symbol, start_date, end_date, filters)
            return df
        except Exception as e:
            self.logger.warning(
                f"FMP error for {symbol}: {e}. Using Nasdaq Data Link fallback")
            return self._fetch_from_nasdaq_dl(symbol, start_date, end_date, filters)

    def _fetch_from_nasdaq_dl(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Fetch market data from Nasdaq Data Link."""
        # Check if Nasdaq Data Link is available
        if NasdaqDataLinkTool is None:
            self.logger.warning("Nasdaq Data Link not available (missing nasdaqdatalink)")
            return pd.DataFrame()

        if self.nasdaq_dl_tool is None:
            self.nasdaq_dl_tool = NasdaqDataLinkTool()

        try:
            df = self.nasdaq_dl_tool.fetch_stock_data(symbol, start_date, end_date)
            if df is None or df.empty:
                self.logger.warning("Nasdaq Data Link returned no data")
                return pd.DataFrame()
            return df
        except Exception as e:
            self.logger.error(f"Nasdaq Data Link error for {symbol}: {e}")
            return pd.DataFrame()

    def _fetch_from_nasdaq(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Alias for _fetch_from_nasdaq_dl for backward compatibility."""
        return self._fetch_from_nasdaq_dl(symbol, start_date, end_date, filters)

    def _fetch_from_csv(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Fetch market data from local CSV files.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            filters: Additional filters

        Returns:
            DataFrame with market data
        """
        csv_dir = self.config.get("csv_dir", "./data/csv/")
        csv_path = os.path.join(csv_dir, f"{symbol}.csv")

        if not os.path.exists(csv_path):
            self.logger.error(f"CSV file not found: {csv_path}")
            return pd.DataFrame()

        try:
            df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)

            # Filter by date range
            df = df[(df.index >= start_date) & (df.index <= end_date)]

            return df
        except Exception as e:
            self.logger.error(f"Error reading CSV file: {e}")
            return pd.DataFrame()

    def test_all_sources(self, symbol: str = "AAPL") -> Dict[str, Any]:
        """
        Test connectivity and availability of all data sources.

        Args:
            symbol: Test symbol to use

        Returns:
            Dictionary with test results for each source
        """
        results = {}

        # Test Alpha Vantage
        try:
            if self.alpha_vantage_tool is None:
                self.alpha_vantage_tool = AlphaVantageTool()
            df = self.alpha_vantage_tool.fetch_stock_data(symbol, "-5d", "today")
            results["alpha_vantage"] = {
                "status": "available" if not df.empty else "no_data",
                "rows": len(df) if not df.empty else 0
            }
        except Exception as e:
            results["alpha_vantage"] = {"status": "error", "error": str(e)}

        # Test Yahoo Finance
        if YahooFinanceTool is not None:
            try:
                if self.yahoo_finance_tool is None:
                    self.yahoo_finance_tool = YahooFinanceTool()
                df = self.yahoo_finance_tool.fetch_stock_data(
                    symbol, "-5d", "today")
                results["yahoo"] = {
                    "status": "available" if not df.empty else "no_data",
                    "rows": len(df) if not df.empty else 0
                }
            except Exception as e:
                results["yahoo"] = {"status": "error", "error": str(e)}
        else:
            results["yahoo"] = {"status": "not_installed"}

        # Test FMP
        if FMPTool is not None:
            try:
                if self.fmp_tool is None:
                    self.fmp_tool = FMPTool()
                df = self.fmp_tool.fetch_stock_data(symbol, "-5d", "today")
                results["fmp"] = {
                    "status": "available" if not df.empty else "no_data",
                    "rows": len(df) if not df.empty else 0
                }
            except Exception as e:
                results["fmp"] = {"status": "error", "error": str(e)}
        else:
            results["fmp"] = {"status": "not_installed"}

        # Test Nasdaq Data Link
        if NasdaqDataLinkTool is not None:
            try:
                if self.nasdaq_dl_tool is None:
                    self.nasdaq_dl_tool = NasdaqDataLinkTool()
                df = self.nasdaq_dl_tool.fetch_stock_data(
                    symbol, "-5d", "today")
                results["nasdaq_dl"] = {
                    "status": "available" if not df.empty else "no_data",
                    "rows": len(df) if not df.empty else 0
                }
            except Exception as e:
                results["nasdaq_dl"] = {"status": "error", "error": str(e)}
        else:
            results["nasdaq_dl"] = {"status": "not_installed"}

        return results


if __name__ == "__main__":
    # Example usage
    tool = MarketDataTool()

    # Test all sources
    print("Testing all available data sources...")
    test_results = tool.test_all_sources()
    for source, result in test_results.items():
        print(f"\n{source}: {result}")

    # Example 1: Using default dynamic dates (last 5 trading days)
    print("\nExample 1: Using default dynamic dates (last 5 trading days)")
    df1 = tool.fetch_market_data("AAPL")
    print(f"Shape: {df1.shape}")
    if not df1.empty:
        print(df1.head())

    # Example 2: Using explicit dates
    print("\nExample 2: Using explicit dates")
    df2 = tool.fetch_market_data("MSFT", "2024-01-01", "2024-01-31")
    print(f"Shape: {df2.shape}")
    if not df2.empty:
        print(df2.head())

    # Example 3: Using relative dates
    print("\nExample 3: Using relative dates")
    df3 = tool.fetch_market_data("GOOGL", "-30d", "today")
    print(f"Shape: {df3.shape}")
    if not df3.empty:
        print(df3.head())

    # Example 4: Using a different data source
    print("\nExample 4: Using Yahoo Finance")
    tool.data_source = "yahoo"
    df4 = tool.fetch_market_data("TSLA", "-10d", "today")
    print(f"Shape: {df4.shape}")
    if not df4.empty:
        print(df4.head())