import yfinance as yf
import pandas as pd
import logging
from typing import Optional
from datetime import datetime, timedelta
from src.tools.date_utils import get_processed_date_range, process_date_param


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

    def fetch_corporate_events(self, ticker: str, days_ahead: int = 30):
        """
        Fetch upcoming corporate events (earnings dates, dividend dates) from Yahoo Finance.
        
        Args:
            ticker: Stock symbol to fetch events for
            days_ahead: Number of days ahead to look for events (default: 30)
                       This helps control token usage by limiting event scope
        
        Returns:
            dict: Dictionary containing upcoming events within the specified timeframe
                 Keys: 'next_earnings_date', 'next_ex_dividend', etc.
                 Values: datetime objects or None if no events found
        """
        try:
            self.logger.info(f"Fetching corporate events for {ticker} (looking {days_ahead} days ahead)")
            
            stock = yf.Ticker(ticker)
            events = {}
            
            # Calculate cutoff date for filtering events
            cutoff_date = datetime.now() + timedelta(days=days_ahead)
            
            try:
                cal = stock.calendar.T  # easier to read as rows
                
                # Process earnings date
                if "Earnings Date" in cal.index:
                    earnings_date = cal.loc["Earnings Date"].iloc[0]
                    # Only include if within our time window
                    if earnings_date <= cutoff_date:
                        events["next_earnings_date"] = earnings_date
                        self.logger.info(f"Found earnings date for {ticker}: {earnings_date}")
                
                # Process ex-dividend date  
                if "Ex-Dividend Date" in cal.index:
                    ex_div_date = cal.loc["Ex-Dividend Date"].iloc[0]
                    # Only include if within our time window
                    if ex_div_date <= cutoff_date:
                        events["next_ex_dividend"] = ex_div_date
                        self.logger.info(f"Found ex-dividend date for {ticker}: {ex_div_date}")
                        
                self.logger.info(f"Found {len(events)} upcoming events for {ticker} within {days_ahead} days")
                
            except Exception as cal_error:
                self.logger.warning(f"Could not fetch calendar data for {ticker}: {cal_error}")
                # Return empty events dict if calendar unavailable
            
            return events

        except Exception as e:
            self.logger.error(f"Error fetching corporate events for {ticker}: {e}")
            return {}
