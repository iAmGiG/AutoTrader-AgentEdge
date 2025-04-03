from .base_agent import BaseAgent
from config.config_loader import ConfigLoader
from src.tools.tools import news_tool, yahoo_finance_tool
from src.tools.tools import fetch_news, fetch_yahoo_data

# Instantiate ConfigLoader once at module-level
_loader = ConfigLoader()

DEFAULT_SENTIMENT_CONFIG = {
    "open_model": _loader.get("open_model"),      # This is passed to BaseAgent
    "newsapi_key": _loader.get("newsapi_key"),
    # "finnhub_key": _loader.get("finnhub_key")
}


class SentimentAgent(BaseAgent):

    def __init__(self, name="SentimentAgent", memory_system=None):
        # Pass the FunctionTool(s) to the BaseAgent's tools parameter
        super().__init__(name=name, tools=[
            news_tool, yahoo_finance_tool], memory_system=memory_system)

    def fetch_news_data(self, keyword="market", count=5):
        """
        Uses the NewsHeadlineTool to fetch news articles.
        Expects to return a Pandas DataFrame.
        """
        articles_df = fetch_news(keyword=keyword, count=count)
        return articles_df

    def fetch_yahoo_data(self, ticker: str = "AAPL", start_date: str = "2025-01-01", end_date: str = "2025-01-02"):
        """
        Uses the YahooFinanceTool to fetch stock data.
        Returns a Pandas DataFrame.
        """
        market_df = fetch_yahoo_data(ticker=ticker, start_date=start_date, end_date=end_date)
        return market_df

    def preprocess_data(self, news_data) -> dict:
        """
        Processes the news data (a DataFrame) to extract sentiment signals.
        Returns a dictionary with:
          - article_count: number of articles fetched
          - headlines: list of headlines
          - average_sentiment: average sentiment score (if available)
        """
        signals = {}
        if news_data.empty:
            signals["error"] = "No news data available"
        else:
            signals["article_count"] = len(news_data)
            # Extract headlines from the DataFrame.
            signals["headlines"] = news_data["Headline"].tolist()
            # Compute average sentiment score if the column exists.
            signals["average_sentiment"] = news_data["Sentiment Score"].mean(
            ) if "Sentiment Score" in news_data.columns else None
        return signals

    def handle_message(self, message: str) -> str:
        """
        Processes an incoming message command.
        Expects messages in the format "Fetch news on <keyword>".
        
        In AutoGen 0.4.x, we should ideally let the LLM-driven agent decide when to use tools,
        but for direct testing we'll use the manual approach.
        """
        # Extract keyword from message (default is "market")
        if 'on' in message:
            keyword = message.split('on')[-1].strip()
        else:
            keyword = "market"
        try:
                        
            # Fetch news data using the function directly
            news_data = self.fetch_news_data(keyword=keyword, count=5)
            if news_data.empty:
                return f"No news found for {keyword}."

            # if not empty: Preprocess the fetched news data to generate sentiment signals.
            signals = self.preprocess_data(news_data=news_data)
            return f"Fetched and processed signals: {signals}"
        except Exception as e:
            return f"Error in handling message: {str(e)}"

    def generate_reply(self, messages, context=None) -> str:
        # Default keyword is "market"; try to extract from the latest message.
        keyword = "market"
        if messages:
            # Assume messages is a list of strings; use the last one.
            last_message = messages[-1]
            if "on" in last_message:
                keyword = last_message.split("on")[-1].strip()

        try:
            # Fetch the news data (expects a DataFrame)
            news_data = self.fetch_news_data(keyword=keyword, count=5)
            # Process the DataFrame to extract sentiment signals
            signals = self.preprocess_data(news_data)
            # Optionally, store the signals in memory for later reference
            self.store_in_memory(f"sentiment_signals_{keyword}", signals)

            # Build the reply string based on the processed data
            if "error" in signals:
                reply = f"Error: {signals['error']}"
            else:
                # Prepare a preview of headlines (e.g., the first three)
                headlines_preview = "; ".join(signals["headlines"][:3])
                avg_sentiment = signals["average_sentiment"] if signals["average_sentiment"] is not None else "N/A"
                reply = (
                    f"Fetched {signals['article_count']} articles on '{keyword}'. "
                    f"Sample headlines: {headlines_preview}. "
                    f"Average Sentiment Score: {avg_sentiment}."
                )
            return reply
        except Exception as e:
            return f"Error generating reply: {str(e)}"
