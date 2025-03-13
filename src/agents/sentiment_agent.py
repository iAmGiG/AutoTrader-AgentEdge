# import sys
# import os

# # Dynamically add the project root (RH2MAS) to sys.path
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from .base_agent import BaseAgent
from config.config_loader import ConfigLoader
from src.tools.data_sources.news_headline_tool import NewsHeadlineTool
import pandas as pd

# Instantiate ConfigLoader once at module-level
_loader = ConfigLoader()

DEFAULT_SENTIMENT_CONFIG = {
    "open_model": _loader.get("open_model"),      # This is passed to BaseAgent
    "newsapi_key": _loader.get("newsapi_key"),
    "finnhub_key": _loader.get("finnhub_key")
}


class SentimentAgent(BaseAgent):

    def __init__(self, name="SentimentAgent", config=None, memory_system=None):
        merged_config = DEFAULT_SENTIMENT_CONFIG.copy()
        if config is not None:
            merged_config.update(config)
        super().__init__(name, merged_config, memory_system)
        # super().__init__(name, config, memory_system)
        # load news head line tool into toolset
        self.load_tool("news_api", NewsHeadlineTool(source="newsapi"))

    def fetch_news_data(self, keyword="market", count=5):
        """
        Uses the loaded NewsHeadlineTool to fetch news articles.
        Expects the tool to return a Pandas DataFrame.
        """
        articles_df = self.use_tool("news_api", keyword=keyword, count=count)
        return articles_df

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
        """
        # Extract keyword from message (default is "market")
        if 'on' in message:
            keyword = message.split('on')[-1].strip()
        else:
            keyword = "market"
        try:
            # Fetch news data using the NewsHeadlineTool.
            news_data = self.fetch_news_data(keyword=keyword, count=5)
            # Preprocess the fetched news data to generate sentiment signals.
            signals = self.preprocess_data(news_data=news_data)
            return f"Processed signals: {signals}"
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


# Standalone tester:
if __name__ == "__main__":
    agent = SentimentAgent()
    response = agent.handle_message("Fetch news on Technology")
    print(response)
