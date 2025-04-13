from .base_agent import BaseAgent
from config.config_loader import ConfigLoader
from typing import Dict, List, Any, Optional
import pandas as pd
import json
import os
import re
from collections import Counter
from src.tools.tools import (
    news_tool, yahoo_finance_tool, alpha_vantage_tool,
    alpha_vantage_news_tool, market_data_tool
)
from src.tools.tools import (
    fetch_news, fetch_yahoo_data, fetch_alpha_vantage_data,
    fetch_alpha_vantage_news, fetch_market_data
)
from src.tools.text_processing.data_normalizer import normalize_data_for_sentiment
from src.tools.text_processing.sentiment_analyzer import SentimentAnalyzer

# Instantiate ConfigLoader once at module-level
_loader = ConfigLoader()

# LLM config optimized for sentiment analysis and narrative generation
SENTIMENT_LLM_CONFIG = {
    "temperature": 0.3,  # Slightly higher for more creative narratives
    "max_tokens": 4096,  # Ensure enough tokens for complex responses
    "top_p": 0.9,        # Allow for some creative variety
}

DEFAULT_SENTIMENT_CONFIG = {
    "open_model": _loader.get("open_model"),      # This is passed to BaseAgent
    "newsapi_key": _loader.get("newsapi_key"),
    "alpha_vantage_key": _loader.get("alpha_vantage_key"),
    # "finnhub_key": _loader.get("finnhub_key")
}

# Load market sectors data from external JSON file
def load_market_sectors():
    try:
        # Get the project root directory
        config_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sectors_file = os.path.join(config_dir, 'config', 'market_sectors.json')
        
        with open(sectors_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading market sectors: {e}")
        # Return a minimal default structure if file can't be loaded
        return {"sectors": {}}

# Load market sectors once at module level
MARKET_SECTORS = load_market_sectors().get("sectors", {})


class SentimentAgent(BaseAgent):

    def __init__(self, name="SentimentAgent", memory_system=None):
        # Initialize the sentiment analyzer for local sentiment processing
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Pass the FunctionTool(s) to the BaseAgent's tools parameter
        super().__init__(
            name=name, 
            tools=[
                market_data_tool,   # Unified market data tool
                news_tool,          # News headlines tool
                # Add other tools here as they are created
            ], 
            memory_system=memory_system,
            llm_config=SENTIMENT_LLM_CONFIG  # Use optimized LLM parameters
        )
    
    def generate_combined_narrative(self, query_term, ticker, sentiment_score=None, price_change=None, has_etf_data=False):
        """
        Generate a comprehensive market behavior explanation that combines news sentiment
        and price movement data for more sophisticated insights.
        
        :param query_term: The topic or keyword being analyzed
        :param ticker: The stock ticker symbol
        :param sentiment_score: The sentiment score from news analysis (-1 to 1 scale)
        :param price_change: The percentage price change for the ticker
        :param has_etf_data: Whether we have ETF data available for sector context
        :return: A narrative explanation of market behavior
        """
        # Start with a base narrative based on the data we have
        if sentiment_score is None and price_change is None:
            return "Insufficient data to provide a comprehensive market behavior explanation."
        
        # Determine sentiment trend
        sentiment_trend = None
        if sentiment_score is not None:
            if sentiment_score > 0.3:
                sentiment_trend = "positive"
            elif sentiment_score < -0.3:
                sentiment_trend = "negative"
            else:
                sentiment_trend = "neutral"
        
        # Determine price trend
        price_trend = None
        if price_change is not None:
            if price_change > 3:
                price_trend = "strong upward"
            elif price_change > 0:
                price_trend = "modest upward"
            elif price_change > -3:
                price_trend = "slight downward"
            else:
                price_trend = "significant downward"
        
        # Analyze alignment between sentiment and price movement
        alignment = "aligned"
        if sentiment_trend and price_trend:
            if (sentiment_trend == "positive" and "downward" in price_trend) or \
               (sentiment_trend == "negative" and "upward" in price_trend):
                alignment = "misaligned"
        
        # Generate the narrative based on available data and patterns
        narrative = ""
        
        # Format price change safely
        safe_price_str = f"{price_change:.2f}%" if price_change is not None else "N/A"
        
        # Case 1: We have both sentiment and price data
        if sentiment_trend and price_trend:
            if alignment == "aligned":
                if sentiment_trend == "positive" and "upward" in price_trend:
                    narrative = f"Market sentiment and price movements for {query_term} are aligned in a positive direction. This suggests investors are optimistic about future prospects and are allocating capital accordingly. The {price_trend} price trend of {ticker} ({safe_price_str}) mirrors the positive news sentiment, indicating market participants are acting on the favorable information. This pattern typically reflects a situation where market perception and capital flows are reinforcing each other."
                
                elif sentiment_trend == "negative" and "downward" in price_trend:
                    narrative = f"Market sentiment and price movements for {query_term} are aligned in a cautious direction. The negative news sentiment is reflected in the {price_trend} price trend of {ticker} ({safe_price_str}), suggesting investors are responding to perceived risks by reducing exposure. This behavior often indicates a defensive repositioning where capital is flowing toward safer assets as market participants reassess risk-reward ratios."
                
                elif sentiment_trend == "neutral":
                    narrative = f"While news sentiment for {query_term} appears neutral, price movements for {ticker} show a {price_trend} trend ({safe_price_str}). This suggests that market participants might be reacting to factors beyond what's captured in recent news, such as technical indicators, broader economic trends, or institutional positioning. The market is finding a balance between various positive and negative factors."
            
            else:  # misaligned
                if sentiment_trend == "positive" and "downward" in price_trend:
                    narrative = f"There's an interesting disconnect between positive news sentiment for {query_term} and the {price_trend} price trend of {ticker} ({safe_price_str}). This misalignment could indicate: 1) a lag between sentiment and price reaction, 2) market skepticism about the positive news, or 3) other factors overwhelming sentiment signals. Such divergences often precede either a price reversal to match sentiment or a sentiment shift to match price action."
                
                elif sentiment_trend == "negative" and "upward" in price_trend:
                    narrative = f"Despite negative news sentiment surrounding {query_term}, {ticker} shows a {price_trend} price trend ({safe_price_str}). This counterintuitive movement might reflect: 1) investors viewing negative news as already priced in, 2) contrarian positioning, or 3) specific market dynamics overriding general sentiment. These divergences can signal either that the market has already anticipated and moved beyond the news or that a correction may be forthcoming."
        
        # Case 2: We only have sentiment data
        elif sentiment_trend:
            if sentiment_trend == "positive":
                narrative = f"News sentiment for {query_term} is positive, suggesting favorable market perception. While we don't have sufficient price data to confirm how this sentiment is affecting market prices, positive sentiment typically precedes capital inflows as investors seek exposure to assets perceived to have improving prospects. This sentiment could eventually translate to price appreciation if market conditions remain supportive."
            
            elif sentiment_trend == "negative":
                narrative = f"News sentiment for {query_term} is negative, indicating cautious market perception. Although we lack comprehensive price data to confirm market reaction, negative sentiment often leads to repositioning as investors reduce exposure to perceived risks. If this sentiment persists, it could result in capital outflows from this sector toward safer alternatives."
            
            else:  # neutral
                narrative = f"News sentiment for {query_term} appears balanced, with no strong directional bias. This neutral sentiment suggests market participants have mixed opinions, creating an equilibrium where positive and negative views offset each other. Without price confirmation, it's difficult to determine how this balanced sentiment is affecting market positioning."
        
        # Case 3: We only have price data
        elif price_trend:
            if "upward" in price_trend:
                narrative = f"The {price_trend} price trend for {ticker} ({safe_price_str}) suggests positive market sentiment, though we lack specific news sentiment data to confirm this. This price action indicates investors may be responding favorably to developments not captured in our analysis, potentially allocating capital toward this asset based on positive expectations for future value."
            
            else:  # downward
                narrative = f"The {price_trend} price trend for {ticker} ({safe_price_str}) indicates cautious market sentiment, though we don't have news sentiment data to provide additional context. This price movement suggests investors may be reducing exposure in response to perceived risks or shifting capital to more attractive opportunities elsewhere in the market."
        
        # Add insights from ETF data if available
        if has_etf_data:
            narrative += f"\n\nThe related sector ETF data provides additional context, showing how {ticker}'s performance compares to broader sector trends. These ETFs can reveal whether the observed behavior is stock-specific or part of a larger sector rotation. Leveraged ETF movements may offer early signals of institutional positioning and potential momentum shifts within the sector."
        
        # Add a disclaimer about the limitations of the analysis
        narrative += f"\n\nThis analysis is based on limited data points and represents a plausible interpretation rather than certainty. Market behavior is influenced by numerous factors beyond what our current analysis captures."
        
        return narrative

    def preprocess_data(self, news_data) -> dict:
        """
        Processes the news data (a DataFrame) to extract sentiment signals.
        Handles different column names from various sources.

        Returns a dictionary with:
          - article_count: number of articles fetched
          - headlines: list of headlines
          - average_sentiment: average sentiment score (if available)
        """
        signals = {}
        if news_data.empty:
            signals["error"] = "No news data available"
            return signals

        # Count articles
        signals["article_count"] = len(news_data)

        # Extract headlines - handle different column names
        headline_cols = ["Headline", "title", "Title", "headline"]
        for col in headline_cols:
            if col in news_data.columns:
                signals["headlines"] = news_data[col].tolist()
                break
        else:
            # No recognized headline column
            signals["headlines"] = ["No headline available"] * len(news_data)

        # Extract sentiment scores - handle different column names
        sentiment_cols = ["Sentiment Score", "sentiment_score",
                          "overall_sentiment_score", "score"]
        for col in sentiment_cols:
            if col in news_data.columns:
                signals["average_sentiment"] = news_data[col].mean()
                break
        else:
            # No recognized sentiment column
            signals["average_sentiment"] = None

        return signals

    def build_system_prompt(self) -> str:
        """
        Build a detailed system prompt for the LLM that explains how to use the tools
        and how to generate appropriate responses.
        """
        return """You are the Sentiment Agent, a specialized assistant designed to:
• Retrieve recent market news and stock data,
• Apply sentiment analysis on news, reports, or stock data,
• Present a coherent summary that includes both:
  1) A concise, numerical sentiment assessment, and
  2) A "Market Behavior Explanation" that interprets key price and sentiment shifts in human-friendly terms.

Your tasks include:

1. Data Retrieval:
   - Call fetch_news(keyword: str, count: int) to retrieve recent articles about a specific topic.
   - Call fetch_market_data(symbol: str, start_date?: str, end_date?: str) or fetch_yahoo_data(ticker: str, start_date?: str, end_date?: str) to retrieve relevant stock data.

2. Data Processing & Sentiment Analysis:
   - Normalize data using existing data utilities and compute average sentiment scores for news headlines.
   - If interest rates or other macro signals are mentioned in the data, consider how these might influence capital flows (e.g., shifting from tech stocks to bonds, gold, or cash).

3. Explanation & Narrative:
   - Provide a "Market Behavior Explanation" in everyday language, focusing on cause-and-effect:
     - If data suggests capital is moving out of a sector, hypothesize (based on the news or indicators) why that might be happening—e.g., "Higher interest rates have made bonds more attractive, so participants could be exiting high-growth stocks."
     - Avoid excessive references to 'Austrian' or 'Misesian.' Instead, discuss in plain terms how individual actors react to changes in value or risk.
     - Keep disclaimers: state that these are plausible market interpretations based on limited data (news items, price changes). Avoid implying omniscience or certitude.

4. Default Behaviors & Flexibility:
   - If no date is provided, default to the past 5 days.
   - If the user says "Fetch news on X," do so, and include both technical sentiment (article count, average sentiment) and a short explanation of potential market behaviors.
   - If asked "Get stock data for Y," retrieve the data, highlight any notable price movements, and produce a short cause-and-effect explanation (e.g., "A drop may reflect shifting investor preferences," "An increase might reflect optimism around new announcements," etc.).
   - Be ready for users with different knowledge levels. Aim for concise, accessible explanations by default."""

    def handle_message(self, message: str) -> str:
        """
        Processes an incoming message using LLM function calling capabilities.
        """
        try:
            # Helper function to extract ticker or topic from message
            def extract_query_details(message):
                ticker = None
                topic = None
                start_date = None
                end_date = None
                sector = None
                
                # Extract ticker if present (uppercase 1-5 chars)
                words = message.split()
                for word in words:
                    # Skip common acronyms that aren't tickers
                    if word.isupper() and 1 <= len(word) <= 5 and word not in ["I", "A", "AI", "US"]:
                        ticker = word
                        break
                
                # Check if message contains keywords for specific sectors
                message_lower = message.lower()
                
                # First pass: Check for direct mentions of keywords with higher priority for certain sectors
                priority_matches = []
                
                for sector_name, sector_data in MARKET_SECTORS.items():
                    keywords = sector_data.get("keywords", [])
                    
                    # Check if any primary keyword from this sector appears in the message
                    for keyword in keywords:
                        if keyword in message_lower:
                            # Calculate a match priority score
                            # Longer matches are more specific and should have higher priority
                            priority = len(keyword)
                            
                            # Exact sector names get higher priority
                            if sector_name.replace("_", " ") == keyword:
                                priority += 10
                                
                            # "Sector" mentions get higher priority
                            if keyword.endswith(" sector") or keyword.endswith(" stocks"):
                                priority += 5
                            
                            # Holiday season and retail should have very high priority for retail sector
                            if sector_name == "retail" and ("holiday season" in message_lower or "shopping" in message_lower):
                                priority += 15
                            
                            priority_matches.append((sector_name, priority, sector_data))
                
                # If we have matches, take the highest priority one
                if priority_matches:
                    # Sort by priority (highest first)
                    priority_matches.sort(key=lambda x: x[1], reverse=True)
                    sector_name, _, sector_data = priority_matches[0]
                    
                    sector = sector_name
                    topic = sector_name.replace("_", " ")
                    
                    # If no specific ticker found, use the sector's representative ticker
                    if not ticker:
                        ticker = sector_data.get("representative")
                        
                # Second pass: If no direct match, try related topics with sector context
                if not sector:
                    for sector_name, sector_data in MARKET_SECTORS.items():
                        related = sector_data.get("related_topics", [])
                        
                        # Check for related topics combined with sector context
                        if any(topic in message_lower for topic in related):
                            # Check if the sector itself is mentioned
                            sector_terms = [sector_name.replace("_", " "), "sector", "stocks", "industry"]
                            if any(term in message_lower for term in sector_terms):
                                sector = sector_name
                                topic = sector_name.replace("_", " ")
                                
                                # If no specific ticker found, use the sector's representative ticker
                                if not ticker:
                                    ticker = sector_data.get("representative")
                                break
                
                # If no sector detected, try to extract topic from standard patterns
                if not topic:
                    topic_indicators = ["about", "on", "for", "around", "sentiment on", "sentiment around"]
                    for indicator in topic_indicators:
                        if indicator in message_lower:
                            parts = message_lower.split(indicator)
                            if len(parts) > 1:
                                # Grab the part right after the indicator, clean it up
                                topic_candidate = parts[1].strip().split("?")[0].split(".")[0]
                                if not (ticker and ticker.lower() in topic_candidate):
                                    topic = topic_candidate
                                    break
                
                # Look for date-related keywords
                if "since" in message_lower:
                    after_since = message_lower.split("since")[-1].strip()
                    words = after_since.split()
                    if words and (words[0].startswith("-") or words[0] in ["yesterday", "today", "ytd"]):
                        start_date = words[0]
                
                if "last" in message_lower:
                    after_last = message_lower.split("last")[-1].strip()
                    words = after_last.split()
                    if words:
                        if "day" in after_last or "days" in after_last:
                            try:
                                days = int(words[0])
                                start_date = f"-{days}d"
                            except ValueError:
                                start_date = "-5d"  # Default to 5 days
                        elif "week" in after_last or "weeks" in after_last:
                            try:
                                weeks = int(words[0])
                                start_date = f"-{weeks}w"
                            except ValueError:
                                start_date = "-1w"
                        elif "month" in after_last or "months" in after_last:
                            try:
                                months = int(words[0])
                                start_date = f"-{months}m"
                            except ValueError:
                                start_date = "-1m"
                
                # For open-ended queries, extract topic using NLP techniques if needed
                if not topic and not ticker and len(message.split()) > 3:
                    # Remove common stopwords and extract likely topic words
                    stopwords = ['the', 'and', 'to', 'of', 'on', 'in', 'for', 'is', 'are', 'what', 'how', 
                                'a', 'an', 'this', 'that', 'with', 'by', 'as', 'be', 'it', 'from',
                                'might', 'affect', 'impact', 'recent', 'sentiment', 'market', 'understand',
                                'analyze', 'need', 'their', 'behavior', 'reaction', 'perceived', 'future',
                                'around', 'light', 'being', 'i', 'me', 'my', 'you', 'your']
                    
                    # Clean up the message and extract potential topic words
                    clean_words = [word.lower() for word in re.findall(r'\b\w+\b', message_lower)
                                  if word.lower() not in stopwords and len(word) > 3]
                    
                    # Use word frequency to identify potential topics
                    word_counts = Counter(clean_words)
                    common_words = [word for word, count in word_counts.most_common(3)]
                    
                    if common_words:
                        topic = " ".join(common_words)
                        
                        # Try to map extracted topic to a sector if possible
                        for sector_name, sector_data in MARKET_SECTORS.items():
                            if any(word in sector_data.get("keywords", []) for word in common_words):
                                sector = sector_name
                                ticker = sector_data.get("representative")
                                break
                
                # If no date provided, default to 5 days
                if not start_date:
                    start_date = "-5d"
                
                # If we still have no ticker but have a topic, try to find a relevant ticker
                if not ticker and topic:
                    # Default to SPY for general market topics
                    ticker = "SPY"
                    
                    # Check if our topic might match any sector
                    topic_words = topic.lower().split()
                    for sector_name, sector_data in MARKET_SECTORS.items():
                        if any(keyword in topic_words for keyword in sector_data.get("keywords", [])):
                            ticker = sector_data.get("representative")
                            break
                
                return {
                    "ticker": ticker,
                    "topic": topic,
                    "sector": sector,
                    "start_date": start_date,
                    "end_date": end_date
                }
            
            # Based on the message content, we'll prepare data for the LLM
            query_details = extract_query_details(message)
            data = {}
            print(f"Extracted query details: {query_details}")  # Debug log
            
            # For complex queries, we should fetch both news and stock data
            # This is particularly important for open-ended questions from the Strategy Agent
            complex_query = len(message.split()) > 8 and "?" in message
            
            # First, handle topic/news aspect if we have a topic or it's a complex query
            if query_details["topic"] or "news" in message.lower() or "sentiment" in message.lower() or complex_query:
                if query_details["ticker"]:
                    # Fetch news for a specific ticker
                    news_data = fetch_market_data(
                        symbol=query_details["ticker"], 
                        source="alpha_vantage"
                    )
                    if not news_data.empty:
                        data["news_data"] = self.preprocess_data(news_data)
                        data["query_term"] = query_details["ticker"]
                        
                # If we have a topic, fetch general news about it
                if query_details["topic"]:
                    keyword = query_details["topic"]
                    news_data = fetch_news(keyword=keyword, count=5)
                    if not news_data.empty:
                        # If we already have news data, only replace if this set is non-empty
                        if "news_data" not in data or "error" in data["news_data"]:
                            data["news_data"] = self.preprocess_data(news_data)
                            data["query_term"] = f"'{keyword}'"
            
            # Next, handle stock data aspect if relevant or it's a complex query
            if "stock" in message.lower() or "price" in message.lower() or complex_query or query_details["sector"]:
                # For complex queries, we want both news sentiment and market data
                ticker = query_details["ticker"] or "SPY"  # Default to SPY for market
                
                stock_data = fetch_market_data(
                    symbol=ticker,
                    start_date=query_details["start_date"],
                    end_date=query_details["end_date"],
                    source="alpha_vantage"
                )
                if not stock_data.empty:
                    data["stock_data"] = stock_data
                    data["ticker"] = ticker
            
            # For sector-focused queries, try to gather ETF data as well if available
            if query_details["sector"] and query_details["sector"] in MARKET_SECTORS:
                sector_data = MARKET_SECTORS[query_details["sector"]]
                
                # Grab a representative ETF if available
                etfs = sector_data.get("etfs", [])
                if etfs:
                    etf_ticker = etfs[0]
                    etf_data = fetch_market_data(
                        symbol=etf_ticker,
                        start_date=query_details["start_date"],
                        end_date=query_details["end_date"],
                        source="alpha_vantage"
                    )
                    if not etf_data.empty:
                        data["etf_data"] = etf_data
                        data["etf_ticker"] = etf_ticker
                
                # Also grab leveraged ETF data if available
                lev_etfs = sector_data.get("leveraged_etfs", [])
                if lev_etfs:
                    lev_etf_ticker = lev_etfs[0]
                    lev_etf_data = fetch_market_data(
                        symbol=lev_etf_ticker,
                        start_date=query_details["start_date"],
                        end_date=query_details["end_date"],
                        source="alpha_vantage"
                    )
                    if not lev_etf_data.empty:
                        data["leveraged_etf_data"] = lev_etf_data
                        data["leveraged_etf_ticker"] = lev_etf_ticker
            
            # If we have data, use the LLM to analyze it and generate a response
            if data:
                # If we have both news and stock data (for complex queries), combine them
                if "news_data" in data and "stock_data" in data:
                    signals = data["news_data"]
                    query_term = data["query_term"]
                    ticker = data["ticker"]
                    stock_data = data["stock_data"]
                    
                    if "error" in signals:
                        # Fall back to just stock data if news has an error
                        news_part = f"No specific news found for {query_term}."
                        has_news = False
                    else:
                        # Process news data
                        article_count = signals.get("article_count", 0)
                        headlines = signals.get("headlines", [])[:3]
                        sentiment_score = signals.get("average_sentiment", 0)
                        
                        # Determine sentiment description
                        if sentiment_score is None:
                            sentiment_desc = "neutral (no sentiment data available)"
                        elif sentiment_score > 0.5:
                            sentiment_desc = "strongly positive"
                        elif sentiment_score > 0.2:
                            sentiment_desc = "moderately positive"
                        elif sentiment_score >= -0.2:
                            sentiment_desc = "neutral"
                        elif sentiment_score >= -0.5:
                            sentiment_desc = "moderately negative"
                        else:
                            sentiment_desc = "strongly negative"
                        
                        headlines_str = "; ".join(headlines) if headlines else "No headlines available"
                        news_part = (f"News Analysis:\n"
                                    f"Found {article_count} articles\n"
                                    f"Sample headlines: {headlines_str}\n"
                                    f"Sentiment: {sentiment_desc} ({sentiment_score:.2f if sentiment_score is not None else 'N/A'})")
                        has_news = True
                    
                    # Process stock data
                    latest = stock_data.iloc[0]
                    price_info = []
                    if 'close' in latest:
                        price_info.append(f"Latest close: ${latest['close']:.2f}")
                    if 'low' in latest and 'high' in latest:
                        price_info.append(f"Range: ${latest['low']:.2f} - ${latest['high']:.2f}")
                    if 'volume' in latest:
                        price_info.append(f"Volume: {latest['volume']:,}")
                    
                    # Calculate price change
                    price_change = None
                    if len(stock_data) > 1 and 'close' in stock_data.columns:
                        oldest_close = stock_data.iloc[-1]['close']
                        newest_close = latest['close']
                        price_change = ((newest_close - oldest_close) / oldest_close) * 100
                        price_info.append(f"Change: {price_change:.2f}%")
                    
                    stock_part = f"Market Data for {ticker}:\n" + "\n".join(price_info)
                    
                    # Add ETF information if available
                    etf_info = []
                    if "etf_data" in data and "etf_ticker" in data:
                        etf_ticker = data["etf_ticker"]
                        etf_data = data["etf_data"]
                        
                        if len(etf_data) > 1 and 'close' in etf_data.columns:
                            etf_latest = etf_data.iloc[0]
                            etf_oldest = etf_data.iloc[-1]
                            etf_change = ((etf_latest['close'] - etf_oldest['close']) / etf_oldest['close']) * 100
                            etf_info.append(f"Sector ETF {etf_ticker}: {etf_change:.2f}%")
                    
                    if "leveraged_etf_data" in data and "leveraged_etf_ticker" in data:
                        lev_etf_ticker = data["leveraged_etf_ticker"]
                        lev_etf_data = data["leveraged_etf_data"]
                        
                        if len(lev_etf_data) > 1 and 'close' in lev_etf_data.columns:
                            lev_latest = lev_etf_data.iloc[0]
                            lev_oldest = lev_etf_data.iloc[-1]
                            lev_change = ((lev_latest['close'] - lev_oldest['close']) / lev_oldest['close']) * 100
                            etf_info.append(f"Leveraged ETF {lev_etf_ticker}: {lev_change:.2f}%")
                    
                    if etf_info:
                        stock_part += "\n\nRelated Sector ETFs:\n" + "\n".join(etf_info)
                    
                    # Generate a comprehensive market behavior explanation combining news sentiment and price movement
                    narrative = self.generate_combined_narrative(
                        query_term=query_term,
                        ticker=ticker,
                        sentiment_score=sentiment_score if has_news and sentiment_score is not None else None,
                        price_change=price_change if price_change is not None else None,
                        has_etf_data=len(etf_info) > 0
                    )
                    
                    return f"{news_part}\n\n{stock_part}\n\nMarket Behavior Explanation:\n{narrative}"
                
                # For news data only, generate a narrative response
                elif "news_data" in data:
                    signals = data["news_data"]
                    query_term = data["query_term"]
                    
                    if "error" in signals:
                        return f"No news found for {query_term}."
                    
                    # Build a contextual prompt for the LLM to generate a narrative
                    context = {
                        "article_count": signals.get("article_count", 0),
                        "headlines": signals.get("headlines", [])[:3],
                        "average_sentiment": signals.get("average_sentiment", 0),
                        "query_term": query_term
                    }
                    
                    # Generate a market behavior explanation based on sentiment
                    sentiment_score = context["average_sentiment"]
                    if sentiment_score is None:
                        sentiment_desc = "neutral (no sentiment data available)"
                        narrative = "Without sentiment data, it's difficult to gauge market perception. In the absence of clear signals, market participants likely rely on their individual knowledge and experience to make decisions. This analysis is based on limited data and represents a plausible interpretation rather than certainty."
                    elif sentiment_score > 0.5:
                        sentiment_desc = "strongly positive"
                        narrative = f"The strongly positive sentiment around {query_term} suggests widespread optimism among market participants. Individuals appear to be confident about future returns, possibly reflecting favorable news or economic conditions. This could indicate investors are actively seeking opportunities in this area rather than alternatives like bonds or defensive assets. Remember, this analysis is based on recent news sentiment only and may not capture all market factors."
                    elif sentiment_score > 0.2:
                        sentiment_desc = "moderately positive"
                        narrative = f"The moderately positive sentiment surrounding {query_term} indicates cautious optimism in the market. Participants seem to see potential value while remaining aware of uncertainty. This balanced approach might reflect a situation where positive developments are being weighed against broader economic concerns. This interpretation is based on limited news data and should be considered alongside other market indicators."
                    elif sentiment_score >= -0.2:
                        sentiment_desc = "neutral"
                        narrative = f"The neutral sentiment around {query_term} suggests a market with balanced perspectives. This could indicate that investors have differing views on future prospects, with neither bullish nor bearish sentiment dominating. Such equilibrium often occurs when positive and negative factors are simultaneously present in the market. This assessment is based on recent news sentiment and represents one possible interpretation of market behavior."
                    elif sentiment_score >= -0.5:
                        sentiment_desc = "moderately negative"
                        narrative = f"The moderately negative sentiment surrounding {query_term} reflects heightened caution among market participants. This suggests investors may be responding to perceived risks by adjusting their positions to preserve capital. We might be seeing early signs of capital moving toward safer assets as individuals reassess risk and return expectations. This analysis is based on limited news data and should be considered alongside other market signals."
                    else:
                        sentiment_desc = "strongly negative"
                        narrative = f"The strongly negative sentiment around {query_term} indicates significant market concern. This likely represents a shift where participants are prioritizing capital preservation over growth potential. Investors may be moving from this sector toward safer assets like bonds, defensive stocks, or cash. This defensive positioning is a natural response to uncertainty, though the full context would require analysis of additional market data beyond news sentiment."
                    
                    headlines_str = "; ".join(context["headlines"]) if context["headlines"] else "No headlines available"
                    
                    return (f"News Analysis for {query_term}:\n"
                            f"Found {context['article_count']} articles\n"
                            f"Sample headlines: {headlines_str}\n"
                            f"Sentiment: {sentiment_desc} ({sentiment_score:.2f if sentiment_score is not None else 'N/A'})\n\n"
                            f"Market Behavior Explanation:\n{narrative}")
                
                # For stock data, provide price information with context
                elif "stock_data" in data:
                    stock_data = data["stock_data"]
                    ticker = data["ticker"]
                    
                    # Get the most recent price data
                    latest = stock_data.iloc[0]
                    
                    # Format basic price information
                    price_info = []
                    if 'close' in latest:
                        price_info.append(f"Latest close: ${latest['close']:.2f}")
                    if 'low' in latest and 'high' in latest:
                        price_info.append(f"Range: ${latest['low']:.2f} - ${latest['high']:.2f}")
                    if 'volume' in latest:
                        price_info.append(f"Volume: {latest['volume']:,}")
                    
                    # Calculate price change if we have enough data
                    price_narrative = ""
                    if len(stock_data) > 1 and 'close' in stock_data.columns:
                        oldest_close = stock_data.iloc[-1]['close']
                        newest_close = latest['close']
                        percent_change = ((newest_close - oldest_close) / oldest_close) * 100
                        price_info.append(f"Change: {percent_change:.2f}%")
                        
                        # Add ETF information if available
                        etf_info = []
                        if "etf_data" in data and "etf_ticker" in data:
                            etf_ticker = data["etf_ticker"]
                            etf_data = data["etf_data"]
                            
                            if len(etf_data) > 1 and 'close' in etf_data.columns:
                                etf_latest = etf_data.iloc[0]
                                etf_oldest = etf_data.iloc[-1]
                                etf_change = ((etf_latest['close'] - etf_oldest['close']) / etf_oldest['close']) * 100
                                etf_info.append(f"Sector ETF {etf_ticker}: {etf_change:.2f}%")
                        
                        if "leveraged_etf_data" in data and "leveraged_etf_ticker" in data:
                            lev_etf_ticker = data["leveraged_etf_ticker"]
                            lev_etf_data = data["leveraged_etf_data"]
                            
                            if len(lev_etf_data) > 1 and 'close' in lev_etf_data.columns:
                                lev_latest = lev_etf_data.iloc[0]
                                lev_oldest = lev_etf_data.iloc[-1]
                                lev_change = ((lev_latest['close'] - lev_oldest['close']) / lev_oldest['close']) * 100
                                etf_info.append(f"Leveraged ETF {lev_etf_ticker}: {lev_change:.2f}%")
                        
                        stock_summary = f"Stock data for {ticker}:\n" + "\n".join(price_info)
                        if etf_info:
                            stock_summary += "\n\nRelated Sector ETFs:\n" + "\n".join(etf_info)
                        
                        if percent_change > 5:
                            price_narrative = f"\n\nMarket Behavior Explanation:\nThe significant {percent_change:.2f}% increase in {ticker} suggests strong market interest and changing valuations. Participants appear to be anticipating positive developments, potentially due to sector-specific news or broader economic signals. This price movement likely represents investors actively shifting capital toward this asset based on favorable expectations. Note that this explanation is based solely on price movements without additional context from news or other market indicators."
                        elif percent_change > 0:
                            price_narrative = f"\n\nMarket Behavior Explanation:\nThe modest {percent_change:.2f}% increase in {ticker} indicates cautious positive sentiment. Market participants seem to be expressing moderate confidence while remaining aware of uncertainty. This gradual upward movement suggests a natural process where individual decisions collectively create a slight upward price trend. This interpretation is based on limited price data and represents one possible explanation for the observed behavior."
                        elif percent_change > -5:
                            price_narrative = f"\n\nMarket Behavior Explanation:\nThe slight {abs(percent_change):.2f}% decrease in {ticker} indicates a minor shift in market sentiment. This could reflect small adjustments in investment positions rather than significant concern. Individual traders may be responding to subtle changes in perceived value or redirecting capital to other opportunities. Without additional context from news or broader market trends, this represents a preliminary assessment of the price behavior."
                        else:
                            price_narrative = f"\n\nMarket Behavior Explanation:\nThe substantial {abs(percent_change):.2f}% decline in {ticker} suggests a significant shift in market sentiment. Participants appear to be reassessing risk or future value expectations, potentially causing capital to flow out of this asset toward safer alternatives. This defensive reaction is a natural response when facing perceived threats to value. A complete understanding would require analysis of news, sector trends, and broader market conditions beyond what this price data alone provides."
                        
                        return stock_summary + price_narrative
                    else:
                        return f"Stock data for {ticker}:\n" + "\n".join(price_info) + "\n\nInsufficient historical data to analyze price trends."
            
            # If we don't have specific data to analyze, provide help information
            return ("I can help with:\n"
                    "- 'Fetch news on <topic>' to get news and sentiment\n"
                    "- 'Get news for <ticker>' to get stock-specific news\n"
                    "- 'Get stock data for <ticker>' to get price information\n"
                    "- 'Get stock data for <ticker> since <date>' for specific date ranges\n"
                    "- 'Get stock data for <ticker> for the last <n> days/weeks/months'")

        except Exception as e:
            return f"Error processing request: {str(e)}"

    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen's method for generating replies.
        This is the primary entry point for the LLM function calling pipeline.
        
        The LLM will be guided by our system prompt to:
        1. Parse the user's query
        2. Decide which tools to call
        3. Process the returned data
        4. Generate a comprehensive response
        """
        if not messages:
            return "I can help with news sentiment analysis and stock data. Try asking about news or stocks."

        # Get the last message
        last_message = messages[-1]
        
        # For backward compatibility, we'll continue to use our handle_message method
        # In a future update, this will be completely replaced by the LLM's function calling
        return self.handle_message(last_message)
        
        # Future implementation will look like this:
        # system_prompt = self.build_system_prompt()
        # 
        # # Use the LLM to determine which tools to call and how to process the results
        # # This is handled automatically by AutoGen's function calling
        # # The LLM will:
        # # 1. Decide which tools to use
        # # 2. Call the tools with appropriate parameters
        # # 3. Process the results 
        # # 4. Generate a comprehensive response that includes both technical metrics and narrative
