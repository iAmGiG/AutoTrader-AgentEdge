"""
Polygon.io API integration for historical market data.

This module provides access to historical price data, news, and market events
using the Polygon.io API. The free tier offers 2 years of historical data
with a rate limit of 5 requests per minute.
"""

import os
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
from pathlib import Path
import logging

try:
    from polygon import RESTClient
except ImportError:
    raise ImportError(
        "polygon-api-client is required. Install with: pip install polygon-api-client"
    )

logger = logging.getLogger(__name__)


class PolygonHistoricalData:
    """
    Historical market data fetcher using Polygon.io API.

    Features:
    - Historical OHLCV price data
    - Ticker-specific news articles
    - Market events (earnings, dividends, splits)
    - Built-in rate limiting (5 requests/minute for free tier)
    - Local caching to minimize API calls
    """

    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize Polygon API client with rate limiting.

        Args:
            api_key: Polygon API key (defaults to POLYGON_API_KEY env var)
            cache_dir: Directory for caching data (defaults to .cache/polygon/)
        """
        self.api_key = api_key or os.getenv('POLYGON_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Polygon API key required. Set POLYGON_API_KEY environment variable."
            )

        self.client = RESTClient(api_key=self.api_key)
        # Free tier has lower rate limit - be conservative
        self.rate_limit_delay = float(os.getenv('POLYGON_RATE_LIMIT_DELAY', '15'))
        self.last_request_time = 0
        self.is_free_tier = True  # Assume free tier by default

        # Setup cache directory
        self.cache_dir = Path(cache_dir or os.getenv('POLYGON_CACHE_DIR', '.cache/polygon'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / 'prices').mkdir(exist_ok=True)
        (self.cache_dir / 'news').mkdir(exist_ok=True)
        (self.cache_dir / 'events').mkdir(exist_ok=True)

        logger.info(f"Polygon client initialized with {self.rate_limit_delay}s rate limit")

    def _enforce_rate_limit(self):
        """Enforce rate limiting to stay within API quota."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _get_cache_path(self, cache_type: str, identifier: str) -> Path:
        """Generate cache file path."""
        return self.cache_dir / cache_type / f"{identifier}.json"

    def _load_from_cache(self, cache_path: Path) -> Optional[pd.DataFrame]:
        """Load data from cache if exists and not expired."""
        if not cache_path.exists():
            return None

        try:
            # Check cache age (expire after 24 hours for prices, 1 hour for news)
            cache_age = time.time() - cache_path.stat().st_mtime
            max_age = 86400 if 'prices' in str(cache_path) else 3600

            if cache_age > max_age:
                logger.debug(f"Cache expired: {cache_path}")
                return None

            with open(cache_path, 'r') as f:
                data = json.load(f)

            logger.debug(f"Loaded from cache: {cache_path}")
            return pd.DataFrame(data)

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    def _save_to_cache(self, data: pd.DataFrame, cache_path: Path):
        """Save DataFrame to cache as JSON."""
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert DataFrame to JSON-serializable format
            data_dict = data.to_dict(orient='records')

            with open(cache_path, 'w') as f:
                json.dump(data_dict, f, default=str, indent=2)

            logger.debug(f"Saved to cache: {cache_path}")

        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def fetch_historical_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        timespan: str = 'day',
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV price data for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            timespan: Aggregation timespan (minute, hour, day, week, month)
            use_cache: Whether to use cached data if available

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, vwap
        """
        # Check cache first
        cache_id = f"{ticker}_{start_date}_to_{end_date}_{timespan}"
        cache_path = self._get_cache_path('prices', cache_id)

        if use_cache:
            cached_data = self._load_from_cache(cache_path)
            if cached_data is not None:
                return cached_data

        # Fetch from API
        self._enforce_rate_limit()

        try:
            logger.info(f"Fetching {ticker} prices from {start_date} to {end_date}")

            aggs = self.client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan=timespan,
                from_=start_date,
                to=end_date,
                adjusted=True,
                sort='asc',
                limit=50000
            )

            # Convert to DataFrame
            data = []
            for agg in aggs:
                data.append({
                    'date': datetime.fromtimestamp(agg.timestamp / 1000),
                    'open': agg.open,
                    'high': agg.high,
                    'low': agg.low,
                    'close': agg.close,
                    'volume': agg.volume,
                    'vwap': getattr(agg, 'vwap', None),
                    'transactions': getattr(agg, 'transactions', None)
                })

            df = pd.DataFrame(data)

            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')

                # Save to cache
                self._save_to_cache(df.reset_index(), cache_path)

            return df

        except Exception as e:
            error_msg = str(e)
            if "NOT_AUTHORIZED" in error_msg or "doesn't include" in error_msg:
                logger.warning(
                    f"Free tier limitation for {ticker}: Historical data may not be available. Consider using recent dates or upgrading to paid tier.")
            else:
                logger.error(f"Failed to fetch prices for {ticker}: {e}")
            return pd.DataFrame()

    def fetch_ticker_news(
        self,
        ticker: str,
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch news articles for a specific ticker.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            limit: Maximum number of articles to fetch
            start_date: Optional start date for news
            end_date: Optional end date for news
            use_cache: Whether to use cached data if available

        Returns:
            DataFrame with columns: published_utc, title, article_url, 
            author, description, keywords, tickers
        """
        # Generate cache identifier
        date_range = f"{start_date or 'all'}_{end_date or 'latest'}"
        cache_id = f"{ticker}_news_{date_range}_{limit}"
        cache_path = self._get_cache_path('news', cache_id)

        if use_cache:
            cached_data = self._load_from_cache(cache_path)
            if cached_data is not None:
                return cached_data

        # Fetch from API
        self._enforce_rate_limit()

        try:
            logger.info(f"Fetching news for {ticker} (limit: {limit})")

            # Build request parameters
            params = {
                'ticker': ticker,
                'limit': limit,
                'sort': 'published_utc',
                'order': 'desc'
            }

            if start_date:
                params['published_utc.gte'] = start_date
            if end_date:
                params['published_utc.lte'] = end_date

            news = self.client.list_ticker_news(**params)

            # Convert to DataFrame
            data = []
            for article in news:
                data.append({
                    'published_utc': article.published_utc,
                    'title': article.title,
                    'article_url': article.article_url,
                    'author': article.author,
                    'description': getattr(article, 'description', ''),
                    'keywords': getattr(article, 'keywords', []),
                    'tickers': article.tickers,
                    'amp_url': getattr(article, 'amp_url', ''),
                    'image_url': getattr(article, 'image_url', ''),
                    'publisher': {
                        'name': article.publisher.name,
                        'homepage_url': article.publisher.homepage_url,
                        'logo_url': article.publisher.logo_url,
                        'favicon_url': article.publisher.favicon_url
                    }
                })

            df = pd.DataFrame(data)

            if not df.empty:
                df['published_utc'] = pd.to_datetime(df['published_utc'])
                df = df.sort_values('published_utc', ascending=False)

                # Save to cache
                self._save_to_cache(df, cache_path)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch news for {ticker}: {e}")
            return pd.DataFrame()

    def fetch_market_events(
        self,
        ticker: str,
        event_types: List[str] = ['dividends', 'splits'],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch market events (dividends, splits) for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            event_types: List of event types to fetch
            start_date: Optional start date
            end_date: Optional end date
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary mapping event type to DataFrame
        """
        results = {}

        for event_type in event_types:
            # Generate cache identifier
            date_range = f"{start_date or 'all'}_{end_date or 'latest'}"
            cache_id = f"{ticker}_{event_type}_{date_range}"
            cache_path = self._get_cache_path('events', cache_id)

            if use_cache:
                cached_data = self._load_from_cache(cache_path)
                if cached_data is not None:
                    results[event_type] = cached_data
                    continue

            # Fetch from API
            self._enforce_rate_limit()

            try:
                logger.info(f"Fetching {event_type} for {ticker}")

                if event_type == 'dividends':
                    response = self.client.list_dividends(
                        ticker=ticker,
                        ex_dividend_date_gte=start_date,
                        ex_dividend_date_lte=end_date,
                        limit=1000
                    )

                    data = []
                    for div in response:
                        data.append({
                            'ex_dividend_date': div.ex_dividend_date,
                            'payment_date': div.payment_date,
                            'record_date': div.record_date,
                            'declaration_date': div.declaration_date,
                            'cash_amount': div.cash_amount,
                            'dividend_type': div.dividend_type,
                            'frequency': div.frequency
                        })

                elif event_type == 'splits':
                    response = self.client.list_splits(
                        ticker=ticker,
                        execution_date_gte=start_date,
                        execution_date_lte=end_date,
                        limit=1000
                    )

                    data = []
                    for split in response:
                        data.append({
                            'execution_date': split.execution_date,
                            'split_from': split.split_from,
                            'split_to': split.split_to
                        })

                else:
                    logger.warning(f"Unsupported event type: {event_type}")
                    continue

                df = pd.DataFrame(data)

                if not df.empty:
                    # Save to cache
                    self._save_to_cache(df, cache_path)

                results[event_type] = df

            except Exception as e:
                logger.error(f"Failed to fetch {event_type} for {ticker}: {e}")
                results[event_type] = pd.DataFrame()

        return results

    def get_aggregated_market_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        include_news: bool = True,
        include_events: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive market data for a ticker including prices, news, and events.

        Args:
            ticker: Stock symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            include_news: Whether to include news articles
            include_events: Whether to include market events

        Returns:
            Dictionary containing prices, news, and events DataFrames
        """
        result = {
            'ticker': ticker,
            'start_date': start_date,
            'end_date': end_date,
            'prices': self.fetch_historical_prices(ticker, start_date, end_date)
        }

        if include_news:
            result['news'] = self.fetch_ticker_news(
                ticker,
                start_date=start_date,
                end_date=end_date
            )

        if include_events:
            result['events'] = self.fetch_market_events(
                ticker,
                start_date=start_date,
                end_date=end_date
            )

        return result


# Tool wrapper for AutoGen integration
def create_polygon_tool(api_key: Optional[str] = None) -> 'PolygonHistoricalTool':
    """
    Create a Polygon historical data tool for AutoGen agents.

    Args:
        api_key: Optional Polygon API key

    Returns:
        PolygonHistoricalTool instance
    """
    return PolygonHistoricalTool(api_key)


class PolygonHistoricalTool:
    """Tool wrapper for Polygon.io historical data access."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Polygon tool."""
        self.polygon_client = PolygonHistoricalData(api_key)
        self.name = "polygon_historical_data"
        self.description = (
            "Fetch historical market data including prices, news, and events "
            "from Polygon.io API with 2 years of history."
        )

    def __call__(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        data_type: str = 'all'
    ) -> Dict[str, Any]:
        """
        Fetch historical data for a ticker.

        Args:
            ticker: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            data_type: Type of data ('prices', 'news', 'events', 'all')

        Returns:
            Dictionary with requested data
        """
        if data_type == 'prices':
            return {
                'prices': self.polygon_client.fetch_historical_prices(
                    ticker, start_date, end_date
                ).to_dict(orient='records')
            }
        elif data_type == 'news':
            return {
                'news': self.polygon_client.fetch_ticker_news(
                    ticker, start_date=start_date, end_date=end_date
                ).to_dict(orient='records')
            }
        elif data_type == 'events':
            events = self.polygon_client.fetch_market_events(
                ticker, start_date=start_date, end_date=end_date
            )
            return {
                'events': {
                    k: v.to_dict(orient='records') for k, v in events.items()
                }
            }
        else:  # 'all'
            result = self.polygon_client.get_aggregated_market_data(
                ticker, start_date, end_date
            )
            # Convert DataFrames to dicts for JSON serialization
            result['prices'] = result['prices'].to_dict(orient='records')
            if 'news' in result:
                result['news'] = result['news'].to_dict(orient='records')
            if 'events' in result:
                result['events'] = {
                    k: v.to_dict(orient='records')
                    for k, v in result['events'].items()
                }
            return result
