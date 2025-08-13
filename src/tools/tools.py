"""
Clean Tools Configuration for RH2MAS
Active tools: Google Search (news), Polygon.io (primary market data), Alpha Vantage (fallback)
"""

# Standard library imports
import logging
import pandas as pd

# Third-party imports  
from autogen_core.tools import FunctionTool

# Project imports
# MarketDataTool deprecated - using Polygon + Alpha Vantage directly
from src.tools.data_sources.market.alpha_vantage_market import AlphaVantageMarketTool
from src.tools.data_sources.market.vxx_volatility_tool import fetch_vxx_volatility_data
from src.tools.data_sources.news.google_search_simple import google_search_simple_tool
from config.config_loader import ConfigLoader

# Polygon.io import with fallback (requires optional package)
try:
    from src.tools.data_sources.market.polygon_historical_tool import PolygonHistoricalTool
    POLYGON_AVAILABLE = True
except ImportError:
    POLYGON_AVAILABLE = False

logger = logging.getLogger(__name__)
config_loader = ConfigLoader()

##################################
# Agent Types
##################################

SENTIMENT_AGENT = "sentiment"
TECH_AGENT = "tech"
STRATEGY_AGENT = "strategy"
MARKET_INTELLIGENCE_AGENT = "market_intelligence"
ALL_AGENTS = [SENTIMENT_AGENT, TECH_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]

##################################
# Alpha Vantage Market Data Tool
##################################

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
alpha_vantage_tool.agent_types = [TECH_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]

##################################
# Market Data Tool (Hierarchical)
##################################

def fetch_market_data(
    symbol: str = "AAPL",
    start_date: str = "-30d",
    end_date: str = "today",
    source: str = "auto"
) -> pd.DataFrame:
    """
    Fetch market data using hierarchical source fallback.

    Args:
        symbol: Stock symbol/ticker to fetch data for
        start_date: Start of date range (YYYY-MM-DD or relative like "-30d")
        end_date: End of date range (YYYY-MM-DD or "today")
        source: Data source preference ("auto", "polygon", "alpha_vantage")

    Returns:
        DataFrame with price and volume data
    """
    try:
        # Try Polygon.io first if available and preferred
        if (source in ["auto", "polygon"]) and POLYGON_AVAILABLE:
            logger.info(f"Attempting Polygon.io for {symbol}")
            polygon_data = fetch_polygon_historical_data(symbol, start_date, end_date, "prices")
            if polygon_data and "prices" in polygon_data:
                df = polygon_data["prices"]
                if isinstance(df, pd.DataFrame) and not df.empty:
                    logger.info(f"✓ Polygon.io data retrieved for {symbol}")
                    return df
        
        # Fallback to Alpha Vantage
        logger.info(f"Attempting Alpha Vantage for {symbol}")
        df = fetch_alpha_vantage_data(symbol, start_date, end_date)
        if isinstance(df, pd.DataFrame) and not df.empty:
            logger.info(f"✓ Alpha Vantage data retrieved for {symbol}")
            return df
        
        # If all else fails, return empty DataFrame
        logger.warning(f"No market data available for {symbol}")
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error fetching market data for {symbol}: {str(e)}")
        return pd.DataFrame()

market_data_tool = FunctionTool(
    func=fetch_market_data,
    name="fetch_market_data",
    description="Fetch market data from specified source for a given ticker and date range."
)
market_data_tool.agent_types = [TECH_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]

##################################
# Polygon.io Historical Data Tool
##################################

def fetch_polygon_historical_data(
    ticker: str = "AAPL",
    start_date: str = "2022-01-01",
    end_date: str = "2022-12-31",
    data_type: str = "all"
) -> dict:
    """
    Fetch historical market data from Polygon.io API.

    Args:
        ticker: Stock symbol to fetch data for
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        data_type: Type of data to fetch ('prices', 'news', 'events', 'all')

    Returns:
        Dictionary containing requested data (prices, news, and/or events)
    """
    # Load API key from config
    api_key = config_loader.get("POLYGON_IO")
    if not api_key:
        print("WARNING: POLYGON_IO API key not found in config. Returning empty data.")
        return {}

    if not POLYGON_AVAILABLE:
        print("WARNING: polygon-api-client not installed. Install with: pip install polygon-api-client")
        return {}

    try:
        tool = PolygonHistoricalTool(api_key)
        return tool(ticker, start_date, end_date, data_type)
    except Exception as e:
        print(f"ERROR fetching Polygon data: {e}")
        return {}

polygon_historical_tool = FunctionTool(
    func=fetch_polygon_historical_data,
    name="fetch_polygon_historical_data",
    description="Fetch historical market data (prices, news, events) from Polygon.io with 2 years of history."
)
polygon_historical_tool.agent_types = [TECH_AGENT, STRATEGY_AGENT, MARKET_INTELLIGENCE_AGENT]

##################################
# VXX Volatility Tool for V2 Sentiment
##################################

vxx_volatility_tool = FunctionTool(
    func=fetch_vxx_volatility_data,
    name="fetch_vxx_volatility_data",
    description="Fetch VXX volatility data for market fear-based sentiment analysis. Returns VXX-based sentiment scores for V2 Market Fear sentiment agent."
)
vxx_volatility_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]

##################################
# Tool Collections by Agent Type
##################################

# SENTIMENT_AGENT tools - Google Search + VXX Volatility
_sentiment_tools_raw = [
    google_search_simple_tool,  # V1: Google Custom Search API with caching
    vxx_volatility_tool,        # V2: VXX volatility data for market fear sentiment
]
SENTIMENT_TOOLS = [tool for tool in _sentiment_tools_raw if tool is not None]

# TECH_AGENT tools - Polygon.io primary (5/min) with Alpha Vantage fallback (25/day)
_tech_tools_raw = [
    polygon_historical_tool,  # Primary: Polygon.io (5 calls/min with caching)
    alpha_vantage_tool,       # Fallback: Alpha Vantage (25 calls/day)
]
TECH_TOOLS = [tool for tool in _tech_tools_raw if tool is not None]

# STRATEGY_AGENT tools - Strategy aggregates outputs from other agents
_strategy_tools_raw = [
    # Strategy agent aggregates results from other agents
    # No direct data access tools needed
]
STRATEGY_TOOLS = [tool for tool in _strategy_tools_raw if tool is not None]

# All tools combined (filter out None values from conditional imports)
ALL_TOOLS = list(set(
    tool for tool in (
        SENTIMENT_TOOLS +
        TECH_TOOLS +
        STRATEGY_TOOLS
    ) if tool is not None
))

# Tool dispatcher dictionary for efficient lookup by name
ALL_TOOLS_DICT = {tool.name: tool for tool in ALL_TOOLS if tool is not None}

##################################
# Helper function to get tools for a specific agent type
##################################

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
    elif agent_type == STRATEGY_AGENT:
        return STRATEGY_TOOLS
    else:
        # Return all tools if agent type is unknown
        return ALL_TOOLS