"""
Hybrid Historical News Tool

Combines multiple sources to provide historical news data:
1. NewsAPI for recent news (0-30 days) 
2. Wayback Machine for historical snapshots (when available)
3. Price-based sentiment fallback

Created to address GitHub Issue #160
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import os
from typing import List, Dict, Optional
import logging
from autogen_core.tools import FunctionTool

# Import FinViz scraper and Google Search tool
from ..sources.scrapers.finviz_historical_scraper import FinVizHistoricalScraper
from ..sources.api_based.google_search_news_tool import GoogleSearchNewsTool

logger = logging.getLogger(__name__)


class HybridHistoricalNewsCache:
    """Cache manager for hybrid historical news data"""

    def __init__(self, cache_dir: str = "./.cache/news/hybrid_historical"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_cache_key(self, date: str, source: str) -> str:
        """Generate cache key for historical data"""
        return f"{source}_{date}"

    def get(self, date: str, source: str) -> Optional[pd.DataFrame]:
        """Get cached historical news data"""
        cache_key = self.get_cache_key(date, source)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                df = pd.DataFrame(data['headlines'])
                if not df.empty and 'published_date' in df.columns:
                    df['published_date'] = pd.to_datetime(df['published_date'])
                return df
            except Exception as e:
                logger.error(f"Error loading cache {cache_key}: {e}")

        return None

    def set(self, date: str, source: str, data: pd.DataFrame):
        """Cache historical news data permanently"""
        if data.empty:
            return

        cache_key = self.get_cache_key(date, source)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        try:
            data_copy = data.copy()
            if 'published_date' in data_copy.columns:
                data_copy['published_date'] = pd.to_datetime(
                    data_copy['published_date']).dt.strftime('%Y-%m-%d %H:%M:%S')

            cache_data = {
                'source': source,
                'date': date,
                'cached_at': datetime.now().isoformat(),
                'headlines': data_copy.to_dict('records')
            }

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"Cached {len(data)} headlines for {date} from {source}")

        except Exception as e:
            logger.error(f"Error caching data for {date}/{source}: {e}")


class NewsAPIHistoricalProvider:
    """NewsAPI provider for recent historical news (0-30 days)"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def can_provide(self, target_date: datetime) -> bool:
        """Check if this provider can provide data for the given date"""
        days_ago = (datetime.now() - target_date).days
        return 0 <= days_ago <= 30

    def fetch_news(self, target_date: datetime, keywords: List[str] = None) -> pd.DataFrame:
        """Fetch news from NewsAPI for a specific date"""
        if not self.can_provide(target_date):
            return pd.DataFrame()

        date_str = target_date.strftime('%Y-%m-%d')
        next_day = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

        # Use broader financial keywords if none provided
        if not keywords:
            keywords = ['stock market', 'earnings', 'financial', 'SPY', 'trading']

        query = ' OR '.join(keywords)

        url = "https://newsapi.org/v2/everything"
        params = {
            'q': query,
            'from': date_str,
            'to': next_day,
            'language': 'en',
            'sortBy': 'relevancy',
            'pageSize': 50,
            'apiKey': self.api_key
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if data.get('status') == 'ok' and data.get('articles'):
                articles = data['articles']

                # Convert to standard format
                news_data = []
                for article in articles:
                    news_data.append({
                        'title': article.get('title', ''),
                        'summary': article.get('description', ''),
                        'url': article.get('url', ''),
                        'published_date': article.get('publishedAt', ''),
                        'source': f"NewsAPI - {article.get('source', {}).get('name', 'Unknown')}",
                        'Data_Source': 'NewsAPI_Historical',
                        'sentiment_ready': True
                    })

                df = pd.DataFrame(news_data)
                if not df.empty:
                    df['published_date'] = pd.to_datetime(df['published_date'])

                return df

        except Exception as e:
            logger.error(f"NewsAPI error for {date_str}: {e}")

        return pd.DataFrame()


class WaybackMachineProvider:
    """Wayback Machine provider for older historical news"""

    def __init__(self):
        # Prioritize professional financial news sites over Reddit
        self.sources = {
            'investing_com': {
                'url': 'investing.com/news/stock-market-news',
                'selectors': ['article h3', 'div.largeTitle a', '.articleItem h3', '.news-analysis-v2-article-item h3']
            },
            'benzinga': {
                'url': 'benzinga.com/news',
                'selectors': ['h3', 'h2 a', 'article h2', '.story-title']
            },
            'reddit_stocks': {
                'url': 'reddit.com/r/stocks',
                'selectors': ['div[data-testid="post-container"] h3', '.thing .title a']
            }
        }

    def can_provide(self, target_date: datetime) -> bool:
        """Check if this provider can provide data (older than 30 days)"""
        days_ago = (datetime.now() - target_date).days
        return days_ago > 30

    def fetch_news(self, target_date: datetime, source_name: str = 'reddit_stocks') -> pd.DataFrame:
        """Fetch news from Wayback Machine for a specific date and source"""
        if not self.can_provide(target_date):
            return pd.DataFrame()

        if source_name not in self.sources:
            logger.warning(f"Unknown source: {source_name}")
            return pd.DataFrame()

        source_config = self.sources[source_name]
        date_str = target_date.strftime('%Y%m%d')

        try:
            # Find snapshot
            snapshot_url = self._find_snapshot(source_config['url'], date_str)
            if not snapshot_url:
                logger.info(f"No snapshot found for {source_name} on {date_str}")
                return pd.DataFrame()

            # Fetch content
            content = self._fetch_archived_content(snapshot_url)
            if not content:
                return pd.DataFrame()

            # Parse content
            headlines = self._parse_content(content, source_config['selectors'], source_name)

            if headlines:
                df = pd.DataFrame(headlines)
                df['published_date'] = target_date
                return df

        except Exception as e:
            logger.error(f"Wayback error for {source_name}/{date_str}: {e}")

        return pd.DataFrame()

    def _find_snapshot(self, url: str, date_str: str) -> Optional[str]:
        """Find Wayback Machine snapshot for given URL and date"""
        cdx_url = "http://web.archive.org/cdx/search/cdx"
        params = {
            'url': url,
            'from': date_str,
            'to': date_str,
            'output': 'json',
            'limit': '1'
        }

        try:
            response = requests.get(cdx_url, params=params, timeout=15)
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                if len(lines) > 1:
                    data = json.loads(lines[1])
                    timestamp = data[0]
                    return f"http://web.archive.org/web/{timestamp}/{url}"
        except:
            pass

        return None

    def _fetch_archived_content(self, wayback_url: str) -> Optional[str]:
        """Fetch content from Wayback Machine"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        try:
            time.sleep(2)  # Rate limiting
            response = requests.get(wayback_url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.text
        except:
            pass

        return None

    def _parse_content(self, html_content: str, selectors: List[str], source_name: str) -> List[Dict]:
        """Parse HTML content to extract headlines"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove Wayback toolbar
        for toolbar in soup.find_all(['div', 'header'], id=['wm-ipp', 'wm-ipp-base']):
            toolbar.decompose()

        headlines = []

        # Try each selector
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements[:10]:  # Limit to prevent spam
                    title = elem.get_text(strip=True)
                    if len(title) > 20:  # Filter meaningful titles
                        headlines.append({
                            'title': title,
                            'summary': '',
                            'url': '',
                            'source': f'Wayback - {source_name}',
                            'Data_Source': 'Wayback_Historical',
                            'sentiment_ready': True
                        })
                break

        return headlines


class FinVizProvider:
    """FinViz provider for current financial news"""

    def __init__(self):
        self.scraper = FinVizHistoricalScraper()

    def can_provide(self, target_date: datetime) -> bool:
        """FinViz can provide current news (within last 7 days)"""
        days_ago = (datetime.now() - target_date).days
        return 0 <= days_ago <= 7

    def fetch_news(self, target_date: datetime, tickers: List[str] = None) -> pd.DataFrame:
        """Fetch news from FinViz for specific tickers or MAG7"""
        if not self.can_provide(target_date):
            return pd.DataFrame()

        try:
            if tickers:
                # Fetch news for specific tickers
                all_news = []
                for ticker in tickers[:5]:  # Limit to avoid rate limiting
                    ticker_news = self.scraper.scrape_stock_news(ticker, use_cache=True)
                    if not ticker_news.empty:
                        all_news.append(ticker_news)

                if all_news:
                    combined_df = pd.concat(all_news, ignore_index=True)
                    # Remove duplicates and sort by date
                    combined_df = combined_df.drop_duplicates(subset=['title'], keep='first')
                    combined_df = combined_df.sort_values('published_date', ascending=False)

                    logger.info(
                        f"FinViz fetched {len(combined_df)} articles for {len(tickers)} tickers")
                    return combined_df
            else:
                # Default to MAG7 stocks
                mag7_news = self.scraper.scrape_mag7_news(use_cache=True)
                if not mag7_news.empty:
                    logger.info(f"FinViz fetched {len(mag7_news)} MAG7 articles")
                    return mag7_news

        except Exception as e:
            logger.error(f"FinViz provider error: {e}")

        return pd.DataFrame()


class GoogleSearchProvider:
    """Google Search provider for historical news from premium sources"""

    def __init__(self):
        self.search_tool = GoogleSearchNewsTool()

    def can_provide(self, target_date: datetime) -> bool:
        """Google Search can provide historical news for any date (if API configured)"""
        # Only provide if API is configured and date is older than 7 days (after FinViz coverage)
        days_ago = (datetime.now() - target_date).days
        has_credentials = (self.search_tool.api_key and self.search_tool.search_engine_id)
        return has_credentials and days_ago > 7

    def fetch_news(self, target_date: datetime, tickers: List[str] = None, max_articles: int = 10) -> pd.DataFrame:
        """Fetch historical news using Google Search API"""
        if not self.can_provide(target_date):
            return pd.DataFrame()

        try:
            all_news = []

            if tickers:
                # Search for specific tickers
                for ticker in tickers[:3]:  # Limit to preserve API quota
                    # Create date range around target date (±15 days for broader coverage)
                    start_date = (target_date - timedelta(days=15)).strftime('%Y-%m-%d')
                    end_date = (target_date + timedelta(days=15)).strftime('%Y-%m-%d')

                    ticker_news = self.search_tool.search_historical_news(
                        ticker, start_date, end_date, max_results=max_articles // len(tickers)
                    )

                    if not ticker_news.empty:
                        all_news.append(ticker_news)
            else:
                # Default to searching for general market news
                # Use SPY as proxy for market news
                start_date = (target_date - timedelta(days=15)).strftime('%Y-%m-%d')
                end_date = (target_date + timedelta(days=15)).strftime('%Y-%m-%d')

                market_news = self.search_tool.search_historical_news(
                    'SPY', start_date, end_date, max_results=max_articles
                )

                if not market_news.empty:
                    all_news.append(market_news)

            if all_news:
                combined_df = pd.concat(all_news, ignore_index=True)
                # Remove duplicates and sort by relevance and date
                combined_df = combined_df.drop_duplicates(subset=['title', 'url'], keep='first')
                combined_df = combined_df.sort_values(['relevance_score', 'published_date'],
                                                      ascending=[False, False])

                logger.info(f"Google Search fetched {len(combined_df)} historical articles")
                return combined_df.head(max_articles)

        except Exception as e:
            logger.error(f"Google Search provider error: {e}")

        return pd.DataFrame()


class HybridHistoricalNewsTool:
    """
    Hybrid tool that combines multiple sources for historical news
    """

    def __init__(self, newsapi_key: str = None):
        self.cache = HybridHistoricalNewsCache()

        # Initialize providers in priority order
        self.providers = []

        # FinViz for recent news (highest priority for current data, 0-7 days)
        self.providers.append(FinVizProvider())

        # Google Search for historical premium news (7+ days, requires API key)
        self.providers.append(GoogleSearchProvider())

        # NewsAPI for recent historical news (0-30 days, requires API key)
        if newsapi_key:
            self.providers.append(NewsAPIHistoricalProvider(newsapi_key))

        # Wayback Machine as last resort for very old data (30+ days)
        self.providers.append(WaybackMachineProvider())

    def fetch_historical_news(
        self,
        target_date: str,
        keywords: List[str] = None,
        max_articles: int = 20,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical news for a specific date using hybrid approach

        Args:
            target_date: Date in YYYY-MM-DD format
            keywords: Keywords to search for
            max_articles: Maximum number of articles to return
            use_cache: Whether to use cached data

        Returns:
            DataFrame with historical news data
        """
        target_dt = datetime.strptime(target_date, '%Y-%m-%d')

        # Check cache first
        if use_cache:
            for provider in self.providers:
                provider_name = provider.__class__.__name__
                cached_data = self.cache.get(target_date, provider_name)
                if cached_data is not None and not cached_data.empty:
                    logger.info(f"Using cached data from {provider_name} for {target_date}")
                    return cached_data.head(max_articles)

        # Try providers in order of preference
        for provider in self.providers:
            if provider.can_provide(target_dt):
                try:
                    data = pd.DataFrame()

                    if isinstance(provider, FinVizProvider):
                        # Extract potential ticker symbols from keywords
                        tickers = None
                        if keywords:
                            # Look for common MAG7 tickers in keywords
                            mag7_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
                            found_tickers = []
                            for keyword in keywords:
                                upper_keyword = keyword.upper()
                                if upper_keyword in mag7_tickers:
                                    found_tickers.append(upper_keyword)
                            if found_tickers:
                                tickers = found_tickers

                        data = provider.fetch_news(target_dt, tickers)

                    elif isinstance(provider, GoogleSearchProvider):
                        # Extract potential ticker symbols from keywords
                        tickers = None
                        if keywords:
                            # Look for common MAG7 tickers in keywords
                            mag7_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
                            found_tickers = []
                            for keyword in keywords:
                                upper_keyword = keyword.upper()
                                if upper_keyword in mag7_tickers:
                                    found_tickers.append(upper_keyword)
                            if found_tickers:
                                tickers = found_tickers

                        data = provider.fetch_news(target_dt, tickers, max_articles)

                    elif isinstance(provider, NewsAPIHistoricalProvider):
                        data = provider.fetch_news(target_dt, keywords)

                    elif isinstance(provider, WaybackMachineProvider):
                        # Try sources in priority order: Investing.com > Benzinga > Reddit
                        for source_name in ['investing_com', 'benzinga', 'reddit_stocks']:
                            data = provider.fetch_news(target_dt, source_name)
                            if not data.empty:
                                logger.info(f"Successfully got historical data from {source_name}")
                                break
                            else:
                                logger.info(f"No data from {source_name}, trying next source")

                    if not data.empty:
                        # Cache the results
                        if use_cache:
                            provider_name = provider.__class__.__name__
                            self.cache.set(target_date, provider_name, data)

                        logger.info(
                            f"Found {len(data)} articles from {provider.__class__.__name__}")
                        return data.head(max_articles)

                except Exception as e:
                    logger.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                    continue

        # If we get here, no real news was found - return empty DataFrame
        logger.warning(f"No real historical news found for {target_date}")
        return pd.DataFrame()


def fetch_hybrid_historical_news(
    target_date: str,
    keywords: List[str] = None,
    max_articles: int = 20
) -> pd.DataFrame:
    """
    Main function to fetch historical news using hybrid approach

    Args:
        target_date: Date in YYYY-MM-DD format  
        keywords: Keywords to search for
        max_articles: Maximum articles to return

    Returns:
        DataFrame with historical news data
    """
    # Load NewsAPI key from config if available
    newsapi_key = None
    try:
        import json
        with open('config/config.json', 'r') as f:
            config = json.load(f)
            newsapi_key = config.get('NEWSAPI_KEY')
    except:
        pass

    tool = HybridHistoricalNewsTool(newsapi_key)
    return tool.fetch_historical_news(target_date, keywords, max_articles)


# Create FunctionTool for AutoGen integration
hybrid_historical_news_tool = FunctionTool(
    func=fetch_hybrid_historical_news,
    name="fetch_hybrid_historical_news",
    description="Fetch historical financial news using hybrid multi-source approach. "
                "Priority order: FinViz (current, 0-7 days), Google Search (historical premium sources like Barrons/WSJ, 7+ days), "
                "NewsAPI (recent 30 days), and Wayback Machine (30+ days) as fallback. "
                "Google Search accesses premium financial news sources for historical data. "
                "Returns DataFrame with real historical news data or empty DataFrame if none found."
)


# Export for easy importing
__all__ = [
    'HybridHistoricalNewsTool',
    'fetch_hybrid_historical_news',
    'hybrid_historical_news_tool'
]
