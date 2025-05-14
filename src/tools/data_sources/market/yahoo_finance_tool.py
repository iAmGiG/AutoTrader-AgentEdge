import yfinance as yf
import pandas as pd
import logging
from typing import Optional
from src.tools.date_utils import get_processed_date_range


class YahooFinanceTool:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_stock_data(self, ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        Fetch stock data from Yahoo Finance.

        Args:
            ticker: Stock symbol to fetch
            start_date: Start date (YYYY-MM-DD) or relative date (e.g., "-30d")
                        If None, uses dynamic calculation (last 5 trading days)
            end_date: End date (YYYY-MM-DD) or relative date (e.g., "today")
                      If None, uses today's date

        Returns:
            DataFrame with stock data
        """
        try:
            # Use dynamic date handling
            processed_start, processed_end = get_processed_date_range(
                start_date, end_date)

            self.logger.info(
                f"Fetching Yahoo Finance data for {ticker} from {processed_start} to {processed_end}")

            stock = yf.Ticker(ticker)
            df = stock.history(start=processed_start, end=processed_end)

            if df.empty:
                self.logger.warning(f"No data fetched for {ticker}")

            return df[['Open', 'High', 'Low', 'Close', 'Volume']]

        except Exception as e:
            self.logger.error(f"Error fetching Yahoo Finance data: {e}")
            return pd.DataFrame()
