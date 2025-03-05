"""api request and news feed tool"""
import requests
import sys
from config.config_loader import ConfigLoader


class NewsHeadlineTool:
    """gets the latest headlines"""

    def __init__(self, source="newsapi"):
        # Load configuration and API key from config file.
        # source might be depricated, might just seperate out each tool into their own file.
        config_loader = ConfigLoader()
        self.api_key = config_loader.get("newsapi_key")
        self.source = source

    def fetch_data(self, keyword="market", count=5):
        """
        Fetches news articles based on a keyword.

        :param keyword: Search keyword for news articles.
        :param count: Number of articles to return.
        :return: A list of articles.
        """
        if self.source == "newsapi":
            url = f"https://newsapi.org/v2/everything?q={keyword}&pageSize={count}&apiKey={self.api_key}"
            response = requests.get(url)
            if response.status_code == 200:
                # Return the list of articles from the JSON response
                data = response.json()
                return data.get("articles", [])
            else:
                raise Exception(
                    f"News API error: {response.status_code} - {response.text}")
        else:
            raise ValueError("Unsupported news source provided.")


if __name__ == "__main__":
    # Remove potential duplicate entry to avoid RuntimeWarning
    module_name = "src.tools.data_sources.news_headline_tool"
    if module_name in sys.modules:
        del sys.modules[module_name]

    # Run the tool normally
    tool = NewsHeadlineTool(source="newsapi")
    try:
        articles = tool.fetch_data(keyword="investment", count=3)
        for idx, article in enumerate(articles, start=1):
            # print(f"Article {idx}: {article.get('title')}") # print article and just title
            print(f"Article {idx}: {article}")  # Print full article dict
    except Exception as e:
        print("Error fetching news:", e)
