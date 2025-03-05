from base_agent import BaseAgent
from src.tools.data_sources.news_headline_tool import NewsHeadlineTool
import pandas as pd
# from textblob import TextBlob


class SentimentAgent(BaseAgent):

    def __init__(self, name="SentimentAgent", config=None, memory_system=None):
        super().__init__(name, config, memory_system)
        # load news head line tool into toolset
        self.load_tool("news_api", NewsHeadlineTool(source="newsapi"))

    def fetch_news_data(self, keywords="market", count=5):
        """
        uses the loaded news headling tool to fetch news articles.
        """
        articles = self.use_tool("news_api", keywords=keywords, count=count)
        return articles

    def preprocess_data(self, news_data) -> dict:
        # e.g. calculate moving averages, implied vol spreads, etc.
        signals = {}
        if not news_data:
            signals["error"] = "No news data availble"
        else:
            signals["article_count"] = len(news_data)
            # list comprehensions create their own scope, and article is only used inside the comprehension.
            signals["headlines"] = [articles.get(
                "title", "") for article in news_data]
        return signals

    def handle_message(self, message: str) -> str:
        """
        Processes an incoming message command.
        expects messages as "fetch news on <keyword>".
        """
        # extract keyword from message (default is "market")
        if 'on' in message:
            keyword = message.split('on')[-1].strip()
        else:
            keyword = "market"
        try:
            # Fetch news data using the news headline tool
            news_data = self.fetch_news_data(keywords=keyword, count=5)
            signals = self.preprocess_data(news_data=news_data)
            return f"Processed signals: {signals}"
        except Exception as e:
            return f"Error in handling message: {str(e)}"


# stand alone tester->
if __name__ == "__main__":
    agent = SentimentAgent()
    response = agent.handle_message("Fetch news on Technology")
    print(response)
