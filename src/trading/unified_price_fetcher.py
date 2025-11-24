#!/usr/bin/env python3
"""
Unified Price Data Fetcher

Single source of truth for getting current prices across all trading modules.
Handles fallbacks and caching consistently.
"""

import logging
import os
import sys
from datetime import datetime, timedelta  # TODO date utils
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.data_sources.sources.market.alpaca_market_data import AlpacaMarketData

logger = logging.getLogger(__name__)


class UnifiedPriceFetcher:
    """
    Centralized price fetching with consistent fallback logic.

    This class provides a single implementation used by all trading modules
    to avoid inconsistent pricing across the system.
    """

    _instance = None
    _cache = {}
    _cache_ttl = 60  # Cache for 60 seconds

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.market_data = AlpacaMarketData()
        return cls._instance

    def get_current_price(self, symbol: str, use_cache: bool = True) -> float:
        """
        Get current price with consistent fallback logic.

        Priority:
        1. Cached price (if fresh)
        2. Latest trade from Alpaca
        3. Quote mid-price from Alpaca
        4. Historical close price
        5. Default fallback prices

        Args:
            symbol: Stock symbol
            use_cache: Whether to use cached prices

        Returns:
            Current price as float
        """
        # Check cache first
        if use_cache and symbol in self._cache:
            cache_entry = self._cache[symbol]
            if (datetime.now() - cache_entry["timestamp"]).seconds < self._cache_ttl:
                logger.debug(f"Using cached price for {symbol}: ${cache_entry['price']:.2f}")
                return cache_entry["price"]

        try:
            # Try latest trade first
            trade_data = self.market_data.get_latest_trade(symbol)
            # Handle nested structure: trade_data['trade']['p']
            if trade_data:
                if "price" in trade_data:
                    price = float(trade_data["price"])
                    self._update_cache(symbol, price)
                    logger.debug(f"Got trade price for {symbol}: ${price:.2f}")
                    return price
                elif "trade" in trade_data and trade_data["trade"] and "p" in trade_data["trade"]:
                    price = float(trade_data["trade"]["p"])
                    self._update_cache(symbol, price)
                    logger.debug(f"Got trade price for {symbol}: ${price:.2f}")
                    return price

            # Fallback to quote mid-price
            quote_data = self.market_data.get_latest_quote(symbol)
            # Handle nested structure: quote_data['quote']['bp'] and ['ap']
            if quote_data:
                # Try direct keys first (legacy format)
                if "bid_price" in quote_data and "ask_price" in quote_data:
                    bid = float(quote_data["bid_price"])
                    ask = float(quote_data["ask_price"])
                    if bid > 0 and ask > 0:
                        price = (bid + ask) / 2
                        self._update_cache(symbol, price)
                        logger.debug(f"Got quote mid-price for {symbol}: ${price:.2f}")
                        return price
                # Try nested structure (Alpaca SDK format)
                elif "quote" in quote_data and quote_data["quote"]:
                    quote = quote_data["quote"]
                    if "bp" in quote and "ap" in quote:
                        bid = float(quote["bp"]) if quote["bp"] else 0
                        ask = float(quote["ap"]) if quote["ap"] else 0
                        if bid > 0 and ask > 0:
                            price = (bid + ask) / 2
                            self._update_cache(symbol, price)
                            logger.debug(f"Got quote mid-price for {symbol}: ${price:.2f}")
                            return price

            # Try historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)
            historical = self.market_data.get_bars(
                symbols=[symbol],
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                timeframe="1Day",
            )

            if historical is not None and len(historical) > 0:
                if isinstance(historical, dict) and symbol in historical:
                    data = historical[symbol]
                    if len(data) > 0:
                        price = float(data["close"].iloc[-1])
                        self._update_cache(symbol, price)
                        logger.warning(f"Using historical close for {symbol}: ${price:.2f}")
                        return price

        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")

        # Last resort: default prices (updated to 2025 levels)
        default_prices = {
            "TQQQ": 85.50,
            "SQQQ": 12.30,
            "SPXL": 140.00,
            "SPXS": 10.50,
            "SPY": 660.00,  # Updated to current market level
            "QQQ": 510.00,  # Updated to current market level
            "SOXL": 28.40,
        }

        price = default_prices.get(symbol, 100.0)
        logger.warning(f"Using default price for {symbol}: ${price:.2f}")
        self._update_cache(symbol, price)
        return price

    def _update_cache(self, symbol: str, price: float):
        """Update the price cache."""
        self._cache[symbol] = {"price": price, "timestamp": datetime.now()}

    def clear_cache(self, symbol: Optional[str] = None):
        """Clear price cache."""
        if symbol:
            self._cache.pop(symbol, None)
        else:
            self._cache.clear()


# Singleton instance
price_fetcher = UnifiedPriceFetcher()


def get_current_price(symbol: str) -> float:
    """
    Convenience function for getting current price.

    This is the function that should be imported and used
    throughout the trading system.
    """
    return price_fetcher.get_current_price(symbol)
