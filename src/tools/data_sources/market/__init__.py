"""
Market data sources package.

This package contains tools for retrieving market data from various sources:
- Alpha Vantage (stock prices, fundamentals)
- Yahoo Finance (historical data, options)
- Other market data providers
"""

# Lazy imports to avoid import errors when optional dependencies are missing
def __getattr__(name):
    """Lazy import of market data tools."""
    if name == "AlphaVantageMarketTool":
        from .alpha_vantage_market import AlphaVantageMarketTool
        return AlphaVantageMarketTool
    elif name == "YahooFinanceTool":
        try:
            from .yahoo_finance_tool import YahooFinanceTool
            return YahooFinanceTool
        except ImportError:
            raise ImportError(
                "YahooFinanceTool requires yfinance. "
                "Install it with: pip install yfinance"
            )
    elif name == "MarketDataTool":
        from .market_data_tool import MarketDataTool
        return MarketDataTool
    elif name == "FMPTool":
        from .fmp_tool import FMPTool
        return FMPTool
    elif name == "NasdaqDataLinkTool":
        from .nasdaq_data_link_tool import NasdaqDataLinkTool
        return NasdaqDataLinkTool
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AlphaVantageMarketTool",
    "YahooFinanceTool",
    "MarketDataTool",
    "FMPTool",
    "NasdaqDataLinkTool",
]
