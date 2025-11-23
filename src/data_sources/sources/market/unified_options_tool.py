"""
Multi-provider options data fetcher with automatic fallback.

This module provides a unified interface for fetching options data from multiple
providers (Polygon, Alpha Vantage, Alpaca, etc.) with automatic failover,
data quality tracking, and intelligent caching.

Part of Issue #373: Enhanced Database Storage for Multi-Provider Support
"""

import logging
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from src.data_sources.cache import TradingCacheManager
from src.data_sources.processors.data_normalizer import (
    normalize_alpha_vantage_data,
    normalize_alpaca_data
)


class UnifiedOptionsDataTool:
    """
    Provider-agnostic options data fetcher with intelligent fallback.

    Features:
    - Automatic provider fallback (Polygon → Alpha Vantage → Alpaca)
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
        'polygon': 100,       # Primary: Best data quality, real-time
        'alpaca': 90,         # Secondary: Good for live trading
        'alpha_vantage': 80,  # Tertiary: Historical backup
    }

    def __init__(self, cache_manager: Optional[TradingCacheManager] = None):
        """
        Initialize unified options fetcher.

        Args:
            cache_manager: Optional cache manager (creates new if None)
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cache = cache_manager or TradingCacheManager()

        # Provider instances (lazy-loaded)
        self._providers = {}

    def fetch_options(self, symbol: str, trading_date: str,
                     preferred_provider: str = None,
                     force_refresh: bool = False) -> Optional[pd.DataFrame]:
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
                        provider_metadata=metadata
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
        providers = sorted(
            self.PROVIDER_PRIORITY.items(),
            key=lambda x: x[1],
            reverse=True
        )
        provider_names = [p[0] for p in providers]

        # Move preferred provider to front if specified
        if preferred and preferred in provider_names:
            provider_names.remove(preferred)
            provider_names.insert(0, preferred)

        return provider_names

    def _fetch_from_provider(self, provider: str, symbol: str, trading_date: str
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
        if provider == 'polygon':
            return self._fetch_polygon(symbol, trading_date)
        elif provider == 'alpha_vantage':
            return self._fetch_alpha_vantage(symbol, trading_date)
        elif provider == 'alpaca':
            return self._fetch_alpaca(symbol, trading_date)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _fetch_polygon(self, symbol: str, trading_date: str
                      ) -> Tuple[Optional[pd.DataFrame], Optional[float], Dict[str, Any]]:
        """Fetch from Polygon (to be implemented)."""
        # TODO: Implement Polygon options fetcher
        # For now, return None to trigger fallback
        metadata = {
            'provider': 'polygon',
            'attempted_at': datetime.now().isoformat(),
            'status': 'not_implemented'
        }
        return None, None, metadata

    def _fetch_alpha_vantage(self, symbol: str, trading_date: str
                            ) -> Tuple[Optional[pd.DataFrame], Optional[float], Dict[str, Any]]:
        """
        Fetch options from Alpha Vantage.

        Note: Alpha Vantage options data is available but requires specific API endpoint.
        This is a placeholder for future implementation.
        """
        metadata = {
            'provider': 'alpha_vantage',
            'attempted_at': datetime.now().isoformat(),
            'status': 'not_implemented',
            'note': 'Alpha Vantage options API requires separate endpoint'
        }
        return None, None, metadata

    def _fetch_alpaca(self, symbol: str, trading_date: str
                     ) -> Tuple[Optional[pd.DataFrame], Optional[float], Dict[str, Any]]:
        """Fetch from Alpaca (to be implemented)."""
        metadata = {
            'provider': 'alpaca',
            'attempted_at': datetime.now().isoformat(),
            'status': 'not_implemented'
        }
        return None, None, metadata

    def _calculate_quality_score(self, options_df: pd.DataFrame,
                                 metadata: Dict[str, Any]) -> float:
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
        greek_columns = ['delta', 'gamma', 'theta', 'vega', 'implied_volatility']
        missing_greeks = sum(1 for col in greek_columns if col not in options_df.columns or options_df[col].isna().all())
        score -= (missing_greeks * 0.05)  # -5% per missing Greek

        # Penalize missing pricing data
        if 'bid' not in options_df.columns or options_df['bid'].isna().all():
            score -= 0.1
        if 'ask' not in options_df.columns or options_df['ask'].isna().all():
            score -= 0.1

        # Penalize low contract count (expect at least 50 contracts)
        if len(options_df) < 50:
            score -= 0.2
        elif len(options_df) < 100:
            score -= 0.1

        # Provider-specific adjustments
        provider = metadata.get('provider', '')
        if provider == 'polygon':
            score += 0.05  # Polygon typically has best data
        elif provider == 'alpha_vantage':
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
            with self.cache._write_lock:
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
