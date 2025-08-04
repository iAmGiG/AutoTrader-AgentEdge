"""
FinViz Historical News Scraper

Scrapes FinViz for historical financial news, specifically targeting MAG7 stocks
and October 2022 timeframe for backtesting purposes.

Created to address GitHub Issue #160 - getting real historical news data
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import os
import re
from typing import Optional
import logging
from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)


class FinVizHistoricalScraper:
    """
    Scraper for FinViz financial news with focus on historical data
    """

    def __init__(self, cache_dir: str = "./.cache/news/finviz"):
        self.base_url = "https://finviz.com"
        self.cache_dir = cache_dir
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)

        # Rate limiting
        self.min_delay = 1.0  # Minimum delay between requests
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _get_cache_key(self, ticker: str, date_str: str = None) -> str:
        """Generate cache key for FinViz data"""
        if date_str:
            return f"finviz_{ticker}_{date_str}"
        else:
            return f"finviz_{ticker}_current"

    def _load_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """Load cached data if available"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)

                df = pd.DataFrame(data['headlines'])
                if not df.empty and 'published_date' in df.columns:
                    df['published_date'] = pd.to_datetime(df['published_date'])

                # Check if cache is recent enough (for current data) or permanent (for historical)
                cached_at = datetime.fromisoformat(data['cached_at'])
                is_historical = 'historical' in data.get('type', '')

                if is_historical or (datetime.now() - cached_at).total_seconds() < 3600:  # 1 hour for current
                    logger.info(f"Using cached FinViz data: {cache_key}")
                    return df

            except Exception as e:
                logger.error(f"Error loading cache {cache_key}: {e}")

        return None

    def _save_to_cache(self, cache_key: str, df: pd.DataFrame, is_historical: bool = False):
        """Save data to cache"""
        if df.empty:
            return

        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        try:
            data_copy = df.copy()
            if 'published_date' in data_copy.columns:
                data_copy['published_date'] = pd.to_datetime(
                    data_copy['published_date']).dt.strftime('%Y-%m-%d %H:%M:%S')

            cache_data = {
                'cached_at': datetime.now().isoformat(),
                'type': 'historical' if is_historical else 'current',
                'headlines': data_copy.to_dict('records')
            }

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"Cached {len(df)} FinViz headlines: {cache_key}")

        except Exception as e:
            logger.error(f"Error caching FinViz data {cache_key}: {e}")

    def scrape_stock_news(self, ticker: str, use_cache: bool = True) -> pd.DataFrame:
        """
        Scrape news for a specific stock from FinViz

        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            use_cache: Whether to use cached data

        Returns:
            DataFrame with news headlines
        """
        ticker = ticker.upper()
        cache_key = self._get_cache_key(ticker)

        # Check cache first
        if use_cache:
            cached_data = self._load_from_cache(cache_key)
            if cached_data is not None:
                return cached_data

        # Scrape fresh data
        url = f"{self.base_url}/quote.ashx?t={ticker}"

        try:
            self._rate_limit()
            response = requests.get(url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                logger.error(f"FinViz request failed: HTTP {response.status_code}")
                return pd.DataFrame()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find news table on the quote page
            news_headlines = []

            # Look for news table - FinViz has a specific structure
            news_table = None
            tables = soup.find_all('table')

            for table in tables:
                # Look for table with news links
                news_links = table.find_all('a', href=re.compile(
                    r'news|yahoo|reuters|cnbc|bloomberg', re.I))
                if len(news_links) > 5:  # Table with multiple news links
                    news_table = table
                    break

            if news_table:
                rows = news_table.find_all('tr')

                for row in rows:
                    cells = row.find_all('td')

                    if len(cells) >= 2:
                        # Usually: [time/date] [headline with link]
                        time_cell = cells[0].get_text(strip=True)
                        headline_cell = cells[1]

                        # Extract headline text
                        headline_text = headline_cell.get_text(strip=True)

                        if len(headline_text) < 20:  # Skip short/empty headlines
                            continue

                        # Extract link
                        link_elem = headline_cell.find('a')
                        link_url = link_elem.get('href', '') if link_elem else ''

                        # Parse time/date
                        published_date = self._parse_finviz_time(time_cell)

                        news_headlines.append({
                            'title': headline_text,
                            'summary': '',  # FinViz doesn't provide summaries
                            'url': link_url,
                            'published_date': published_date,
                            'source': f'FinViz - {ticker}',
                            'Data_Source': 'FinViz_Historical',
                            'sentiment_ready': True
                        })

            # Convert to DataFrame
            if news_headlines:
                df = pd.DataFrame(news_headlines)

                # Cache the results
                if use_cache:
                    self._save_to_cache(cache_key, df, is_historical=False)

                logger.info(f"Scraped {len(df)} headlines for {ticker} from FinViz")
                return df
            else:
                logger.warning(f"No news headlines found for {ticker} on FinViz")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error scraping FinViz for {ticker}: {e}")
            return pd.DataFrame()

    def _parse_finviz_time(self, time_text: str) -> datetime:
        """Parse FinViz time format to datetime"""
        time_text = time_text.strip()
        now = datetime.now()

        try:
            # FinViz uses various time formats
            if 'ago' in time_text.lower():
                return self._parse_relative_time(time_text)
            elif re.match(r'\d{2}-\d{2}-\d{2}', time_text):  # MM-DD-YY format
                return datetime.strptime(time_text, '%m-%d-%y')
            elif re.match(r'\d{4}-\d{2}-\d{2}', time_text):  # YYYY-MM-DD format
                return datetime.strptime(time_text, '%Y-%m-%d')
            else:
                # Default to current time if can't parse
                return now

        except Exception:
            return now

    def _parse_relative_time(self, time_text: str) -> datetime:
        """Parse relative time like '2h ago', '1d ago'"""
        time_text = time_text.lower().strip()
        now = datetime.now()

        # Extract number and unit
        match = re.search(r'(\d+)\s*(h|hour|d|day|m|min|minute)', time_text)

        if match:
            number = int(match.group(1))
            unit = match.group(2)

            if unit.startswith('h'):
                return now - timedelta(hours=number)
            elif unit.startswith('d'):
                return now - timedelta(days=number)
            elif unit.startswith('m'):
                return now - timedelta(minutes=number)

        return now

    def scrape_mag7_news(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Scrape news for all MAG7 stocks

        Args:
            use_cache: Whether to use cached data

        Returns:
            DataFrame with combined MAG7 news
        """
        mag7_stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']

        all_news = []

        for ticker in mag7_stocks:
            logger.info(f"Scraping FinViz news for {ticker}...")

            try:
                df = self.scrape_stock_news(ticker, use_cache)
                if not df.empty:
                    all_news.append(df)

            except Exception as e:
                logger.error(f"Error scraping {ticker}: {e}")
                continue

        if all_news:
            combined_df = pd.concat(all_news, ignore_index=True)

            # Remove duplicates
            combined_df = combined_df.drop_duplicates(subset=['title', 'url'], keep='first')

            # Sort by date
            combined_df = combined_df.sort_values('published_date', ascending=False)

            logger.info(
                f"Combined FinViz news: {len(combined_df)} headlines from {len(all_news)} stocks")
            return combined_df
        else:
            logger.warning("No FinViz news found for any MAG7 stocks")
            return pd.DataFrame()


def fetch_finviz_mag7_news(use_cache: bool = True, max_articles: int = 50) -> pd.DataFrame:
    """
    Main function to fetch MAG7 news from FinViz

    Args:
        use_cache: Whether to use cached data
        max_articles: Maximum number of articles to return

    Returns:
        DataFrame with MAG7 news from FinViz
    """
    scraper = FinVizHistoricalScraper()

    try:
        df = scraper.scrape_mag7_news(use_cache)

        if not df.empty:
            # Limit to requested number of articles
            df = df.head(max_articles)

            logger.info(f"Retrieved {len(df)} MAG7 news articles from FinViz")
            return df
        else:
            logger.warning("No MAG7 news found on FinViz")
            return pd.DataFrame()

    except Exception as e:
        logger.error(f"Error fetching FinViz MAG7 news: {e}")
        return pd.DataFrame()


def fetch_finviz_stock_news(ticker: str, use_cache: bool = True, max_articles: int = 20) -> pd.DataFrame:
    """
    Fetch news for a specific stock from FinViz

    Args:
        ticker: Stock ticker symbol
        use_cache: Whether to use cached data
        max_articles: Maximum number of articles to return

    Returns:
        DataFrame with stock news from FinViz
    """
    scraper = FinVizHistoricalScraper()

    try:
        df = scraper.scrape_stock_news(ticker.upper(), use_cache)

        if not df.empty:
            df = df.head(max_articles)
            logger.info(f"Retrieved {len(df)} news articles for {ticker} from FinViz")
            return df
        else:
            logger.warning(f"No news found for {ticker} on FinViz")
            return pd.DataFrame()

    except Exception as e:
        logger.error(f"Error fetching FinViz news for {ticker}: {e}")
        return pd.DataFrame()


# Create FunctionTool for AutoGen integration
finviz_mag7_news_tool = FunctionTool(
    func=fetch_finviz_mag7_news,
    name="fetch_finviz_mag7_news",
    description="Fetch MAG7 stock news from FinViz financial news aggregator. "
                "Returns DataFrame with real financial news headlines including "
                "title, url, published_date, and source information."
)

finviz_stock_news_tool = FunctionTool(
    func=fetch_finviz_stock_news,
    name="fetch_finviz_stock_news",
    description="Fetch news for a specific stock ticker from FinViz. "
                "Useful for getting current financial news about individual stocks. "
                "Returns DataFrame with news headlines."
)


# Export for easy importing
__all__ = [
    'FinVizHistoricalScraper',
    'fetch_finviz_mag7_news',
    'fetch_finviz_stock_news',
    'finviz_mag7_news_tool',
    'finviz_stock_news_tool'
]
