"""
Input Parser Utilities - Parse user intent and extract symbols from input.

Issue #436: Extracted from cli_session.py for better modularity.

This module provides input parsing functions for:
- Detecting user intent (buy/sell/review)
- Extracting ticker symbols from natural language
"""

import re
from typing import Optional


def detect_user_intent(user_input: str) -> Optional[str]:
    """
    Detect explicit user intent from input.

    Issue #347: Respects user intent when signals disagree.

    Args:
        user_input: User's natural language input

    Returns:
        "buy" if user explicitly wants to buy/go long
        "sell" if user explicitly wants to sell/close
        None if no explicit intent (just querying/analyzing)

    Example:
        >>> detect_user_intent("buy some AAPL")
        'buy'
        >>> detect_user_intent("should I sell TSLA?")
        None
        >>> detect_user_intent("short NVDA")
        'sell'
    """
    input_lower = user_input.lower()

    # Buy/long indicators
    buy_indicators = [
        "buy",
        "long",
        "go long",
        "going long",
        "bullish",
        "bet it goes up",
        "think it will rise",
        "upside",
        "get ",  # Note: space to avoid 'target', 'forget'
        "acquire",
        "purchase",
        "pick up",
        "grab",
    ]
    if any(indicator in input_lower for indicator in buy_indicators):
        return "buy"

    # Sell/close indicators
    sell_indicators = [
        "sell",
        "short",
        "shorting",
        "go short",
        "exit",
        "close",
        "get out",
        "dump",
        "liquidate",
        "cash out",
        "bet against",
        "profit from decline",
    ]
    if any(indicator in input_lower for indicator in sell_indicators):
        return "sell"

    # Review/analyze indicators (no explicit action)
    review_indicators = [
        "analyze",
        "analysis",
        "review",
        "check",
        "look at",
        "what about",
        "how is",
        "should i",
        "is it good",
    ]
    if any(indicator in input_lower for indicator in review_indicators):
        return None  # Just querying, no explicit intent

    return None  # Default: no explicit intent


def extract_ticker_from_query(user_input: str) -> Optional[str]:
    """
    Extract ticker symbol from natural language query.

    Issue #348: Parse user queries like 'show orders for AAPL'
    Issue #436: Extracted from cli_session.py for modularity.

    Args:
        user_input: User's natural language input

    Returns:
        Ticker symbol (uppercase) or None if not found

    Example:
        >>> extract_ticker_from_query("show orders for AAPL")
        'AAPL'
        >>> extract_ticker_from_query("what's the stop on $TSLA?")
        'TSLA'
        >>> extract_ticker_from_query("show me the orders")
        None
    """
    # Common ticker patterns
    # Match: $AAPL, AAPL, "AAPL", 'AAPL'
    ticker_patterns = [
        r"\$([A-Z]{1,5})\b",  # $AAPL format
        r"\b([A-Z]{1,5})\b",  # Plain AAPL (must be uppercase)
    ]

    input_upper = user_input.upper()

    # Try each pattern
    for pattern in ticker_patterns:
        matches = re.findall(pattern, input_upper)
        if matches:
            # Filter out common words that look like tickers
            exclude = {
                "FOR",
                "THE",
                "AND",
                "ALL",
                "GET",
                "SET",
                "SHOW",
                "ORDER",
                "ORDERS",
                "STOP",
                "ON",
                "LEVEL",
            }
            for match in matches:
                if match not in exclude and len(match) >= 1:
                    return match

    return None


# Buy/sell indicators exported for use by other modules
BUY_INDICATORS = [
    "buy",
    "long",
    "go long",
    "going long",
    "bullish",
    "bet it goes up",
    "think it will rise",
    "upside",
    "get ",
    "acquire",
    "purchase",
    "pick up",
    "grab",
]

SELL_INDICATORS = [
    "sell",
    "short",
    "shorting",
    "go short",
    "exit",
    "close",
    "get out",
    "dump",
    "liquidate",
    "cash out",
    "bet against",
    "profit from decline",
    "make money when it falls",
]


__all__ = [
    "detect_user_intent",
    "extract_ticker_from_query",
    "BUY_INDICATORS",
    "SELL_INDICATORS",
]
