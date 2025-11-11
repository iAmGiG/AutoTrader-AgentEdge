"""
Google Custom Search News Tool
Uses Google Custom Search API to find historical financial news from premium sources like Barrons
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from typing import Optional, Dict
from typing import List, Dict, Optional
import logging
from urllib.parse import urlparse
import re
from autogen_core.tools import FunctionTool
# Quota management removed for simplified V0-V4 framework
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Ticker disambiguation configuration for ambiguous stock symbols
TICKER_SEARCH_OVERRIDES = {
    'SPY': {
        'enhanced_terms': ['SPDR S&P 500 ETF SPY', 'S&P 500 index fund SPY'],
        'negative_filters': ['-espionage', '-intelligence', '-CIA', '-FBI', '-surveillance', '-agent', '-security'],
        'required_context': ['market', 'stock', 'index', 'etf', 'fund', 's&p', 'trading', 'spdr']
    },
    'CAT': {
        'enhanced_terms': ['Caterpillar Inc CAT stock', 'CAT machinery earnings'],
        'negative_filters': ['-pet', '-animal', '-kitten', '-cat food'],
        'required_context': ['machinery', 'construction', 'earnings', 'industrial', 'equipment']
    },
    'HOME': {
        'enhanced_terms': ['Home Depot HD stock', 'HOME retail earnings'],
        'negative_filters': ['-real estate', '-mortgage', '-housing market', '-home sales'],
        'required_context': ['retail', 'store', 'earnings', 'depot', 'home improvement']
    },
    'PLUG': {
        'enhanced_terms': ['Plug Power PLUG stock', 'PLUG fuel cell company'],
        'negative_filters': ['-electrical plug', '-power plug', '-charger'],
        'required_context': ['fuel cell', 'hydrogen', 'energy', 'stock', 'earnings']
    },
    'WOOD': {
        'enhanced_terms': ['ARK Innovation ETF ARKK WOOD', 'Cathie Wood ARK'],
        'negative_filters': ['-lumber', '-timber', '-forest', '-wooden'],
        'required_context': ['ETF', 'innovation', 'ARK', 'Cathie Wood', 'investment']
    }
}


class GoogleSearchNewsCache:
    """Cache manager for Google search results with monthly organization structure"""

    def __init__(self, cache_dir: str = "./.cache/news_filtered"):
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
        title = re.sub(
            r'^(BREAKING:|UPDATE:|EXCLUSIVE:|CORRECTING AND REPLACING)[\s/]*', '', title, flags=re.IGNORECASE)
        title = re.sub(
            r'\s*[-–—]\s*(MarketWatch|WSJ|Bloomberg|Reuters|CNBC|Barrons).*$', '', title, flags=re.IGNORECASE)

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

                    # Use URL-extracted date as fallback for NaN published_dates
                    if 'published_date' in df.columns and 'article_date' in df.columns:
                        # Convert to datetime
                        df['published_date'] = pd.to_datetime(df['published_date'], errors='coerce')
                        df['article_date'] = pd.to_datetime(df['article_date'], errors='coerce')

                        # Use article_date as fallback for NaN published_dates
                        df['published_date'] = df['published_date'].fillna(df['article_date'])

                    # Enhanced date filtering for V4 daily requests vs V1/V3 range requests
                    if 'article_date' in df.columns:
                        df['article_date'] = pd.to_datetime(df['article_date'])
                        start_dt = pd.to_datetime(start_date)
                        end_dt = pd.to_datetime(end_date)

                        # Check if this is a daily request (V4 pattern: start_date == end_date)
                        if start_date == end_date:
                            # V4 daily request: Return articles in a relevant time window around target date
                            window_days = 3  # ±3 days window for daily relevance
                            window_start = start_dt - timedelta(days=window_days)
                            window_end = start_dt + timedelta(days=window_days)
                            df_filtered = df[(df['article_date'] >= window_start)
                                             & (df['article_date'] <= window_end)]
                            logger.info(
                                f"Using cached news for {ticker} (daily window): {len(df_filtered)} articles around {start_date} (±{window_days} days)")
                        else:
                            # V1/V3 range request: Original logic - all articles up to end_date
                            df_filtered = df[df['article_date'] <= end_dt]
                            logger.info(
                                f"Using cached news for {ticker} (range): {len(df_filtered)} articles up to {end_date}")

                        return df_filtered
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

                            logger.info(
                                f"Using nearby cached news for {ticker} from {check_date.strftime('%Y-%m-%d')} (offset: {days_offset} days)")
                            return df
                    except Exception as e:
                        continue

            return None

        except Exception as e:
            logger.error(f"Error searching nearby dates for {ticker}: {e}")
            return None

    def set(self, ticker: str, start_date: str, end_date: str, data: pd.DataFrame, query: str = ""):
        """Cache search results with set-based deduplication and WSJ segregation"""
        if data.empty:
            return

        # Filter for relevant articles only
        data = data[data.get('relevance_score', 0.0) > 0.0].copy()
        if data.empty:
            logger.info(f"No relevant articles to cache for {ticker}")
            return

        # Cache all articles directly (WSJ already filtered out at source level)
        self._cache_articles_to_file(ticker, start_date, data, query)
        logger.info(f"Cached {len(data)} articles for {ticker}")

    def _cache_articles_to_file(self, ticker: str, start_date: str, data: pd.DataFrame, query: str):
        """Internal method to cache articles to file"""
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
                    # Clean up NaN values and convert dates to strings
                    for key in article:
                        if pd.isna(article[key]):
                            article[key] = None

                    # Convert published_date to string if it's a datetime
                    if 'published_date' in article and pd.notna(article['published_date']):
                        if isinstance(article['published_date'], pd.Timestamp):
                            article['published_date'] = article['published_date'].strftime(
                                '%Y-%m-%d %H:%M:%S')

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
                        article['article_date'] = article['published_date'][:10] if isinstance(
                            article['published_date'], str) else article['published_date']
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

                logger.info(
                    f"Appended {len(new_articles)} new articles to {ticker} weekly cache (skipped {duplicates_skipped} duplicates)")
            else:
                logger.info(
                    f"No new articles to cache for {ticker} (all {duplicates_skipped} were duplicates)")

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

    def get_enhanced_ticker_term(self, ticker: str) -> str:
        """
        Get enhanced search term for ambiguous tickers

        Args:
            ticker: Stock ticker symbol

        Returns:
            Enhanced search term or original ticker if no override exists
        """
        ticker_upper = ticker.upper()

        if ticker_upper in TICKER_SEARCH_OVERRIDES:
            # Use the first (primary) enhanced term for the ticker
            enhanced_terms = TICKER_SEARCH_OVERRIDES[ticker_upper]['enhanced_terms']
            if enhanced_terms:
                logger.info(f"Using enhanced search term for {ticker}: {enhanced_terms[0]}")
                return enhanced_terms[0]

        return ticker  # No override needed, use original ticker

    def filter_results_by_context(self, results_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """
        Filter results based on ticker disambiguation rules

        Args:
            results_df: DataFrame with search results
            ticker: Original ticker symbol

        Returns:
            Filtered DataFrame with only contextually relevant articles
        """
        ticker_upper = ticker.upper()

        if ticker_upper not in TICKER_SEARCH_OVERRIDES:
            return results_df  # No filtering needed

        config = TICKER_SEARCH_OVERRIDES[ticker_upper]
        required_context = config.get('required_context', [])
        negative_filters = config.get('negative_filters', [])

        if results_df.empty or not required_context:
            return results_df

        filtered_results = []

        for _, article in results_df.iterrows():
            title_lower = str(article.get('title', '')).lower()
            summary_lower = str(article.get('summary', '')).lower()
            text = title_lower + ' ' + summary_lower

            # Check for required financial context
            has_required_context = any(keyword.lower() in text for keyword in required_context)

            # Check for negative filters (intelligence/spy terms for SPY)
            has_negative_content = any(
                neg_filter.replace('-', '').lower() in text
                for neg_filter in negative_filters
            )

            # Keep article if it has required context and no negative content
            if has_required_context and not has_negative_content:
                filtered_results.append(article)
            elif ticker_upper == 'SPY' and any(term in text for term in ['s&p', 'etf', 'fund', 'index']) and not has_negative_content:
                # Special case for SPY - keep if clearly financial even without all context
                filtered_results.append(article)

        if filtered_results:
            filtered_df = pd.DataFrame(filtered_results)
            logger.info(
                f"Content filtering for {ticker}: {len(results_df)} → {len(filtered_df)} articles")
            return filtered_df
        else:
            # If filtering too aggressive, return original results
            logger.warning(
                f"Content filtering for {ticker} too aggressive, returning original results")
            return results_df

    def build_search_query(self, ticker: str, start_date: str, end_date: str,
                           source_sites: List[str] = None) -> str:
        """Build optimized search query for historical financial news with ticker disambiguation"""

        # Updated configuration - sources with reliable historical data OR URL dates
        # Business Wire + Reuters: proven date accuracy
        # CNBC + Bloomberg: 100% reliable URL date patterns
        if not source_sites:
            source_sites = [
                "businesswire.com",  # 100% date accuracy, 0% contamination
                "reuters.com",       # 75% date accuracy, 25% contamination
                "cnbc.com",          # 100% URL date extraction accuracy
                "bloomberg.com",     # 100% URL date extraction accuracy
            ]

        # Build site restriction
        site_query = " OR ".join([f"site:{site}" for site in source_sites])

        # Get enhanced ticker term for disambiguation
        enhanced_ticker = self.get_enhanced_ticker_term(ticker)

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

            # Build query with historical context - simplified
            date_query = " OR ".join(historical_terms)
            # Exclude recent years
            query = f"({site_query}) {enhanced_ticker} ({date_query}) -2024 -2025"
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

            # Simple, focused query for reliable historical data
            target_year = start_dt.year
            month_year = start_dt.strftime('%B %Y')  # e.g., "October 2024"

            # With only 2 reliable sources, we can use site restriction directly
            # This ensures we only get results from sources with good date accuracy
            if target_year <= 2024:
                # Include year exclusions to prevent future contamination
                query = f"({site_query}) {enhanced_ticker} \"{month_year}\" -2025 -2026"
            else:
                query = f"({site_query}) {enhanced_ticker} \"{month_year}\""

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

        # Use URL pattern search strategy (more effective than combined queries)
        return self._search_with_url_patterns(ticker, start_date, end_date, max_results)

    def _search_with_url_patterns(self, ticker: str, start_date: str, end_date: str, max_results: int) -> pd.DataFrame:
        """
        Search using individual URL pattern queries for each reliable source
        More effective than combined OR queries - now with ticker disambiguation
        """

        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        year_month = start_dt.strftime('%Y-%m')  # e.g., "2024-10"

        # Get enhanced ticker term for disambiguation
        enhanced_ticker = self.get_enhanced_ticker_term(ticker)

        # Individual URL pattern queries for each reliable source using enhanced ticker
        source_queries = [
            (f"site:cnbc.com/{year_month.replace('-', '/')} {enhanced_ticker}", "CNBC"),
            (f"site:bloomberg.com/news/articles/{year_month} {enhanced_ticker}", "Bloomberg"),
            (f"site:reuters.com {enhanced_ticker} {year_month}", "Reuters"),
            # YYYYMM format
            (f"site:businesswire.com {enhanced_ticker} {year_month.replace('-', '')}", "BusinessWire")
        ]

        all_results = []

        logger.info(f"Using URL pattern search strategy for {ticker} {year_month}")

        for query, source_name in source_queries:
            logger.info(f"Searching {source_name}: {query}")

            try:
                # Google Custom Search API endpoint
                url = "https://www.googleapis.com/customsearch/v1"

                params = {
                    'key': self.api_key,
                    'cx': self.search_engine_id,
                    'q': query,
                    'num': min(3, max_results),  # 3 results per source, max 12 total
                }

                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])

                    logger.info(f"{source_name}: Found {len(items)} results")

                    for item in items:
                        title = item.get('title', 'Untitled')
                        snippet = item.get('snippet', '')
                        link = item.get('link', '')

                        if not link:
                            continue

                        # Extract publication date from URL pattern
                        published_date = self._extract_date_from_url(link)
                        if not published_date:
                            # Fallback to estimated date from search
                            published_date = start_dt

                        # Calculate relevance score
                        relevance_score = self._calculate_relevance(title, snippet, ticker)

                        # Only include if relevance score > 0
                        if relevance_score > 0:
                            result = {
                                'title': title,
                                'summary': snippet,
                                'url': link,
                                'published_date': published_date,
                                'source': f'Google Search - {source_name}',
                                'Data_Source': 'Google_Search_Historical',
                                'sentiment_ready': True,
                                'relevance_score': relevance_score,
                                'ticker': ticker.upper(),
                                'url_pattern_source': source_name
                            }
                            all_results.append(result)

                elif response.status_code == 429:
                    logger.warning(f"Rate limit hit for {source_name}")
                    break  # Stop trying other sources if we hit rate limit
                else:
                    logger.warning(f"{source_name} search failed: {response.status_code}")

            except Exception as e:
                logger.error(f"Error searching {source_name}: {e}")
                continue

        if all_results:
            df = pd.DataFrame(all_results)

            # Remove duplicates by URL
            df = df.drop_duplicates(subset=['url'], keep='first')

            # Apply content filtering for ambiguous tickers
            df = self.filter_results_by_context(df, ticker)

            # Sort by relevance score and date
            df = df.sort_values(['relevance_score', 'published_date'],
                                ascending=[False, False], na_position='last')

            # Cache the filtered results
            if len(df) > 0:
                query_summary = f"URL_patterns_{len(source_queries)}_sources_filtered"
                self.cache.set(ticker, start_date, end_date, df, query_summary)
                logger.info(f"Cached {len(df)} filtered articles from URL pattern search")

            logger.info(f"URL pattern search found {len(df)} quality articles for {ticker}")
            return df.head(max_results)
        else:
            logger.info(f"No results found via URL pattern search for {ticker}")
            return pd.DataFrame()

    def _extract_date_from_url(self, url: str) -> Optional[datetime]:
        """Extract publication date from URL patterns of reliable sources"""
        import re

        # CNBC: /yyyy/mm/dd/
        cnbc_pattern = r'cnbc\.com/(\d{4})/(\d{2})/(\d{2})/'
        match = re.search(cnbc_pattern, url)
        if match:
            year, month, day = match.groups()
            try:
                return datetime(int(year), int(month), int(day))
            except:
                pass

        # Bloomberg: /news/articles/yyyy-mm-dd/
        bloomberg_pattern = r'bloomberg\.com/news/articles/(\d{4})-(\d{2})-(\d{2})'
        match = re.search(bloomberg_pattern, url)
        if match:
            year, month, day = match.groups()
            try:
                return datetime(int(year), int(month), int(day))
            except:
                pass

        # Reuters: article-name-yyyy-mm-dd/ at the end
        reuters_pattern = r'reuters\.com/.*-(\d{4})-(\d{2})-(\d{2})/?$'
        match = re.search(reuters_pattern, url)
        if match:
            year, month, day = match.groups()
            try:
                return datetime(int(year), int(month), int(day))
            except:
                pass

        # Business Wire: /home/YYYYMMDD#####/
        businesswire_pattern = r'businesswire\.com/news/home/(\d{4})(\d{2})(\d{2})\d+/'
        match = re.search(businesswire_pattern, url)
        if match:
            year, month, day = match.groups()
            try:
                return datetime(int(year), int(month), int(day))
            except:
                pass

        return None

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
                                    extracted_date = pd.to_datetime(
                                        f"{match.group(1)}-{match.group(2)}-{match.group(3)}")
                                else:
                                    extracted_date = pd.to_datetime(
                                        f"{match.group(1)}/{match.group(2)}/{match.group(3)}")

                            # CRITICAL: Validate date is historical (not future)
                            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                            # Allow articles up to the end date plus 7 days tolerance
                            if extracted_date <= end_date_obj + timedelta(days=7):
                                return extracted_date
                            else:
                                logger.warning(
                                    f"Rejecting future article: {extracted_date.strftime('%Y-%m-%d')} > {end_date}")
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
                                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                                    if extracted_date <= end_date_obj + timedelta(days=7):
                                        return extracted_date
                                    else:
                                        logger.warning(
                                            f"Rejecting future pagemap date: {extracted_date.strftime('%Y-%m-%d')} > {end_date}")
                                        return None
                                except:
                                    continue

        # PRIORITY 3: Only if no reliable date found, use fallback
        # But mark as suspicious for manual review
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        fallback_date = start_dt + (end_dt - start_dt) / 2

        logger.warning(
            f"No reliable date found for article, using fallback: {fallback_date.strftime('%Y-%m-%d')}")
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
