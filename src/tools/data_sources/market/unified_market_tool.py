"""
Unified Market Data Tool using CacheAdapter.

Routes all market data requests through the unified cache system,
regardless of source (Polygon, Alpha Vantage, etc.).
"""

import pandas as pd
from typing import Optional
from datetime import datetime

from src.tools.cache import cache_adapter
from src.tools.data_sources.market.polygon_historical_tool import PolygonHistoricalData  
from src.tools.data_sources.market.alpha_vantage_market import AlphaVantageMarketTool


def fetch_unified_market_data(
    symbol: str = "AAPL",
    start_date: str = "2024-01-01", 
    end_date: str = "2024-12-31",
    source: str = "auto"
) -> pd.DataFrame:
    """
    Fetch market data using unified cache system.
    
    Args:
        symbol: Stock symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD) 
        source: Data source ("auto", "polygon", "alpha_vantage")
    
    Returns:
        DataFrame with OHLCV data
    """
    # First try to get from unified cache
    cached_data = cache_adapter.get_market_data(symbol, start_date, end_date, source)
    if cached_data is not None:
        return cached_data
    
    # Cache miss - fetch from appropriate source
    if source == "auto":
        # Try Polygon first, fallback to Alpha Vantage
        data = _fetch_from_polygon(symbol, start_date, end_date)
        if data is None or data.empty:
            data = _fetch_from_alpha_vantage(symbol, start_date, end_date)
            source = "alpha_vantage"
        else:
            source = "polygon"
    elif source == "polygon":
        data = _fetch_from_polygon(symbol, start_date, end_date)
    elif source == "alpha_vantage":
        data = _fetch_from_alpha_vantage(symbol, start_date, end_date)
    else:
        raise ValueError(f"Unknown source: {source}")
    
    # Store in unified cache for future use
    if data is not None and not data.empty:
        cache_adapter.set_market_data(symbol, start_date, end_date, source, data)
    
    return data if data is not None else pd.DataFrame()


def _fetch_from_polygon(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Fetch from Polygon.io API."""
    try:
        polygon_client = PolygonHistoricalData()
        data = polygon_client.fetch_historical_prices(symbol, start_date, end_date)
        return data
    except Exception as e:
        print(f"Polygon fetch failed: {e}")
        return None


def _fetch_from_alpha_vantage(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Fetch from Alpha Vantage API."""
    try:
        av_client = AlphaVantageMarketTool()
        data = av_client.fetch_stock_data(symbol, start_date, end_date)
        return data
    except Exception as e:
        print(f"Alpha Vantage fetch failed: {e}")
        return None