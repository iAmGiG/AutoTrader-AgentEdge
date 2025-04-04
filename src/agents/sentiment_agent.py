from .base_agent import BaseAgent
from config.config_loader import ConfigLoader
from src.tools.tools import (
    news_tool, yahoo_finance_tool, alpha_vantage_tool,
    alpha_vantage_news_tool, market_data_tool
)
from src.tools.tools import (
    fetch_news, fetch_yahoo_data, fetch_alpha_vantage_data,
    fetch_alpha_vantage_news, fetch_market_data
)
from src.tools.text_processing.data_normalizer import normalize_data_for_sentiment

# Instantiate ConfigLoader once at module-level
_loader = ConfigLoader()

DEFAULT_SENTIMENT_CONFIG = {
    "open_model": _loader.get("open_model"),      # This is passed to BaseAgent
    "newsapi_key": _loader.get("newsapi_key"),
    "alpha_vantage_key": _loader.get("alpha_vantage_key"),
    # "finnhub_key": _loader.get("finnhub_key")
}


class SentimentAgent(BaseAgent):

    def __init__(self, name="SentimentAgent", memory_system=None):
        # Pass the FunctionTool(s) to the BaseAgent's tools parameter
        super().__init__(name=name, tools=[
            market_data_tool  # Only need the unified MarketDataTool
        ], memory_system=memory_system)

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

    def handle_message(self, message: str) -> str:
        """
        Processes an incoming message command using the unified MarketDataTool.
        Expects messages in formats like:
        - "Fetch news on <keyword>" or "Get news for <ticker>"
        - "Get stock data for <ticker>"
        """
        try:
            # Determine intent from message
            if "news" in message.lower():
                # Extract ticker or topic from message
                ticker = None
                topic = None

                if "for" in message:
                    query = message.split("for")[-1].strip()
                    # If query looks like a ticker (all caps, 1-5 chars), treat as ticker
                    if query.isupper() and 1 <= len(query) <= 5:
                        ticker = query
                    else:
                        topic = query

                if ticker:
                    # Fetch news by ticker
                    news_data = fetch_market_data(
                        symbol=ticker, source="alpha_vantage")
                    if news_data.empty:
                        return f"No news found for ticker {ticker}."
                else:
                    # For non-ticker queries, use the default news source
                    keyword = topic or "market"
                    news_data = fetch_news(keyword=keyword, count=5)
                    if news_data.empty:
                        return f"No news found for {keyword}."

                # Process the news data to extract sentiment signals
                signals = self.preprocess_data(news_data)

                # Format a nicer response
                headlines = "; ".join(
                    signals["headlines"][:3]) if "headlines" in signals else "No headlines available"
                sentiment = signals.get("average_sentiment", "N/A")

                query_term = ticker if ticker else f"'{keyword}'"
                return (f"News for {query_term}:\n"
                        f"Found {signals.get('article_count', 0)} articles\n"
                        f"Sample headlines: {headlines}\n"
                        f"Average sentiment score: {sentiment}")

            elif "stock" in message.lower() or "price" in message.lower():
                # Extract ticker from message
                if 'for' in message:
                    ticker = message.split('for')[-1].strip()
                else:
                    ticker = "AAPL"  # Default ticker

                # Use standard date range
                start_date = "2024-01-01"
                end_date = "2024-01-31"

                # Fetch stock data using the unified market data tool
                stock_data = fetch_market_data(
                    symbol=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    source="alpha_vantage"
                )

                if stock_data.empty:
                    return f"No stock data found for {ticker}."

                # Get the most recent price data
                # Assuming data is sorted with newest first
                latest = stock_data.iloc[0]

                # Format output based on available columns
                price_info = []
                if 'close' in latest:
                    price_info.append(f"Latest close: ${latest['close']:.2f}")
                if 'low' in latest and 'high' in latest:
                    price_info.append(
                        f"Range: ${latest['low']:.2f} - ${latest['high']:.2f}")
                if 'volume' in latest:
                    price_info.append(f"Volume: {latest['volume']:,}")

                return f"Stock data for {ticker}:\n" + "\n".join(price_info)

            else:
                # Generic fallback for other commands
                return ("I can help with:\n"
                        "- 'Fetch news on <topic>' to get news and sentiment\n"
                        "- 'Get news for <ticker>' to get stock-specific news\n"
                        "- 'Get stock data for <ticker>' to get price information")

        except Exception as e:
            return f"Error processing request: {str(e)}"

    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen's method for generating replies.
        Parses the last message to identify intent and generate an appropriate response.
        """
        if not messages:
            return "I can help with news sentiment analysis and stock data. Try asking about news or stocks."

        # Get the last message
        last_message = messages[-1]

        # This method just routes to our handle_message method for consistency
        return self.handle_message(last_message)
