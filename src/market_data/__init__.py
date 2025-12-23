"""
Market data sources package.

This package contains tools for retrieving market data from:
- Polygon.io (primary market data source)
- Alpha Vantage (fallback market data source)
"""

# Lazy imports to avoid import errors when optional dependencies are missing


def __getattr__(name):
    """Lazy import of market data tools."""
    if name == "AlphaVantageMarketTool":
        from .alpha_vantage_market import AlphaVantageMarketTool

        return AlphaVantageMarketTool
    elif name == "PolygonHistoricalTool":
        from .polygon_historical_tool import PolygonHistoricalTool

        return PolygonHistoricalTool
    elif name == "create_polygon_tool":
        from .polygon_historical_tool import create_polygon_tool

        return create_polygon_tool
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Support for dir() and IDE autocomplete."""
    return __all__


# pylint: disable=undefined-all-variable  # Names are lazy-loaded via __getattr__
__all__ = [
    "AlphaVantageMarketTool",
    "PolygonHistoricalTool",
    "create_polygon_tool",
]
