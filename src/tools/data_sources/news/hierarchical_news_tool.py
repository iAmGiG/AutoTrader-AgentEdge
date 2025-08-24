"""
Hierarchical Adaptive News Quota System for V4 Sentiment Agent
Implements Issue #208: Three-tier news system (Direct, Sector, Market)
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import pandas as pd

from .google_search_api import GoogleSearchNewsTool

logger = logging.getLogger(__name__)

class HierarchicalNewsConfig:
    """Configuration for hierarchical news fetching"""
    
    def __init__(self, 
                 total_items: int = 12,
                 direct_range: Tuple[int, int] = (5, 8),
                 sector_range: Tuple[int, int] = (2, 4), 
                 market_range: Tuple[int, int] = (1, 3),
                 relevance_thresholds: Dict[str, float] = None):
        """
        Initialize hierarchical news configuration
        
        Args:
            total_items: Total news items to return
            direct_range: Min/max items for company-specific news
            sector_range: Min/max items for sector ETF news  
            market_range: Min/max items for broad market news
            relevance_thresholds: Minimum relevance scores by category
        """
        self.total_items = total_items
        self.direct_range = direct_range
        self.sector_range = sector_range
        self.market_range = market_range
        
        # Default relevance thresholds
        self.relevance_thresholds = relevance_thresholds or {
            'direct': 0.4,
            'sector': 0.3,
            'market': 0.3
        }
        
        # Sector mappings for major tickers
        self.sector_mappings = {
            # Tech
            'AAPL': ['QQQ', 'XLK'],
            'MSFT': ['QQQ', 'XLK'], 
            'GOOGL': ['QQQ', 'XLK'],
            'META': ['QQQ', 'XLK'],
            'NVDA': ['QQQ', 'XLK'],
            'TSLA': ['QQQ', 'XLK'],  # Tesla is in tech ETFs
            
            # Financials
            'JPM': ['XLF'],
            'BAC': ['XLF'],
            'GS': ['XLF'],
            'WFC': ['XLF'],
            
            # Healthcare
            'JNJ': ['XLV'],
            'UNH': ['XLV'],
            'PFE': ['XLV'],
            'ABBV': ['XLV'],
            
            # Consumer
            'AMZN': ['XLY'],  # Consumer discretionary
            'HD': ['XLY'],
            'MCD': ['XLP'],   # Consumer staples
            'PG': ['XLP'],
            
            # Energy
            'XOM': ['XLE'],
            'CVX': ['XLE'],
            
            # Default for unknown tickers
            'DEFAULT': ['QQQ', 'SPY']
        }

class HierarchicalNewsTool:
    """
    Hierarchical news fetching tool that provides:
    1. Direct: Company-specific news (5-8 items)
    2. Sector: ETF news for relevant sectors (2-4 items)  
    3. Market: SPY broad market sentiment (1-3 items)
    """
    
    def __init__(self, config: Optional[HierarchicalNewsConfig] = None):
        """
        Initialize hierarchical news tool
        
        Args:
            config: Configuration for news hierarchy, uses default if None
        """
        self.config = config or HierarchicalNewsConfig()
        self.news_tool = GoogleSearchNewsTool()
        
    def get_sector_etfs(self, ticker: str) -> List[str]:
        """Get relevant sector ETFs for a ticker, excluding self to prevent duplication"""
        ticker = ticker.upper()
        sector_etfs = self.config.sector_mappings.get(ticker, self.config.sector_mappings['DEFAULT'])
        
        # Remove primary ticker from sector ETFs to avoid duplication
        return [etf for etf in sector_etfs if etf != ticker]
    
    def fetch_direct_news(self, ticker: str, start_date: str, end_date: str, max_items: int) -> pd.DataFrame:
        """
        Fetch direct company-specific news
        
        Args:
            ticker: Company ticker (e.g., 'AAPL')
            start_date: Start date for news search
            end_date: End date for news search  
            max_items: Maximum number of articles to fetch
            
        Returns:
            DataFrame with direct company news
        """
        logger.info(f"Fetching direct news for {ticker} (max: {max_items})")
        
        try:
            df = self.news_tool.search_historical_news(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                max_results=max_items
            )
            
            if not df.empty:
                # Filter by relevance threshold
                threshold = self.config.relevance_thresholds['direct']
                df = df[df.get('relevance_score', 0) >= threshold]
                
                # Add category marker
                df['news_category'] = 'direct'
                df['news_source_ticker'] = ticker
                
                logger.info(f"Retrieved {len(df)} direct news articles for {ticker}")
                return df.head(max_items)
            
        except Exception as e:
            logger.error(f"Error fetching direct news for {ticker}: {e}")
        
        return pd.DataFrame()
    
    def fetch_sector_news(self, ticker: str, start_date: str, end_date: str, max_items: int) -> pd.DataFrame:
        """
        Fetch sector ETF news relevant to the ticker
        
        Args:
            ticker: Company ticker to determine relevant sectors
            start_date: Start date for news search
            end_date: End date for news search
            max_items: Maximum number of articles to fetch
            
        Returns:
            DataFrame with sector news
        """
        sector_etfs = self.get_sector_etfs(ticker)
        logger.info(f"Fetching sector news for {ticker} via ETFs: {sector_etfs} (max: {max_items})")
        
        all_sector_news = []
        items_per_etf = max(1, max_items // len(sector_etfs))
        
        for etf in sector_etfs:
            try:
                df = self.news_tool.search_historical_news(
                    ticker=etf,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=items_per_etf
                )
                
                if not df.empty:
                    # Filter by relevance threshold
                    threshold = self.config.relevance_thresholds['sector']
                    df = df[df.get('relevance_score', 0) >= threshold]
                    
                    # Add category markers
                    df['news_category'] = 'sector'
                    df['news_source_ticker'] = etf
                    df['target_ticker'] = ticker
                    
                    all_sector_news.append(df)
                    
            except Exception as e:
                logger.error(f"Error fetching sector news for {etf}: {e}")
        
        if all_sector_news:
            combined_df = pd.concat(all_sector_news, ignore_index=True)
            
            # Sort by relevance and limit total
            combined_df = combined_df.sort_values('relevance_score', ascending=False)
            result = combined_df.head(max_items)
            
            logger.info(f"Retrieved {len(result)} sector news articles for {ticker}")
            return result
        
        return pd.DataFrame()
    
    def fetch_market_news(self, primary_ticker: str, start_date: str, end_date: str, max_items: int) -> pd.DataFrame:
        """
        Fetch broad market sentiment news via SPY
        
        Args:
            primary_ticker: Primary ticker being analyzed (to avoid duplication)
            start_date: Start date for news search
            end_date: End date for news search
            max_items: Maximum number of articles to fetch
            
        Returns:
            DataFrame with market news
        """
        # Skip market news if primary ticker is already SPY to avoid duplication
        if primary_ticker.upper() == 'SPY':
            logger.info(f"Skipping market news - primary ticker {primary_ticker} is market ETF")
            return pd.DataFrame()
            
        logger.info(f"Fetching market news via SPY (max: {max_items})")
        
        try:
            df = self.news_tool.search_historical_news(
                ticker='SPY',
                start_date=start_date,
                end_date=end_date,
                max_results=max_items
            )
            
            if not df.empty:
                # Filter by relevance threshold
                threshold = self.config.relevance_thresholds['market']
                df = df[df.get('relevance_score', 0) >= threshold]
                
                # Add category marker
                df['news_category'] = 'market'
                df['news_source_ticker'] = 'SPY'
                
                logger.info(f"Retrieved {len(df)} market news articles")
                return df.head(max_items)
            
        except Exception as e:
            logger.error(f"Error fetching market news: {e}")
        
        return pd.DataFrame()
    
    def fetch_hierarchical_news(self, 
                               ticker: str, 
                               start_date: str, 
                               end_date: str) -> pd.DataFrame:
        """
        Fetch hierarchical news mix for V4 sentiment analysis
        
        Args:
            ticker: Primary ticker for analysis
            start_date: Start date for news search (YYYY-MM-DD)
            end_date: End date for news search (YYYY-MM-DD)
            
        Returns:
            DataFrame with mixed news from all three categories
        """
        logger.info(f"Fetching hierarchical news for {ticker} from {start_date} to {end_date}")
        
        # Calculate target counts for each category
        direct_target = self.config.direct_range[0]  # Start with minimum
        sector_target = self.config.sector_range[0]
        market_target = self.config.market_range[0]
        
        all_news = []
        
        # 1. Fetch direct news (highest priority)
        direct_news = self.fetch_direct_news(ticker, start_date, end_date, direct_target + 2)
        if not direct_news.empty:
            all_news.append(direct_news)
        
        # 2. Fetch sector news
        sector_news = self.fetch_sector_news(ticker, start_date, end_date, sector_target + 1)
        if not sector_news.empty:
            all_news.append(sector_news)
        
        # 3. Fetch market news
        market_news = self.fetch_market_news(ticker, start_date, end_date, market_target + 1)
        if not market_news.empty:
            all_news.append(market_news)
        
        if not all_news:
            logger.warning(f"No news articles retrieved for {ticker}")
            return pd.DataFrame()
        
        # Combine and balance the results
        combined_df = pd.concat(all_news, ignore_index=True)
        
        # Balance the categories to meet targets
        balanced_news = self._balance_news_categories(
            combined_df, 
            direct_target=direct_target,
            sector_target=sector_target, 
            market_target=market_target
        )
        
        # Final sorting and limiting
        balanced_news = balanced_news.sort_values(
            ['news_category', 'relevance_score'], 
            ascending=[True, False]
        )
        
        final_result = balanced_news.head(self.config.total_items)
        
        # Log final distribution
        category_counts = final_result['news_category'].value_counts()
        logger.info(f"Final hierarchical news distribution for {ticker}:")
        for category, count in category_counts.items():
            logger.info(f"  {category}: {count} articles")
        
        return final_result
    
    def _balance_news_categories(self, 
                                df: pd.DataFrame, 
                                direct_target: int,
                                sector_target: int,
                                market_target: int) -> pd.DataFrame:
        """
        Balance news articles across categories to meet target distributions
        
        Args:
            df: Combined DataFrame with all news articles
            direct_target: Target number of direct articles
            sector_target: Target number of sector articles
            market_target: Target number of market articles
            
        Returns:
            Balanced DataFrame with target distribution
        """
        balanced_parts = []
        
        for category, target in [
            ('direct', direct_target),
            ('sector', sector_target), 
            ('market', market_target)
        ]:
            category_df = df[df['news_category'] == category]
            
            if not category_df.empty:
                # Sort by relevance and take top N
                sorted_df = category_df.sort_values('relevance_score', ascending=False)
                balanced_parts.append(sorted_df.head(target))
            else:
                logger.warning(f"No {category} news articles available")
        
        if balanced_parts:
            return pd.concat(balanced_parts, ignore_index=True)
        else:
            return pd.DataFrame()

# Create the tool function for integration with autogen
def fetch_hierarchical_news(
    ticker: str = "AAPL",
    start_date: str = "2024-01-01", 
    end_date: str = "2024-01-31"
) -> pd.DataFrame:
    """
    Fetch hierarchical adaptive news for V4 sentiment analysis.
    
    Provides a balanced mix of:
    - Direct company news (5-8 items)
    - Sector ETF news (2-4 items) 
    - Market sentiment via SPY (1-3 items)
    
    Args:
        ticker: Primary stock ticker for analysis
        start_date: Start date for news search (YYYY-MM-DD)
        end_date: End date for news search (YYYY-MM-DD)
        
    Returns:
        DataFrame with hierarchical news mix for sentiment analysis
    """
    tool = HierarchicalNewsTool()
    return tool.fetch_hierarchical_news(ticker, start_date, end_date)