import requests


class NewsHeadlineTool:
    def __init__(self, api_key, source="finnhub"):
        self.api_key = api_key
        self.source = source

    def fetch_news(self, keyword="market", count=5):
        if self.source == "finnhub":
            url = f"https://finnhub.io/api/v1/news?category=general&token={self.api_key}"
        elif self.source == "newsapi":
            url = f"https://newsapi.org/v2/everything?q={keyword}&apiKey={self.api_key}"
        else:
            raise ValueError("Unsupported news source")

        response = requests.get(url).json()
        return response[:count] if self.source == "finnhub" else response["articles"][:count]


# Example Usage
news_tool = NewsHeadlineTool("YOUR_API_KEY", source="finnhub")
articles = news_tool.fetch_news("inflation", count=3)
for article in articles:
    print(article["headline"] if "headline" in article else article["title"])
