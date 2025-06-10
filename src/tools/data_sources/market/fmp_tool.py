"""
Financial Modeling Prep (FMP) data source tool for corporate actions.

This tool provides access to FMP API for earnings calendar, dividends, stock splits,
and other corporate actions. FMP offers good free tier access to corporate events data.
"""

import requests
import logging
import pandas as pd
from typing import Optional
import os
from src.tools.date_utils import process_date_param


class FMPTool:
    """
    A tool for accessing corporate actions data from Financial Modeling Prep (FMP).

    Provides earnings calendar, dividend calendar, stock splits, and other
    corporate actions data with good free tier access.
    """

    def __init__(self, api_key: Optional[str] = None, verbose: bool = False):
        """
        Initialize the FMP data tool.

        Args:
            api_key: Optional API key for FMP. If not provided, will load from config.
            verbose: Whether to enable verbose logging.
        """
        # Set up logger
        self.logger = logging.getLogger(self.__class__.__name__)
        if verbose:
            logging.basicConfig(level=logging.INFO)

        # Load API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("FMP")

            if not api_key:
                self.logger.error("No FMP API key provided in environment")
                raise ValueError(
                    "FMP API key is required. Set the FMP environment variable."
                )

        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com/api/v3"
        self.logger.info("FMP API client initialized successfully")

    def fetch_earnings_calendar(self, start_date: str = "today", end_date: str = "+30d") -> pd.DataFrame:
        """
        Fetch earnings calendar from FMP API.

        Args:
            start_date: Start date (YYYY-MM-DD or relative like "today")
            end_date: End date (YYYY-MM-DD or relative like "+30d")

        Returns:
            DataFrame with earnings calendar data
        """
        try:
            # Process date parameters
            processed_start = process_date_param(
                start_date) or process_date_param("today")
            processed_end = process_date_param(
                end_date) or process_date_param("+30d")

            url = f"{self.base_url}/earning_calendar"
            params = {
                'from': processed_start,
                'to': processed_end,
                'apikey': self.api_key
            }

            self.logger.info(
                f"Fetching earnings calendar from {processed_start} to {processed_end}")
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if not data or not isinstance(data, list):
                self.logger.warning(
                    "No earnings calendar data returned from FMP")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)

            if not df.empty:
                # Standardize column names
                column_mapping = {
                    'symbol': 'Symbol',
                    'date': 'Earnings_Date',
                    'epsActual': 'EPS_Actual',
                    'epsEstimate': 'EPS_Estimate',
                    'revenueActual': 'Revenue_Actual',
                    'revenueEstimate': 'Revenue_Estimate',
                    'time': 'Time',
                    'updatedFromDate': 'Updated_Date'
                }

                # Rename existing columns
                df = df.rename(
                    columns={k: v for k, v in column_mapping.items() if k in df.columns})

                # Convert date to datetime
                if 'Earnings_Date' in df.columns:
                    df['Earnings_Date'] = pd.to_datetime(df['Earnings_Date'])

                df['Data_Source'] = 'FMP'

            return df

        except Exception as e:
            self.logger.error(
                f"Error fetching earnings calendar from FMP: {e}")
            return pd.DataFrame()

    def fetch_dividend_calendar(self, start_date: str = "today", end_date: str = "+30d") -> pd.DataFrame:
        """
        Fetch dividend calendar from FMP API.

        Args:
            start_date: Start date (YYYY-MM-DD or relative like "today")
            end_date: End date (YYYY-MM-DD or relative like "+30d")

        Returns:
            DataFrame with dividend calendar data
        """
        try:
            # Process date parameters
            processed_start = process_date_param(
                start_date) or process_date_param("today")
            processed_end = process_date_param(
                end_date) or process_date_param("+30d")

            url = f"{self.base_url}/stock_dividend_calendar"
            params = {
                'from': processed_start,
                'to': processed_end,
                'apikey': self.api_key
            }

            self.logger.info(
                f"Fetching dividend calendar from {processed_start} to {processed_end}")
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if not data or not isinstance(data, list):
                self.logger.warning(
                    "No dividend calendar data returned from FMP")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)

            if not df.empty:
                # Standardize column names
                column_mapping = {
                    'symbol': 'Symbol',
                    'date': 'Ex_Dividend_Date',
                    'dividend': 'Dividend_Amount',
                    'recordDate': 'Record_Date',
                    'paymentDate': 'Payment_Date',
                    'declarationDate': 'Declaration_Date'
                }

                # Rename existing columns
                df = df.rename(
                    columns={k: v for k, v in column_mapping.items() if k in df.columns})

                # Convert dates to datetime
                date_columns = ['Ex_Dividend_Date', 'Record_Date',
                                'Payment_Date', 'Declaration_Date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])

                df['Data_Source'] = 'FMP'

            return df

        except Exception as e:
            self.logger.error(
                f"Error fetching dividend calendar from FMP: {e}")
            return pd.DataFrame()

    def fetch_stock_split_calendar(self, start_date: str = "today", end_date: str = "+30d") -> pd.DataFrame:
        """
        Fetch stock split calendar from FMP API.

        Args:
            start_date: Start date (YYYY-MM-DD or relative like "today")
            end_date: End date (YYYY-MM-DD or relative like "+30d")

        Returns:
            DataFrame with stock split calendar data
        """
        try:
            # Process date parameters
            processed_start = process_date_param(
                start_date) or process_date_param("today")
            processed_end = process_date_param(
                end_date) or process_date_param("+30d")

            url = f"{self.base_url}/stock_split_calendar"
            params = {
                'from': processed_start,
                'to': processed_end,
                'apikey': self.api_key
            }

            self.logger.info(
                f"Fetching stock split calendar from {processed_start} to {processed_end}")
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if not data or not isinstance(data, list):
                self.logger.warning(
                    "No stock split calendar data returned from FMP")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)

            if not df.empty:
                # Standardize column names
                column_mapping = {
                    'symbol': 'Symbol',
                    'date': 'Split_Date',
                    'numerator': 'Split_Numerator',
                    'denominator': 'Split_Denominator',
                    'splitRatio': 'Split_Ratio'
                }

                # Rename existing columns
                df = df.rename(
                    columns={k: v for k, v in column_mapping.items() if k in df.columns})

                # Convert date to datetime
                if 'Split_Date' in df.columns:
                    df['Split_Date'] = pd.to_datetime(df['Split_Date'])

                df['Data_Source'] = 'FMP'

            return df

        except Exception as e:
            self.logger.error(
                f"Error fetching stock split calendar from FMP: {e}")
            return pd.DataFrame()

    def fetch_historical_dividends(self, symbol: str, start_date: str = "-1y", end_date: str = "today") -> pd.DataFrame:
        """
        Fetch historical dividend data for a specific symbol from FMP API.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date (YYYY-MM-DD or relative like "-1y")
            end_date: End date (YYYY-MM-DD or relative like "today")

        Returns:
            DataFrame with historical dividend data
        """
        try:
            url = f"{self.base_url}/historical-price-full/stock_dividend/{symbol}"
            params = {
                'apikey': self.api_key
            }

            self.logger.info(f"Fetching historical dividends for {symbol}")
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if not data or 'historical' not in data:
                self.logger.warning(
                    f"No historical dividend data returned for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data['historical'])

            if not df.empty:
                # Filter by date range if needed
                processed_start = process_date_param(start_date)
                processed_end = process_date_param(end_date)

                if processed_start and processed_end:
                    df['date'] = pd.to_datetime(df['date'])
                    df = df[(df['date'] >= processed_start)
                            & (df['date'] <= processed_end)]

                # Standardize column names
                column_mapping = {
                    'date': 'Ex_Dividend_Date',
                    'dividend': 'Dividend_Amount',
                    'adjDividend': 'Adjusted_Dividend',
                    'recordDate': 'Record_Date',
                    'paymentDate': 'Payment_Date',
                    'declarationDate': 'Declaration_Date'
                }

                # Rename existing columns
                df = df.rename(
                    columns={k: v for k, v in column_mapping.items() if k in df.columns})

                # Add symbol and source
                df['Symbol'] = symbol
                df['Data_Source'] = 'FMP'

                # Convert dates to datetime
                date_columns = ['Ex_Dividend_Date', 'Record_Date',
                                'Payment_Date', 'Declaration_Date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])

            return df

        except Exception as e:
            self.logger.error(
                f"Error fetching historical dividends for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_historical_earnings(self, symbol: str, limit: int = 80) -> pd.DataFrame:
        """
        Fetch historical earnings data for a specific symbol from FMP API.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            limit: Maximum number of earnings records to retrieve

        Returns:
            DataFrame with historical earnings data
        """
        try:
            url = f"{self.base_url}/historical/earning_calendar/{symbol}"
            params = {
                'limit': limit,
                'apikey': self.api_key
            }

            self.logger.info(f"Fetching historical earnings for {symbol}")
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if not data or not isinstance(data, list):
                self.logger.warning(
                    f"No historical earnings data returned for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)

            if not df.empty:
                # Standardize column names
                column_mapping = {
                    'symbol': 'Symbol',
                    'date': 'Earnings_Date',
                    'epsActual': 'EPS_Actual',
                    'epsEstimate': 'EPS_Estimate',
                    'revenueActual': 'Revenue_Actual',
                    'revenueEstimate': 'Revenue_Estimate',
                    'time': 'Time',
                    'updatedFromDate': 'Updated_Date'
                }

                # Rename existing columns
                df = df.rename(
                    columns={k: v for k, v in column_mapping.items() if k in df.columns})

                # Convert date to datetime
                if 'Earnings_Date' in df.columns:
                    df['Earnings_Date'] = pd.to_datetime(df['Earnings_Date'])

                df['Data_Source'] = 'FMP'

            return df

        except Exception as e:
            self.logger.error(
                f"Error fetching historical earnings for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_ipo_calendar(self, start_date: str = "today", end_date: str = "+30d") -> pd.DataFrame:
        """
        Fetch IPO calendar from FMP API.

        Args:
            start_date: Start date (YYYY-MM-DD or relative like "today")
            end_date: End date (YYYY-MM-DD or relative like "+30d")

        Returns:
            DataFrame with IPO calendar data
        """
        try:
            # Process date parameters
            processed_start = process_date_param(
                start_date) or process_date_param("today")
            processed_end = process_date_param(
                end_date) or process_date_param("+30d")

            url = f"{self.base_url}/ipo_calendar"
            params = {
                'from': processed_start,
                'to': processed_end,
                'apikey': self.api_key
            }

            self.logger.info(
                f"Fetching IPO calendar from {processed_start} to {processed_end}")
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if not data or not isinstance(data, list):
                self.logger.warning("No IPO calendar data returned from FMP")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)

            if not df.empty:
                # Standardize column names
                column_mapping = {
                    'symbol': 'Symbol',
                    'date': 'IPO_Date',
                    'exchange': 'Exchange',
                    'name': 'Company_Name',
                    'numberOfShares': 'Number_Of_Shares',
                    'price': 'IPO_Price',
                    'status': 'Status'
                }

                # Rename existing columns
                df = df.rename(
                    columns={k: v for k, v in column_mapping.items() if k in df.columns})

                # Convert date to datetime
                if 'IPO_Date' in df.columns:
                    df['IPO_Date'] = pd.to_datetime(df['IPO_Date'])

                df['Data_Source'] = 'FMP'

            return df

        except Exception as e:
            self.logger.error(f"Error fetching IPO calendar from FMP: {e}")
            return pd.DataFrame()

    def fetch_stock_data(self, symbol: str, start_date: str = "-1y", end_date: str = "today") -> pd.DataFrame:
        """
        Fetch basic stock price data from FMP API (alternative to Yahoo/Alpha Vantage).

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date (YYYY-MM-DD or relative like "-1y") 
            end_date: End date (YYYY-MM-DD or relative like "today")

        Returns:
            DataFrame with basic stock price data (Open, High, Low, Close, Volume)
        """
        try:
            # Process date parameters
            processed_start = process_date_param(
                start_date) or process_date_param("-1y")
            processed_end = process_date_param(
                end_date) or process_date_param("today")

            url = f"{self.base_url}/historical-price-full/{symbol}"
            params = {
                'from': processed_start,
                'to': processed_end,
                'apikey': self.api_key
            }

            self.logger.info(
                f"Fetching stock data for {symbol} from {processed_start} to {processed_end}")
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if not data or 'historical' not in data:
                self.logger.warning(f"No stock data returned for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data['historical'])

            if not df.empty:
                # Standardize column names to match other market data tools
                column_mapping = {
                    'date': 'Date',
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'close': 'Close',
                    'volume': 'Volume'
                }

                # Rename existing columns
                df = df.rename(
                    columns={k: v for k, v in column_mapping.items() if k in df.columns})

                # Convert date to datetime and set as index
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df.set_index('Date', inplace=True)

                # Sort by date (oldest to newest)
                df = df.sort_index()

                # Keep only OHLCV columns
                ohlcv_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                df = df[[col for col in ohlcv_columns if col in df.columns]]

            return df

        except Exception as e:
            self.logger.error(f"Error fetching stock data for {symbol}: {e}")
            return pd.DataFrame()
