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
            processed_start, processed_end = get_processed_date_range(start_date, end_date)
            
            self.logger.info(f"Fetching Yahoo Finance data for {ticker} from {processed_start} to {processed_end}")
            
            stock = yf.Ticker(ticker)
            df = stock.history(start=processed_start, end=processed_end)
            
            if df.empty:
                self.logger.warning(f"No data fetched for {ticker}")
            
            return df[['Open', 'High', 'Low', 'Close', 'Volume']]
            
        except Exception as e:
            self.logger.error(f"Error fetching Yahoo Finance data: {e}")
            return pd.DataFrame()


if __name__ == "__main__":
    # Initialize the tool
    tool = YahooFinanceTool()
    
    # Example 1: Using default dynamic dates (last 5 trading days)
    print("\nExample 1: Using default dynamic dates (last 5 trading days)")
    df1 = tool.fetch_stock_data("AAPL")
    print(f"Fetched {df1.shape[0]} rows of data")
    print(df1.head())
    
    # Example 2: Using explicit dates
    print("\nExample 2: Using explicit dates")
    df2 = tool.fetch_stock_data("MSFT", "2023-01-01", "2023-02-01")
    print(f"Fetched {df2.shape[0]} rows of data")
    print(df2.head())
    
    # Example 3: Using relative dates
    print("\nExample 3: Using relative dates")
    df3 = tool.fetch_stock_data("GOOGL", "-30d", "today")
    print(f"Fetched {df3.shape[0]} rows of data")
    print(df3.head())
