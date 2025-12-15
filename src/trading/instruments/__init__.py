"""
Ticker and timeframe management - instruments, indicators, data.
"""

from .approved_tickers import ApprovedTickersManager
from .data_fetch import fetch_market_data
from .indicator_registry import (
                                 BaseIndicator,
                                 IndicatorRegistry,
                                 IndicatorResult,
                                 MACDIndicator,
                                 RSIIndicator,
                                 create_indicator,
                                 get_indicator_registry,
                                 register_indicator_class,
)
from .indicators import calculate_macd, calculate_rsi
from .ticker_database import TickerDatabase, TickerMode
from .timeframe_tools import TimeframeManager, get_current_timeframe, set_current_timeframe

__all__ = [
    "ApprovedTickersManager",
    "TickerDatabase",
    "TickerMode",
    "TimeframeManager",
    "get_current_timeframe",
    "set_current_timeframe",
    "calculate_macd",
    "calculate_rsi",
    "fetch_market_data",
    # Indicator registry (Issue #364)
    "BaseIndicator",
    "IndicatorRegistry",
    "IndicatorResult",
    "MACDIndicator",
    "RSIIndicator",
    "create_indicator",
    "get_indicator_registry",
    "register_indicator_class",
]
# Custom timeframe builder (Issue #407)

__all__.extend(
    [
        "CustomTimeframeBuilder",
        "TimeframeParser",
        "TimeframeSpec",
        "build_custom_bars",
        "get_custom_timeframe_builder",
        "validate_timeframe",
    ]
)
