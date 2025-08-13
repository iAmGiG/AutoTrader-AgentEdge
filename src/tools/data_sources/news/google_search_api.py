"""
Google Custom Search News Tool
Uses Google Custom Search API to find historical financial news from premium sources like Barrons
"""

import requests
import pandas as pd
from datetime import datetime
import json
import os
from typing import List, Dict, Optional, Any
import logging
from urllib.parse import urlparse
import re
from autogen_core.tools import FunctionTool
# Quota management removed for simplified V0-V4 framework
from config.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class GoogleSearchNewsCache:
    """Cache manager for Google search results"""

    def __init__(self, cache_dir: str = "./.cache/news/google_search"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_cache_key(self, query: str, start_date: str, end_date: str) -> str:
        """Generate cache key for search query"""
        # Create a hash-like key from query parameters
        key_parts = [query.replace(" ", "_"), start_date, end_date]
        return "_".join(key_parts).replace(":", "_").replace("/", "_")

    def get(self, query: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Get cached search results"""
        cache_key = self.get_cache_key(query, start_date, end_date)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                df = pd.DataFrame(data['results'])
                if not df.empty and 'published_date' in df.columns:
                    df['published_date'] = pd.to_datetime(df['published_date'])

                logger.info(f"Using cached Google search results: {cache_key}")
                return df
            except Exception as e:
                logger.error(f"Error loading Google search cache {cache_key}: {e}")

        return None

    def set(self, query: str, start_date: str, end_date: str, data: pd.DataFrame):
        """Cache search results permanently (historical data doesn't change)"""
        if data.empty:
            return

        cache_key = self.get_cache_key(query, start_date, end_date)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        try:
            data_copy = data.copy()
            if 'published_date' in data_copy.columns:
                data_copy['published_date'] = pd.to_datetime(
                    data_copy['published_date']).dt.strftime('%Y-%m-%d %H:%M:%S')

            cache_data = {
                'query': query,
                'start_date': start_date,
                'end_date': end_date,
                'cached_at': datetime.now().isoformat(),
                'results': data_copy.to_dict('records')
            }

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"Cached {len(data)} Google search results: {cache_key}")

        except Exception as e:
            logger.error(f"Error caching Google search data {cache_key}: {e}")


class GoogleSearchNewsTool:
    """Tool to search for historical financial news using Google Custom Search API"""

    def __init__(self, api_key: str = None, search_engine_id: str = None):
        """
        Initialize Google Search News Tool

        Args:
            api_key: Google Custom Search API key
            search_engine_id: Custom Search Engine ID
        """
        # Load from config.json first, then fallback to environment variables
        config_loader = ConfigLoader()
        self.api_key = api_key or config_loader.get(
            'GOOGLE_SEARCH_API_KEY') or os.getenv('GOOGLE_SEARCH_API_KEY')
        self.search_engine_id = search_engine_id or config_loader.get(
            'GOOGLE_SEARCH_ENGINE_ID') or os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        self.cache = GoogleSearchNewsCache()

        if not self.api_key:
            logger.warning(
                "Google Search API key not found. Set GOOGLE_SEARCH_API_KEY environment variable.")
        if not self.search_engine_id:
            logger.warning(
                "Google Search Engine ID not found. Set GOOGLE_SEARCH_ENGINE_ID environment variable.")

    def build_search_query(self, ticker: str, start_date: str, end_date: str,
                           source_sites: List[str] = None) -> str:
        """Build optimized search query for historical financial news"""

        # Default to premium financial news sites
        if not source_sites:
            source_sites = [
                "barrons.com",
                "wsj.com",
                "marketwatch.com",
                "bloomberg.com",
                "reuters.com",
                "cnbc.com"
            ]

        # Build site restriction
        site_query = " OR ".join([f"site:{site}" for site in source_sites])

        # Build more specific historical search terms
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        # For 2022 searches, be more specific about historical context
        if start_dt.year == 2022:
            # Use more specific date ranges and historical keywords
            month_name = start_dt.strftime('%B')  # October
            year = start_dt.strftime('%Y')        # 2022

            # Add historical context terms
            historical_terms = [
                f'"{month_name} {year}"',
                f'"{year}" earnings',
                f'"{year}" quarterly',
                f'"Q3 {year}"',
                f'"{year}" report'
            ]

            # Build query with historical context
            date_query = " OR ".join(historical_terms)
            query = f"({site_query}) {ticker} ({date_query}) -2024 -2025"  # Exclude recent years
        else:
            # Original logic for other years
            date_terms = []
            for dt in [start_dt, end_dt]:
                month_name = dt.strftime('%B')
                month_abbr = dt.strftime('%b')
                year = dt.strftime('%Y')

                date_terms.extend([
                    f'"{month_name} {year}"',
                    f'"{month_abbr} {year}"'
                ])

            date_terms = list(set(date_terms))
            date_query = " OR ".join(date_terms)
            query = f"({site_query}) {ticker} ({date_query})"

        return query

    def search_historical_news(self, ticker: str, start_date: str, end_date: str,
                               max_results: int = 10) -> pd.DataFrame:
        """
        Search for historical news using Google Custom Search API

        Args:
            ticker: Stock ticker (e.g., 'TSLA')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            max_results: Maximum number of results to return

        Returns:
            DataFrame with historical news results
        """

        # Check cache first
        query = self.build_search_query(ticker, start_date, end_date)
        cached_data = self.cache.get(query, start_date, end_date)
        if cached_data is not None:
            logger.info(f"Using cached data for {ticker} {start_date}-{end_date}")
            return cached_data.head(max_results)

        if not self.api_key or not self.search_engine_id:
            logger.error("Google Search API credentials not configured")
            return pd.DataFrame()

        # Simplified quota check - assume we have quota available
        # (Quota management was simplified for V0-V4 framework)
        logger.info("Making Google Search API call (quota management simplified)")

        try:
            # Google Custom Search API endpoint
            url = "https://www.googleapis.com/customsearch/v1"

            params = {
                'key': self.api_key,
                'cx': self.search_engine_id,
                'q': query,
                'num': min(max_results, 10),  # API limit is 10 per request
                'sort': 'date'  # Sort by date for historical accuracy
            }

            # Add date range restriction for historical searches
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')

            # Format dates for Google API (YYYYMMDD)
            date_restrict_start = start_dt.strftime('%Y%m%d')
            date_restrict_end = end_dt.strftime('%Y%m%d')

            # Add date restriction parameter
            params['dateRestrict'] = f'd:{date_restrict_start}:{date_restrict_end}'

            logger.info(f"Google search query: {query}")

            response = requests.get(url, params=params, timeout=30)

            # Simplified usage tracking (quota management simplified for V0-V4)
            logger.info("Google Search API call completed")

            if response.status_code == 200:
                data = response.json()

                if 'items' in data:
                    results = []

                    for item in data['items']:
                        # Extract article information
                        title = item.get('title', '')
                        link = item.get('link', '')
                        snippet = item.get('snippet', '')

                        # Try to extract publication date
                        published_date = self._extract_date_from_item(item, start_date, end_date)

                        # Determine source from URL
                        source = self._get_source_from_url(link)

                        # Calculate relevance score based on title and snippet
                        relevance_score = self._calculate_relevance(title, snippet, ticker)

                        results.append({
                            'title': title,
                            'summary': snippet,
                            'url': link,
                            'published_date': published_date,
                            'source': f'Google Search - {source}',
                            'Data_Source': 'Google_Search_Historical',
                            'sentiment_ready': True,
                            'relevance_score': relevance_score,
                            'ticker': ticker.upper()
                        })

                    if results:
                        df = pd.DataFrame(results)

                        # Ensure published_date is datetime for sorting
                        df['published_date'] = pd.to_datetime(df['published_date'], errors='coerce')

                        # Sort by relevance and date
                        df = df.sort_values(['relevance_score', 'published_date'],
                                            ascending=[False, False], na_position='last')

                        # Cache the results
                        self.cache.set(query, start_date, end_date, df)

                        logger.info(f"Found {len(df)} articles via Google Search for {ticker}")
                        return df.head(max_results)

                else:
                    logger.info(f"No search results found for {ticker}")

            else:
                logger.error(f"Google Search API error: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error in Google search for {ticker}: {e}")

        return pd.DataFrame()

    def _extract_date_from_item(self, item: Dict, start_date: str, end_date: str) -> datetime:
        """Extract publication date from Google search result"""

        # Try pagemap first (structured data)
        if 'pagemap' in item:
            pagemap = item['pagemap']

            # Check various structured data formats
            for data_type in ['metatags', 'newsarticle', 'article']:
                if data_type in pagemap:
                    for entry in pagemap[data_type]:
                        # Common date fields
                        date_fields = [
                            'article:published_time', 'datePublished', 'publishedDate',
                            'date', 'publish_date', 'publication_date'
                        ]

                        for field in date_fields:
                            if field in entry:
                                try:
                                    return pd.to_datetime(entry[field])
                                except:
                                    continue

        # Try to extract date from title or snippet
        text_to_search = f"{item.get('title', '')} {item.get('snippet', '')}"

        # Date patterns to look for
        date_patterns = [
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{2}-\d{2}'
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                try:
                    return pd.to_datetime(match.group())
                except:
                    continue

        # Default to middle of date range if no date found
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        middle_date = start_dt + (end_dt - start_dt) / 2

        return middle_date

    def _get_source_from_url(self, url: str) -> str:
        """Extract source name from URL"""
        try:
            domain = urlparse(url).netloc.lower()

            # Map domains to readable names
            source_map = {
                'barrons.com': 'Barrons',
                'wsj.com': 'Wall Street Journal',
                'marketwatch.com': 'MarketWatch',
                'bloomberg.com': 'Bloomberg',
                'reuters.com': 'Reuters',
                'cnbc.com': 'CNBC',
                'finance.yahoo.com': 'Yahoo Finance',
                'seekingalpha.com': 'Seeking Alpha'
            }

            for domain_key, source_name in source_map.items():
                if domain_key in domain:
                    return source_name

            # Default to domain name
            return domain.replace('www.', '').replace('.com', '').title()

        except:
            return 'Unknown Source'

    def _calculate_relevance(self, title: str, snippet: str, ticker: str) -> float:
        """Calculate relevance score for news article"""

        text = f"{title} {snippet}".lower()
        ticker_lower = ticker.lower()

        score = 0.0

        # Ticker mentions (high weight)
        ticker_count = text.count(ticker_lower)
        score += ticker_count * 0.3

        # Financial keywords
        financial_keywords = [
            'stock', 'shares', 'earnings', 'revenue', 'profit', 'loss',
            'trading', 'price', 'market', 'analyst', 'upgrade', 'downgrade',
            'buy', 'sell', 'rating', 'target', 'forecast', 'guidance'
        ]

        for keyword in financial_keywords:
            if keyword in text:
                score += 0.1

        # Company-specific terms (varies by ticker)
        company_terms = {
            'TSLA': ['tesla', 'musk', 'electric', 'ev', 'model'],
            'AAPL': ['apple', 'iphone', 'ipad', 'mac', 'ios'],
            'MSFT': ['microsoft', 'windows', 'azure', 'office'],
            'GOOGL': ['google', 'alphabet', 'search', 'android'],
            'AMZN': ['amazon', 'aws', 'prime', 'bezos'],
            'META': ['meta', 'facebook', 'instagram', 'metaverse'],
            'NVDA': ['nvidia', 'gpu', 'chip', 'ai', 'gaming']
        }

        if ticker.upper() in company_terms:
            for term in company_terms[ticker.upper()]:
                if term in text:
                    score += 0.15

        # Normalize score to 0-1 range
        return min(score, 1.0)


def search_google_historical_news(
    ticker: str,
    start_date: str,
    end_date: str,
    max_results: int = 10
) -> pd.DataFrame:
    """
    Main function to search historical news using Google Custom Search

    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        max_results: Maximum results to return

    Returns:
        DataFrame with historical news results
    """

    tool = GoogleSearchNewsTool()
    return tool.search_historical_news(ticker, start_date, end_date, max_results)


# Create FunctionTool for AutoGen integration
google_search_news_tool = FunctionTool(
    func=search_google_historical_news,
    name="search_google_historical_news",
    description="Search for historical financial news using Google Custom Search API. "
                "Finds articles from premium sources like Barrons, WSJ, Bloomberg for specific date ranges. "
                "Requires Google Search API key. Returns DataFrame with relevance-scored results."
)


# Export for easy importing
__all__ = [
    'GoogleSearchNewsTool',
    'search_google_historical_news',
    'google_search_news_tool'
]
