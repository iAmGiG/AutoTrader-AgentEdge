"""
V1 Sentiment Agent: NLP Analysis with VADER
Fetches news via Google Search and analyzes with VADER sentiment
Pure mechanical NLP, no LLM involvement
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import re
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from src.tools.data_sources.news.google_search_simple import GoogleSearchNewsTool
from src.tools.cache.news_cache import NewsCache

logger = logging.getLogger(__name__)


class SentimentV1Agent:
    """
    V1: NLP-based Sentiment Agent using VADER
    
    Fetches news articles and analyzes sentiment mechanically using VADER
    No LLM involvement - pure NLP processing
    """
    
    def __init__(self, name: str = "SentimentV1Agent", memory_system=None):
        self.name = name
        self.logger = logger
        
        # Initialize VADER sentiment analyzer
        self.vader = SentimentIntensityAnalyzer()
        
        # Initialize news tool and cache
        self.news_tool = GoogleSearchNewsTool()
        self.news_cache = NewsCache()
        
    def analyze_text_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text using VADER.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with sentiment scores
        """
        scores = self.vader.polarity_scores(text)
        return scores
    
    def fetch_and_analyze_news(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Fetch news and analyze sentiment with VADER.
        
        Args:
            symbol: Stock ticker symbol
            date: Target date (YYYY-MM-DD)
            
        Returns:
            Dict with aggregated sentiment analysis
        """
        try:
            # Check cache first
            cache_key = f"v1_{symbol}_{date}"
            cached_data = self.news_cache.get(cache_key)
            if cached_data:
                logger.info(f"Using cached V1 sentiment for {symbol} on {date}")
                return cached_data
            
            # Fetch news from Google Search
            news_results = self.news_tool.fetch_news(
                query=f"{symbol} stock market news",
                days_back=3
            )
            
            if news_results is None or news_results.empty:
                logger.warning(f"No news found for {symbol}")
                return {
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": "No news articles found",
                    "articles_analyzed": 0
                }
            
            # Analyze each article with VADER
            sentiments = []
            article_details = []
            
            for _, article in news_results.iterrows():
                # Combine title and snippet for analysis
                text = f"{article.get('title', '')} {article.get('snippet', '')}"
                
                if text.strip():
                    scores = self.analyze_text_sentiment(text)
                    sentiments.append(scores['compound'])
                    
                    article_details.append({
                        "title": article.get('title', ''),
                        "sentiment": scores['compound'],
                        "positive": scores['pos'],
                        "negative": scores['neg'],
                        "neutral": scores['neu']
                    })
            
            if not sentiments:
                return {
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": "No analyzable text in articles",
                    "articles_analyzed": 0
                }
            
            # Calculate aggregate sentiment
            avg_sentiment = sum(sentiments) / len(sentiments)
            
            # Calculate confidence based on consistency and article count
            if len(sentiments) > 1:
                sentiment_std = pd.Series(sentiments).std()
                # Higher consistency = higher confidence
                consistency_score = max(0, 1 - sentiment_std)
                # More articles = higher confidence
                volume_score = min(1, len(sentiments) / 10)
                confidence = (consistency_score + volume_score) / 2
            else:
                confidence = 0.3  # Low confidence with single article
            
            # Generate reasoning
            if avg_sentiment > 0.05:
                sentiment_label = "positive"
            elif avg_sentiment < -0.05:
                sentiment_label = "negative"
            else:
                sentiment_label = "neutral"
            
            reasoning = (
                f"VADER NLP analysis of {len(sentiments)} articles shows "
                f"{sentiment_label} sentiment (avg: {avg_sentiment:.3f})"
            )
            
            result = {
                "sentiment": round(avg_sentiment, 4),
                "confidence": round(confidence, 4),
                "reasoning": reasoning,
                "articles_analyzed": len(sentiments),
                "mode": "vader_nlp",
                "version": "V1",
                "details": article_details[:5]  # Include top 5 for transparency
            }
            
            # Cache the result
            self.news_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in V1 sentiment analysis: {str(e)}")
            return {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}",
                "articles_analyzed": 0,
                "mode": "vader_nlp",
                "version": "V1"
            }
    
    def generate_reply(self, messages, context=None) -> str:
        """
        Generate VADER-based sentiment response.
        
        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context (not used)
            
        Returns:
            JSON string with VADER sentiment analysis
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
        
        logger.info(f"V1 Sentiment: Analyzing {symbol} for {date} with VADER")
        
        # Fetch and analyze news
        result = self.fetch_and_analyze_news(symbol, date)
        
        # Log the result
        logger.info(f"V1 Result: sentiment={result['sentiment']}, confidence={result['confidence']}")
        
        return json.dumps(result)