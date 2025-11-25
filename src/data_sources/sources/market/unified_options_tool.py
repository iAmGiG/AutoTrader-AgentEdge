"""
Multi-provider options data fetcher with automatic fallback.

This module provides a unified interface for fetching options data from multiple
providers (Polygon, Alpha Vantage, Alpaca, etc.) with automatic failover,
data quality tracking, and intelligent caching.

Part of Issue #373: Enhanced Database Storage for Multi-Provider Support
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.data_sources.cache import TradingCacheManager
from src.utils.config_loader import ConfigLoader
from src.utils.date_utils import now_iso

# Lazy imports for providers
try:
    from polygon import RESTClient as PolygonClient

    POLYGON_AVAILABLE = True
except ImportError:
    PolygonClient = None
    POLYGON_AVAILABLE = False

try:
    from alpaca.data import OptionHistoricalDataClient
    from alpaca.data.requests import OptionChainRequest

    ALPACA_AVAILABLE = True
except ImportError:
    OptionHistoricalDataClient = None
    OptionChainRequest = None
    ALPACA_AVAILABLE = False


class UnifiedOptionsDataTool:
    """
    Provider-agnostic options data fetcher with intelligent fallback.

    Features:
    - Automatic provider fallback (Polygon → Alpaca → Alpha Vantage)
    - Data quality scoring and tracking
    - Intelligent caching with provider metadata
    - Seamless integration with existing data normalization system

    Example:
        >>> fetcher = UnifiedOptionsDataTool()
        >>> options = fetcher.fetch_options("SPY", "2024-01-15")
        >>> # Automatically tries providers in priority order
        >>> # Returns normalized DataFrame with best available data
    """

    # Provider priority order (higher = try first)
    PROVIDER_PRIORITY = {
        "alpaca": 100,  # Primary: Main broker with live trading data
        "polygon": 90,  # Secondary: Best data quality, real-time (paid tier)
        "alpha_vantage": 80,  # Tertiary: Historical backup
    }

    # TODO: Future multi-broker/multi-account routing (Issue #373 extension)
    # Vision: Support multiple brokers across different vendors (Alpaca A, Alpaca B, IB, etc.)
    # Route API calls to match specific account based on:
    # - Account credentials mapping
    # - Broker capabilities (options, futures, etc.)
    # - Cost optimization (use cheaper data source when equivalent)
    # - Geographic restrictions
    # Example future API:
    #   fetcher.fetch_options("SPY", "2024-01-15", account_id="alpaca_main")
    #   → Routes to Alpaca account "alpaca_main" specifically

    def __init__(self, cache_manager: Optional[TradingCacheManager] = None):
        """
        Initialize unified options fetcher.

        Args:
            cache_manager: Optional cache manager (creates new if None)
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cache = cache_manager or TradingCacheManager()

        # Provider instances (lazy-loaded)
        self._polygon_client = None
        self._alpaca_client = None
        self._config = ConfigLoader()

    def fetch_options(
        self,
        symbol: str,
        trading_date: str,
        preferred_provider: str = None,
        force_refresh: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch options chain with automatic provider fallback.

        Args:
            symbol: Stock symbol (e.g., "SPY")
            trading_date: Trading date in YYYY-MM-DD format
            preferred_provider: Try this provider first (None = use priority order)
            force_refresh: Skip cache and fetch fresh data

        Returns:
            Normalized DataFrame with options data, or None if all providers fail

        Example:
            >>> options = fetcher.fetch_options("SPY", "2024-01-15")
            >>> if options is not None:
            ...     calls = options[options['option_type'] == 'call']
            ...     print(f"Found {len(calls)} call contracts")
        """
        # Check cache first (unless forcing refresh)
        if not force_refresh:
            cached_options = self.cache.get_raw_options(symbol, trading_date)
            if cached_options is not None:
                self.logger.info(f"Cache hit for {symbol} {trading_date}")
                return cached_options

        # Determine provider order
        provider_order = self._get_provider_order(preferred_provider)

        # Try each provider in order
        for provider_name in provider_order:
            self.logger.info(f"Trying {provider_name} for {symbol} {trading_date}")

            try:
                # Fetch from provider
                options_df, underlying_price, metadata = self._fetch_from_provider(
                    provider_name, symbol, trading_date
                )

                if options_df is not None and not options_df.empty:
                    # Calculate data quality score
                    quality_score = self._calculate_quality_score(options_df, metadata)

                    # Store in cache with metadata
                    self.cache.store_raw_options(
                        symbol=symbol,
                        trading_date=trading_date,
                        options_df=options_df,
                        underlying_price=underlying_price,
                        source=provider_name,
                        data_quality_score=quality_score,
                        provider_metadata=metadata,
                    )

                    self.logger.info(
                        f"Successfully fetched {len(options_df)} contracts from {provider_name} "
                        f"(quality: {quality_score:.2f})"
                    )
                    return options_df

            except Exception as e:
                self.logger.warning(f"Provider {provider_name} failed: {e}")
                continue

        # All providers failed
        self.logger.error(f"All providers failed for {symbol} {trading_date}")
        return None

    def _get_provider_order(self, preferred: str = None) -> List[str]:
        """
        Get provider order based on priority.

        Args:
            preferred: Optional preferred provider to try first

        Returns:
            List of provider names in priority order
        """
        # Get all providers sorted by priority
        providers = sorted(self.PROVIDER_PRIORITY.items(), key=lambda x: x[1], reverse=True)
        provider_names = [p[0] for p in providers]

        # Move preferred provider to front if specified
        if preferred and preferred in provider_names:
            provider_names.remove(preferred)
            provider_names.insert(0, preferred)

        return provider_names

    def _fetch_from_provider(
        self, provider: str, symbol: str, trading_date: str
    ) -> Tuple[Optional[pd.DataFrame], Optional[float], Dict[str, Any]]:
        """
        Fetch options data from a specific provider.

        Args:
            provider: Provider name ("polygon", "alpha_vantage", "alpaca")
            symbol: Stock symbol
            trading_date: Trading date

        Returns:
            Tuple of (options_df, underlying_price, metadata)
        """
        if provider == "polygon":
            return self._fetch_polygon(symbol, trading_date)
        elif provider == "alpha_vantage":
            return self._fetch_alpha_vantage(symbol, trading_date)
        elif provider == "alpaca":
            return self._fetch_alpaca(symbol, trading_date)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _fetch_polygon(
        self, symbol: str, trading_date: str
    ) -> Tuple[Optional[pd.DataFrame], Optional[float], Dict[str, Any]]:
        """
        Fetch options data from Polygon.io

        Uses Polygon's options snapshot and contract endpoints to fetch
        complete options chain data.
        """
        metadata = {
            "provider": "polygon",
            "attempted_at": now_iso(),
            "status": "attempted",
        }

        try:
            if not POLYGON_AVAILABLE:
                raise ImportError("polygon-api-client not installed")

            # Initialize Polygon client (lazy)
            if self._polygon_client is None:
                api_key = os.getenv("POLYGON_API_KEY") or self._config.get("POLYGON_IO")
                if not api_key:
                    raise ValueError("Polygon API key not configured")
                self._polygon_client = PolygonClient(api_key)

            # Polygon options snapshot endpoint
            # Note: This is a placeholder - actual implementation depends on Polygon API version
            # and subscription tier. Free tier may not have options data.

            metadata["status"] = "not_available_free_tier"
            metadata["note"] = "Polygon options require paid subscription"

            self.logger.warning(
                "Polygon options data requires paid subscription. " "Falling back to next provider."
            )
            return None, None, metadata

        except Exception as e:
            metadata["status"] = "error"
            metadata["error"] = str(e)
            self.logger.error(f"Polygon fetch failed: {e}")
            return None, None, metadata

    def _fetch_alpha_vantage(
        self, symbol: str, trading_date: str
    ) -> Tuple[Optional[pd.DataFrame], Optional[float], Dict[str, Any]]:
        """
        Fetch options from Alpha Vantage.

        Note: Alpha Vantage options data is available but requires specific API endpoint.
        Implementation pending API endpoint verification.
        """
        metadata = {
            "provider": "alpha_vantage",
            "attempted_at": now_iso(),
            "status": "not_implemented",
            "note": "Alpha Vantage options API endpoint requires verification",
        }

        self.logger.info(
            "Alpha Vantage options fetcher not yet implemented. " "Falling back to next provider."
        )
        return None, None, metadata

    def _fetch_alpaca(
        self, symbol: str, trading_date: str
    ) -> Tuple[Optional[pd.DataFrame], Optional[float], Dict[str, Any]]:
        """
        Fetch options from Alpaca.

        Uses Alpaca's options historical data API to fetch options chain.
        """
        metadata = {
            "provider": "alpaca",
            "attempted_at": now_iso(),
            "status": "attempted",
        }

        try:
            if not ALPACA_AVAILABLE:
                raise ImportError("alpaca-py SDK not installed")

            # Initialize Alpaca client (lazy)
            if self._alpaca_client is None:
                api_key = self._config.get("ALPACA_PAPER_API_KEY")
                secret_key = self._config.get("ALPACA_PAPER_SECRET")

                if not api_key or not secret_key:
                    raise ValueError("Alpaca API credentials not configured")

                self._alpaca_client = OptionHistoricalDataClient(
                    api_key=api_key, secret_key=secret_key
                )

            # Fetch options chain for the trading date
            # Note: Alpaca options API requires specific date format
            request = OptionChainRequest(
                underlying_symbol=symbol, feed="opra"  # Options Price Reporting Authority feed
            )

            # This is a placeholder - actual Alpaca options API usage may vary
            metadata["status"] = "pending_api_verification"
            metadata["note"] = "Alpaca options API implementation pending verification"

            self.logger.info(
                "Alpaca options fetcher pending API verification. " "Falling back to next provider."
            )
            return None, None, metadata

        except Exception as e:
            metadata["status"] = "error"
            metadata["error"] = str(e)
            self.logger.error(f"Alpaca fetch failed: {e}")
            return None, None, metadata

    def _calculate_quality_score(self, options_df: pd.DataFrame, metadata: Dict[str, Any]) -> float:
        """
        Calculate data quality score based on completeness and metadata.

        Args:
            options_df: Options DataFrame
            metadata: Provider metadata

        Returns:
            Quality score from 0.0 to 1.0

        Scoring factors:
        - Data completeness (Greeks, pricing)
        - Contract count
        - Bid-ask spread quality
        - Provider reliability
        """
        score = 1.0

        # Penalize missing Greeks
        greek_columns = ["delta", "gamma", "theta", "vega", "implied_volatility"]
        missing_greeks = sum(
            1
            for col in greek_columns
            if col not in options_df.columns or options_df[col].isna().all()
        )
        score -= missing_greeks * 0.05  # -5% per missing Greek

        # Penalize missing pricing data
        if "bid" not in options_df.columns or options_df["bid"].isna().all():
            score -= 0.1
        if "ask" not in options_df.columns or options_df["ask"].isna().all():
            score -= 0.1

        # Penalize low contract count (expect at least 50 contracts)
        if len(options_df) < 50:
            score -= 0.2
        elif len(options_df) < 100:
            score -= 0.1

        # Provider-specific adjustments
        provider = metadata.get("provider", "")
        if provider == "polygon":
            score += 0.05  # Polygon typically has best data
        elif provider == "alpha_vantage":
            score -= 0.05  # Alpha Vantage may have delays

        # Ensure score stays in valid range
        return max(0.0, min(1.0, score))

    def get_best_provider(self, symbol: str, trading_date: str) -> Optional[str]:
        """
        Determine which provider has the best data for a symbol/date.

        Args:
            symbol: Stock symbol
            trading_date: Trading date

        Returns:
            Provider name with highest quality score, or None
        """
        try:
            # Query cache for all providers
            import sqlite3

            query = """
                SELECT source, data_quality_score, COUNT(*) as contract_count
                FROM raw_options_chain
                WHERE symbol = ? AND trading_date = ?
                GROUP BY source
                ORDER BY data_quality_score DESC, contract_count DESC
                LIMIT 1
            """
            with sqlite3.connect(self.cache.db_path) as conn:
                result = conn.execute(query, (symbol.upper(), trading_date)).fetchone()

            if result:
                return result[0]  # source

            return None

        except Exception as e:
            self.logger.error(f"Error getting best provider: {e}")
            return None
