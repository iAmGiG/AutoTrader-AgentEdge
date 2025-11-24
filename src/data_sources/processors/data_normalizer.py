"""
Data normalization utilities for standardizing data from different sources into a common schema.
"""

import logging
import re
from datetime import datetime  # TODO utilze date_utils.py
from typing import Optional

import pandas as pd

# Define common schemas

# Schema for news/text data
NEWS_SCHEMA = {
    "timestamp": "datetime64[ns]",  # When the article/data was published
    "title": "str",  # Article title or headline
    "content": "str",  # Main content text
    "source": "str",  # Source of the content (e.g., "Bloomberg", "Reuters")
    "url": "str",  # URL to the original content
    "sentiment_score": "float",  # Pre-calculated sentiment score if available
    "keywords": "object",  # List of keywords or tags
    # News category (e.g., "Economy", "Markets", "Technology")
    "category": "str",
}

# Schema for market data
MARKET_SCHEMA = {
    "timestamp": "datetime64[ns]",  # Date/time of the data point
    "symbol": "str",  # Stock/asset symbol
    "open": "float",  # Opening price
    "high": "float",  # High price
    "low": "float",  # Low price
    "close": "float",  # Closing price
    "volume": "float",  # Trading volume
    "source": "str",  # Data source (e.g., "Yahoo", "AlphaVantage")
}

# Schema for options data (Issue #373)
OPTIONS_SCHEMA = {
    "symbol": "str",  # Underlying symbol
    "strike": "float",  # Strike price
    "option_type": "str",  # 'call' or 'put'
    "expiration": "datetime64[ns]",  # Expiration date
    "bid": "float",  # Bid price
    "ask": "float",  # Ask price
    "last": "float",  # Last trade price
    "volume": "int",  # Contract volume
    "open_interest": "int",  # Open interest
    "implied_volatility": "float",  # IV
    "delta": "float",  # Delta
    "gamma": "float",  # Gamma
    "theta": "float",  # Theta
    "vega": "float",  # Vega
    "rho": "float",  # Rho
    "underlying_price": "float",  # Spot price
    "contract_symbol": "str",  # Contract identifier
    "source": "str",  # Data provider
}

# Schema for economic data (from FRED and similar sources)
ECONOMIC_SCHEMA = {
    "timestamp": "datetime64[ns]",  # Date/time of the data point
    "indicator": "str",  # Economic indicator name/code (e.g., "GDP", "UNRATE")
    "value": "float",  # Value of the indicator
    # Units of measurement (e.g., "Percent", "Billions of Dollars")
    "units": "str",
    "frequency": "str",  # Data frequency (e.g., "Monthly", "Quarterly")
    "title": "str",  # Full title/description of the indicator
    "source": "str",  # Data source (e.g., "FRED", "BEA")
}


def create_empty_news_df() -> pd.DataFrame:
    """Create an empty DataFrame with the standard news schema."""
    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in NEWS_SCHEMA.items()})
    return df


def create_empty_market_df() -> pd.DataFrame:
    """Create an empty DataFrame with the standard market schema."""
    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in MARKET_SCHEMA.items()})
    return df


def create_empty_economic_df() -> pd.DataFrame:
    """Create an empty DataFrame with the standard economic data schema."""
    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in ECONOMIC_SCHEMA.items()})
    return df


def standardize_indicator_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename indicator columns to `INDICATOR_param` format."""
    rename_map = {}
    pattern = re.compile(r"([A-Za-z]+)(\d+)$")
    for col in df.columns:
        m = pattern.match(col)
        if m:
            rename_map[col] = f"{m.group(1).upper()}_{m.group(2)}"
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def normalize_newsapi_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize data from NewsHeadlineTool to the common news schema.

    Args:
        raw_df: Raw DataFrame returned by NewsHeadlineTool

    Returns:
        Normalized DataFrame following the common schema
    """
    if raw_df.empty:
        return create_empty_news_df()

    normalized_df = pd.DataFrame()

    # Map columns to standard schema
    normalized_df["timestamp"] = raw_df["Timestamp"]
    normalized_df["title"] = raw_df["Headline"]
    normalized_df["content"] = raw_df["Content"]
    normalized_df["source"] = raw_df["Source"]
    normalized_df["url"] = raw_df["URL"]
    normalized_df["sentiment_score"] = raw_df["Sentiment Score"]

    # Add empty columns for missing fields
    normalized_df["keywords"] = None
    normalized_df["category"] = "General"  # Default category

    return normalized_df


def normalize_finnhub_data(raw_data: list) -> pd.DataFrame:
    """
    Normalize data from FinnHubTool to the common news schema.

    Args:
        raw_data: Raw list of article dictionaries returned by FinnHubTool

    Returns:
        Normalized DataFrame following the common schema
    """
    if not raw_data:
        return create_empty_news_df()

    normalized_data = []

    for article in raw_data:
        # Extract fields with appropriate fallbacks
        timestamp = article.get("datetime", None)
        if timestamp:
            # Convert Unix timestamp to datetime if needed
            if isinstance(timestamp, int):
                timestamp = datetime.fromtimestamp(timestamp)

        entry = {
            "timestamp": timestamp,
            "title": article.get("headline", article.get("title", "")),
            "content": article.get("summary", article.get("description", "")),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "sentiment_score": None,  # Finnhub doesn't provide sentiment scores directly
            "keywords": article.get("related", article.get("category", "").split(",")),
            "category": article.get("category", "General"),
        }
        normalized_data.append(entry)

    return pd.DataFrame(normalized_data)


def normalize_yahoo_finance_data(raw_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Normalize data from YahooFinanceTool to the common market schema.

    Args:
        raw_df: Raw DataFrame returned by YahooFinanceTool
        symbol: The stock symbol for the data

    Returns:
        Normalized DataFrame following the common market schema
    """
    if raw_df.empty:
        return create_empty_market_df()

    # Create new DataFrame with normalized schema
    normalized_df = pd.DataFrame()

    # Map columns to standard schema
    normalized_df["timestamp"] = raw_df.index  # Yahoo uses DatetimeIndex
    normalized_df["symbol"] = symbol
    normalized_df["open"] = raw_df["Open"]
    normalized_df["high"] = raw_df["High"]
    normalized_df["low"] = raw_df["Low"]
    normalized_df["close"] = raw_df["Close"]
    normalized_df["volume"] = raw_df["Volume"]
    normalized_df["source"] = "Yahoo Finance"

    return normalized_df


def normalize_alpha_vantage_data(raw_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Normalize data from AlphaVantageTool to the common market schema.

    Args:
        raw_df: Raw DataFrame returned by AlphaVantageTool
        symbol: The stock symbol for the data

    Returns:
        Normalized DataFrame following the common market schema
    """
    if raw_df.empty:
        return create_empty_market_df()

    normalized_df = pd.DataFrame()

    # Check column names since Alpha Vantage might use different column names
    # based on the specific API endpoint used

    # Time series data typically has format:
    # timestamp, open, high, low, close, volume (may be capitalized)
    if "1. open" in raw_df.columns:
        # Map Alpha Vantage's numbered column format
        column_map = {
            "1. open": "open",
            "2. high": "high",
            "3. low": "low",
            "4. close": "close",
            "5. volume": "volume",
        }

        for av_col, norm_col in column_map.items():
            if av_col in raw_df.columns:
                normalized_df[norm_col] = raw_df[av_col]

        # Alpha Vantage typically uses index as timestamp
        normalized_df["timestamp"] = raw_df.index

    elif "open" in raw_df.columns or "Open" in raw_df.columns:
        # Handle more standard column names
        col_mapping = {
            "open": "open",
            "Open": "open",
            "high": "high",
            "High": "high",
            "low": "low",
            "Low": "low",
            "close": "close",
            "Close": "close",
            "volume": "volume",
            "Volume": "volume",
        }

        for raw_col, norm_col in col_mapping.items():
            if raw_col in raw_df.columns:
                normalized_df[norm_col] = raw_df[raw_col]

        # Set timestamp from index if needed
        if "timestamp" not in normalized_df and "date" not in raw_df.columns:
            normalized_df["timestamp"] = raw_df.index
        elif "date" in raw_df.columns:
            normalized_df["timestamp"] = raw_df["date"]

    # Add symbol and source if not present
    normalized_df["symbol"] = symbol
    normalized_df["source"] = "Alpha Vantage"

    return normalized_df


def normalize_market_data_for_sentiment(
    market_df: pd.DataFrame,
) -> Optional[pd.DataFrame]:
    """
    Convert market data to a format usable for sentiment analysis or skip it.
    This function either:
    1. Returns None to indicate that market data should be skipped from sentiment pipeline
    2. Transforms market data into a news-compatible format

    For now, we'll skip market data in the sentiment pipeline since it doesn't
    contain text that can be directly analyzed for sentiment.

    Args:
        market_df: Normalized market data DataFrame

    Returns:
        None to indicate skipping, or a transformed DataFrame
    """
    # For now, we'll skip market data for sentiment analysis
    return None


def normalize_fred_data(raw_df: pd.DataFrame, indicator: str = "Unknown") -> pd.DataFrame:
    """
    Normalize data from FRED to the common economic schema.

    Args:
        raw_df: Raw DataFrame returned by FREDDataTool
        indicator: The economic indicator name or code

    Returns:
        Normalized DataFrame following the common economic schema
    """
    if raw_df.empty:
        return create_empty_economic_df()

    normalized_df = pd.DataFrame()

    # Check and map columns based on what's available in the raw dataframe
    if "Date" in raw_df.columns and "Value" in raw_df.columns:
        # Standard FRED format from get_series or get_indicator
        normalized_df["timestamp"] = pd.to_datetime(raw_df["Date"])
        normalized_df["value"] = raw_df["Value"]

        # Extract metadata if available
        normalized_df["indicator"] = raw_df.get("Series ID", indicator)
        normalized_df["title"] = raw_df.get("Title", indicator)
        normalized_df["units"] = raw_df.get("Units", "Unknown")
        normalized_df["frequency"] = raw_df.get("Frequency", "Unknown")

    elif "Date" in raw_df.columns:
        # This could be a yield curve or other multi-column dataset
        normalized_df["timestamp"] = pd.to_datetime(raw_df["Date"])

        # For yield curve, we'll use a different approach - maintain original columns
        # but ensure we have the required economic schema columns
        normalized_df["indicator"] = indicator
        normalized_df["title"] = f"{indicator} Data"
        normalized_df["units"] = "Percent"  # Most FRED data are in percent
        normalized_df["frequency"] = "Daily"  # Most yield curve data are daily

        # Handle the value column specially for yield curve
        # We'll use the 10Y as a representative value
        if "10Y" in raw_df.columns:
            normalized_df["value"] = raw_df["10Y"]
        else:
            # If there's no 10Y, use the first non-Date column
            value_cols = [col for col in raw_df.columns if col != "Date"]
            if value_cols:
                normalized_df["value"] = raw_df[value_cols[0]]
            else:
                normalized_df["value"] = None

    else:
        # Try to handle other formats or return empty
        return create_empty_economic_df()

    # Set source to FRED
    normalized_df["source"] = "FRED"

    return normalized_df


def normalize_alpaca_data(raw_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Normalize data from Alpaca Markets API to the common market schema.

    Args:
        raw_df: Raw DataFrame returned by Alpaca API
        symbol: The stock symbol for the data

    Returns:
        Normalized DataFrame following the common market schema
    """
    if raw_df.empty:
        return create_empty_market_df()

    normalized_df = pd.DataFrame()

    # Handle Alpaca's column format
    # Alpaca uses: t (timestamp), o (open), h (high), l (low), c (close), v (volume)
    # Also: vw (VWAP), n (trade_count)

    # Map Alpaca columns to standard schema
    if "t" in raw_df.columns:
        # Raw Alpaca format
        column_mapping = {
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
            "n": "trade_count",
        }

        for alpaca_col, norm_col in column_mapping.items():
            if alpaca_col in raw_df.columns:
                if norm_col == "timestamp":
                    # Convert Alpaca timestamp (RFC3339) to datetime
                    normalized_df[norm_col] = pd.to_datetime(raw_df[alpaca_col])
                else:
                    normalized_df[norm_col] = raw_df[alpaca_col]

    elif "timestamp" in raw_df.columns or "date" in raw_df.columns:
        # Already normalized or partially normalized format
        time_col = "timestamp" if "timestamp" in raw_df.columns else "date"
        normalized_df["timestamp"] = pd.to_datetime(raw_df[time_col])

        # Map standard column names
        std_columns = ["open", "high", "low", "close", "volume"]
        for col in std_columns:
            if col in raw_df.columns:
                normalized_df[col] = raw_df[col]
            elif col.title() in raw_df.columns:
                normalized_df[col] = raw_df[col.title()]

        # Optional columns
        if "vwap" in raw_df.columns:
            normalized_df["vwap"] = raw_df["vwap"]
        if "trade_count" in raw_df.columns:
            normalized_df["trade_count"] = raw_df["trade_count"]

    # Add symbol and source
    normalized_df["symbol"] = symbol
    normalized_df["source"] = "alpaca"

    # Fill missing optional columns
    if "vwap" not in normalized_df.columns:
        normalized_df["vwap"] = normalized_df.get("close", None)
    if "trade_count" not in normalized_df.columns:
        normalized_df["trade_count"] = 0

    return normalized_df


def normalize_data_for_sentiment(
    df: pd.DataFrame, data_type: str, **kwargs
) -> Optional[pd.DataFrame]:
    """
    Main entry point for normalizing any data source for sentiment analysis.

    Args:
        df: Raw DataFrame from a data source
        data_type: Type of data ('news', 'market', 'economic', etc.)
        **kwargs: Additional arguments like symbol for market data

    Returns:
        Normalized DataFrame or None if data should be skipped
    """
    if df.empty:
        return create_empty_news_df()

    if data_type == "news_api":
        return normalize_newsapi_data(df)
    elif data_type == "finnhub":
        return normalize_finnhub_data(df)
    elif data_type == "yahoo_finance":
        # Market data isn't directly usable for sentiment, so skip it
        # or we could transform it if needed
        market_df = normalize_yahoo_finance_data(df, kwargs.get("symbol", "UNKNOWN"))
        return normalize_market_data_for_sentiment(market_df)
    elif data_type == "alpha_vantage":
        market_df = normalize_alpha_vantage_data(df, kwargs.get("symbol", "UNKNOWN"))
        return normalize_market_data_for_sentiment(market_df)
    elif data_type == "alpaca":
        # Alpaca market data isn't directly usable for sentiment
        market_df = normalize_alpaca_data(df, kwargs.get("symbol", "UNKNOWN"))
        return normalize_market_data_for_sentiment(market_df)
    elif data_type == "fred":
        # FRED economic data isn't directly usable for sentiment without transformation
        # For now, we'll just return None to skip it
        return None
    else:
        # Unknown data source
        return None


# === OPTIONS DATA NORMALIZATION (Issue #373) ===


def create_empty_options_df() -> pd.DataFrame:
    """Create an empty DataFrame with the standard options schema."""
    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in OPTIONS_SCHEMA.items()})
    return df


def normalize_polygon_options(raw_df: pd.DataFrame, symbol: str, trading_date: str) -> pd.DataFrame:
    """
    Normalize options data from Polygon.io to common schema.

    Args:
        raw_df: Raw options DataFrame from Polygon
        symbol: Underlying symbol
        trading_date: Trading date

    Returns:
        Normalized DataFrame following OPTIONS_SCHEMA
    """
    if raw_df.empty:
        return create_empty_options_df()

    normalized_df = pd.DataFrame()

    # Map Polygon columns to standard schema
    # Polygon uses: strike, type/option_type, expiration, bid, ask, last, volume, oi, iv, greeks
    column_mapping = {
        "strike": "strike",
        "type": "option_type",
        "option_type": "option_type",
        "expiration": "expiration",
        "expiration_date": "expiration",
        "bid": "bid",
        "ask": "ask",
        "last": "last",
        "last_price": "last",
        "volume": "volume",
        "oi": "open_interest",
        "open_interest": "open_interest",
        "iv": "implied_volatility",
        "implied_volatility": "implied_volatility",
        "delta": "delta",
        "gamma": "gamma",
        "theta": "theta",
        "vega": "vega",
        "rho": "rho",
        "underlying_price": "underlying_price",
        "contract_symbol": "contract_symbol",
        "ticker": "contract_symbol",
    }

    for raw_col, norm_col in column_mapping.items():
        if raw_col in raw_df.columns:
            normalized_df[norm_col] = raw_df[raw_col]

    # Add symbol and source
    normalized_df["symbol"] = symbol
    normalized_df["source"] = "polygon"

    # Normalize option_type to lowercase
    if "option_type" in normalized_df.columns:
        normalized_df["option_type"] = normalized_df["option_type"].str.lower()

    # Convert expiration to datetime
    if "expiration" in normalized_df.columns:
        normalized_df["expiration"] = pd.to_datetime(normalized_df["expiration"])

    return normalized_df


def normalize_alpha_vantage_options(
    raw_df: pd.DataFrame, symbol: str, trading_date: str
) -> pd.DataFrame:
    """
    Normalize options data from Alpha Vantage to common schema.

    Args:
        raw_df: Raw options DataFrame from Alpha Vantage
        symbol: Underlying symbol
        trading_date: Trading date

    Returns:
        Normalized DataFrame following OPTIONS_SCHEMA

    Note:
        Alpha Vantage options API format may vary. This handles common formats.
    """
    if raw_df.empty:
        return create_empty_options_df()

    normalized_df = pd.DataFrame()

    # Alpha Vantage may use different column names
    column_mapping = {
        "strike": "strike",
        "strike_price": "strike",
        "type": "option_type",
        "option_type": "option_type",
        "contractID": "contract_symbol",
        "contract_id": "contract_symbol",
        "expiration": "expiration",
        "expiration_date": "expiration",
        "bid": "bid",
        "ask": "ask",
        "last": "last",
        "lastPrice": "last",
        "volume": "volume",
        "openInterest": "open_interest",
        "open_interest": "open_interest",
        "impliedVolatility": "implied_volatility",
        "delta": "delta",
        "gamma": "gamma",
        "theta": "theta",
        "vega": "vega",
        "rho": "rho",
    }

    for raw_col, norm_col in column_mapping.items():
        if raw_col in raw_df.columns:
            normalized_df[norm_col] = raw_df[raw_col]

    # Add symbol and source
    normalized_df["symbol"] = symbol
    normalized_df["source"] = "alpha_vantage"

    # Normalize option_type
    if "option_type" in normalized_df.columns:
        normalized_df["option_type"] = normalized_df["option_type"].str.lower()

    # Convert expiration to datetime
    if "expiration" in normalized_df.columns:
        normalized_df["expiration"] = pd.to_datetime(normalized_df["expiration"])

    return normalized_df


def normalize_alpaca_options(raw_df: pd.DataFrame, symbol: str, trading_date: str) -> pd.DataFrame:
    """
    Normalize options data from Alpaca to common schema.

    Args:
        raw_df: Raw options DataFrame from Alpaca
        symbol: Underlying symbol
        trading_date: Trading date

    Returns:
        Normalized DataFrame following OPTIONS_SCHEMA
    """
    if raw_df.empty:
        return create_empty_options_df()

    normalized_df = pd.DataFrame()

    # Alpaca column mapping
    column_mapping = {
        "strike_price": "strike",
        "strike": "strike",
        "type": "option_type",
        "option_type": "option_type",
        "expiration_date": "expiration",
        "expiration": "expiration",
        "symbol": "contract_symbol",
        "contract_symbol": "contract_symbol",
        "bid_price": "bid",
        "bid": "bid",
        "ask_price": "ask",
        "ask": "ask",
        "last_price": "last",
        "last": "last",
        "volume": "volume",
        "open_interest": "open_interest",
        "implied_volatility": "implied_volatility",
        "greeks.delta": "delta",
        "delta": "delta",
        "greeks.gamma": "gamma",
        "gamma": "gamma",
        "greeks.theta": "theta",
        "theta": "theta",
        "greeks.vega": "vega",
        "vega": "vega",
        "greeks.rho": "rho",
        "rho": "rho",
    }

    for raw_col, norm_col in column_mapping.items():
        if raw_col in raw_df.columns:
            normalized_df[norm_col] = raw_df[raw_col]

    # Add symbol and source
    normalized_df["symbol"] = symbol
    normalized_df["source"] = "alpaca"

    # Normalize option_type
    if "option_type" in normalized_df.columns:
        normalized_df["option_type"] = normalized_df["option_type"].str.lower()

    # Convert expiration to datetime
    if "expiration" in normalized_df.columns:
        normalized_df["expiration"] = pd.to_datetime(normalized_df["expiration"])

    return normalized_df


def normalize_options_data(
    raw_df: pd.DataFrame, symbol: str, trading_date: str, source: str
) -> pd.DataFrame:
    """
    Main entry point for normalizing options data from any provider.

    Args:
        raw_df: Raw DataFrame from options provider
        symbol: Underlying symbol
        trading_date: Trading date
        source: Data source ('polygon', 'alpha_vantage', 'alpaca')

    Returns:
        Normalized DataFrame following OPTIONS_SCHEMA

    Example:
        >>> raw_options = fetch_from_provider(...)
        >>> normalized = normalize_options_data(raw_options, "SPY", "2024-01-15", "polygon")
    """
    if raw_df.empty:
        return create_empty_options_df()

    if source == "polygon":
        return normalize_polygon_options(raw_df, symbol, trading_date)
    elif source == "alpha_vantage":
        return normalize_alpha_vantage_options(raw_df, symbol, trading_date)
    elif source == "alpaca":
        return normalize_alpaca_options(raw_df, symbol, trading_date)
    else:
        # Unknown source, try generic normalization
        logging.warning(f"Unknown options source: {source}, using generic normalization")
        return normalize_polygon_options(raw_df, symbol, trading_date)
