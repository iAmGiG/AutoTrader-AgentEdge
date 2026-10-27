"""
Market data sources package.

This package contains tools for retrieving market data from:
- Alpaca (primary market data source, via unified_market_tool)
- Alpha Vantage (fallback source)

Polygon.io was removed in Oct 2026 (#607).
"""

# Lazy imports to avoid import errors when optional dependencies are missing


def __getattr__(name):
    """Lazy import of market data tools."""
    if name == "AlphaVantageMarketTool":
        from .alpha_vantage_market import AlphaVantageMarketTool

        return AlphaVantageMarketTool
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Support for dir() and IDE autocomplete."""
    return __all__


# pylint: disable=undefined-all-variable  # Names are lazy-loaded via __getattr__
__all__ = [
    "AlphaVantageMarketTool",
]
