"""
Data normalization utilities for standardizing data from different sources into a common schema.
"""

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, Union


# Define common schemas

# Schema for news/text data
NEWS_SCHEMA = {
    'timestamp': 'datetime64[ns]',     # When the article/data was published
    'title': 'str',                    # Article title or headline
    'content': 'str',                  # Main content text
    'source': 'str',                   # Source of the content (e.g., "Bloomberg", "Reuters")
    'url': 'str',                      # URL to the original content
    'sentiment_score': 'float',        # Pre-calculated sentiment score if available
    'keywords': 'object',              # List of keywords or tags
    'category': 'str'                  # News category (e.g., "Economy", "Markets", "Technology")
}

# Schema for market data
MARKET_SCHEMA = {
    'timestamp': 'datetime64[ns]',     # Date/time of the data point
    'symbol': 'str',                   # Stock/asset symbol
    'open': 'float',                   # Opening price
    'high': 'float',                   # High price
    'low': 'float',                    # Low price
    'close': 'float',                  # Closing price
    'volume': 'float',                 # Trading volume
    'source': 'str'                    # Data source (e.g., "Yahoo", "AlphaVantage")
}


def create_empty_news_df() -> pd.DataFrame:
    """Create an empty DataFrame with the standard news schema."""
    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in NEWS_SCHEMA.items()})
    return df


def create_empty_market_df() -> pd.DataFrame:
    """Create an empty DataFrame with the standard market schema."""
    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in MARKET_SCHEMA.items()})
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
    normalized_df['timestamp'] = raw_df['Timestamp']
    normalized_df['title'] = raw_df['Headline']
    normalized_df['content'] = raw_df['Content']
    normalized_df['source'] = raw_df['Source']
    normalized_df['url'] = raw_df['URL']
    normalized_df['sentiment_score'] = raw_df['Sentiment Score']
    
    # Add empty columns for missing fields
    normalized_df['keywords'] = None
    normalized_df['category'] = 'General'  # Default category
    
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
        timestamp = article.get('datetime', None)
        if timestamp:
            # Convert Unix timestamp to datetime if needed
            if isinstance(timestamp, int):
                timestamp = datetime.fromtimestamp(timestamp)
                
        entry = {
            'timestamp': timestamp,
            'title': article.get('headline', article.get('title', '')),
            'content': article.get('summary', article.get('description', '')),
            'source': article.get('source', ''),
            'url': article.get('url', ''),
            'sentiment_score': None,  # Finnhub doesn't provide sentiment scores directly
            'keywords': article.get('related', article.get('category', '').split(',')),
            'category': article.get('category', 'General')
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
    normalized_df['timestamp'] = raw_df.index  # Yahoo uses DatetimeIndex
    normalized_df['symbol'] = symbol
    normalized_df['open'] = raw_df['Open']
    normalized_df['high'] = raw_df['High']
    normalized_df['low'] = raw_df['Low']
    normalized_df['close'] = raw_df['Close']
    normalized_df['volume'] = raw_df['Volume']
    normalized_df['source'] = 'Yahoo Finance'
    
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
    if '1. open' in raw_df.columns:
        # Map Alpha Vantage's numbered column format
        column_map = {
            '1. open': 'open',
            '2. high': 'high',
            '3. low': 'low',
            '4. close': 'close',
            '5. volume': 'volume'
        }
        
        for av_col, norm_col in column_map.items():
            if av_col in raw_df.columns:
                normalized_df[norm_col] = raw_df[av_col]
                
        # Alpha Vantage typically uses index as timestamp
        normalized_df['timestamp'] = raw_df.index
        
    elif 'open' in raw_df.columns or 'Open' in raw_df.columns:
        # Handle more standard column names
        col_mapping = {
            'open': 'open', 'Open': 'open',
            'high': 'high', 'High': 'high',
            'low': 'low', 'Low': 'low',
            'close': 'close', 'Close': 'close',
            'volume': 'volume', 'Volume': 'volume',
        }
        
        for raw_col, norm_col in col_mapping.items():
            if raw_col in raw_df.columns:
                normalized_df[norm_col] = raw_df[raw_col]
                
        # Set timestamp from index if needed
        if 'timestamp' not in normalized_df and 'date' not in raw_df.columns:
            normalized_df['timestamp'] = raw_df.index
        elif 'date' in raw_df.columns:
            normalized_df['timestamp'] = raw_df['date']
    
    # Add symbol and source if not present
    normalized_df['symbol'] = symbol
    normalized_df['source'] = 'Alpha Vantage'
    
    return normalized_df


def normalize_market_data_for_sentiment(market_df: pd.DataFrame) -> Optional[pd.DataFrame]:
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


def normalize_data_for_sentiment(df: pd.DataFrame, data_type: str, **kwargs) -> Optional[pd.DataFrame]:
    """
    Main entry point for normalizing any data source for sentiment analysis.
    
    Args:
        df: Raw DataFrame from a data source
        data_type: Type of data ('news', 'market', etc.)
        **kwargs: Additional arguments like symbol for market data
        
    Returns:
        Normalized DataFrame or None if data should be skipped
    """
    if df.empty:
        return create_empty_news_df()
    
    if data_type == 'news_api':
        return normalize_newsapi_data(df)
    elif data_type == 'finnhub':
        return normalize_finnhub_data(df)
    elif data_type == 'yahoo_finance':
        # Market data isn't directly usable for sentiment, so skip it
        # or we could transform it if needed
        market_df = normalize_yahoo_finance_data(df, kwargs.get('symbol', 'UNKNOWN'))
        return normalize_market_data_for_sentiment(market_df)
    elif data_type == 'alpha_vantage':
        market_df = normalize_alpha_vantage_data(df, kwargs.get('symbol', 'UNKNOWN'))
        return normalize_market_data_for_sentiment(market_df)
    else:
        # Unknown data source
        return None