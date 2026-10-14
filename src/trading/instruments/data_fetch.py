"""
Market Data Fetching - Pure Functions

Clean interface for market data retrieval (cached by the unified market data tool).
"""

from typing import Dict, List, Optional

import pandas as pd

from src.market_data.unified_market_tool import fetch_unified_market_data

_OHLCV_NAMES = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}


def fetch_market_data(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "1Day",
) -> Optional[pd.DataFrame]:
    """
    Fetch market data for a symbol and date range.

    Caching happens in fetch_unified_market_data (which skips the cache for the
    current trading day during market hours).

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        timeframe: Bar timeframe (e.g., "1Min", "5Min", "1Hour", "1Day")

    Returns:
        DataFrame with OHLCV data (capitalized column names) or None if failed
    """
    try:
        data = fetch_unified_market_data(symbol, start_date, end_date, timeframe=timeframe)

        if data is not None and not data.empty:
            # Standardize column names on a copy, so a cached frame is never changed
            return data.rename(columns=_OHLCV_NAMES)

    except Exception as e:
        print(f"Error fetching market data for {symbol}: {e}")

    return None


def fetch_multiple_tickers(
    tickers: List[str], start_date: str, end_date: str
) -> Dict[str, pd.DataFrame]:
    """
    Fetch market data for multiple tickers.

    Args:
        tickers: List of stock symbols
        start_date: Start date
        end_date: End date

    Returns:
        Dictionary mapping ticker to DataFrame
    """
    results = {}

    for ticker in tickers:
        data = fetch_market_data(ticker, start_date, end_date)
        if data is not None:
            results[ticker] = data

    return results
