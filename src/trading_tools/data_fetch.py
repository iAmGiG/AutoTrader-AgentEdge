"""
Market Data Fetching - Pure Functions

Clean interface for market data retrieval with caching.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Add data sources to path
sys.path.append(str(Path(__file__).parent.parent / "data_sources"))


def fetch_market_data(
    symbol: str, start_date: str, end_date: str, use_cache: bool = True
) -> Optional[pd.DataFrame]:
    """
    Fetch market data for a symbol and date range.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        use_cache: Whether to use cached data first

    Returns:
        DataFrame with OHLCV data or None if failed
    """
    try:
        if use_cache:
            cached_data = get_cached_data(symbol, start_date, end_date)
            if cached_data is not None:
                return cached_data

        # Try to use existing market data tools
        from data_sources.sources.market.unified_market_tool import UnifiedMarketTool

        market_tool = UnifiedMarketTool()
        data = market_tool.get_historical_data(symbol, start_date, end_date)

        if data is not None and not data.empty:
            # Standardize column names
            if "close" in data.columns:
                data.rename(columns={"close": "Close"}, inplace=True)
            if "open" in data.columns:
                data.rename(columns={"open": "Open"}, inplace=True)
            if "high" in data.columns:
                data.rename(columns={"high": "High"}, inplace=True)
            if "low" in data.columns:
                data.rename(columns={"low": "Low"}, inplace=True)
            if "volume" in data.columns:
                data.rename(columns={"volume": "Volume"}, inplace=True)

            return data

    except Exception as e:
        print(f"Error fetching market data for {symbol}: {e}")

    return None


def get_cached_data(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    Get cached market data if available.

    Args:
        symbol: Stock symbol
        start_date: Start date
        end_date: End date

    Returns:
        Cached DataFrame or None
    """
    try:
        # Check cache directory structure
        cache_dir = Path(".cache/market_data")
        if not cache_dir.exists():
            return None

        # Look for cached files
        for cache_file in cache_dir.glob(f"{symbol}_*.csv"):
            try:
                cached_df = pd.read_csv(cache_file, index_col=0, parse_dates=True)

                # Check if date range is covered
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)

                if cached_df.index.min() <= start_dt and cached_df.index.max() >= end_dt:

                    # Filter to requested range
                    filtered = cached_df[
                        (cached_df.index >= start_dt) & (cached_df.index <= end_dt)
                    ]

                    if not filtered.empty:
                        return filtered

            except Exception:
                continue

    except Exception as e:
        print(f"Error accessing cached data: {e}")

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


def get_current_price(symbol: str) -> Optional[float]:
    """
    Get current price for a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        Current price or None
    """
    try:
        # Get recent data (last few days)
        import datetime

        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=5)

        data = fetch_market_data(
            symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), use_cache=False
        )

        if data is not None and not data.empty:
            return float(data["Close"].iloc[-1])

    except Exception as e:
        print(f"Error getting current price for {symbol}: {e}")

    return None
