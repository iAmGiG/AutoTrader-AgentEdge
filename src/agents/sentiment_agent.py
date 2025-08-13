"""
Sentiment Agent for V0-V3: Pure Data Puller
No LLM conversation, no sentiment analysis decisions
Just fetches news data and returns structured information
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re

from src.tools.data_sources.news.google_search_simple import GoogleSearchNewsTool
from src.tools.cache.news_cache import NewsCache

logger = logging.getLogger(__name__)


class SentimentAgent:
    """
    Mechanical Sentiment Agent for V0-V3 versions.
    
    Pure data fetcher - no LLM, no sentiment scoring, no analysis.
    Just pulls news data and returns structured information.
    For V0: Will return fixed sentiment
    For V1: Will return news for VADER processing
    For V2: Will return market fear indicators
    For V3: Will return combined data
    """
    
    def __init__(self, name: str = "SentimentAgent", memory_system=None):
        self.name = name
        self.logger = logger
        # memory_system parameter kept for compatibility but not used
        
        # Initialize news tool and cache
        self.news_tool = GoogleSearchNewsTool()
        self.news_cache = NewsCache()
        
    def fetch_news_data(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Fetch news data for a given symbol and date.
        
        Args:
            symbol: Stock ticker symbol
            date: Target date (YYYY-MM-DD)
            
        Returns:
            Dict with news articles and metadata
        """
        try:
            # Parse date
            target_date = pd.to_datetime(date)
            
            # Check cache first
            cache_key = f"{symbol}_{date}"
            cached_data = self.news_cache.get(cache_key)
            if cached_data:
                logger.info(f"Using cached news for {symbol} on {date}")
                return cached_data
            
            # Fetch news from Google Search
            # Search for news from past 3 days to ensure we get relevant articles
            news_results = self.news_tool.fetch_news(
                query=f"{symbol} stock market news",
                days_back=3
            )
            
            if not news_results or news_results.empty:
                logger.warning(f"No news found for {symbol}")
                return {
                    "symbol": symbol,
                    "date": date,
                    "articles": [],
                    "count": 0
                }
            
            # Convert to structured format
            articles = []
            for _, article in news_results.iterrows():
                articles.append({
                    "title": article.get("title", ""),
                    "snippet": article.get("snippet", ""),
                    "source": article.get("source", ""),
                    "date": article.get("date", ""),
                    "link": article.get("link", "")
                })
            
            result = {
                "symbol": symbol,
                "date": date,
                "articles": articles,
                "count": len(articles)
            }
            
            # Cache the result
            self.news_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {str(e)}")
            return {
                "symbol": symbol,
                "date": date,
                "articles": [],
                "count": 0,
                "error": str(e)
            }
    
    def fetch_market_fear_data(self, date: str) -> Dict[str, Any]:
        """
        Fetch market fear indicators (VIX/VXX data).
        For V2 sentiment approach.
        
        Args:
            date: Target date (YYYY-MM-DD)
            
        Returns:
            Dict with fear indicators
        """
        try:
            from src.tools.tools import fetch_market_data
            
            # Fetch VIX data
            end_date = pd.to_datetime(date)
            start_date = end_date - timedelta(days=5)
            
            vix_data = fetch_market_data(
                symbol="VIX",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d")
            )
            
            if vix_data is not None and not vix_data.empty:
                current_vix = float(vix_data['Close'].iloc[-1])
                prev_vix = float(vix_data['Close'].iloc[-2]) if len(vix_data) > 1 else current_vix
                
                return {
                    "vix_current": round(current_vix, 2),
                    "vix_previous": round(prev_vix, 2),
                    "vix_change": round(current_vix - prev_vix, 2),
                    "fear_level": "high" if current_vix > 30 else "moderate" if current_vix > 20 else "low"
                }
            else:
                return {
                    "vix_current": None,
                    "vix_previous": None,
                    "vix_change": None,
                    "fear_level": "unknown"
                }
                
        except Exception as e:
            logger.error(f"Error fetching market fear data: {str(e)}")
            return {
                "vix_current": None,
                "vix_previous": None,
                "vix_change": None,
                "fear_level": "unknown",
                "error": str(e)
            }
    
    def generate_reply(self, messages, context=None) -> str:
        """
        Generate pure data response - no LLM, just data fetching.
        
        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context (not used)
            
        Returns:
            JSON string with news/fear data
        """
        # Extract message content
        if isinstance(messages, str):
            message = messages
        elif isinstance(messages, list) and messages:
            message = messages[-1].get("content", "") if isinstance(messages[-1], dict) else str(messages[-1])
        elif isinstance(messages, dict):
            message = messages.get("content", "")
        else:
            message = ""
        
        # Parse for symbol and date
        symbol_match = re.search(r'\b([A-Z]{2,5})\b', message)
        symbol = symbol_match.group(1) if symbol_match else "SPY"
        
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
        date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")
        
        # Determine what type of data to fetch based on message content
        message_lower = message.lower()
        
        result = {}
        
        # Always include basic metadata
        result["symbol"] = symbol
        result["date"] = date
        
        # Check what's being requested
        if "fear" in message_lower or "vix" in message_lower or "v2" in message_lower:
            # V2: Market fear data
            logger.info(f"Fetching market fear data for {date}")
            fear_data = self.fetch_market_fear_data(date)
            result.update(fear_data)
            
        elif "v0" in message_lower:
            # V0: Fixed baseline
            logger.info("V0 mode - returning fixed sentiment")
            result["sentiment"] = 1.0
            result["mode"] = "fixed_baseline"
            
        else:
            # Default: Fetch news data (for V1, V3, or general requests)
            logger.info(f"Fetching news data for {symbol} on {date}")
            news_data = self.fetch_news_data(symbol, date)
            result.update(news_data)
        
        # Log the result
        logger.info(f"Sentiment data result: {json.dumps(result, indent=2)}")
        
        # Return as JSON string
        return json.dumps(result)


# Import pandas for date handling
import pandas as pd