"""
Yahoo Finance News Scraper Tool

This module provides web scraping functionality for Yahoo Finance news
as a replacement for the IP-banned yfin API tool. Integrates with the
existing RH2MAS sentiment analysis pipeline.

Created to address GitHub Issue #151
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import random
import json
import os
from typing import List, Dict, Optional, Any
import logging
from urllib.parse import urljoin
from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)


class YahooNewsCache:
    """
    News-specific cache manager for Yahoo Finance scraper.
    Integrates with existing .cache directory structure.
    """

    def __init__(self, cache_dir: str = "./.cache/news/yahoo_finance"):
        self.cache_dir = cache_dir
        self.metadata_file = os.path.join(cache_dir, "metadata.json")
        self.stats = {
            'hits': 0,
            'misses': 0,
            'total_items_cached': 0
        }

        # Create cache directory structure
        os.makedirs(cache_dir, exist_ok=True)
        self._load_metadata()

    def _load_metadata(self):
        """Load cache metadata."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
            except:
                self.metadata = {}
        else:
            self.metadata = {}

    def _save_metadata(self):
        """Save cache metadata."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")

    def _generate_cache_key(self, category: str, timestamp: datetime = None) -> str:
        """Generate cache key for news category."""
        if timestamp is None:
            timestamp = datetime.now()
        # Group by 5-minute intervals for cache efficiency
        rounded_time = timestamp.replace(second=0, microsecond=0)
        rounded_time = rounded_time.replace(minute=(rounded_time.minute // 5) * 5)
        return f"{category}_{rounded_time.strftime('%Y%m%d_%H%M')}"

    def get(self, category: str, ttl_minutes: int = 5) -> Optional[pd.DataFrame]:
        """Get cached news data if still valid."""
        cache_key = self._generate_cache_key(category)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                # Check if cache is still valid
                file_age = time.time() - os.path.getmtime(cache_file)
                if file_age < (ttl_minutes * 60):
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                    df = pd.DataFrame(data['headlines'])
                    if not df.empty:
                        # Handle both timestamp and published_date columns
                        for time_col in ['timestamp', 'published_date']:
                            if time_col in df.columns:
                                df[time_col] = pd.to_datetime(df[time_col])
                    self.stats['hits'] += 1
                    return df
            except Exception as e:
                logger.error(f"Error loading cache {cache_key}: {e}")

        self.stats['misses'] += 1
        return None

    def set(self, category: str, data: pd.DataFrame, ttl_minutes: int = 5):
        """Cache news data."""
        if data.empty:
            return

        cache_key = self._generate_cache_key(category)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        try:
            # Convert DataFrame to JSON-serializable format
            data_copy = data.copy()
            # Handle both 'timestamp' and 'published_date' columns
            time_col = 'timestamp' if 'timestamp' in data_copy.columns else 'published_date'
            if time_col in data_copy.columns:
                data_copy[time_col] = pd.to_datetime(data_copy[time_col]).dt.strftime('%Y-%m-%d %H:%M:%S')

            cache_data = {
                'category': category,
                'cached_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat(),
                'headlines': data_copy.to_dict('records')
            }

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            # Update metadata
            self.metadata[cache_key] = {
                'category': category,
                'cached_at': cache_data['cached_at'],
                'expires_at': cache_data['expires_at'],
                'item_count': len(data)
            }
            self._save_metadata()
            self.stats['total_items_cached'] += len(data)

        except Exception as e:
            logger.error(f"Error caching data for {category}: {e}")

    def cleanup_expired(self):
        """Remove expired cache files."""
        current_time = time.time()
        removed_count = 0

        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.json') and filename != 'metadata.json':
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    file_age = current_time - os.path.getmtime(filepath)
                    if file_age > (30 * 60):  # Remove files older than 30 minutes
                        os.remove(filepath)
                        removed_count += 1
                        # Remove from metadata
                        cache_key = filename.replace('.json', '')
                        if cache_key in self.metadata:
                            del self.metadata[cache_key]
                except Exception as e:
                    logger.error(f"Error removing expired cache {filename}: {e}")

        if removed_count > 0:
            self._save_metadata()
            logger.info(f"Cleaned up {removed_count} expired cache files")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0

        return {
            **self.stats,
            'hit_rate': hit_rate,
            'cache_files': len([f for f in os.listdir(self.cache_dir) if f.endswith('.json') and f != 'metadata.json'])
        }


class HtmlClient:
    """HTTP client for web scraping with rate limiting and user agent rotation."""

    USER_AGENTS = [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    ]

    def __init__(self, rate_limit_delay: float = 2.0):
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.session = requests.Session()

    def load_document(self, url: str) -> BeautifulSoup:
        """Load HTML document with rate limiting and error handling."""
        # Rate limiting
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last_request)

        headers = {
            'User-Agent': random.choice(self.USER_AGENTS)
        }

        try:
            response = self.session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 429:
                # Rate limited - wait longer
                time.sleep(self.rate_limit_delay * 2)
                raise requests.exceptions.HTTPError(f"Rate limited: {response.status_code}")

            response.raise_for_status()
            self.last_request_time = time.time()
            return BeautifulSoup(response.text, 'html.parser')

        except Exception as e:
            logger.error(f"Error loading {url}: {str(e)}")
            raise


class YahooFinanceNewsScraper:
    """
    Yahoo Finance news scraper with multiple selector strategies
    and integration with RH2MAS sentiment pipeline.
    """

    BASE_URL = "https://finance.yahoo.com"
    NEWS_URLS = {
        "stock-market-news": "/topic/stock-market-news/",
        "economic-news": "/topic/economic-news/",
        "earnings": "/topic/earnings/",
        "crypto": "/topic/crypto/",
        "latest": "/news/"
    }

    def __init__(self, cache_manager: Optional[YahooNewsCache] = None):
        self.cache_manager = cache_manager or YahooNewsCache()

    def extract_headlines(self, soup: BeautifulSoup, url: str) -> List[Dict]:
        """Extract headlines using multiple selector strategies."""
        headlines = []

        # Multiple selector strategies for Yahoo's changing HTML structure
        selector_strategies = [
            # Strategy 1: Current Yahoo Finance structure
            {
                'container': 'li[data-test-locator="story-item"]',
                'title': 'h3 a',
                'link': 'h3 a',
                'summary': 'p',
                'time': 'time'
            },
            # Strategy 2: Alternative structure
            {
                'container': 'div[data-test-locator="story-item"]',
                'title': 'h3',
                'link': 'a[href*="/news/"]',
                'summary': 'p',
                'time': 'time'
            },
            # Strategy 3: Generic news item
            {
                'container': 'li.story-item, div.story-item',
                'title': 'h3, h2',
                'link': 'a',
                'summary': 'p',
                'time': 'time'
            },
            # Strategy 4: Fallback
            {
                'container': 'article, div[class*="story"]',
                'title': 'h3, h2, h1',
                'link': 'a[href]',
                'summary': 'p',
                'time': 'time, span[class*="time"]'
            }
        ]

        containers = []
        used_strategy = None

        for i, strategy in enumerate(selector_strategies):
            containers = soup.select(strategy['container'])
            if containers and len(containers) >= 3:  # Need at least 3 items
                used_strategy = i + 1
                logger.info(f"Found {len(containers)} news items using strategy {used_strategy}")
                break

        if not containers:
            logger.warning("No news containers found with any strategy")
            return headlines

        # Extract data from containers
        for container in containers[:20]:  # Limit to prevent excessive processing
            try:
                headline_data = {}

                # Extract title
                title_elem = container.select_one(selector_strategies[used_strategy - 1]['title'])
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                if not title or len(title) < 10:  # Skip very short titles
                    continue

                headline_data['title'] = title

                # Extract link
                link_elem = container.select_one(selector_strategies[used_strategy - 1]['link'])
                link = ""
                if link_elem:
                    link = link_elem.get('href', '')
                    if link and not link.startswith('http'):
                        link = urljoin(self.BASE_URL, link)

                headline_data['url'] = link

                # Extract summary
                summary_elem = container.select_one(
                    selector_strategies[used_strategy - 1]['summary'])
                summary = ""
                if summary_elem:
                    summary = summary_elem.get_text(strip=True)

                headline_data['summary'] = summary

                # Extract timestamp
                time_elem = container.select_one(selector_strategies[used_strategy - 1]['time'])
                timestamp = datetime.now()
                if time_elem:
                    time_text = time_elem.get('datetime') or time_elem.get_text(strip=True)
                    if time_text:
                        try:
                            if 'T' in time_text:  # ISO format
                                timestamp = datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                            else:
                                # Parse relative time like "2 hours ago"
                                timestamp = self._parse_relative_time(time_text)
                        except:
                            pass

                headline_data['timestamp'] = timestamp
                headline_data['source'] = 'Yahoo Finance'
                headline_data['category'] = url.split('/')[-2] if '/topic/' in url else 'general'
                headline_data['relevance_score'] = 1.0

                headlines.append(headline_data)

            except Exception as e:
                logger.error(f"Error extracting headline: {str(e)}")
                continue

        logger.info(f"Successfully extracted {len(headlines)} headlines")
        return headlines

    def _parse_relative_time(self, time_text: str) -> datetime:
        """Parse relative time strings like '2 hours ago'."""
        time_text = time_text.lower().strip()
        now = datetime.now()

        if 'minute' in time_text:
            minutes = int(''.join(filter(str.isdigit, time_text)) or 0)
            return now - timedelta(minutes=minutes)
        elif 'hour' in time_text:
            hours = int(''.join(filter(str.isdigit, time_text)) or 0)
            return now - timedelta(hours=hours)
        elif 'day' in time_text:
            days = int(''.join(filter(str.isdigit, time_text)) or 0)
            return now - timedelta(days=days)

        return now

    def fetch_news(self, category: str = "stock-market-news", use_cache: bool = True) -> pd.DataFrame:
        """Fetch news headlines from Yahoo Finance."""
        url = self.BASE_URL + self.NEWS_URLS.get(category, self.NEWS_URLS["stock-market-news"])

        # Check cache first
        if use_cache:
            cached_data = self.cache_manager.get(category)
            if cached_data is not None and not cached_data.empty:
                logger.info(f"Using cached data for {category}")
                return cached_data

        # Fetch fresh data
        try:
            client = HtmlClient(rate_limit_delay=2.5)
            soup = client.load_document(url)
            headlines = self.extract_headlines(soup, url)

            if not headlines:
                logger.warning(f"No headlines found for category: {category}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(headlines)

            # Cache the results
            if use_cache and not df.empty:
                self.cache_manager.set(category, df, ttl_minutes=5)

            return df

        except Exception as e:
            logger.error(f"Error fetching news for {category}: {str(e)}")
            return pd.DataFrame()


def normalize_yahoo_news_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize Yahoo scraped data to match RH2MAS UnifiedNewsTool schema.
    This ensures compatibility with existing sentiment analysis pipeline.
    """
    if df.empty:
        return df

    # Match the schema expected by your sentiment analysis tools
    normalized_df = pd.DataFrame({
        'title': df['title'],
        'summary': df['summary'].fillna(''),
        'url': df['url'],
        'published_date': df['timestamp'],
        'source': df['source'],
        'relevance_score': df.get('relevance_score', 1.0),
        'Data_Source': 'YahooScraper',  # Match existing pattern
        'category': df['category']
    })

    # Add sentiment-ready flag
    normalized_df['sentiment_ready'] = True

    # Ensure datetime format
    normalized_df['published_date'] = pd.to_datetime(normalized_df['published_date'])

    return normalized_df


def fetch_yahoo_finance_news(
    keywords: List[str] = None,
    count: int = 10,
    categories: List[str] = None,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Fetch Yahoo Finance news - drop-in replacement for banned yfin tool.

    Args:
        keywords: Keywords to filter news (optional)
        count: Number of headlines to return
        categories: News categories to fetch from
        use_cache: Whether to use caching

    Returns:
        DataFrame with normalized news data
    """
    if categories is None:
        categories = ["stock-market-news", "earnings", "economic-news"]

    # Initialize scraper with cache
    cache_manager = YahooNewsCache()
    scraper = YahooFinanceNewsScraper(cache_manager)

    # Fetch from all categories
    all_news = []
    for category in categories:
        try:
            result = scraper.fetch_news(category, use_cache)
            if isinstance(result, pd.DataFrame) and not result.empty:
                all_news.append(result)
        except Exception as e:
            logger.error(f"Error fetching {category}: {str(e)}")

    if all_news:
        combined_df = pd.concat(all_news, ignore_index=True)
        # Remove duplicates by URL
        combined_df = combined_df.drop_duplicates(subset=['url'], keep='first')
        # Sort by timestamp
        combined_df = combined_df.sort_values('timestamp', ascending=False)
        raw_news = combined_df
    else:
        raw_news = pd.DataFrame()

    if raw_news.empty:
        logger.warning("No news found from Yahoo Finance scraper")
        return pd.DataFrame()

    # Filter by keywords if provided
    if keywords:
        keyword_pattern = '|'.join(keywords)
        mask = (
            raw_news['title'].str.contains(keyword_pattern, case=False, na=False) |
            raw_news['summary'].str.contains(keyword_pattern, case=False, na=False)
        )
        filtered_news = raw_news[mask]

        # If no results after filtering, return top results anyway
        if filtered_news.empty:
            logger.info(f"No news found with keywords {keywords}, returning general news")
            filtered_news = raw_news
    else:
        filtered_news = raw_news

    # Limit to requested count
    filtered_news = filtered_news.head(count)

    # Normalize data to match existing schema
    normalized_news = normalize_yahoo_news_data(filtered_news)

    # Cleanup expired cache files
    cache_manager.cleanup_expired()

    return normalized_news


# Create FunctionTool for AutoGen integration
yahoo_finance_scraper_tool = FunctionTool(
    func=fetch_yahoo_finance_news,
    name="fetch_yahoo_finance_news",
    description="Fetch financial news headlines from Yahoo Finance using web scraping. "
                "Backup data source when other news APIs are rate-limited or unavailable. "
                "Returns DataFrame with title, summary, url, published_date, source, and relevance_score."
)


# Export for easy importing
__all__ = [
    'YahooFinanceNewsScraper',
    'YahooNewsCache',
    'fetch_yahoo_finance_news',
    'yahoo_finance_scraper_tool',
    'normalize_yahoo_news_data'
]


