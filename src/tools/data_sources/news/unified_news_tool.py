"""
Unified News Data Tool for fetching from multiple news sources with a consistent interface.

This tool provides a unified abstraction layer for retrieving financial news data 
from multiple sources (AlphaVantage, Finnhub, NewsAPI, etc.) with standardized output
and configurable source selection.

Features:
- Fetch news from multiple sources with a single call
- Consistent output format regardless of source
- Configurable sources and priorities
- Easy addition of new sources
- Async fetching for improved performance
"""

from src.tools.processors.sentiment_analyzer import SentimentAnalyzer
from src.tools.processors.data_normalizer import normalize_data_for_sentiment
from src.tools.data_sources.news.finnhub_tool import FinnHubTool
from src.tools.data_sources.news.alpha_vantage_news import AlphaVantageNewsTool
from src.tools.data_sources.news.news_headline_tool import NewsHeadlineTool
from pydantic import BaseModel, Field
import pandas as pd
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Literal
from datetime import datetime
import os
import json
import asyncio
from config.config_loader import ConfigLoader

config_loader = ConfigLoader()


# Import individual news data sources


# =====================
# Pydantic data models
# =====================

class NewsSource(BaseModel):
    """Configuration for a news data source"""
    name: str
    enabled: bool = True
    priority: int = 1
    api_key_config_name: Optional[str] = None

    # Source-specific configuration
    config: Dict[str, Any] = {}


class NewsArticle(BaseModel):
    """Standardized news article schema"""
    source_id: str
    title: str
    url: Optional[str] = None
    published_date: datetime
    summary: Optional[str] = None
    content: Optional[str] = None
    tickers: List[str] = []
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    categories: List[str] = []

    # Original data (for debugging/reference)
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class NewsQueryParams(BaseModel):
    """Parameters for news query"""
    ticker: Optional[str] = None
    keywords: Optional[List[str]] = None
    start_date: Optional[str] = "-7d"  # Default 7 days ago
    end_date: Optional[str] = "today"
    sources: Optional[List[str]] = None  # None means "all enabled sources"
    category: Optional[Literal["financial", "economic", "general"]] = None
    count: Optional[int] = 10
    include_sentiment: bool = True


# =====================
# Source providers
# =====================

class NewsSourceProvider(ABC):
    """Abstract base class for news source providers"""

    def __init__(self, config: NewsSource):
        self.config = config
        self.sentiment_analyzer = SentimentAnalyzer()
        self._load_api_key()

    def _load_api_key(self):
        """Load API key from environment if configured"""
        if self.config.api_key_config_name:
            self.api_key = os.getenv(
                self.config.api_key_config_name.upper(),
                config_loader.get(self.config.api_key_config_name.upper()),
            )
        else:
            self.api_key = None

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this news source"""
        pass

    @property
    def supported_query_params(self) -> List[str]:
        """List of query parameters this source supports"""
        return ["keywords", "start_date", "end_date", "count"]

    @abstractmethod
    def fetch_news(self, params: NewsQueryParams) -> List[NewsArticle]:
        """Fetch news from this source using provided parameters"""
        pass

    def add_sentiment(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Add sentiment analysis to articles if not already present"""
        for article in articles:
            if article.sentiment_score is None:
                # Use title + summary if available, otherwise just title
                text = article.title
                if article.summary:
                    text += " " + article.summary

                # Calculate sentiment
                article.sentiment_score = self.sentiment_analyzer.analyze_text(
                    text)

                # Add label based on score
                if article.sentiment_score > 0.2:
                    article.sentiment_label = "positive"
                elif article.sentiment_score < -0.2:
                    article.sentiment_label = "negative"
                else:
                    article.sentiment_label = "neutral"

        return articles


class AlphaVantageNewsProvider(NewsSourceProvider):
    """AlphaVantage news provider implementation"""

    def __init__(self, config: NewsSource):
        super().__init__(config)
        self._alpha_vantage_tool = AlphaVantageNewsTool()

    @property
    def source_id(self) -> str:
        return "alpha_vantage"

    @property
    def supported_query_params(self) -> List[str]:
        return ["ticker", "start_date", "end_date"]

    def fetch_news(self, params: NewsQueryParams) -> List[NewsArticle]:
        """Fetch news from AlphaVantage"""
        if not params.ticker:
            return []

        try:
            # Get news from AlphaVantage
            df = self._alpha_vantage_tool.fetch_news_sentiment(params.ticker)

            # Exit early if no results
            if df is None or df.empty:
                return []

            # Normalize the data
            normalized_df = normalize_data_for_sentiment(
                df, "alpha_vantage", symbol=params.ticker)
            if normalized_df is None or normalized_df.empty:
                normalized_df = df

            # Convert to standardized articles
            articles = []
            for _, row in normalized_df.iterrows():
                # Create article object
                # Handle ticker_sentiment - it may be a list of dicts instead of strings
                ticker_list = [params.ticker]
                ticker_sentiment = row.get('ticker_sentiment', [])
                if ticker_sentiment and isinstance(ticker_sentiment, list):
                    # If it's a list of dicts, extract the ticker strings
                    if ticker_sentiment and isinstance(ticker_sentiment[0], dict):
                        extra_tickers = [item.get('ticker', '') for item in ticker_sentiment if isinstance(
                            item, dict) and 'ticker' in item]
                    else:
                        extra_tickers = ticker_sentiment
                    ticker_list.extend([t for t in extra_tickers if t])

                article = NewsArticle(
                    source_id=self.source_id,
                    title=row.get('title', ''),
                    url=row.get('url', None),
                    published_date=pd.to_datetime(
                        row.get('time_published', row.get('timestamp', datetime.now()))),
                    summary=row.get('summary', None),
                    tickers=ticker_list,
                    # Use pre-calculated sentiment if available
                    sentiment_score=row.get('sentiment_score', None),
                    sentiment_label=row.get('sentiment', None),
                    categories=row.get('categories', []),
                    raw_data=row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                )
                articles.append(article)

            # Limit to requested count
            articles = articles[:params.count]

            # Add sentiment if needed
            if params.include_sentiment:
                articles = self.add_sentiment(articles)

            return articles

        except Exception as e:
            print(f"Error in AlphaVantageNewsProvider: {e}")
            return []


class FinnhubNewsProvider(NewsSourceProvider):
    """Finnhub news provider implementation"""

    def __init__(self, config: NewsSource):
        super().__init__(config)
        self._finnhub_tool = FinnHubTool(self.api_key)

    @property
    def source_id(self) -> str:
        return "finnhub"

    @property
    def supported_query_params(self) -> List[str]:
        return ["ticker", "keywords", "category", "count"]

    def fetch_news(self, params: NewsQueryParams) -> List[NewsArticle]:
        """Fetch news from Finnhub"""
        try:
            df = None

            # Determine which method to call based on parameters
            if params.ticker:
                # Ticker-specific news
                df = self._finnhub_tool.fetch_news(
                    category="general",
                    tickers=[params.ticker],
                    count=params.count or 10
                )
            elif params.category == "economic":
                # Economic headlines
                df = self._finnhub_tool.fetch_economic_headlines(
                    count=params.count or 10
                )
            elif params.category == "financial" or params.category is None:
                # Financial headlines (default)
                df = self._finnhub_tool.fetch_financial_headlines(
                    count=params.count or 10
                )
            else:
                # General category
                df = self._finnhub_tool.fetch_news(
                    category=params.category or "general",
                    count=params.count or 10
                )

            # Exit early if no results
            if df is None or df.empty:
                return []

            # Convert to standardized articles
            articles = []
            for _, row in df.iterrows():
                # Skip if doesn't match keywords
                if params.keywords and not any(kw.lower() in row.get('headline', '').lower()
                                               for kw in params.keywords):
                    continue

                # Create article object
                # Get published date - Finnhub tool already converts datetime to Date column
                pub_date = row.get('Date', None)
                if pub_date is None and 'datetime' in row:
                    # If we have raw datetime timestamp, convert it
                    pub_date = pd.to_datetime(row['datetime'], unit='s')
                elif pub_date is None:
                    # Fallback to current time
                    pub_date = datetime.now()

                article = NewsArticle(
                    source_id=self.source_id,
                    title=row.get('Headline', row.get('headline', '')),
                    url=row.get('URL', row.get('url', None)),
                    published_date=pub_date,
                    summary=row.get('Summary', row.get('summary', None)),
                    tickers=row.get('related') if isinstance(
                        row.get('related'), list) else [],
                    categories=[
                        row.get('Category', row.get('category', 'general'))],
                    raw_data=row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                )
                articles.append(article)

            # Limit to requested count
            articles = articles[:params.count]

            # Add sentiment if needed
            if params.include_sentiment:
                articles = self.add_sentiment(articles)

            return articles

        except Exception as e:
            print(f"Error in FinnhubNewsProvider: {e}")
            return []


class NewsAPIProvider(NewsSourceProvider):
    """NewsAPI provider implementation"""

    def __init__(self, config: NewsSource):
        super().__init__(config)
        self._news_headline_tool = NewsHeadlineTool(source="newsapi")

    @property
    def source_id(self) -> str:
        return "newsapi"

    @property
    def supported_query_params(self) -> List[str]:
        return ["keywords", "count"]

    def fetch_news(self, params: NewsQueryParams) -> List[NewsArticle]:
        """Fetch news from NewsAPI"""
        try:
            # Use ticker as keyword if no keywords provided
            keyword = params.ticker
            if params.keywords:
                keyword = " ".join(params.keywords)

            if not keyword:
                # Default to general market news
                keyword = "market"

            # Get news from NewsAPI
            df = self._news_headline_tool.fetch_data(
                keyword=keyword,
                count=params.count or 10
            )

            # Exit early if no results
            if df is None or df.empty:
                return []

            # Convert to standardized articles
            articles = []
            for _, row in df.iterrows():
                # Skip if doesn't match ticker
                if params.ticker and params.ticker.lower() not in row.get('Content', '').lower():
                    continue

                # Create article object
                article = NewsArticle(
                    source_id=self.source_id,
                    title=row.get('Headline', ''),
                    url=row.get('URL', None),
                    published_date=pd.to_datetime(
                        row.get('Timestamp', datetime.now())),
                    content=row.get('Content', None),
                    categories=[],
                    raw_data=row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                )
                articles.append(article)

            # Limit to requested count
            articles = articles[:params.count]

            # Add sentiment if needed
            if params.include_sentiment:
                articles = self.add_sentiment(articles)

            return articles

        except Exception as e:
            print(f"Error in NewsAPIProvider: {e}")
            return []


# =====================
# Source registry
# =====================

class NewsSourceRegistry:
    """Registry of available news sources"""

    def __init__(self):
        """Initialize the registry with default sources"""
        self._sources = {}
        self._load_sources_from_config()

    def _load_sources_from_config(self):
        """Load news sources from configuration file"""
        # Default source configurations
        default_sources = [
            NewsSource(
                name="alpha_vantage",
                enabled=True,
                priority=3,
                api_key_config_name="alpha_vantage_key",
                config={"sentiment_included": True}
            ),
            NewsSource(
                name="finnhub",
                enabled=True,
                priority=1,
                api_key_config_name="finnhub_key",
                config={"categories": ["general", "forex", "crypto", "merger"]}
            ),
            NewsSource(
                name="newsapi",
                enabled=True,
                priority=2,
                api_key_config_name="newsapi_key",
                config={"default_language": "en"}
            )
        ]

        # Try to load from config file if it exists
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))), "config")
        config_path = os.path.join(config_dir, "news_sources.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    sources_config = json.load(f)

                # Create sources from config
                sources = [NewsSource(**source_config)
                           for source_config in sources_config]
            except Exception as e:
                print(f"Error loading news sources config: {e}")
                sources = default_sources
        else:
            sources = default_sources

        # Create provider instances
        for source in sources:
            if not source.enabled:
                continue

            # Create appropriate provider based on source name
            if source.name == "alpha_vantage":
                provider = AlphaVantageNewsProvider(source)
            elif source.name == "finnhub":
                provider = FinnhubNewsProvider(source)
            elif source.name == "newsapi":
                provider = NewsAPIProvider(source)
            else:
                print(f"Unknown news source: {source.name}")
                continue

            self._sources[source.name] = provider

    def get_provider(self, name: str) -> Optional[NewsSourceProvider]:
        """Get a specific provider by name"""
        return self._sources.get(name)

    def get_all_providers(self) -> List[NewsSourceProvider]:
        """Get all registered providers"""
        return list(self._sources.values())

    def get_enabled_providers(self, sources: Optional[List[str]] = None) -> List[NewsSourceProvider]:
        """
        Get enabled providers, optionally filtered by source names

        Args:
            sources: List of source names to include, or None for all

        Returns:
            List of enabled provider instances
        """
        if sources:
            return [self._sources[name] for name in sources if name in self._sources]
        else:
            return self.get_all_providers()


# =====================
# Unified news controller
# =====================

class UnifiedNewsController:
    """Controller for unified news fetching"""

    def __init__(self):
        """Initialize with source registry"""
        self.registry = NewsSourceRegistry()
        self.sentiment_analyzer = SentimentAnalyzer()

    async def fetch_unified_news(self, params: NewsQueryParams) -> pd.DataFrame:
        """
        Fetch news from multiple sources based on parameters

        Args:
            params: Query parameters for fetching news

        Returns:
            DataFrame with unified news data
        """
        # Get enabled providers
        providers = self.registry.get_enabled_providers(params.sources)

        # Filter providers based on supported parameters
        filtered_providers = []
        for provider in providers:
            # Skip if provider doesn't support ticker queries when ticker is specified
            if params.ticker and "ticker" not in provider.supported_query_params:
                continue
            filtered_providers.append(provider)

        # Fetch from all filtered providers (run in parallel)
        all_articles = []
        tasks = []

        for provider in filtered_providers:
            # Create async task for each provider
            task = asyncio.create_task(
                self._fetch_from_provider(provider, params)
            )
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks)

        # Flatten results
        for articles in results:
            all_articles.extend(articles)

        # Deduplicate articles
        deduplicated = self._deduplicate_articles(all_articles)

        # Limit to requested count
        limited_articles = deduplicated[:params.count] if params.count else deduplicated

        # Convert to DataFrame
        if not limited_articles:
            return pd.DataFrame()

        # Convert to dictionary records
        articles_dicts = [article.dict(
            exclude={"raw_data"}) for article in limited_articles]

        # Create DataFrame
        df = pd.DataFrame(articles_dicts)

        # Add convenience columns
        if 'sentiment_score' in df.columns:
            # Map sentiment score to readable labels if not already present
            if 'sentiment_label' not in df.columns:
                df['sentiment_label'] = df['sentiment_score'].apply(
                    lambda x: 'positive' if x > 0.2 else ('negative' if x < -0.2 else 'neutral'))

        return df

    async def _fetch_from_provider(self, provider: NewsSourceProvider,
                                   params: NewsQueryParams) -> List[NewsArticle]:
        """
        Fetch articles from a specific provider

        Args:
            provider: The news source provider
            params: Query parameters

        Returns:
            List of news articles
        """
        try:
            # Run provider's fetch_news in a thread pool
            loop = asyncio.get_event_loop()
            articles = await loop.run_in_executor(
                None, lambda: provider.fetch_news(params)
            )
            return articles
        except Exception as e:
            print(f"Error fetching from {provider.source_id}: {e}")
            return []

    def _deduplicate_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """
        Remove duplicate articles based on title similarity

        Args:
            articles: List of articles to deduplicate

        Returns:
            Deduplicated list of articles
        """
        # Simple deduplication by title
        seen_titles = set()
        unique_articles = []

        for article in articles:
            # Normalize title for comparison (lowercase, remove punctuation)
            norm_title = "".join(c.lower()
                                 for c in article.title if c.isalnum())

            # Skip if we've seen this title before
            if norm_title in seen_titles:
                continue

            seen_titles.add(norm_title)
            unique_articles.append(article)

        return unique_articles


# =====================
# Helper functions for tool interface
# =====================

def create_query_params(
    keywords: Optional[Union[str, List[str]]] = None,
    ticker: Optional[str] = None,
    start_date: str = "-7d",
    end_date: str = "today",
    category: Optional[str] = None,
    sources: Optional[Union[str, List[str]]] = None,
    count: int = 10,
    include_sentiment: bool = True
) -> NewsQueryParams:
    """
    Create query parameters from function arguments

    Args:
        keywords: Keywords to search for (string or list)
        ticker: Stock ticker to get news about
        start_date: Start date for news
        end_date: End date for news
        category: Type of news to fetch
        sources: News sources to use (comma-separated string or list)
        count: Maximum number of news articles to return
        include_sentiment: Whether to include sentiment analysis

    Returns:
        NewsQueryParams object
    """
    # Convert string keywords to list
    if isinstance(keywords, str):
        keywords_list = [kw.strip() for kw in keywords.split(",")]
    else:
        keywords_list = keywords

    # Convert string sources to list
    if isinstance(sources, str):
        sources_list = [s.strip() for s in sources.split(",")]
    else:
        sources_list = sources

    # Create params object
    return NewsQueryParams(
        ticker=ticker,
        keywords=keywords_list,
        start_date=start_date,
        end_date=end_date,
        category=category,
        sources=sources_list,
        count=count,
        include_sentiment=include_sentiment
    )


async def fetch_unified_news_async(
    keywords: Optional[str] = None,
    ticker: Optional[str] = None,
    start_date: str = "-7d",
    end_date: str = "today",
    category: Optional[str] = None,
    sources: Optional[str] = None,
    count: int = 10,
    include_sentiment: bool = True
) -> Dict[str, Any]:
    """
    Async function to fetch unified news

    Args:
        keywords: Keywords to search for (comma-separated)
        ticker: Stock ticker to get news about
        start_date: Start date for news (YYYY-MM-DD or relative like "-7d")
        end_date: End date for news (YYYY-MM-DD or "today")
        category: Type of news to fetch ("financial", "economic", "general")
        sources: Comma-separated list of sources to use
        count: Maximum number of news articles to return
        include_sentiment: Whether to include sentiment analysis

    Returns:
        Dictionary with news articles and metadata
    """
    # Create controller
    controller = UnifiedNewsController()

    # Create query parameters
    params = create_query_params(
        keywords=keywords,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        category=category,
        sources=sources,
        count=count,
        include_sentiment=include_sentiment
    )

    # Execute query
    df = await controller.fetch_unified_news(params)

    # Handle empty results
    if df.empty:
        return {
            "articles": [],
            "count": 0,
            "sources_used": [],
            "message": "No news articles found matching the criteria"
        }

    # Convert dates to strings for serialization
    if 'published_date' in df.columns:
        df['published_date'] = df['published_date'].dt.strftime(
            '%Y-%m-%d %H:%M:%S')

    # Calculate relevance scores
    if keywords or ticker:
        df['relevance_score'] = 0.0

        # Calculate keyword matches in title and summary/content
        if keywords and 'title' in df.columns:
            keyword_list = keywords.lower().split(',') if isinstance(
                keywords, str) else [k.lower() for k in keywords]
            for keyword in keyword_list:
                # Check title matches
                if 'title' in df.columns:
                    df['title_match'] = df['title'].str.lower().str.contains(
                        keyword, na=False).astype(float) * 2.0
                    df['relevance_score'] += df['title_match']

                # Check summary/content matches
                if 'summary' in df.columns:
                    df['summary_match'] = df['summary'].str.lower(
                    ).str.contains(keyword, na=False).astype(float)
                    df['relevance_score'] += df['summary_match']
                elif 'content' in df.columns:
                    df['content_match'] = df['content'].str.lower(
                    ).str.contains(keyword, na=False).astype(float)
                    df['relevance_score'] += df['content_match']

        # Add ticker relevance
        if ticker and 'tickers' in df.columns:
            df['ticker_match'] = df['tickers'].apply(
                lambda x: 3.0 if ticker.upper() in [t.upper() for t in x] else 0.0)
            df['relevance_score'] += df['ticker_match']

        # Sort by relevance score
        df = df.sort_values(by='relevance_score', ascending=False)

        # Drop helper columns
        for col in ['title_match', 'summary_match', 'content_match', 'ticker_match']:
            if col in df.columns:
                df = df.drop(columns=[col])

    # Find very low relevance articles
    low_relevance_count = 0
    if 'relevance_score' in df.columns:
        low_relevance_count = (df['relevance_score'] < 0.5).sum()

    # Format the result with search guidance
    result = {
        "articles": df.to_dict(orient="records"),
        "count": len(df),
        "sources_used": df['source_id'].unique().tolist() if not df.empty else [],
        "ticker": ticker,
        "keywords": keywords,
        "date_range": f"{start_date} to {end_date}"
    }

    # Add search guidance
    if len(df) == 0:
        result["search_guidance"] = "No articles found. Try broader keywords, a different ticker, or a wider date range."
    elif low_relevance_count > 0 and low_relevance_count >= len(df) / 2:
        result["search_guidance"] = f"{low_relevance_count} of {len(df)} articles have low relevance. Consider refining keywords for more specific results."
    elif len(df) < 3 and (keywords or ticker):
        result["search_guidance"] = f"Only {len(df)} articles found. Try broader keywords or a wider date range."
    else:
        result["search_guidance"] = f"Found {len(df)} relevant articles from {len(result['sources_used'])} source(s)."

    return result


def fetch_unified_news(
    keywords: Optional[str] = None,
    ticker: Optional[str] = None,
    start_date: str = "-7d",
    end_date: str = "today",
    category: Optional[str] = None,
    sources: Optional[str] = None,
    count: int = 10,
    include_sentiment: bool = True
) -> Dict[str, Any]:
    """
    Fetch news from multiple sources with unified output format.

    Args:
        keywords: Keywords to search for (comma-separated)
        ticker: Stock ticker to get news about
        start_date: Start date for news (YYYY-MM-DD or relative like "-7d")
        end_date: End date for news (YYYY-MM-DD or "today")
        category: Type of news to fetch ("financial", "economic", "general")
        sources: Comma-separated list of sources to use (default: all sources)
        count: Maximum number of news articles to return
        include_sentiment: Whether to include sentiment analysis

    Returns:
        Dictionary with news articles and metadata
    """
    # Execute the async function using asyncio.run
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            fetch_unified_news_async(
                keywords=keywords,
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                category=category,
                sources=sources,
                count=count,
                include_sentiment=include_sentiment
            )
        )
        return result
    finally:
        loop.close()
