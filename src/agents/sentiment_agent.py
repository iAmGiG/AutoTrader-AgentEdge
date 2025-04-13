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
                                start_date = "-5d"  # Default to 5 days if no specific timeframe
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
                
                # If no date provided, default to 5 days
                if not start_date:
                    start_date = "-5d"
                
                return {
                    "ticker": ticker,
                    "topic": topic,
                    "start_date": start_date,
                    "end_date": end_date
                }
            
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
                        
                        if percent_change > 5:
                            price_narrative = f"\n\nMarket Behavior Explanation:\nThe significant {percent_change:.2f}% increase in {ticker} suggests strong market interest and changing valuations. Participants appear to be anticipating positive developments, potentially due to sector-specific news or broader economic signals. This price movement likely represents investors actively shifting capital toward this asset based on favorable expectations. Note that this explanation is based solely on price movements without additional context from news or other market indicators."
                        elif percent_change > 0:
                            price_narrative = f"\n\nMarket Behavior Explanation:\nThe modest {percent_change:.2f}% increase in {ticker} indicates cautious positive sentiment. Market participants seem to be expressing moderate confidence while remaining aware of uncertainty. This gradual upward movement suggests a natural process where individual decisions collectively create a slight upward price trend. This interpretation is based on limited price data and represents one possible explanation for the observed behavior."
                        elif percent_change > -5:
                            price_narrative = f"\n\nMarket Behavior Explanation:\nThe slight {abs(percent_change):.2f}% decrease in {ticker} indicates a minor shift in market sentiment. This could reflect small adjustments in investment positions rather than significant concern. Individual traders may be responding to subtle changes in perceived value or redirecting capital to other opportunities. Without additional context from news or broader market trends, this represents a preliminary assessment of the price behavior."
                        else:
                            price_narrative = f"\n\nMarket Behavior Explanation:\nThe substantial {abs(percent_change):.2f}% decline in {ticker} suggests a significant shift in market sentiment. Participants appear to be reassessing risk or future value expectations, potentially causing capital to flow out of this asset toward safer alternatives. This defensive reaction is a natural response when facing perceived threats to value. A complete understanding would require analysis of news, sector trends, and broader market conditions beyond what this price data alone provides."
                    
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
