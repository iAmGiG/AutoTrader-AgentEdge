"""
Finnhub data source tool for retrieving financial news and sentiment data.

This tool provides access to the Finnhub API to fetch financial news, company sentiment,
earnings information, and other market data with a focus on financial news and sentiment
analysis use cases.
"""

import requests
import logging
import pandas as pd
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
from config.config_loader import ConfigLoader

# Define news categories supported by Finnhub
NEWS_CATEGORIES = {
    "general": "General news",
    "forex": "Forex news",
    "crypto": "Cryptocurrency news",
    "merger": "Merger & Acquisitions news",
    "business": "Business news",
    "technology": "Technology news",
    "economic": "Economic news",
    "stock": "Stock-specific news"
}

class FinnHubTool:
    """
    A tool for accessing financial news and sentiment data from Finnhub.
    
    Finnhub provides real-time financial data and news with a focus on sentiment
    analysis, making it well-suited for the SentimentAgent.
    """

    def __init__(self, api_key: Optional[str] = None, verbose: bool = False):
        """
        Initialize the Finnhub data tool.
        
        Args:
            api_key: Optional API key for Finnhub. If not provided, will load from config.
            verbose: Whether to enable verbose logging.
        """
        # Set up logger
        self.logger = logging.getLogger(self.__class__.__name__)
        if verbose:
            logging.basicConfig(level=logging.INFO)
        
        # Load API key from config if not provided
        if api_key is None:
            config_loader = ConfigLoader()
            api_key = config_loader.get("finnhub_key")
            
            if not api_key:
                self.logger.error("No Finnhub API key provided in config.json")
                raise ValueError("Finnhub API key is required. Add it to config.json under 'finnhub_key' key.")
        
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
        self.logger.info("Finnhub API client initialized successfully")
        
        # Store the news categories for reference
        self.news_categories = NEWS_CATEGORIES
        
    def fetch_news(self, 
                 category: str = "general", 
                 tickers: Optional[List[str]] = None,
                 min_id: Optional[int] = None,
                 count: int = 10) -> pd.DataFrame:
        """
        Fetch news articles from Finnhub.
        
        Args:
            category: News category ('general', 'forex', 'crypto', 'merger', etc.)
            tickers: List of ticker symbols to filter by (optional)
            min_id: Minimum news ID (optional)
            count: Number of news articles to retrieve
            
        Returns:
            DataFrame with news articles
        """
        try:
            # Validate the category
            if category not in self.news_categories:
                self.logger.warning(f"Unknown category: {category}, defaulting to 'general'")
                category = "general"
            
            # Build the URL
            url = f"{self.base_url}/news?category={category}&token={self.api_key}"
            
            # Add ticker filter if provided
            if tickers is not None and len(tickers) > 0:
                tickers_str = ",".join(tickers)
                url += f"&tickers={tickers_str}"
            
            # Add min_id if provided
            if min_id is not None:
                url += f"&minId={min_id}"
            
            # Make the request
            self.logger.info(f"Fetching news from Finnhub for category: {category}")
            response = requests.get(url)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Parse the JSON response
            data = response.json()
            
            # Check if we got articles back
            if not data or not isinstance(data, list):
                self.logger.warning("No news articles returned from Finnhub")
                return pd.DataFrame()
            
            # Limit to requested count
            articles = data[:count]
            
            # Convert to DataFrame
            df = pd.DataFrame(articles)
            
            # Rename columns to standardized format
            if not df.empty:
                column_mapping = {
                    'headline': 'Headline',
                    'datetime': 'Date',
                    'source': 'Source',
                    'summary': 'Summary',
                    'url': 'URL',
                    'category': 'Category',
                    'related': 'Related'
                }
                df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
                
                # Convert epoch timestamp to datetime
                if 'datetime' in df.columns:
                    df['Date'] = pd.to_datetime(df['datetime'], unit='s')
                
                # Add source indicator
                df['Data Source'] = 'Finnhub'
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching news from Finnhub: {e}")
            return pd.DataFrame()
    
    def fetch_company_news(self, 
                          ticker: str, 
                          from_date: Optional[str] = None, 
                          to_date: Optional[str] = None,
                          count: int = 10) -> pd.DataFrame:
        """
        Fetch news for a specific company.
        
        Args:
            ticker: Company ticker symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            count: Number of news articles to retrieve
            
        Returns:
            DataFrame with company news
        """
        try:
            # Default dates to last 30 days if not provided
            if not to_date:
                to_date = datetime.now().strftime('%Y-%m-%d')
            
            if not from_date:
                from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Build the URL
            url = f"{self.base_url}/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={self.api_key}"
            
            # Make the request
            self.logger.info(f"Fetching company news from Finnhub for ticker: {ticker}")
            response = requests.get(url)
            response.raise_for_status()
            
            # Parse the JSON response
            data = response.json()
            
            # Check if we got articles back
            if not data or not isinstance(data, list):
                self.logger.warning(f"No company news returned from Finnhub for {ticker}")
                return pd.DataFrame()
            
            # Limit to requested count
            articles = data[:count]
            
            # Convert to DataFrame
            df = pd.DataFrame(articles)
            
            # Rename columns to standardized format
            if not df.empty:
                column_mapping = {
                    'headline': 'Headline',
                    'datetime': 'Date',
                    'source': 'Source',
                    'summary': 'Summary',
                    'url': 'URL',
                    'related': 'Related'
                }
                df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
                
                # Convert epoch timestamp to datetime
                if 'datetime' in df.columns:
                    df['Date'] = pd.to_datetime(df['datetime'], unit='s')
                
                # Add ticker and source indicators
                df['Ticker'] = ticker
                df['Data Source'] = 'Finnhub'
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching company news from Finnhub for {ticker}: {e}")
            return pd.DataFrame()
    
    def fetch_sentiment(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch sentiment data for a company.
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            Dictionary with sentiment data
        """
        try:
            # Build the URL
            url = f"{self.base_url}/news-sentiment?symbol={ticker}&token={self.api_key}"
            
            # Make the request
            self.logger.info(f"Fetching sentiment data from Finnhub for ticker: {ticker}")
            response = requests.get(url)
            response.raise_for_status()
            
            # Parse the JSON response
            data = response.json()
            
            # Check if we got data back
            if not data or not isinstance(data, dict):
                self.logger.warning(f"No sentiment data returned from Finnhub for {ticker}")
                return {}
            
            # Add timestamp for when this was fetched
            data['fetched_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching sentiment data from Finnhub for {ticker}: {e}")
            return {}
    
    def fetch_sentiment_as_dataframe(self, ticker: str) -> pd.DataFrame:
        """
        Fetch sentiment data for a company and return as DataFrame.
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            DataFrame with sentiment data
        """
        sentiment_data = self.fetch_sentiment(ticker)
        
        if not sentiment_data:
            return pd.DataFrame()
        
        # Extract the buzz and sentiment data
        buzz = sentiment_data.get('buzz', {})
        sentiment = sentiment_data.get('sentiment', {})
        
        # Create a dictionary with the data
        data = {
            'Ticker': ticker,
            'Date': sentiment_data.get('fetched_at'),
            'Buzz_ArticlesInLastWeek': buzz.get('articlesInLastWeek'),
            'Buzz_Buzz': buzz.get('buzz'),
            'Buzz_WeeklyAverage': buzz.get('weeklyAverage'),
            'CompanyNewsScore': sentiment.get('companyNewsScore'),
            'SectorAverageNewsScore': sentiment.get('sectorAverageNewsScore'),
            'BullishPercent': sentiment.get('bullishPercent'),
            'BearishPercent': sentiment.get('bearishPercent'),
            'Data Source': 'Finnhub'
        }
        
        # Convert to DataFrame with a single row
        df = pd.DataFrame([data])
        return df
    
    def fetch_news_and_sentiment(self, 
                               ticker: str, 
                               from_date: Optional[str] = None, 
                               to_date: Optional[str] = None,
                               count: int = 10) -> pd.DataFrame:
        """
        Fetch both news and sentiment data for a company and combine them.
        
        Args:
            ticker: Company ticker symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            count: Number of news articles to retrieve
            
        Returns:
            DataFrame with news and sentiment data
        """
        try:
            # Fetch company news
            news_df = self.fetch_company_news(ticker, from_date, to_date, count)
            
            # Fetch sentiment data
            sentiment_df = self.fetch_sentiment_as_dataframe(ticker)
            
            # If we have both news and sentiment data, calculate a sentiment score for each article
            if not news_df.empty and not sentiment_df.empty:
                company_score = sentiment_df['CompanyNewsScore'].iloc[0]
                bullish_percent = sentiment_df['BullishPercent'].iloc[0]
                
                # Use these values to calculate a simple sentiment score for each article
                # This is a simplified approach; in reality, you'd want to use NLP for each article
                if 'Headline' in news_df.columns and 'Summary' in news_df.columns:
                    # Seed each article with the company's overall sentiment
                    news_df['sentiment_score'] = company_score
                    news_df['sentiment'] = news_df['sentiment_score'].apply(
                        lambda x: 'bullish' if x > 0.5 else ('bearish' if x < 0.3 else 'neutral')
                    )
            
            # If we only have news data, return it as is
            if news_df.empty:
                self.logger.warning(f"No news data available for {ticker}")
                return pd.DataFrame()
                
            return news_df
            
        except Exception as e:
            self.logger.error(f"Error fetching news and sentiment for {ticker}: {e}")
            return pd.DataFrame()
    
    def list_news_categories(self) -> pd.DataFrame:
        """
        List available news categories.
        
        Returns:
            DataFrame with category IDs and descriptions
        """
        data = []
        for category_id, description in self.news_categories.items():
            data.append({
                'category_id': category_id,
                'description': description
            })
        
        return pd.DataFrame(data)


# Example usage
if __name__ == "__main__":
    # Enable logging for example
    logging.basicConfig(level=logging.INFO, 
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Initialize the tool
    finnhub_tool = FinnHubTool(verbose=True)
    
    try:
        # Example 1: Fetch general news
        print("\nExample 1: Fetch general news")
        news_df = finnhub_tool.fetch_news(category="general", count=3)
        if not news_df.empty:
            print(f"Fetched {len(news_df)} news articles")
            for _, article in news_df.iterrows():
                print(f"- {article.get('Headline', 'No headline')}")
        
        # Example 2: Fetch company news
        print("\nExample 2: Fetch company news for AAPL")
        apple_news = finnhub_tool.fetch_company_news("AAPL", count=3)
        if not apple_news.empty:
            print(f"Fetched {len(apple_news)} Apple news articles")
            for _, article in apple_news.iterrows():
                print(f"- {article.get('Headline', 'No headline')}")
        
        # Example 3: Fetch sentiment data
        print("\nExample 3: Fetch sentiment data for TSLA")
        sentiment = finnhub_tool.fetch_sentiment("TSLA")
        if sentiment:
            print(f"TSLA Sentiment Score: {sentiment.get('sentiment', {}).get('companyNewsScore')}")
            print(f"Bullish Articles: {sentiment.get('sentiment', {}).get('bullishPercent', 0):.1%}")
            print(f"Bearish Articles: {sentiment.get('sentiment', {}).get('bearishPercent', 0):.1%}")
        
        # Example 4: Fetch combined news and sentiment
        print("\nExample 4: Fetch news and sentiment for NVDA")
        combined_df = finnhub_tool.fetch_news_and_sentiment("NVDA", count=3)
        if not combined_df.empty:
            print(f"Fetched {len(combined_df)} NVDA news articles with sentiment")
            for _, article in combined_df.iterrows():
                if 'sentiment' in article:
                    print(f"- {article.get('Headline', 'No headline')} (Sentiment: {article.get('sentiment', 'unknown')})")
                else:
                    print(f"- {article.get('Headline', 'No headline')}")
    
    except Exception as e:
        print(f"Error in example: {e}")