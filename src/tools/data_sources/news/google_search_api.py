"""
Google Custom Search News Tool
Uses Google Custom Search API to find historical financial news from premium sources like Barrons
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
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
    """Cache manager for Google search results with monthly organization structure"""

    def __init__(self, cache_dir: str = "./.cache/news_monthly"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_cache_path(self, ticker: str, target_date: str) -> str:
        """Generate cache file path for ticker and month"""
        try:
            dt = datetime.strptime(target_date, '%Y-%m-%d')
            year_month = dt.strftime('%Y-%m')
        except ValueError:
            # Fallback for different date formats
            year_month = target_date[:7]  # Assume YYYY-MM-DD format
        
        ticker_dir = os.path.join(self.cache_dir, ticker.upper())
        os.makedirs(ticker_dir, exist_ok=True)
        
        return os.path.join(ticker_dir, f"{year_month}.json")
    
    def normalize_title_for_dedup(self, title):
        """Normalize title for deduplication during append operations"""
        if not title:
            return ""
        
        # Remove common prefixes and suffixes
        title = re.sub(r'^(BREAKING:|UPDATE:|EXCLUSIVE:|CORRECTING AND REPLACING)[\s/]*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*[-–—]\s*(MarketWatch|WSJ|Bloomberg|Reuters|CNBC|Barrons).*$', '', title, flags=re.IGNORECASE)
        
        # Normalize whitespace and punctuation
        title = ' '.join(title.split())
        title = re.sub(r'[^\w\s\-\']', ' ', title)
        title = ' '.join(title.split())
        
        return title.lower().strip()

    def get(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Get cached search results with date filtering to prevent future spill"""
        cache_file = self.get_cache_path(ticker, start_date)
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                if 'results' in data and data['results']:
                    df = pd.DataFrame(data['results'])
                    
                    # Filter articles to only include those up to the requested date
                    if 'article_date' in df.columns:
                        df['article_date'] = pd.to_datetime(df['article_date'])
                        end_dt = pd.to_datetime(end_date)
                        df = df[df['article_date'] <= end_dt]
                    
                    if not df.empty:
                        if 'published_date' in df.columns:
                            df['published_date'] = pd.to_datetime(df['published_date'])
                        
                        logger.info(f"Using cached news for {ticker}: {len(df)} articles up to {end_date}")
                        return df
            except Exception as e:
                logger.error(f"Error loading news cache {cache_file}: {e}")
        
        # No fallback to nearby dates - monthly cache should have all data for the month
        return None
    
    def _search_nearby_dates(self, ticker: str, target_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Search for cached news in nearby dates within the same month"""
        try:
            dt = datetime.strptime(target_date, '%Y-%m-%d')
            year_month = dt.strftime('%Y-%m')
            
            ticker_dir = os.path.join(self.cache_dir, ticker.upper())
            month_dir = os.path.join(ticker_dir, year_month)
            
            if not os.path.exists(month_dir):
                return None
            
            # Look for files within ±7 days
            for days_offset in range(-7, 8):
                check_date = dt + timedelta(days=days_offset)
                if check_date.strftime('%Y-%m') != year_month:
                    continue  # Don't cross month boundaries
                
                cache_file = os.path.join(month_dir, f"{check_date.strftime('%Y-%m-%d')}.json")
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'r') as f:
                            data = json.load(f)
                        
                        if 'results' in data and data['results']:
                            df = pd.DataFrame(data['results'])
                            if not df.empty and 'published_date' in df.columns:
                                df['published_date'] = pd.to_datetime(df['published_date'])
                            
                            logger.info(f"Using nearby cached news for {ticker} from {check_date.strftime('%Y-%m-%d')} (offset: {days_offset} days)")
                            return df
                    except Exception as e:
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching nearby dates for {ticker}: {e}")
            return None

    def set(self, ticker: str, start_date: str, end_date: str, data: pd.DataFrame, query: str = ""):
        """Cache search results with set-based deduplication and appending"""
        if data.empty:
            return
        
        # Filter for relevant articles only
        data = data[data.get('relevance_score', 0.0) > 0.0].copy()
        if data.empty:
            logger.info(f"No relevant articles to cache for {ticker}")
            return
        
        cache_file = self.get_cache_path(ticker, start_date)
        
        try:
            # Load existing cache if it exists
            existing_articles = []
            existing_titles = set()
            week_info = {}
            
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    existing_data = json.load(f)
                existing_articles = existing_data.get('results', [])
                week_info = {
                    'week_id': existing_data.get('week_id', ''),
                    'week_start': existing_data.get('week_start', ''),
                    'week_end': existing_data.get('week_end', '')
                }
                
                # Build set of existing normalized titles
                for article in existing_articles:
                    title = article.get('title', '')
                    normalized = self.normalize_title_for_dedup(title)
                    if normalized:
                        existing_titles.add(normalized)
            
            # Process new articles and deduplicate
            new_articles = []
            duplicates_skipped = 0
            
            for _, row in data.iterrows():
                article = row.to_dict()
                title = article.get('title', '')
                normalized_title = self.normalize_title_for_dedup(title)
                
                if normalized_title and normalized_title not in existing_titles:
                    # Convert published_date to string if it's a datetime
                    if 'published_date' in article and pd.notna(article['published_date']):
                        if isinstance(article['published_date'], pd.Timestamp):
                            article['published_date'] = article['published_date'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    new_articles.append(article)
                    existing_titles.add(normalized_title)
                else:
                    duplicates_skipped += 1
            
            if new_articles:
                # Get month info
                try:
                    dt = datetime.strptime(start_date, '%Y-%m-%d')
                    month_key = dt.strftime('%Y-%m')
                except ValueError:
                    month_key = start_date[:7]  # Assume YYYY-MM-DD format
                
                # Add article_date to each new article for date filtering
                for article in new_articles:
                    if 'published_date' in article and not pd.isna(article['published_date']):
                        article['article_date'] = article['published_date'][:10] if isinstance(article['published_date'], str) else article['published_date']
                    else:
                        article['article_date'] = start_date
                
                # Combine existing and new articles
                all_articles = existing_articles + new_articles
                
                # Sort articles by date for easier lookup
                all_articles.sort(key=lambda x: x.get('article_date', ''))
                
                cache_data = {
                    'month': month_key,
                    'ticker': ticker.upper(),
                    'cached_at': datetime.now().isoformat(),
                    'last_query': query,
                    'results': all_articles,
                    'articles_count': len(all_articles),
                    'methodology': 'monthly_consolidation_with_deduplication'
                }
                
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                
                logger.info(f"Appended {len(new_articles)} new articles to {ticker} weekly cache (skipped {duplicates_skipped} duplicates)")
            else:
                logger.info(f"No new articles to cache for {ticker} (all {duplicates_skipped} were duplicates)")
        
        except Exception as e:
            logger.error(f"Error caching news data for {ticker}: {e}")


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
            
            # Add date exclusions for all searches to prevent future contamination
            target_year = start_dt.year
            if target_year <= 2024:
                # Exclude years after the target year to prevent contamination
                future_years = [str(y) for y in range(target_year + 1, 2027)]
                exclusions = " ".join([f"-{year}" for year in future_years])
                query = f"({site_query}) {ticker} ({date_query}) {exclusions}"
            else:
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
        cached_data = self.cache.get(ticker, start_date, end_date)
        if cached_data is not None:
            logger.info(f"Using cached data for {ticker} {start_date}-{end_date}")
            return cached_data.head(max_results)

        if not self.api_key or not self.search_engine_id:
            logger.error("Google Search API credentials not configured")
            return pd.DataFrame()

        # Build search query
        query = self.build_search_query(ticker, start_date, end_date)

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

            # Use sort parameter with date range in query instead of dateRestrict
            # Google Custom Search dateRestrict is unreliable for historical data
            # Better to use date terms in the query itself for historical accuracy

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

                        # Sort articles by their actual publication dates into appropriate cache files
                        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                        
                        if len(df) > 0:
                            # Group articles by their actual publication dates
                            articles_by_date = {}
                            articles_without_dates = []
                            
                            for idx, row in df.iterrows():
                                pub_date = row['published_date']
                                if pd.notna(pub_date):
                                    date_key = pub_date.strftime('%Y-%m-%d')
                                    if date_key not in articles_by_date:
                                        articles_by_date[date_key] = []
                                    articles_by_date[date_key].append(row.to_dict())
                                else:
                                    articles_without_dates.append(row.to_dict())
                            
                            # Cache articles in their proper date buckets
                            cached_count = 0
                            for date_key, articles in articles_by_date.items():
                                if articles:
                                    articles_df = pd.DataFrame(articles)
                                    self.cache.set(ticker, date_key, date_key, articles_df, query)
                                    cached_count += len(articles)
                                    logger.info(f"Cached {len(articles)} articles for {ticker} on {date_key}")
                            
                            # Cache articles without dates in the original requested date
                            if articles_without_dates:
                                no_date_df = pd.DataFrame(articles_without_dates)
                                self.cache.set(ticker, start_date, end_date, no_date_df, query)
                                logger.info(f"Cached {len(articles_without_dates)} articles without dates for {ticker} on {start_date}")
                                cached_count += len(articles_without_dates)
                            
                            logger.info(f"Total cached: {cached_count} articles across {len(articles_by_date)} dates for {ticker}")
                            
                            # Return articles sorted by relevance for immediate use
                            df = df.sort_values(['relevance_score', 'published_date'],
                                                ascending=[False, False], na_position='last')
                            
                            logger.info(f"Found {len(df)} articles via Google Search for {ticker}")
                            return df.head(max_results)
                        else:
                            logger.info(f"No articles found for {ticker}")
                            return pd.DataFrame()

                else:
                    logger.info(f"No search results found for {ticker}")

            else:
                logger.error(f"Google Search API error: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error in Google search for {ticker}: {e}")

        return pd.DataFrame()

    def _extract_date_from_item(self, item: Dict, start_date: str, end_date: str) -> datetime:
        """Extract publication date from Google search result with strict validation"""

        snippet = item.get('snippet', '')
        
        # PRIORITY 1: Extract date from BEGINNING of snippet (most reliable)
        if snippet:
            # Look for date at start of snippet (Google's publication date)
            date_patterns_start = [
                r'^([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})',  # "May 21, 2025"
                r'^(\d{1,2})/(\d{1,2})/(\d{4})',              # "05/21/2025"
                r'^(\d{4})-(\d{2})-(\d{2})',                   # "2025-05-21"
            ]
            
            for pattern in date_patterns_start:
                match = re.match(pattern, snippet.strip(), re.IGNORECASE)
                if match:
                    try:
                        if len(match.groups()) == 3:
                            if match.group(1).isalpha():
                                # Month name format
                                date_str = f"{match.group(1)} {match.group(2)}, {match.group(3)}"
                                extracted_date = pd.to_datetime(date_str)
                            else:
                                # Numeric format
                                if pattern.startswith('^(\\d{4})'):
                                    extracted_date = pd.to_datetime(f"{match.group(1)}-{match.group(2)}-{match.group(3)}")
                                else:
                                    extracted_date = pd.to_datetime(f"{match.group(1)}/{match.group(2)}/{match.group(3)}")
                            
                            # CRITICAL: Validate date is historical (not future)
                            request_date = datetime.strptime(start_date, '%Y-%m-%d')
                            if extracted_date <= request_date + timedelta(days=1):  # Allow 1 day tolerance
                                return extracted_date
                            else:
                                logger.warning(f"Rejecting future article: {extracted_date.strftime('%Y-%m-%d')} > {start_date}")
                                return None
                    except:
                        continue

        # PRIORITY 2: Try pagemap (structured data)
        if 'pagemap' in item:
            pagemap = item['pagemap']
            for data_type in ['metatags', 'newsarticle', 'article']:
                if data_type in pagemap:
                    for entry in pagemap[data_type]:
                        date_fields = [
                            'article:published_time', 'datePublished', 'publishedDate',
                            'date', 'publish_date', 'publication_date'
                        ]
                        for field in date_fields:
                            if field in entry:
                                try:
                                    extracted_date = pd.to_datetime(entry[field])
                                    request_date = datetime.strptime(start_date, '%Y-%m-%d')
                                    if extracted_date <= request_date + timedelta(days=1):
                                        return extracted_date
                                    else:
                                        logger.warning(f"Rejecting future pagemap date: {extracted_date.strftime('%Y-%m-%d')} > {start_date}")
                                        return None
                                except:
                                    continue

        # PRIORITY 3: Only if no reliable date found, use fallback
        # But mark as suspicious for manual review
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        fallback_date = start_dt + (end_dt - start_dt) / 2
        
        logger.warning(f"No reliable date found for article, using fallback: {fallback_date.strftime('%Y-%m-%d')}")
        return fallback_date

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
