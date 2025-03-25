"""api request and news feed tool with DataFrame output and sentiment analysis"""
import sys
from datetime import datetime
from config.config_loader import ConfigLoader
import requests
import pandas as pd
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer


class NewsHeadlineTool:
    """gets the latest headlines and returns them as a DataFrame with sentiment analysis"""

    def __init__(self, source="newsapi"):
        # Load configuration and API key from config file
        config_loader = ConfigLoader()
        self.api_key = config_loader.get("newsapi_key")
        self.source = source

        # Initialize sentiment analyzer
        try:
            # Download required NLTK resources if not already present
            nltk.download('vader_lexicon', quiet=True)
            self.sentiment_analyzer = SentimentIntensityAnalyzer()
        except Exception as e:
            print(f"Error initializing sentiment analyzer: {e}")
            self.sentiment_analyzer = None

    def _analyze_sentiment(self, text):
        """
        Analyzes the sentiment of the given text.

        :param text: Text to analyze
        :return: A sentiment score between -1 (negative) and 1 (positive)
        """
        if self.sentiment_analyzer is None or not text:
            return 0.0

        sentiment = self.sentiment_analyzer.polarity_scores(text)
        # Return the compound score which is between -1 and 1
        return sentiment['compound']

    def fetch_data(self, keyword="market", count=5):
        """
        Fetches news articles based on a keyword and returns a DataFrame.

        :param keyword: Search keyword for news articles.
        :param count: Number of articles to return.
        :return: A pandas DataFrame containing news data with sentiment analysis.
        """
        # Create an empty DataFrame with the required columns
        df = pd.DataFrame(
            columns=['Timestamp', 'Headline', 'Source', 'Sentiment Score', 'URL', 'Content'])

        if self.source == "newsapi":
            url = f"https://newsapi.org/v2/everything?q={keyword}&pageSize={count}&apiKey={self.api_key}"
            response = requests.get(url)

            if response.status_code == 200:
                # Get the list of articles from the JSON response
                data = response.json()
                articles = data.get("articles", [])

                # Process each article and add it to the DataFrame
                for article in articles:
                    # Extract the required fields
                    headline = article.get('title', '')
                    source = article.get('source', {}).get('name', 'Unknown')
                    published_at = article.get('publishedAt', '')
                    url = article.get('url', '')
                    content = article.get(
                        'content', article.get('description', ''))

                    # Parse the timestamp
                    try:
                        timestamp = datetime.strptime(
                            published_at, "%Y-%m-%dT%H:%M:%SZ")
                    except (ValueError, TypeError):
                        timestamp = datetime.now()  # Use current time if parsing fails

                    # Calculate sentiment score for headline and content combined
                    sentiment_text = f"{headline} {content}"
                    sentiment_score = self._analyze_sentiment(sentiment_text)

                    # Add the article to the DataFrame
                    new_row = {
                        'Timestamp': timestamp,
                        'Headline': headline,
                        'Source': source,
                        'Sentiment Score': sentiment_score,
                        'URL': url,
                        'Content': content
                    }
                    df = pd.concat(
                        [df, pd.DataFrame([new_row])], ignore_index=True)

                return df
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
        # Fetch news data as a DataFrame
        news_df = tool.fetch_data(keyword="investment", count=3)

        # Display the DataFrame
        print("\nNews DataFrame:")
        print(news_df[['Timestamp', 'Headline',
              'Source', 'Sentiment Score']].to_string())

        # Print full details of the first article
        if not news_df.empty:
            print("\nDetailed view of first article:")
            first_article = news_df.iloc[0]
            for column, value in first_article.items():
                print(f"{column}: {value}")
    except Exception as e:
        print("Error fetching news:", e)
