"""
Market Context Tool for V4 Sentiment Enhancement
Fetches SPY/QQQ market context data to enhance sentiment analysis
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

from autogen_core.tools import FunctionTool

from ...cache.sqlite_cache import TradingCacheManager

# Add path for agent_utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from utils.agent_utils import load_agent_config

logger = logging.getLogger(__name__)


def fetch_market_context_data(
    date: str = "2024-01-15", symbols: List[str] = ["SPY", "QQQ"]
) -> Dict[str, Any]:
    """
    Fetch market context data (SPY/QQQ) for enhanced sentiment analysis.

    Provides broader market context to complement individual stock analysis.
    Focus: Market direction and tech sector sentiment for LLM reasoning.

    Args:
        date: Date for market data (YYYY-MM-DD format)
        symbols: Market symbols to fetch (default: SPY, QQQ)

    Returns:
        Dict containing market context data for LLM analysis
    """
    try:
        logger.info(f"Fetching market context for {symbols} on {date}")

        # Initialize SQLite cache manager for Polygon.io primary + Alpha Vantage fallback
        cache_manager = TradingCacheManager()

        market_data = {}

        for symbol in symbols:
            try:
                # Fetch recent data around the target date
                start_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=7)).strftime(
                    "%Y-%m-%d"
                )
                end_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )

                # Get market data using Polygon.io primary + Alpha Vantage fallback pattern
                data = cache_manager.get(symbol, start_date, end_date, source="polygon")
                data_source = "Polygon.io"

                if data is None or data.empty:
                    data = cache_manager.get(symbol, start_date, end_date, source="alpha_vantage")
                    data_source = "Alpha Vantage"

                if data is None or data.empty:
                    logger.warning(
                        f"No market data available from either Polygon.io or Alpha Vantage for {symbol}"
                    )
                    data_source = "None"

                if data is not None and len(data) > 0:
                    # Get the most recent data point
                    latest = data.iloc[-1] if len(data) > 0 else None
                    prev = data.iloc[-2] if len(data) > 1 else None

                    if latest is not None:
                        # Calculate daily change
                        daily_change = 0.0
                        if prev is not None:
                            daily_change = ((latest["close"] - prev["close"]) / prev["close"]) * 100

                        # Calculate recent trend (5-day if available)
                        trend_change = 0.0
                        if len(data) >= 5:
                            first = data.iloc[-5]
                            trend_change = (
                                (latest["close"] - first["close"]) / first["close"]
                            ) * 100

                        market_data[symbol] = {
                            "symbol": symbol,
                            "date_analyzed": date,
                            "current_price": float(latest["close"]),
                            "volume": int(latest["volume"]) if "volume" in latest else 0,
                            "daily_change_pct": round(daily_change, 2),
                            "trend_5day_pct": round(trend_change, 2),
                            "interpretation": _interpret_market_signal(
                                symbol, daily_change, trend_change
                            ),
                        }

                        logger.info(
                            f"Market context for {symbol}: {daily_change:+.2f}% daily, {trend_change:+.2f}% 5-day (source: {data_source})"
                        )
                    else:
                        logger.warning(f"No data available for {symbol} on {date}")
                        market_data[symbol] = _create_fallback_data(symbol, date)
                else:
                    logger.warning(f"No market data returned for {symbol} from either source")
                    market_data[symbol] = _create_fallback_data(symbol, date)

            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                market_data[symbol] = _create_fallback_data(symbol, date, str(e))

        # Create summary interpretation
        summary = _create_market_summary(market_data)

        result = {
            "market_context": market_data,
            "market_summary": summary,
            "date_analyzed": date,
            "symbols_analyzed": symbols,
            "tool_name": "market_context",
        }

        logger.info(f"Market context analysis complete: {summary['overall_sentiment']}")
        return result

    except Exception as e:
        logger.error(f"Market context tool error: {e}")
        return {
            "market_context": {},
            "market_summary": {"overall_sentiment": "NEUTRAL", "error": str(e)},
            "date_analyzed": date,
            "symbols_analyzed": symbols,
            "tool_name": "market_context",
        }


def _interpret_market_signal(symbol: str, daily_change: float, trend_change: float) -> str:
    """Interpret market signal for LLM consumption."""

    if symbol == "SPY":
        base = "Market (S&P 500)"
    elif symbol == "QQQ":
        base = "Tech Sector (Nasdaq)"
    else:
        base = symbol

    # Interpret daily movement
    if abs(daily_change) < 0.5:
        daily_desc = "stable"
    elif daily_change > 1.0:
        daily_desc = "strong positive"
    elif daily_change > 0.5:
        daily_desc = "positive"
    elif daily_change < -1.0:
        daily_desc = "strong negative"
    else:
        daily_desc = "negative"

    # Interpret trend
    if abs(trend_change) < 1.0:
        trend_desc = "sideways"
    elif trend_change > 2.0:
        trend_desc = "strong uptrend"
    elif trend_change > 1.0:
        trend_desc = "uptrend"
    elif trend_change < -2.0:
        trend_desc = "strong downtrend"
    else:
        trend_desc = "downtrend"

    return f"{base}: {daily_desc} day ({daily_change:+.1f}%), {trend_desc} ({trend_change:+.1f}%)"


def _create_market_summary(market_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create overall market sentiment summary for LLM."""

    spy_data = market_data.get("SPY", {})
    qqq_data = market_data.get("QQQ", {})

    # Extract signals
    spy_daily = spy_data.get("daily_change_pct", 0.0)
    qqq_daily = qqq_data.get("daily_change_pct", 0.0)
    spy_trend = spy_data.get("trend_5day_pct", 0.0)
    qqq_trend = qqq_data.get("trend_5day_pct", 0.0)

    # Calculate overall sentiment
    daily_avg = (spy_daily + qqq_daily) / 2
    trend_avg = (spy_trend + qqq_trend) / 2

    # Determine overall market sentiment
    if daily_avg > 1.0 and trend_avg > 2.0:
        overall = "STRONG_BULLISH"
    elif daily_avg > 0.5 and trend_avg > 1.0:
        overall = "BULLISH"
    elif daily_avg > -0.5 and trend_avg > -1.0:
        overall = "NEUTRAL"
    elif daily_avg < -0.5 and trend_avg < -1.0:
        overall = "BEARISH"
    else:
        overall = "STRONG_BEARISH"

    return {
        "overall_sentiment": overall,
        "market_daily_avg": round(daily_avg, 2),
        "market_trend_avg": round(trend_avg, 2),
        "spy_signal": spy_data.get("interpretation", "No data"),
        "qqq_signal": qqq_data.get("interpretation", "No data"),
        "interpretation": f"Market sentiment: {overall} (daily: {daily_avg:+.1f}%, trend: {trend_avg:+.1f}%)",
    }


def _create_fallback_data(symbol: str, date: str, error: str = None) -> Dict[str, Any]:
    """Create fallback data when market data is unavailable."""
    return {
        "symbol": symbol,
        "date_analyzed": date,
        "current_price": 0.0,
        "volume": 0,
        "daily_change_pct": 0.0,
        "trend_5day_pct": 0.0,
        "interpretation": f"{symbol}: No data available" + (f" ({error})" if error else ""),
        "error": error,
    }


# Load description from YAML config with fallback
def _get_market_context_description():
    """Get market context tool description from YAML or use fallback."""
    default_desc = """Fetch market context data (SPY/QQQ) for enhanced sentiment analysis.

Provides broader market direction and tech sector sentiment to complement
individual stock analysis. Designed for LLM reasoning about market conditions.

Parameters:
- date: Target date for analysis (YYYY-MM-DD)
- symbols: Market symbols (default: ["SPY", "QQQ"])

Returns market context including:
- Daily price movements
- Short-term trends
- Market sentiment interpretation
- Overall market direction summary

Use this to understand if the broader market and tech sector are supportive
of individual stock decisions."""

    try:
        tools_config = load_agent_config("tools")
        desc = tools_config.get("market_context", {}).get("description", "")
        return desc.strip() if desc else default_desc
    except Exception:
        return default_desc


# Create the FunctionTool for AutoGen
market_context_tool = FunctionTool(
    fetch_market_context_data, description=_get_market_context_description()
)

# Set agent type compatibility
market_context_tool.agent_types = ["sentiment"]
