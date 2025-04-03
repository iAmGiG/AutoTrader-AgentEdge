from autogen_core.tools import FunctionTool
from src.tools.data_sources.news_headline_tool import NewsHeadlineTool
from src.tools.data_sources.market_data_tool import MarketDataTool
from src.tools.data_sources.yahoo_finance_tool import YahooFinanceTool
from src.tools.data_sources.alpha_vantage_tool import AlphaVantageTool
# from src.tools.data_sources.finnhub_tool import FinnHubTool
import pandas as pd
from src.tools.text_processing.data_normalizer import normalize_data_for_sentiment
# Import other vendor tools as needed

##################################
# 1) News Headline Tool as a Function
##################################


def fetch_news(keyword: str = "market", count: int = 5) -> pd.DataFrame:
    """
    Fetch news articles (as a DataFrame) from NewsHeadlineTool.
    """
    tool = NewsHeadlineTool(source="newsapi")
    df = tool.fetch_data(keyword=keyword, count=count)
    return df  # Return raw DataFrame


news_tool = FunctionTool(
    func=fetch_news,
    name="fetch_news",
    description="Fetch news articles for a given keyword, returning a Pandas DataFrame."
)

####################################
# 2) Market Data Tool as a Function
####################################

# NOTE: not connected to an API just yet, should be alpha vantage, but skip for now!


def fetch_market_data(
    symbol: str = "AAPL",
    start_date: str = "2023-01-01",
    end_date: str = "2023-02-01"
) -> pd.DataFrame:
    """
    Fetch historical market data from MarketDataTool, returning a DataFrame.
    """
    config = {
        "data_source": "csv",  # or 'api', 'sql', etc.
        # add other config fields if needed
    }
    tool = MarketDataTool(config)
    df = tool.fetch_options_data(symbol, start_date, end_date)
    return df


market_data_tool = FunctionTool(
    func=fetch_market_data,
    name="fetch_market_data",
    description="Fetches market data for a given symbol and date range."
)

##################################
# 3) YAHOO FINANCE DATA
##################################


def fetch_yahoo_data(
    ticker: str = "AAPL",
    start_date: str = "2023-01-01",
    end_date: str = "2023-02-01"
) -> pd.DataFrame:
    """
    Fetch stock data from YahooFinanceTool, returning a DataFrame with [Open, High, Low, Close, Volume].
    """
    tool = YahooFinanceTool()
    df = tool.fetch_stock_data(ticker, start_date, end_date)
    return df


yahoo_finance_tool = FunctionTool(
    func=fetch_yahoo_data,
    name="fetch_yahoo_data",
    description="Fetch stock data from Yahoo Finance for a given ticker and date range, returning a DataFrame."
)

########################################
# 4) Alpha Vantage Market Data Tool
########################################


def fetch_alpha_vantage_data(
    symbol: str = "AAPL",
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31"
) -> pd.DataFrame:
    """
    Fetch stock data from Alpha Vantage API, returning a DataFrame with [open, high, low, close, volume].
    """
    tool = AlphaVantageTool()
    df = tool.fetch_stock_data(symbol, start_date, end_date)
    return df


alpha_vantage_tool = FunctionTool(
    func=fetch_alpha_vantage_data,
    name="fetch_alpha_vantage_data",
    description="Fetch stock data from Alpha Vantage for a given ticker and date range, returning a DataFrame."
)


def fetch_alpha_vantage_news(
    symbol: str = "AAPL",
    topics: str = None
) -> pd.DataFrame:
    """
    Fetch news and sentiment data from Alpha Vantage API.
    """
    tool = AlphaVantageTool()
    df = tool.fetch_news_sentiment(symbol, topics)
    # Normalize for sentiment analysis
    normalized_df = normalize_data_for_sentiment(
        df, "alpha_vantage", symbol=symbol)
    return normalized_df if normalized_df is not None else df


alpha_vantage_news_tool = FunctionTool(
    func=fetch_alpha_vantage_news,
    name="fetch_alpha_vantage_news",
    description="Fetch news and sentiment data from Alpha Vantage for a given ticker."
)


########################################
# 5) Unified Market Data Tool
########################################

def fetch_market_data(
    symbol: str = "AAPL",
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    source: str = "alpha_vantage"
) -> pd.DataFrame:
    """
    Fetch market data from the specified source (alpha_vantage, yahoo, csv).
    """
    tool = MarketDataTool({"data_source": source})
    df = tool.fetch_market_data(symbol, start_date, end_date)
    return df


market_data_tool = FunctionTool(
    func=fetch_market_data,
    name="fetch_market_data",
    description="Fetch market data from specified source for a given ticker and date range."
)


# Need to fix up the finnhub api request and data frame return


# def fetch_finnhub_data(keyword: str = "Technology", count=5):
#     tool = FinnHubTool()
#     df = tool.fetch_finn_news(keyword=keyword, count=5)
#     return df


# finnhub = FunctionTool(func=fetch_finnhub_data, name="fetch_finnhub_data",
#                        description="Fetches market data from finnhub, and returns it as a DataFrame.")


########################################
# Optionally define a list of all tools
########################################
ALL_TOOLS = [
    news_tool,
    yahoo_finance_tool,
    alpha_vantage_tool,
    alpha_vantage_news_tool,
    market_data_tool
]
