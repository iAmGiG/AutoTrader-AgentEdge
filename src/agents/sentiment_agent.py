from .base_agent import BaseAgent
from config.config_loader import ConfigLoader
from typing import Dict, List, Any, Optional
import pandas as pd
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
• Present a coherent summary that includes both numerical sentiment scores and a missesian-style narrative interpretation.

Your tasks include:
1. Fetch data:
   • Use fetch_news(keyword: str, count: int) to retrieve recent news articles about a specific topic.
   • Use fetch_market_data(symbol: str, start_date?: str, end_date?: str) or fetch_yahoo_data(ticker: str, start_date?: str, end_date?: str) to retrieve stock data.

2. Process data and apply sentiment analysis:
   • Analyze the textual content of news headlines/articles and compute an average sentiment score.
   • Use shared utilities (such as data normalization and sentiment analyzer tools) to standardize input data, ensuring consistency across various data sources.

3. Provide two layers of output:
   • A technical summary detailing the number of articles fetched, sample headlines, and the average sentiment score.
   • A missesian-style narrative explanation that interprets the market situation in human-friendly language. For example, if the news suggests caution in the market, the response might include:
     "It appears that investors are reacting to significant policy adjustments, reflecting broader human concerns about uncertainty—much like how individuals naturally adjust their behavior in the face of unforeseen challenges."

4. Default behaviors:
   • If no date range is specified, default to a 5-day range.
   • When a user says "Fetch news on X," invoke fetch_news with the keyword X (and a count of 5 by default), then combine technical sentiment with the missesian narrative.
   • If a user requests "Get stock data for AAPL," invoke fetch_market_data or fetch_yahoo_data with "AAPL" as the ticker.

5. Future-Proofing:
   • The system is designed modularly. As new tools (e.g., SEC data or FRED economic indicators) are integrated, they can be incorporated in the same manner. Their outputs should be normalized by the existing data normalizer so that subsequent sentiment analysis and narrative synthesis remain consistent.

Follow these instructions exactly. Only call a data-fetching tool when the user's request requires it; otherwise, provide a direct answer with both technical details and a missesian-style interpretation of the market."""

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
                
                # Extract ticker if present (uppercase 1-5 chars)
                words = message.split()
                for word in words:
                    if word.isupper() and 1 <= len(word) <= 5:
                        ticker = word
                        break
                
                # Extract topic if "about" or "on" or "for" is in the message
                topic_indicators = ["about", "on", "for"]
                for indicator in topic_indicators:
                    if indicator in message.lower():
                        parts = message.lower().split(indicator)
                        if len(parts) > 1:
                            # Skip if what follows is just the ticker we already found
                            topic_candidate = parts[1].strip()
                            if not (ticker and ticker.lower() in topic_candidate):
                                topic = topic_candidate
                                break
                
                # Look for date-related keywords
                if "since" in message:
                    after_since = message.split("since")[-1].strip()
                    words = after_since.split()
                    if words and (words[0].startswith("-") or words[0] in ["yesterday", "today", "ytd"]):
                        start_date = words[0]
                
                if "last" in message:
                    after_last = message.split("last")[-1].strip()
                    words = after_last.split()
                    if words:
                        if "day" in after_last or "days" in after_last:
                            try:
                                days = int(words[0])
                                start_date = f"-{days}d"
                            except ValueError:
                                start_date = "-30d"
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
                
                return {
                    "ticker": ticker,
                    "topic": topic,
                    "start_date": start_date,
                    "end_date": end_date
                }
            
            # Step 1: Use the LLM to analyze the message directly and decide what to do
            # This is the new function calling approach where we pass the message to the LLM
            # and let it decide which tools to call
            
            # For now, we'll implement a hybrid approach that will work with the existing
            # infrastructure while we transition to the full function calling approach
            
            # Based on the message content, we'll prepare data for the LLM
            query_details = extract_query_details(message)
            data = {}
            
            # Determine the type of request
            if "news" in message.lower() or "sentiment" in message.lower():
                # News sentiment request
                if query_details["ticker"]:
                    # Fetch news for a specific ticker
                    news_data = fetch_market_data(
                        symbol=query_details["ticker"], 
                        source="alpha_vantage"
                    )
                    if not news_data.empty:
                        data["news_data"] = self.preprocess_data(news_data)
                        data["query_term"] = query_details["ticker"]
                else:
                    # Fetch general news
                    keyword = query_details["topic"] or "market"
                    news_data = fetch_news(keyword=keyword, count=5)
                    if not news_data.empty:
                        data["news_data"] = self.preprocess_data(news_data)
                        data["query_term"] = f"'{keyword}'"
            
            elif "stock" in message.lower() or "price" in message.lower():
                # Stock price request
                ticker = query_details["ticker"] or "AAPL"  # Default ticker
                stock_data = fetch_market_data(
                    symbol=ticker,
                    start_date=query_details["start_date"],
                    end_date=query_details["end_date"],
                    source="alpha_vantage"
                )
                if not stock_data.empty:
                    data["stock_data"] = stock_data
                    data["ticker"] = ticker
            
            # If we have data, use the LLM to analyze it and generate a response
            if data:
                # For news data, we want to generate a narrative response
                if "news_data" in data:
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
                    
                    # Generate a more sophisticated missesian narrative based on sentiment
                    sentiment_score = context["average_sentiment"]
                    if sentiment_score is None:
                        sentiment_desc = "neutral (no sentiment data available)"
                        narrative = "Without sentiment data, it's difficult to gauge market perception. In the absence of clear signals, market participants likely rely on their individual knowledge and experience to make decisions, as described in Mises' theory of human action."
                    elif sentiment_score > 0.5:
                        sentiment_desc = "strongly positive (bullish)"
                        narrative = f"The strongly positive sentiment around {query_term} reflects collective optimism among market participants. From a Misesian perspective, this optimism represents the coordinated actions of individuals making choices based on their unique knowledge and future expectations. Investors appear to be demonstrating confidence in future returns, suggesting a shared perception of value and opportunity."
                    elif sentiment_score > 0.2:
                        sentiment_desc = "moderately positive"
                        narrative = f"The moderately positive sentiment surrounding {query_term} indicates cautious optimism in the market. According to the Austrian view of human action, this represents a balance where market participants see potential value but remain aware of uncertainty. This measured approach suggests investors are exercising their subjective judgment while maintaining some prudence."
                    elif sentiment_score >= -0.2:
                        sentiment_desc = "neutral"
                        narrative = f"The neutral sentiment around {query_term} suggests a market in equilibrium, with diverse opinions balancing each other. From a Misesian perspective, this represents a natural state where individual actors have different time preferences and risk tolerances, leading to a steady market with neither excessive optimism nor pessimism driving action."
                    elif sentiment_score >= -0.5:
                        sentiment_desc = "moderately negative"
                        narrative = f"The moderately negative sentiment surrounding {query_term} reflects heightened caution among market participants. Through a Misesian lens, this represents individuals responding rationally to perceived uncertainty by adjusting their actions to preserve capital. This behavior demonstrates how market actors adapt to changing conditions based on their subjective valuations and expectations."
                    else:
                        sentiment_desc = "strongly negative (bearish)"
                        narrative = f"The strongly negative sentiment around {query_term} indicates significant market concern. In Austrian economic terms, this represents a collective reevaluation of time preferences, where market participants are shifting focus from longer-term investments to more immediate security. This defensive positioning reflects the natural human response to uncertainty—a core principle in Mises' theory of human action."
                    
                    headlines_str = "; ".join(context["headlines"]) if context["headlines"] else "No headlines available"
                    
                    return (f"News Analysis for {query_term}:\n"
                            f"Found {context['article_count']} articles\n"
                            f"Sample headlines: {headlines_str}\n"
                            f"Sentiment: {sentiment_desc} ({sentiment_score})\n\n"
                            f"Narrative Interpretation:\n{narrative}")
                
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
                        
                        if percent_change > 5:
                            price_narrative = f"\n\nMissesian Narrative:\nThe significant {percent_change:.2f}% increase in {ticker} reflects a strong shift in market participants' valuations. From an Austrian perspective, this price movement represents the coordinated actions of individuals expressing their subjective valuations through voluntary exchange. The rising price suggests market actors are anticipating future value creation based on their diverse knowledge and expectations."
                        elif percent_change > 0:
                            price_narrative = f"\n\nMissesian Narrative:\nThe modest {percent_change:.2f}% increase in {ticker} represents the aggregated decisions of market participants acting on their individual knowledge and expectations. This gradual upward movement suggests a natural market process where actors are expressing cautious optimism while maintaining awareness of future uncertainty."
                        elif percent_change > -5:
                            price_narrative = f"\n\nMissesian Narrative:\nThe slight {abs(percent_change):.2f}% decrease in {ticker} indicates a subtle shift in market sentiment. From a Misesian perspective, this represents individuals adjusting their actions based on changing expectations and time preferences, demonstrating how market prices emerge from human choices rather than abstract forces."
                        else:
                            price_narrative = f"\n\nMissesian Narrative:\nThe substantial {abs(percent_change):.2f}% decline in {ticker} reflects a significant reevaluation by market participants. Through an Austrian lens, this price movement represents individuals responding to uncertainty by adjusting their time preferences and risk assessments. This natural defensive reaction demonstrates the human element in market dynamics, as actors preserve capital when facing perceived threats to future value."
                    
                    return f"Stock data for {ticker}:\n" + "\n".join(price_info) + price_narrative
            
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
