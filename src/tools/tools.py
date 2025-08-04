from autogen_core.tools import FunctionTool
from src.tools.data_sources.news.sources.api_based.news_headline_tool import NewsHeadlineTool
from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.tools.data_sources.market.alpha_vantage_market import AlphaVantageMarketTool
from src.tools.data_sources.news.sources.api_based.alpha_vantage_news import AlphaVantageNewsTool
try:
    from src.tools.data_sources.government.FRED_data_tool import FREDDataTool
except ImportError:
    FREDDataTool = None
try:
    from src.tools.data_sources.government.sec_edgar_tool import SECEdgarTool
except ImportError:
    SECEdgarTool = None
from src.tools.data_sources.news.sources.api_based.finnhub_tool import FinnHubTool
from src.tools.data_sources.news.aggregators.legacy.unified_news_tool import fetch_unified_news
from src.tools.data_sources.news.sources.scrapers.yahoo_scraper_tool import yahoo_finance_scraper_tool
from src.tools.data_sources.news.aggregators.hybrid_historical_news_tool import hybrid_historical_news_tool
import pandas as pd
from src.tools.processors.data_normalizer import normalize_data_for_sentiment
import os
from config.config_loader import ConfigLoader

# Lazy imports for optional dependencies
YahooFinanceTool = None
FMPTool = None

try:
    from src.tools.data_sources.market.yahoo_finance_tool import YahooFinanceTool
except ImportError:
    pass

try:
    from src.tools.data_sources.market.fmp_tool import FMPTool
except ImportError:
    pass

config_loader = ConfigLoader()
# Import other vendor tools as needed

##################################
# Tool Organization by Agent Type
##################################

# Every tool is tagged with the agent types that should use it
# This allows for better separation of concerns between agents

# Agent Types
SENTIMENT_AGENT = "sentiment"
TECH_AGENT = "tech"
RISK_AGENT = "risk"
STRATEGY_AGENT = "strategy"
MARKET_INTELLIGENCE_AGENT = "market_intelligence"
ALL_AGENTS = [SENTIMENT_AGENT, TECH_AGENT, RISK_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]

# CORPORATE ACTIONS TOOL HIERARCHY:
# 1. PRIMARY: Yahoo Finance tools - Free but rate limited, enhanced with caching/throttling
#    - fetch_yahoo_corporate_events (with historical support via days_back parameter)
# 2. UNOBTAINIUM: Premium-locked corporate actions (both require paid subscriptions)
#    - FMP tools: fetch_fmp_earnings_calendar, fetch_fmp_dividend_calendar (EXPERIMENTAL)
#    - Finnhub tools: fetch_finnhub_earnings_calendar, fetch_finnhub_insider_transactions
# 3. NOTE: Corporate actions data is largely premium-only across major financial APIs
#    - Consider web scraping alternatives for comprehensive free corporate actions data

##################################
# 1) News Headline Tool as a Function
##################################


def fetch_news(keyword: str = "market", count: int = 5) -> pd.DataFrame:
    """
    Fetch news articles (as a DataFrame) from NewsHeadlineTool.

    Args:
        keyword: Topic or keyword to search for
        count: Number of news articles to retrieve

    Returns:
        DataFrame with news headlines, published dates, and sources
    """
    tool = NewsHeadlineTool(source="newsapi")
    df = tool.fetch_data(keyword=keyword, count=count)
    return df  # Return raw DataFrame


news_tool = FunctionTool(
    func=fetch_news,
    name="fetch_news",
    description="Fetch news articles for a given keyword, returning a Pandas DataFrame with headlines, published dates, and sources with headlines, published dates, and sources."
)
# Market intelligence needs news for context
news_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]

##################################
# 2) Alpha Vantage News Tool
##################################


def fetch_alpha_vantage_news(
    symbol: str = "AAPL",
    topics: str = None
) -> pd.DataFrame:
    """
    Fetch news and sentiment data from Alpha Vantage API.

    Args:
        symbol: Stock symbol to fetch news about
        topics: Optional topics to filter by

    Returns:
        DataFrame with news and pre-calculated sentiment scores
    """
    tool = AlphaVantageNewsTool()
    df = tool.fetch_news_sentiment(symbol, topics)
    # Normalize for sentiment analysis
    normalized_df = normalize_data_for_sentiment(
        df, "alpha_vantage", symbol=symbol)
    return normalized_df if normalized_df is not None else df


alpha_vantage_news_tool = FunctionTool(
    func=fetch_alpha_vantage_news,
    name="fetch_alpha_vantage_news",
    description="Fetch news and sentiment data from Alpha Vantage for a given ticker, with pre-calculated sentiment scores."
)
# Only sentiment agent should use this
alpha_vantage_news_tool.agent_types = [SENTIMENT_AGENT]

##################################
# 3) Unified News Tool
##################################


def fetch_all_news(
    keywords: str = None,
    ticker: str = None,
    start_date: str = "-7d",
    end_date: str = "today",
    category: str = None,
    sources: str = None,
    count: int = 10
) -> dict:
    """
    Unified news fetching from multiple sources (AlphaVantage, Finnhub, NewsAPI) with
    standardized output format, sentiment analysis, and deduplication.

    Args:
        keywords: Keywords to search for (comma-separated)
        ticker: Stock ticker to get news about
        start_date: Start date for news (YYYY-MM-DD or relative date like "-7d")
        end_date: End date for news (YYYY-MM-DD or "today")
        category: Type of news to fetch ("financial", "economic", "general")
        sources: Comma-separated list of sources to use (default: all available sources)
        count: Maximum number of news articles to return

    Returns:
        Dictionary with news articles and metadata including sentiment analysis
    """
    result = fetch_unified_news(
        keywords=keywords,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        category=category,
        sources=sources,
        count=count,
        include_sentiment=True
    )
    articles = result.get("articles", []) if isinstance(result, dict) else []
    if not articles:
        return {
            "status": "EMPTY",
            "reason": "No headlines matched that date/keyword",
            "ticker": ticker,
            "keywords": keywords,
            "articles": [],
        }
    return result


unified_news_tool = FunctionTool(
    func=fetch_all_news,
    name="fetch_all_news",
    description="Fetch news from multiple sources (AlphaVantage, Finnhub, NewsAPI) with unified output, sentiment analysis, relevance scoring, and deduplication. Articles are sorted by relevance to your query, with higher scores for more relevant content. The tool also provides search guidance if results are inadequate."
)
# Market intelligence uses news for comprehensive analysis
unified_news_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]

##################################
# 4) FMP Corporate Actions Tools (EXPERIMENTAL - PREMIUM LOCKED)
##################################


def fetch_fmp_earnings_calendar(
    start_date: str = "today",
    end_date: str = "+30d"
) -> pd.DataFrame:
    """
    Fetch earnings calendar from FMP API.

    Args:
        start_date: Start date (YYYY-MM-DD or relative like "today")
        end_date: End date (YYYY-MM-DD or relative like "+30d")

    Returns:
        DataFrame with earnings calendar data
    """
    tool = FMPTool()
    df = tool.fetch_earnings_calendar(start_date, end_date)
    return df


fmp_earnings_calendar_tool = FunctionTool(
    func=fetch_fmp_earnings_calendar,
    name="fetch_fmp_earnings_calendar",
    description="EXPERIMENTAL: Fetch earnings calendar from FMP. REQUIRES PREMIUM SUBSCRIPTION. Alternative to Finnhub for corporate actions. Will return 403 errors with free tier."
)
fmp_earnings_calendar_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]


def fetch_fmp_dividend_calendar(
    start_date: str = "today",
    end_date: str = "+30d"
) -> pd.DataFrame:
    """
    Fetch dividend calendar from FMP API.

    Args:
        start_date: Start date (YYYY-MM-DD or relative like "today")
        end_date: End date (YYYY-MM-DD or relative like "+30d")

    Returns:
        DataFrame with dividend calendar data
    """
    tool = FMPTool()
    df = tool.fetch_dividend_calendar(start_date, end_date)
    return df


fmp_dividend_calendar_tool = FunctionTool(
    func=fetch_fmp_dividend_calendar,
    name="fetch_fmp_dividend_calendar",
    description="EXPERIMENTAL: Fetch dividend calendar from FMP. REQUIRES PREMIUM SUBSCRIPTION. Alternative to Finnhub for dividend data. Will return 403 errors with free tier."
)
fmp_dividend_calendar_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]


def fetch_fmp_historical_earnings(
    symbol: str,
    limit: int = 80
) -> pd.DataFrame:
    """
    Fetch historical earnings data for a specific symbol from FMP API.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        limit: Maximum number of earnings records to retrieve

    Returns:
        DataFrame with historical earnings data
    """
    tool = FMPTool()
    df = tool.fetch_historical_earnings(symbol, limit)
    return df


fmp_historical_earnings_tool = FunctionTool(
    func=fetch_fmp_historical_earnings,
    name="fetch_fmp_historical_earnings",
    description="EXPERIMENTAL: Fetch historical earnings data from FMP. REQUIRES PREMIUM SUBSCRIPTION. Alternative for historical earnings analysis. Requires symbol parameter."
)
fmp_historical_earnings_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]


def fetch_fmp_historical_dividends(
    symbol: str,
    start_date: str = "-1y",
    end_date: str = "today"
) -> pd.DataFrame:
    """
    Fetch historical dividend data for a specific symbol from FMP API.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        start_date: Start date (YYYY-MM-DD or relative like "-1y")
        end_date: End date (YYYY-MM-DD or relative like "today")

    Returns:
        DataFrame with historical dividend data
    """
    tool = FMPTool()
    df = tool.fetch_historical_dividends(symbol, start_date, end_date)
    return df


fmp_historical_dividends_tool = FunctionTool(
    func=fetch_fmp_historical_dividends,
    name="fetch_fmp_historical_dividends",
    description="EXPERIMENTAL: Fetch historical dividend data from FMP. REQUIRES PREMIUM SUBSCRIPTION. Alternative for dividend analysis. Requires symbol parameter."
)
fmp_historical_dividends_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]


def fetch_fmp_stock_split_calendar(
    start_date: str = "today",
    end_date: str = "+30d"
) -> pd.DataFrame:
    """
    Fetch stock split calendar from FMP API.

    Args:
        start_date: Start date (YYYY-MM-DD or relative like "today")
        end_date: End date (YYYY-MM-DD or relative like "+30d")

    Returns:
        DataFrame with stock split calendar data
    """
    tool = FMPTool()
    df = tool.fetch_stock_split_calendar(start_date, end_date)
    return df


fmp_stock_split_calendar_tool = FunctionTool(
    func=fetch_fmp_stock_split_calendar,
    name="fetch_fmp_stock_split_calendar",
    description="EXPERIMENTAL: Fetch stock split calendar from FMP. REQUIRES PREMIUM SUBSCRIPTION. Alternative for stock split data."
)
fmp_stock_split_calendar_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]


##################################
# 5) Finnhub News and Sentiment Tool (SECONDARY - Premium locked)
##################################


def fetch_finnhub_news(
    category: str = "general",
    tickers: list = None,
    count: int = 10
) -> pd.DataFrame:
    """
    Fetch financial news articles from Finnhub using the free tier API.

    Args:
        category: News category ('general', 'forex', 'crypto', 'merger', 'business', 'economic', etc.)
        tickers: List of ticker symbols to filter by (optional, may not work in free tier)
        count: Number of news articles to retrieve

    Returns:
        DataFrame with financial news headlines, dates, and sources
    """
    # Load API key from environment
    api_key = os.getenv("FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

    tool = FinnHubTool(api_key)
    df = tool.fetch_news(category=category, tickers=tickers, count=count)
    return df


finnhub_news_tool = FunctionTool(
    func=fetch_finnhub_news,
    name="fetch_finnhub_news",
    description="Fetch financial news articles from Finnhub by category or ticker, returning a DataFrame with headlines and sources."
)
# Primarily for sentiment agent
finnhub_news_tool.agent_types = [SENTIMENT_AGENT]


def fetch_finnhub_financial_headlines(
    count: int = 10
) -> pd.DataFrame:
    """
    Fetch a combined set of financial and economic headlines from multiple categories
    on Finnhub. Combines business, economic, forex, and general news for comprehensive
    market coverage.

    Args:
        count: Number of news headlines to retrieve per category

    Returns:
        DataFrame with diverse financial headlines for sentiment analysis
    """
    # Load API key from environment
    api_key = os.getenv("FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

    tool = FinnHubTool(api_key)
    df = tool.fetch_financial_headlines(count=count)
    return df


finnhub_financial_headlines_tool = FunctionTool(
    func=fetch_finnhub_financial_headlines,
    name="fetch_finnhub_financial_headlines",
    description="Fetch diverse financial headlines from multiple categories on Finnhub, combining business, economic, and market news."
)
finnhub_financial_headlines_tool.agent_types = [
    SENTIMENT_AGENT]  # Primarily for sentiment agent


def fetch_finnhub_economic_headlines(
    count: int = 10
) -> pd.DataFrame:
    """
    Fetch headlines specifically from the 'economic' category on Finnhub.
    This provides economic news focused content for sentiment analysis.

    Args:
        count: Number of economic news headlines to retrieve

    Returns:
        DataFrame with economic headlines from Finnhub
        DataFrame with economic headlines from Finnhub
    """
    # Load API key from environment
    api_key = os.getenv("FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

    tool = FinnHubTool(api_key)
    df = tool.fetch_economic_headlines(count=count)
    # Load API key from environment
    api_key = os.getenv("FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

    tool = FinnHubTool(api_key)
    df = tool.fetch_economic_headlines(count=count)
    return df


finnhub_economic_headlines_tool = FunctionTool(
    func=fetch_finnhub_economic_headlines,
    name="fetch_finnhub_economic_headlines",
    description="Fetch economic news headlines from Finnhub for analyzing economic sentiment and trends."
)
finnhub_economic_headlines_tool.agent_types = [
    SENTIMENT_AGENT, STRATEGY_AGENT]  # Useful for sentiment and strategy agents


def fetch_finnhub_earnings_calendar(
    start_date: str = "today",
    end_date: str = "+30d"
) -> pd.DataFrame:
    """
    Fetch earnings calendar from Finnhub free tier API.

    Args:
        start_date: Start date (YYYY-MM-DD or relative like "today")
        end_date: End date (YYYY-MM-DD or relative like "+30d")

    Returns:
        DataFrame with earnings calendar data including EPS estimates and actuals
    """
    # Load API key from environment
    api_key = os.getenv("FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

    tool = FinnHubTool(api_key)
    df = tool.fetch_earnings_calendar(start_date, end_date)
    return df


finnhub_earnings_calendar_tool = FunctionTool(
    func=fetch_finnhub_earnings_calendar,
    name="fetch_finnhub_earnings_calendar",
    description="SECONDARY: Fetch earnings calendar from Finnhub with EPS estimates and actuals. Requires premium subscription. Use only if FMP tools fail or are unavailable."
)
finnhub_earnings_calendar_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]


def fetch_finnhub_insider_transactions(
    symbol: str,
    start_date: str = "-90d",
    end_date: str = "today"
) -> pd.DataFrame:
    """
    Fetch insider transaction data from Finnhub free tier API.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        start_date: Start date (YYYY-MM-DD or relative like "-90d")
        end_date: End date (YYYY-MM-DD or relative like "today")

    Returns:
        DataFrame with insider transaction data
    """
    # Load API key from environment
    api_key = os.getenv("FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

    tool = FinnHubTool(api_key)
    df = tool.fetch_insider_transactions(symbol, start_date, end_date)
    return df


finnhub_insider_transactions_tool = FunctionTool(
    func=fetch_finnhub_insider_transactions,
    name="fetch_finnhub_insider_transactions",
    description="SECONDARY: Fetch insider transaction data from Finnhub. Requires premium subscription. Use only if other tools are unavailable."
)
finnhub_insider_transactions_tool.agent_types = [
    SENTIMENT_AGENT, STRATEGY_AGENT]


def fetch_finnhub_dividends(
    symbol: str,
    start_date: str = "-1y",
    end_date: str = "today"
) -> pd.DataFrame:
    """
    Fetch dividend data from Finnhub free tier API.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        start_date: Start date (YYYY-MM-DD or relative like "-1y")
        end_date: End date (YYYY-MM-DD or relative like "today")

    Returns:
        DataFrame with dividend data including ex-dividend dates and amounts
    """
    # Load API key from environment
    api_key = os.getenv("FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

    tool = FinnHubTool(api_key)
    df = tool.fetch_dividends(symbol, start_date, end_date)
    return df


finnhub_dividends_tool = FunctionTool(
    func=fetch_finnhub_dividends,
    name="fetch_finnhub_dividends",
    description="SECONDARY: Fetch dividend data from Finnhub. Requires premium subscription. Use only if FMP tools fail. Requires symbol parameter."
)
finnhub_dividends_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]


def fetch_finnhub_earnings_estimates(
    symbol: str
) -> pd.DataFrame:
    """
    Fetch earnings estimates from Finnhub free tier API.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')

    Returns:
        DataFrame with EPS estimates and historical earnings surprises
    """
    # Load API key from environment
    api_key = os.getenv("FINNHUB_KEY", config_loader.get("FINNHUB_KEY"))

    tool = FinnHubTool(api_key)
    df = tool.fetch_earnings_estimates(symbol)
    return df


finnhub_earnings_estimates_tool = FunctionTool(
    func=fetch_finnhub_earnings_estimates,
    name="fetch_finnhub_earnings_estimates",
    description="SECONDARY: Fetch earnings estimates from Finnhub. Requires premium subscription. Use only if FMP tools fail."
)
finnhub_earnings_estimates_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]

##################################
# 5) Market Data Tools
##################################


def fetch_yahoo_data(
    ticker: str = "AAPL",
    start_date: str = "2023-01-01",
    end_date: str = "2023-02-01"
) -> pd.DataFrame:
    """
    Fetch stock price data from Yahoo Finance.

    Args:
        ticker: Stock symbol/ticker to fetch data for
        start_date: Start of date range (YYYY-MM-DD or relative like "-7d")
        end_date: End of date range (YYYY-MM-DD or relative like "-1d")

    Returns:
        DataFrame with Open, High, Low, Close and Volume data
    """
    if YahooFinanceTool is None:
        return pd.DataFrame()  # Return empty if not available
    tool = YahooFinanceTool()
    df = tool.fetch_stock_data(ticker, start_date, end_date)
    return df


# Only create tool if Yahoo is available
if YahooFinanceTool is not None:
    yahoo_finance_tool = FunctionTool(
        func=fetch_yahoo_data,
        name="fetch_yahoo_data",
        description="Fetch stock price data from Yahoo Finance for a given ticker and date range."
    )
    # Market intelligence needs price data for market analysis
    yahoo_finance_tool.agent_types = [TECH_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]
else:
    yahoo_finance_tool = None


def fetch_yahoo_corporate_events(
    ticker: str,
    days_ahead: int = 30,
    days_back: int = 0
) -> pd.DataFrame:
    """
    Fetch corporate events (earnings dates, dividend dates) from Yahoo Finance.
    Can fetch both upcoming events and recent historical events.

    Args:
        ticker: Stock symbol to fetch events for
        days_ahead: Number of days ahead to look for upcoming events (default: 30)
        days_back: Number of days back to look for historical events (default: 0)
                  Set to 30 for last month, 7 for last week, etc.

    Returns:
        DataFrame containing events within the specified timeframe
    """
    if YahooFinanceTool is None:
        return pd.DataFrame()  # Return empty if not available
    tool = YahooFinanceTool()
    events_df = tool.fetch_corporate_events(ticker, days_ahead, days_back)
    return events_df


# Only create tool if Yahoo is available
if YahooFinanceTool is not None:
    yahoo_corporate_events_tool = FunctionTool(
        func=fetch_yahoo_corporate_events,
        name="fetch_yahoo_corporate_events",
        description="BACKUP: Fetch corporate events from Yahoo Finance as DataFrame. Can get both upcoming events (days_ahead) and historical events (days_back). For 'last month' queries, use days_back=30. For upcoming events, use days_ahead=30. Use when Finnhub tools return empty results. Note: Subject to rate limiting."
    )
    # Useful for sentiment and strategy agents for event-driven analysis
    yahoo_corporate_events_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]
else:
    yahoo_corporate_events_tool = None


def fetch_alpha_vantage_data(
    symbol: str = "AAPL",
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31"
) -> pd.DataFrame:
    """
    Fetch stock price data from Alpha Vantage API.

    Args:
        symbol: Stock symbol/ticker to fetch data for
        start_date: Start of date range (YYYY-MM-DD or relative like "-7d")
        end_date: End of date range (YYYY-MM-DD or relative like "-1d")

    Returns:
        DataFrame with open, high, low, close, volume data
    """
    tool = AlphaVantageMarketTool()
    df = tool.fetch_stock_data(symbol, start_date, end_date)
    return df


alpha_vantage_tool = FunctionTool(
    func=fetch_alpha_vantage_data,
    name="fetch_alpha_vantage_data",
    description="Fetch stock price data from Alpha Vantage for a given ticker and date range."
)
# Market intelligence may use this as fallback
alpha_vantage_tool.agent_types = [TECH_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]


def fetch_market_data(
    symbol: str = "AAPL",
    start_date: str = "-30d",  # Changed to relative date for current data
    end_date: str = "today",   # Changed to always get current data
    source: str = "alpha_vantage"
) -> pd.DataFrame:
    """
    Fetch market data from the specified source (alpha_vantage, yahoo, csv).

    Args:
        symbol: Stock symbol/ticker to fetch data for
        start_date: Start of date range (YYYY-MM-DD or relative like "-30d")
        end_date: End of date range (YYYY-MM-DD or "today")
        source: Data source to use ("alpha_vantage", "yahoo", "csv")

    Returns:
        DataFrame with price and volume data
    """
    tool = MarketDataTool({"data_source": source})
    df = tool.fetch_market_data(symbol, start_date, end_date)
    return df


market_data_tool = FunctionTool(
    func=fetch_market_data,
    name="fetch_market_data",
    description="Fetch market data from specified source for a given ticker and date range."
)
# Market intelligence needs market data for analysis
market_data_tool.agent_types = [TECH_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]

##################################
# 6) FRED Economic Data Tool
##################################


def fetch_economic_indicator(
    indicator: str = "gdp",
    start_date: str = "-5y",  # Changed to relative date format
    end_date: str = "today"   # Changed to relative date format
) -> pd.DataFrame:
    """
    Fetch economic data from FRED (Federal Reserve Economic Data).

    Args:
        indicator: Name of economic indicator (e.g., 'gdp', 'unemployment', 'inflation')
        start_date: Start date in YYYY-MM-DD format or relative date like "-5y" (default: 5 years ago)
        end_date: End date in YYYY-MM-DD format or relative date like "today" (default: today)

    Returns:
        DataFrame with dates and indicator values
    """

    if FREDDataTool is None:
        print("WARNING: FREDDataTool not available (missing fredapi). Returning empty DataFrame.")
        return pd.DataFrame()

    tool = FREDDataTool()
    raw_df = tool.get_indicator(indicator, start_date, end_date)

    # Optionally normalize the data (commented out for now as it may not be needed)
    # normalized_df = normalize_fred_data(raw_df, indicator)
    # return normalized_df

    return raw_df


if FREDDataTool is not None:
    fred_indicator_tool = FunctionTool(
        func=fetch_economic_indicator,
        name="fetch_economic_indicator",
        description="Fetch economic indicator data from FRED (Federal Reserve)."
    )
    # Market intelligence needs economic indicators
    fred_indicator_tool.agent_types = [TECH_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]
else:
    fred_indicator_tool = None


def fetch_interest_rates(
    rate_type: str = "fed_funds",
    start_date: str = "-5y",  # Changed to relative date format
    end_date: str = "today"   # Changed to relative date format
) -> pd.DataFrame:
    """
    Fetch interest rate data from FRED.

    Args:
        rate_type: Type of interest rate ('fed_funds', 'treasury_10y', 'treasury_2y', 'treasury_3m')
        start_date: Start date in YYYY-MM-DD format or relative date like "-5y" (default: 5 years ago)
        end_date: End date in YYYY-MM-DD format or relative date like "today" (default: today)

    Returns:
        DataFrame with dates and interest rate values
    """
    tool = FREDDataTool()
    df = tool.get_interest_rates(start_date, end_date, rate_type)
    return df


fred_rates_tool = FunctionTool(
    func=fetch_interest_rates,
    name="fetch_interest_rates",
    description="Fetch interest rate data from FRED (Federal Reserve)."
)
# Market intelligence needs interest rate data
fred_rates_tool.agent_types = [TECH_AGENT, STRATEGY_AGENT, RISK_AGENT, MARKET_INTELLIGENCE_AGENT]


def fetch_yield_curve(date: str = "today") -> pd.DataFrame:
    """
    Fetch the yield curve for a specific date.

    Args:
        date: Date in YYYY-MM-DD format or relative date like "today" (default: today)

    Returns:
        DataFrame with yield curve data for various maturities
    """
    if FREDDataTool is None:
        print("WARNING: FREDDataTool not available (missing fredapi). Returning empty DataFrame.")
        return pd.DataFrame()

    tool = FREDDataTool()
    df = tool.get_yield_curve(date)
    return df


if FREDDataTool is not None:
    fred_yield_curve_tool = FunctionTool(
        func=fetch_yield_curve,
        name="fetch_yield_curve",
        description="Fetch the Treasury yield curve for a specific date."
    )
    fred_yield_curve_tool.agent_types = [
        TECH_AGENT, STRATEGY_AGENT, RISK_AGENT]  # Relevant for multiple agents
else:
    fred_yield_curve_tool = None

##################################
# 7) SEC EDGAR Filings Tool (EXPERIMENTAL)
##################################
# NOTE: SEC Edgar tools are now considered EXPERIMENTAL features.
# Use Yahoo Finance and Finnhub corporate action tools as primary sources
# for earnings dates, dividend information, and insider transactions.
# SEC tools remain available for detailed regulatory filings analysis when needed.


def fetch_sec_filings(
    ticker: str,
    form_type: str = "10-K",
    num_filings: int = 1,
    extract_sections: list = None
) -> pd.DataFrame:
    """
    Fetch SEC filings for a company.

    Args:
        ticker: Company ticker symbol (e.g., 'AAPL')
        form_type: Type of SEC form ('10-K', '10-Q', '8-K', etc.)
        num_filings: Number of filings to retrieve
        extract_sections: List of sections to extract (e.g., ['risk_factors', 'business'])

    Returns:
        DataFrame with filing data and extracted sections
    """
    if extract_sections is None:
        extract_sections = ["risk_factors"]

    if SECEdgarTool is None:
        print("WARNING: SECEdgarTool not available (missing beautifulsoup4). Returning empty DataFrame.")
        return pd.DataFrame()

    tool = SECEdgarTool(use_temp_dir=True)
    df = tool.fetch_filings(ticker, form_type, num_filings,
                            extract_sections=extract_sections)
    return df


if SECEdgarTool is not None:
    sec_filings_tool = FunctionTool(
        func=fetch_sec_filings,
        name="fetch_sec_filings",
        description="Fetch SEC filings for a company and extract relevant sections."
    )
    # Primarily for risk assessment
    sec_filings_tool.agent_types = [RISK_AGENT, STRATEGY_AGENT]
else:
    sec_filings_tool = None


def search_sec_filings(
    ticker: str,
    search_terms: list,
    form_type: str = "10-K",
    section: str = None,
    num_filings: int = 3
) -> pd.DataFrame:
    """
    Search SEC filings for specific terms.

    Args:
        ticker: Company ticker symbol (e.g., 'AAPL')
        search_terms: List of terms to search for (must not be empty)
        form_type: Type of SEC form ('10-K', '10-Q', '8-K', etc.)
        section: Specific section to search (e.g., 'risk_factors')
        num_filings: Number of filings to search

    Returns:
        DataFrame with search results and context
    """
    # Guard against empty search terms
    if not search_terms or len(search_terms) == 0:
        print(f"WARNING: search_sec_filings called with empty search_terms. Returning empty DataFrame.")
        return pd.DataFrame(columns=["ticker", "form_type", "filing_date", "search_term", "section", "context",
                                     "message"])

    if SECEdgarTool is None:
        print("WARNING: SECEdgarTool not available (missing beautifulsoup4). Returning empty DataFrame.")
        return pd.DataFrame(columns=["ticker", "form_type", "filing_date", "search_term", "section", "context",
                                     "message"])

    tool = SECEdgarTool(use_temp_dir=True)
    df = tool.search_filings(ticker, search_terms,
                             form_type, section, num_filings)
    return df


if SECEdgarTool is not None:
    sec_search_tool = FunctionTool(
        func=search_sec_filings,
        name="search_sec_filings",
        description="Search SEC filings for specific terms and get context. Note: search_terms must be a non-empty list of keywords to search for in the filings."
    )
    # Useful for risk and sentiment analysis
    sec_search_tool.agent_types = [RISK_AGENT, SENTIMENT_AGENT]
else:
    sec_search_tool = None


def compare_sec_filings(
    ticker: str,
    form_type: str = "10-K",
    section: str = "risk_factors",
    num_filings: int = 3
) -> pd.DataFrame:
    """
    Compare SEC filing sections over time.

    Args:
        ticker: Company ticker symbol (e.g., 'AAPL')
        form_type: Type of SEC form ('10-K', '10-Q')
        section: Section to compare ('risk_factors', 'business', etc.)
        num_filings: Number of filings to compare

    Returns:
        DataFrame with comparison metrics between filings
    """
    if SECEdgarTool is None:
        print("WARNING: SECEdgarTool not available (missing beautifulsoup4). Returning empty DataFrame.")
        return pd.DataFrame()

    tool = SECEdgarTool(use_temp_dir=True)
    df = tool.compare_filings_over_time(
        ticker, form_type, section, num_filings)
    return df


if SECEdgarTool is not None:
    sec_compare_tool = FunctionTool(
        func=compare_sec_filings,
        name="compare_sec_filings",
        description="Compare SEC filing sections over time to track changes."
    )
    # Primarily for risk assessment
    sec_compare_tool.agent_types = [RISK_AGENT]
else:
    sec_compare_tool = None

##################################
# Tool Collections by Agent Type
##################################

# SENTIMENT_AGENT tools
# Build sentiment tools list (filtering out None values)
_sentiment_tools_raw = [
    unified_news_tool,  # The unified news tool as primary news source
    hybrid_historical_news_tool,  # Hybrid historical news tool with FinViz integration
    yahoo_finance_scraper_tool,  # Yahoo Finance web scraper as backup news source
    sec_search_tool,    # SEC search tool for regulatory information
]
# Filter out None values from conditional imports
SENTIMENT_TOOLS = [tool for tool in _sentiment_tools_raw if tool is not None]

# TECH_AGENT tools
_tech_tools_raw = [
    yahoo_finance_tool,
    alpha_vantage_tool,
    market_data_tool,
    fred_indicator_tool,
    fred_rates_tool,
    fred_yield_curve_tool
]
# Filter out None values from conditional imports
TECH_TOOLS = [tool for tool in _tech_tools_raw if tool is not None]

# RISK_AGENT tools
_risk_tools_raw = [
    sec_filings_tool,
    sec_search_tool,
    sec_compare_tool,
    fred_rates_tool,
    fred_yield_curve_tool
]
# Filter out None values from conditional imports
RISK_TOOLS = [tool for tool in _risk_tools_raw if tool is not None]

# STRATEGY_AGENT tools
_strategy_tools_raw = [
    news_tool,
    yahoo_finance_tool,
    alpha_vantage_tool,
    market_data_tool,
    fred_indicator_tool,
    fred_rates_tool,
    fred_yield_curve_tool,
    sec_filings_tool,
]
# Filter out None values from conditional imports
STRATEGY_TOOLS = [tool for tool in _strategy_tools_raw if tool is not None]


# All tools combined (filter out None values from conditional imports)
ALL_TOOLS = list(set(
    tool for tool in (
        SENTIMENT_TOOLS +
        TECH_TOOLS +
        RISK_TOOLS +
        STRATEGY_TOOLS
    ) if tool is not None
))


########################################
# Tool dispatcher dictionary for efficient lookup by name
########################################
ALL_TOOLS_DICT = {tool.name: tool for tool in ALL_TOOLS if tool is not None}


########################################
# Helper function to get tools for a specific agent type
########################################
def get_tools_for_agent(agent_type):
    """
    Get the list of tools that should be used by a specific agent type.

    Args:
        agent_type: Type of agent (e.g., 'sentiment', 'tech')

    Returns:
        List of FunctionTool objects appropriate for the agent type
    """
    if agent_type == SENTIMENT_AGENT:
        return SENTIMENT_TOOLS
    elif agent_type == TECH_AGENT:
        return TECH_TOOLS
    elif agent_type == RISK_AGENT:
        return RISK_TOOLS
    elif agent_type == STRATEGY_AGENT:
        return STRATEGY_TOOLS
    else:
        # Return all tools if agent type is unknown
        return ALL_TOOLS
