from base_agent import BaseAgent
from src.tools.data_sources.news_headline_tool import NewsHeadlineTool
import pandas as pd


class SentimentAgent(BaseAgent):

    def __init__(self, name="SentimentAgent", config=None, memory_system=None):
        super().__init__(name, config, memory_system)
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
    # Fetch and preprocess data
    # Generate response or sentiment signals
    # Return the final string response (for LLM prompting)


# Standalone tester:
if __name__ == "__main__":
    agent = SentimentAgent()
    response = agent.handle_message("Fetch news on Technology")
    print(response)