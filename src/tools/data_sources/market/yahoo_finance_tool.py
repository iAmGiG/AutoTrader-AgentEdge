import yfinance as yf
import pandas as pd
import logging
import time
from typing import Optional
from datetime import datetime, timedelta
from src.tools.date_utils import get_processed_date_range, localize_df, get_default_timezone

# Global cache and throttling variables
_last_request_time = {}
_request_cache = {}
CACHE_DURATION = 120  # Cache for 2 minutes
MIN_REQUEST_INTERVAL = 2  # Minimum 2 seconds between requests per ticker


def _get_cache_key(ticker: str, method: str) -> str:
    """Generate a cache key for a ticker and method combination."""
    return f"{ticker}:{method}"


def _is_cache_valid(cache_key: str) -> bool:
    """Check if cached data is still valid."""
    if cache_key not in _request_cache:
        return False

    cached_time, _ = _request_cache[cache_key]
    return (datetime.now() - cached_time).total_seconds() < CACHE_DURATION


def _get_from_cache(cache_key: str):
    """Get data from cache if valid."""
    if _is_cache_valid(cache_key):
        _, data = _request_cache[cache_key]
        # Return cached data even if it's None (represents a failed API call)
        return data
    return "NOT_CACHED"  # Use sentinel value to distinguish from cached None


def _store_in_cache(cache_key: str, data):
    """Store data in cache with timestamp."""
    _request_cache[cache_key] = (datetime.now(), data)

    # Clean up expired cache entries to prevent memory issues
    _cleanup_cache()


def _cleanup_cache():
    """Remove expired entries from cache."""
    current_time = datetime.now()
    keys_to_remove = []

    for key, (cached_time, _) in _request_cache.items():
        if (current_time - cached_time).total_seconds() > CACHE_DURATION:
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del _request_cache[key]


def _throttle_request(ticker: str):
    """Ensure minimum time between requests for the same ticker."""
    current_time = time.time()
    last_time = _last_request_time.get(ticker, 0)

    time_since_last = current_time - last_time
    if time_since_last < MIN_REQUEST_INTERVAL:
        sleep_time = MIN_REQUEST_INTERVAL - time_since_last
        time.sleep(sleep_time)

    _last_request_time[ticker] = time.time()


def _retry_on_rate_limit(func, *args, max_retries=3, **kwargs):
    """Retry a function with exponential backoff on rate limit errors."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate limited" in str(e):
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5  # 0.5, 1, 2 seconds
                    logging.warning(
                        f"Rate limited, waiting {wait_time} seconds before retry {attempt + 1}")
                    time.sleep(wait_time)
                else:
                    raise e  # Re-raise on final attempt
            else:
                raise e  # Re-raise non-rate-limit errors immediately


class YahooFinanceTool:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_ticker_calendar_cached(self, ticker: str):
        """Get ticker calendar with caching and throttling."""
        cache_key = _get_cache_key(ticker, "calendar")

        # Try cache first
        cached_data = _get_from_cache(cache_key)
        if cached_data != "NOT_CACHED":
            self.logger.info(f"Using cached calendar data for {ticker}")
            return cached_data

        # Throttle request
        _throttle_request(ticker)

        # Make request with retry logic
        def _fetch_calendar():
            stock = yf.Ticker(ticker)
            return stock.calendar

        try:
            calendar_data = _retry_on_rate_limit(_fetch_calendar)
            _store_in_cache(cache_key, calendar_data)
            return calendar_data
        except Exception as e:
            self.logger.warning(
                f"Failed to fetch calendar for {ticker} after retries: {e}")
            # Store None in cache to avoid immediate retries
            _store_in_cache(cache_key, None)
            raise e

    def _get_ticker_actions_cached(self, ticker: str):
        """Get ticker actions with caching and throttling."""
        cache_key = _get_cache_key(ticker, "actions")

        # Try cache first
        cached_data = _get_from_cache(cache_key)
        if cached_data != "NOT_CACHED":
            self.logger.info(f"Using cached actions data for {ticker}")
            return cached_data

        # Throttle request
        _throttle_request(ticker)

        # Make request with retry logic
        def _fetch_actions():
            stock = yf.Ticker(ticker)
            return stock.actions

        try:
            actions_data = _retry_on_rate_limit(_fetch_actions)
            _store_in_cache(cache_key, actions_data)
            return actions_data
        except Exception as e:
            self.logger.warning(
                f"Failed to fetch actions for {ticker} after retries: {e}")
            # Store None in cache to avoid immediate retries
            _store_in_cache(cache_key, None)
            raise e

    def fetch_stock_data(self, ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        Fetch stock data from Yahoo Finance with caching and throttling.

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

            # Create cache key based on ticker and date range
            cache_key = _get_cache_key(
                ticker, f"history_{processed_start}_{processed_end}")

            # Try cache first
            cached_data = _get_from_cache(cache_key)
            if cached_data != "NOT_CACHED":
                self.logger.info(f"Using cached stock data for {ticker}")
                return cached_data

            self.logger.info(
                f"Fetching Yahoo Finance data for {ticker} from {processed_start} to {processed_end}")

            # Throttle request
            _throttle_request(ticker)

            # Make request with retry logic
            def _fetch_history():
                stock = yf.Ticker(ticker)
                return stock.history(start=processed_start, end=processed_end)

            df = _retry_on_rate_limit(_fetch_history)

            if df.empty:
                self.logger.warning(f"No data fetched for {ticker}")
                result = pd.DataFrame()
            else:
                result = df[['Open', 'High', 'Low', 'Close', 'Volume']]
                result = localize_df(result, get_default_timezone())

            # Cache the result
            _store_in_cache(cache_key, result)
            return result

        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate limited" in str(e):
                self.logger.warning(
                    f"Rate limited while fetching stock data for {ticker}: {e}")
                # Return empty DataFrame with error info
                return pd.DataFrame()
            else:
                self.logger.error(f"Error fetching Yahoo Finance data: {e}")
                return pd.DataFrame()

    def fetch_corporate_events(self, ticker: str, days_ahead: int = 30, days_back: int = 0):
        """
        Fetch corporate events (earnings dates, dividend dates) from Yahoo Finance.
        Can fetch both upcoming events and recent historical events.

        Args:
            ticker: Stock symbol to fetch events for
            days_ahead: Number of days ahead to look for upcoming events (default: 30)
            days_back: Number of days back to look for historical events (default: 0)
                      If > 0, will fetch historical dividends and actions

        Returns:
            pd.DataFrame: DataFrame containing events within the specified timeframe
                         Columns: 'Symbol', 'Event_Type', 'Event_Date', 'Data_Source'
        """
        try:
            if days_back > 0:
                self.logger.info(
                    f"Fetching corporate events for {ticker} (looking {days_back} days back and {days_ahead} days ahead)")
            else:
                self.logger.info(
                    f"Fetching corporate events for {ticker} (looking {days_ahead} days ahead)")

            events_list = []

            # Calculate date ranges for filtering events
            today = datetime.now()
            cutoff_date_future = today + timedelta(days=days_ahead)
            cutoff_date_past = today - \
                timedelta(days=days_back) if days_back > 0 else today

            try:
                cal = self._get_ticker_calendar_cached(ticker)

                # Handle different response formats from Yahoo Finance API
                if cal is not None and not cal.empty:
                    # Try transposing if it's a DataFrame
                    if hasattr(cal, 'T'):
                        cal = cal.T

                    # Process upcoming earnings date
                    if "Earnings Date" in cal.index:
                        earnings_date = cal.loc["Earnings Date"].iloc[0]
                        # Only include if within our future time window
                        if earnings_date <= cutoff_date_future:
                            events_list.append({
                                'Symbol': ticker,
                                'Event_Type': 'Earnings',
                                'Event_Date': earnings_date,
                                'Data_Source': 'Yahoo Finance'
                            })
                            self.logger.info(
                                f"Found upcoming earnings date for {ticker}: {earnings_date}")

                    # Process upcoming ex-dividend date
                    if "Ex-Dividend Date" in cal.index:
                        ex_div_date = cal.loc["Ex-Dividend Date"].iloc[0]
                        # Only include if within our future time window
                        if ex_div_date <= cutoff_date_future:
                            events_list.append({
                                'Symbol': ticker,
                                'Event_Type': 'Ex-Dividend',
                                'Event_Date': ex_div_date,
                                'Data_Source': 'Yahoo Finance'
                            })
                            self.logger.info(
                                f"Found upcoming ex-dividend date for {ticker}: {ex_div_date}")
                else:
                    self.logger.warning(
                        f"No calendar data available for {ticker}")

                self.logger.info(
                    f"Found {len(events_list)} upcoming events for {ticker} within {days_ahead} days")

            except Exception as cal_error:
                self.logger.warning(
                    f"Could not fetch calendar data for {ticker}: {cal_error}")
                # Continue with empty events list

            # Fetch historical events if requested
            if days_back > 0:
                try:
                    self.logger.info(
                        f"Fetching historical corporate actions for {ticker} over last {days_back} days")

                    # Get historical actions (dividends, splits)
                    actions = self._get_ticker_actions_cached(ticker)
                    if actions is not None and not actions.empty:
                        # Filter actions within our time window
                        recent_actions = actions[actions.index >=
                                                 cutoff_date_past]

                        for date, row in recent_actions.iterrows():
                            # Add dividend events
                            if 'Dividends' in row and row['Dividends'] > 0:
                                events_list.append({
                                    'Symbol': ticker,
                                    'Event_Type': 'Dividend',
                                    'Event_Date': date,
                                    'Data_Source': 'Yahoo Finance',
                                    'Amount': row['Dividends']
                                })
                                self.logger.info(
                                    f"Found historical dividend for {ticker} on {date}: ${row['Dividends']}")

                            # Add stock split events
                            if 'Stock Splits' in row and row['Stock Splits'] != 1.0 and row['Stock Splits'] > 0:
                                events_list.append({
                                    'Symbol': ticker,
                                    'Event_Type': 'Stock Split',
                                    'Event_Date': date,
                                    'Data_Source': 'Yahoo Finance',
                                    'Split_Ratio': row['Stock Splits']
                                })
                                self.logger.info(
                                    f"Found stock split for {ticker} on {date}: {row['Stock Splits']}:1")

                except Exception as actions_error:
                    self.logger.warning(
                        f"Could not fetch historical actions for {ticker}: {actions_error}")
                    # Continue without historical data

            # Convert to DataFrame
            if events_list:
                return pd.DataFrame(events_list)
            else:
                # Return empty DataFrame with proper columns
                return pd.DataFrame(columns=['Symbol', 'Event_Type', 'Event_Date', 'Data_Source'])

        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate limited" in str(e):
                self.logger.warning(
                    f"Yahoo Finance rate limit hit for {ticker}: {e}")
                # Return informative DataFrame about rate limiting
                return pd.DataFrame({
                    'Symbol': [ticker],
                    'Event_Type': ['Rate Limit Error'],
                    'Event_Date': [datetime.now()],
                    'Data_Source': ['Yahoo Finance'],
                    'Message': [f'Rate limited after retries. Cached data may be available in {CACHE_DURATION} seconds. Try using Finnhub tools as alternative.']
                })
            else:
                self.logger.error(
                    f"Error fetching corporate events for {ticker}: {e}")
                return pd.DataFrame(columns=['Symbol', 'Event_Type', 'Event_Date', 'Data_Source'])
