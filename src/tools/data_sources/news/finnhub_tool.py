"""
Finnhub data source tool for retrieving financial news headlines.

This tool provides access to the Finnhub API to fetch financial news headlines across
various categories including general business, economic, and market news. It focuses
on features available in the free tier API plan, specifically optimized for headline
retrieval for sentiment analysis.
"""

import requests
import logging
from config.config_loader import ConfigLoader
import pandas as pd
from typing import Optional, List
import os
from src.tools.date_utils import process_date_param, get_processed_date_range

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
    A tool for accessing financial news headlines from Finnhub.

    Designed to work with Finnhub's free tier API to retrieve news headlines
    across various categories (business, economic, forex, etc.). This tool
    focuses specifically on headline retrieval for sentiment analysis
    without requiring premium features.
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

        # Load API key from environment if not provided
        if api_key is None:
            config_loader = ConfigLoader()
            api_key = os.getenv(
                "FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

            if not api_key:
                self.logger.error("No Finnhub API key provided in environment")
                raise ValueError(
                    "Finnhub API key is required. Set the FINNHUB_KEY environment variable."
                )

        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
        self.logger.info("Finnhub API client initialized successfully")

        # Store the news categories for reference
        self.news_categories = NEWS_CATEGORIES

    def fetch_news(self,
                   category: str = "general",
                   tickers: Optional[List[str]] = None,
                   count: int = 10) -> pd.DataFrame:
        """
        Fetch news headlines from Finnhub free tier API.

        Args:
            category: News category ('general', 'forex', 'crypto', 'business', 'economic', etc.)
            tickers: List of ticker symbols to filter by (optional, may not work in free tier)
            count: Number of news articles to retrieve

        Returns:
            DataFrame with news headlines optimized for sentiment analysis
        """
        try:
            # Validate the category
            if category not in self.news_categories:
                self.logger.warning(
                    f"Unknown category: {category}, defaulting to 'general'")
                category = "general"

            # Build the URL
            url = f"{self.base_url}/news?category={category}&token={self.api_key}"

            # Add ticker filter if provided (note: may not work in free tier)
            if tickers is not None and len(tickers) > 0:
                tickers_str = ",".join(tickers)
                url += f"&tickers={tickers_str}"

            # Make the request
            self.logger.info(
                f"Fetching news headlines from Finnhub for category: {category}")
            response = requests.get(url)
            response.raise_for_status()  # Raise exception for HTTP errors

            # Parse the JSON response
            data = response.json()

            # Check if we got articles back
            if not data or not isinstance(data, list):
                self.logger.warning("No news headlines returned from Finnhub")
                return pd.DataFrame()

            # Limit to requested count
            articles = data[:count]

            # Filter only the fields we need (reducing memory footprint)
            simplified_articles = []
            for article in articles:
                simplified_articles.append({
                    'headline': article.get('headline', ''),
                    'datetime': article.get('datetime', 0),
                    'source': article.get('source', ''),
                    # Limit summary length
                    'summary': article.get('summary', '')[:200] if article.get('summary') else '',
                    'url': article.get('url', ''),
                    'category': article.get('category', '')
                })

            # Convert to DataFrame
            df = pd.DataFrame(simplified_articles)

            # Rename columns to standardized format
            if not df.empty:
                column_mapping = {
                    'headline': 'Headline',
                    'datetime': 'Date',
                    'source': 'Source',
                    'summary': 'Summary',
                    'url': 'URL',
                    'category': 'Category'
                }
                df = df.rename(
                    columns={k: v for k, v in column_mapping.items() if k in df.columns})

                # Convert epoch timestamp to datetime
                if 'datetime' in df.columns:
                    df['Date'] = pd.to_datetime(df['datetime'], unit='s')

                # Add source indicator
                df['Data Source'] = 'Finnhub'

            return df

        except Exception as e:
            self.logger.error(f"Error fetching news from Finnhub: {e}")
            return pd.DataFrame()

    def fetch_financial_headlines(self, count: int = 10) -> pd.DataFrame:
        """
        Fetch a combined set of financial and economic headlines from multiple categories.
        This method is specifically designed for sentiment analysis and combines business,
        economic, and market news into a single DataFrame.

        Args:
            count: Number of news headlines to retrieve per category

        Returns:
            DataFrame with diverse financial headlines for sentiment analysis
        """
        try:
            # Fetch headlines from multiple financial categories
            self.logger.info(
                "Fetching diverse financial headlines from Finnhub")

            # These categories are available in the free tier and cover different
            # aspects of financial markets
            categories = ["business", "economic", "forex", "general"]

            all_headlines = []
            for category in categories:
                # Get headlines for this category
                category_df = self.fetch_news(
                    category=category, count=count // len(categories))

                if not category_df.empty:
                    all_headlines.append(category_df)

            # Combine into a single DataFrame
            if all_headlines:
                combined_df = pd.concat(all_headlines, ignore_index=True)
                combined_df = combined_df.sort_values(
                    by='Date', ascending=False)
                return combined_df
            else:
                self.logger.warning(
                    "No financial headlines found from any category")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(
                f"Error fetching financial headlines from Finnhub: {e}")
            return pd.DataFrame()

    def fetch_market_headlines(self, count: int = 10) -> pd.DataFrame:
        """
        Alias for fetch_financial_headlines that focuses specifically on market-related headlines.
        This method has the same functionality but uses a more descriptive name for clarity.

        Args:
            count: Number of news headlines to retrieve

        Returns:
            DataFrame with market headlines for sentiment analysis
        """
        return self.fetch_financial_headlines(count=count)

    def fetch_earnings_calendar(self, start_date: str = "today", end_date: str = "+30d") -> pd.DataFrame:
        """
        Fetch earnings calendar from Finnhub free tier API.

        Args:
            start_date: Start date (YYYY-MM-DD or relative like "today")
            end_date: End date (YYYY-MM-DD or relative like "+30d")

        Returns:
            DataFrame with earnings calendar data
        """
        try:
            # Process date parameters using date_utils
            processed_start = process_date_param(
                start_date) or process_date_param("today")
            processed_end = process_date_param(
                end_date) or process_date_param("+30d")

            url = f"{self.base_url}/calendar/earnings?from={processed_start}&to={processed_end}&token={self.api_key}"

            self.logger.info(
                f"Fetching earnings calendar from {processed_start} to {processed_end}")
            response = requests.get(url)
            response.raise_for_status()

            data = response.json()

            if not data or 'earningsCalendar' not in data:
                self.logger.warning(
                    "No earnings calendar data returned from Finnhub")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data['earningsCalendar'])

            if not df.empty:
                # Standardize column names
                df = df.rename(columns={
                    'symbol': 'Symbol',
                    'date': 'Earnings_Date',
                    'epsActual': 'EPS_Actual',
                    'epsEstimate': 'EPS_Estimate',
                    'revenueActual': 'Revenue_Actual',
                    'revenueEstimate': 'Revenue_Estimate',
                    'quarter': 'Quarter',
                    'year': 'Year'
                })

                # Convert date to datetime
                if 'Earnings_Date' in df.columns:
                    df['Earnings_Date'] = pd.to_datetime(df['Earnings_Date'])

                df['Data Source'] = 'Finnhub'

            return df

        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                self.logger.warning(
                    f"Earnings calendar requires premium Finnhub subscription (403 Forbidden)")
                return pd.DataFrame(columns=['Symbol', 'Earnings_Date', 'EPS_Actual', 'EPS_Estimate', 'Data Source'])
            else:
                self.logger.error(
                    f"Error fetching earnings calendar from Finnhub: {e}")
                return pd.DataFrame()

    def fetch_insider_transactions(self, symbol: str, start_date: str = "-90d", end_date: str = "today") -> pd.DataFrame:
        """
        Fetch insider transaction data from Finnhub free tier API.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date (YYYY-MM-DD or relative like "-90d")
            end_date: End date (YYYY-MM-DD or relative like "today")

        Returns:
            DataFrame with insider transaction data
        """
        try:
            # Process date parameters using date_utils
            processed_start = process_date_param(
                start_date) or process_date_param("-90d")
            processed_end = process_date_param(
                end_date) or process_date_param("today")

            url = f"{self.base_url}/stock/insider-transactions?symbol={symbol}&from={processed_start}&to={processed_end}&token={self.api_key}"

            self.logger.info(
                f"Fetching insider transactions for {symbol} from {processed_start} to {processed_end}")
            response = requests.get(url)
            response.raise_for_status()

            data = response.json()

            if not data or 'data' not in data:
                self.logger.warning(
                    f"No insider transaction data returned for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data['data'])

            if not df.empty:
                # Standardize column names
                df = df.rename(columns={
                    'symbol': 'Symbol',
                    'transactionDate': 'Transaction_Date',
                    'name': 'Insider_Name',
                    'share': 'Shares',
                    'change': 'Share_Change',
                    'filingDate': 'Filing_Date',
                    'transactionCode': 'Transaction_Code'
                })

                # Convert dates to datetime
                if 'Transaction_Date' in df.columns:
                    df['Transaction_Date'] = pd.to_datetime(
                        df['Transaction_Date'])
                if 'Filing_Date' in df.columns:
                    df['Filing_Date'] = pd.to_datetime(df['Filing_Date'])

                df['Data Source'] = 'Finnhub'

            return df

        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                self.logger.warning(
                    f"Insider transactions for {symbol} require premium Finnhub subscription (403 Forbidden)")
                return pd.DataFrame(columns=['Symbol', 'Transaction_Date', 'Insider_Name', 'Shares', 'Data Source'])
            else:
                self.logger.error(
                    f"Error fetching insider transactions for {symbol}: {e}")
                return pd.DataFrame()

    def fetch_dividends(self, symbol: str, start_date: str = "-1y", end_date: str = "today") -> pd.DataFrame:
        """
        Fetch dividend data from Finnhub free tier API.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date (YYYY-MM-DD or relative like "-1y")
            end_date: End date (YYYY-MM-DD or relative like "today")

        Returns:
            DataFrame with dividend data
        """
        try:
            # Process date parameters using date_utils
            processed_start = process_date_param(
                start_date) or process_date_param("-1y")
            processed_end = process_date_param(
                end_date) or process_date_param("today")

            url = f"{self.base_url}/stock/dividend?symbol={symbol}&from={processed_start}&to={processed_end}&token={self.api_key}"

            self.logger.info(
                f"Fetching dividend data for {symbol} from {processed_start} to {processed_end}")
            response = requests.get(url)
            response.raise_for_status()

            data = response.json()

            if not data:
                self.logger.warning(f"No dividend data returned for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)

            if not df.empty:
                # Standardize column names
                df = df.rename(columns={
                    'symbol': 'Symbol',
                    'date': 'Ex_Dividend_Date',
                    'amount': 'Dividend_Amount',
                    'adjustedAmount': 'Adjusted_Amount',
                    'payDate': 'Pay_Date',
                    'recordDate': 'Record_Date',
                    'declarationDate': 'Declaration_Date'
                })

                # Convert dates to datetime
                date_columns = ['Ex_Dividend_Date', 'Pay_Date',
                                'Record_Date', 'Declaration_Date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])

                df['Data Source'] = 'Finnhub'

            return df

        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                self.logger.warning(
                    f"Dividend data for {symbol} requires premium Finnhub subscription (403 Forbidden)")
                # Return empty DataFrame with proper structure for consistency
                return pd.DataFrame(columns=['Symbol', 'Ex_Dividend_Date', 'Dividend_Amount', 'Data Source'])
            else:
                self.logger.error(
                    f"Error fetching dividend data for {symbol}: {e}")
                return pd.DataFrame()

    def fetch_earnings_estimates(self, symbol: str) -> pd.DataFrame:
        """
        Fetch earnings estimates from Finnhub free tier API.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            DataFrame with EPS estimates and historical earnings
        """
        try:
            url = f"{self.base_url}/stock/earnings?symbol={symbol}&token={self.api_key}"

            self.logger.info(f"Fetching earnings estimates for {symbol}")
            response = requests.get(url)
            response.raise_for_status()

            data = response.json()

            if not data:
                self.logger.warning(
                    f"No earnings estimates returned for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)

            if not df.empty:
                # Standardize column names
                df = df.rename(columns={
                    'symbol': 'Symbol',
                    'period': 'Period',
                    'actual': 'EPS_Actual',
                    'estimate': 'EPS_Estimate',
                    'surprise': 'Surprise',
                    'surprisePercent': 'Surprise_Percent'
                })

                # Convert period to datetime if possible
                if 'Period' in df.columns:
                    df['Period'] = pd.to_datetime(df['Period'])

                df['Data Source'] = 'Finnhub'

            return df

        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                self.logger.warning(
                    f"Earnings estimates for {symbol} require premium Finnhub subscription (403 Forbidden)")
                return pd.DataFrame(columns=['Symbol', 'Period', 'EPS_Actual', 'EPS_Estimate', 'Data Source'])
            else:
                self.logger.error(
                    f"Error fetching earnings estimates for {symbol}: {e}")
                return pd.DataFrame()

    def fetch_economic_headlines(self, count: int = 10) -> pd.DataFrame:
        """
        Fetch headlines specifically from the 'economic' category.
        This provides a more targeted set of headlines related to economic news.

        Args:
            count: Number of economic news headlines to retrieve

        Returns:
            DataFrame with economic headlines for sentiment analysis
        """
        return self.fetch_news(category="economic", count=count)

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

        # Example 2: Try fetching news with ticker filter (may not work in free tier)
        print("\nExample 2: Fetch news with ticker filter")
        stock_news = finnhub_tool.fetch_news(
            category="business", tickers=["AAPL", "TSLA"], count=3)
        if not stock_news.empty:
            print(
                f"Fetched {len(stock_news)} news articles related to specified tickers")
            for _, article in stock_news.iterrows():
                print(f"- {article.get('Headline', 'No headline')}")
        else:
            print("No ticker-specific news found (expected with free tier)")

        # Example 3: Fetch economic headlines
        print("\nExample 3: Fetch economic headlines")
        economic_df = finnhub_tool.fetch_economic_headlines(count=3)
        if not economic_df.empty:
            print(f"Fetched {len(economic_df)} economic headlines")
            for _, article in economic_df.iterrows():
                print(f"- {article.get('Headline', 'No headline')}")

        # Example 4: Fetch combined financial headlines
        print("\nExample 4: Fetch combined financial headlines")
        financial_df = finnhub_tool.fetch_financial_headlines(count=8)
        if not financial_df.empty:
            print(
                f"Fetched {len(financial_df)} financial headlines from multiple categories")
            print(
                f"Categories included: {', '.join(financial_df['Category'].unique())}")
            for _, article in financial_df.head(3).iterrows():
                print(
                    f"- {article.get('Headline', 'No headline')} ({article.get('Category', 'unknown')})")

        # Example 5: List available news categories
        print("\nExample 5: List available news categories")
        categories_df = finnhub_tool.list_news_categories()
        print(f"Available categories:")
        for _, category in categories_df.iterrows():
            print(f"- {category['category_id']}: {category['description']}")

    except Exception as e:
        print(f"Error in example: {e}")
