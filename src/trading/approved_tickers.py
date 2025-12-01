#!/usr/bin/env python3
"""
Approved Tickers Manager

Issue #415: Approved Ticker List with Entry Modes (buy/buy_add/watchOnly)

Manages pre-approved ticker list for automated trading:
- Configurable entry modes per ticker
- Profile overrides (conservative/moderate/aggressive)
- Position limits per ticker
- Integration with VoterAgent analysis
- SQLite backend for persistence and metadata
"""

import logging
from typing import Dict, List, Optional

from src.core.trading_modes import TradingMode
from src.trading.ticker_database import (
    ApprovedTicker,
    TickerDatabase,
    TickerMetadata,
    TickerMode,
    TickerType,
)

logger = logging.getLogger(__name__)


class ApprovedTickersManager:
    """
    Manages approved ticker list for automated trading.

    Issue #415: Approved Ticker List with Entry Modes

    Provides:
    - Add/remove tickers with modes (persisted to SQLite)
    - List approved tickers with metadata
    - Query ticker configuration
    - Profile overrides
    - Position limit enforcement
    - Leveraged ETF lookup and classification
    """

    def __init__(self, db_path: str = "data/tickers.db"):
        """
        Initialize approved tickers manager with SQLite backend.

        Args:
            db_path: Path to SQLite database file
        """
        self.db = TickerDatabase(db_path)
        logger.info(f"ApprovedTickersManager initialized with database: {db_path}")

    def add_ticker(
        self,
        symbol: str,
        mode: TickerMode = TickerMode.BUY_ADD,
        profile: Optional[TradingMode] = None,
        max_position: Optional[float] = None,
        max_shares: Optional[int] = None,
        min_confidence: float = 0.65,
        notes: str = "",
    ) -> ApprovedTicker:
        """
        Add a ticker to the approved list.

        Args:
            symbol: Ticker symbol (e.g., "AAPL")
            mode: Entry mode (buy, buy_add, watch_only, disabled)
            profile: Optional profile override (conservative/moderate/aggressive)
            max_position: Maximum position size in USD
            max_shares: Maximum position size in shares
            min_confidence: Minimum confidence threshold for signals (0.0-1.0)
            notes: User notes about this ticker

        Returns:
            ApprovedTicker for the added ticker
        """
        approved = self.db.approve_ticker(
            symbol=symbol,
            mode=mode,
            profile=profile,
            max_position=max_position,
            max_shares=max_shares,
            min_confidence=min_confidence,
            notes=notes,
        )

        logger.info(
            f"Added {symbol} to approved list: mode={mode.value}, "
            f"profile={profile.value if profile else 'default'}"
        )

        return approved

    def remove_ticker(self, symbol: str) -> bool:
        """
        Remove a ticker from the approved list.

        Args:
            symbol: Ticker symbol to remove

        Returns:
            True if removed, False if not found
        """
        result = self.db.remove_approved(symbol)
        if result:
            logger.info(f"Removed {symbol} from approved list")
        else:
            logger.warning(f"Ticker {symbol} not found in approved list")
        return result

    def set_ticker_mode(self, symbol: str, mode: TickerMode) -> bool:
        """
        Change mode for a ticker.

        Args:
            symbol: Ticker symbol
            mode: New entry mode

        Returns:
            True if updated, False if not found
        """
        ticker = self.db.get_approved(symbol)
        if not ticker:
            logger.warning(f"Ticker {symbol} not found in approved list")
            return False

        old_mode = ticker.mode
        ticker.mode = mode
        # Re-approve with updated mode
        self.db.approve_ticker(
            symbol=symbol,
            mode=mode,
            profile=ticker.profile,
            max_position=ticker.max_position,
            max_shares=ticker.max_shares,
            min_confidence=ticker.min_confidence,
            notes=ticker.notes,
        )
        logger.info(f"Updated {symbol} mode: {old_mode.value} → {mode.value}")
        return True

    def get_ticker(self, symbol: str) -> Optional[ApprovedTicker]:
        """
        Get configuration for a specific ticker.

        Args:
            symbol: Ticker symbol

        Returns:
            ApprovedTicker or None if not found
        """
        return self.db.get_approved(symbol)

    def list_approved(self, active_only: bool = False) -> List[ApprovedTicker]:
        """
        List all approved tickers.

        Args:
            active_only: Only return active (non-disabled) tickers

        Returns:
            List of ApprovedTicker
        """
        tickers = self.db.list_approved()

        if active_only:
            tickers = [t for t in tickers if t.is_active()]

        # Sort by symbol for consistent ordering
        return sorted(tickers, key=lambda t: t.symbol)

    def list_by_mode(self, mode: TickerMode) -> List[ApprovedTicker]:
        """
        Get all tickers with a specific mode.

        Args:
            mode: Entry mode to filter by

        Returns:
            List of ApprovedTicker with matching mode
        """
        return self.db.list_approved(mode=mode)

    def is_approved(self, symbol: str) -> bool:
        """
        Check if a ticker is in the approved list.

        Args:
            symbol: Ticker symbol

        Returns:
            True if approved and active, False otherwise
        """
        ticker = self.db.get_approved(symbol)
        return ticker is not None and ticker.is_active()

    def can_open_position(self, symbol: str) -> bool:
        """
        Check if we can open a new position for this ticker.

        Args:
            symbol: Ticker symbol

        Returns:
            True if ticker allows new positions
        """
        ticker = self.db.get_approved(symbol)
        return ticker is not None and ticker.allows_new_positions()

    def can_add_to_position(self, symbol: str) -> bool:
        """
        Check if we can add to an existing position for this ticker.

        Args:
            symbol: Ticker symbol

        Returns:
            True if ticker allows adding to existing positions
        """
        ticker = self.db.get_approved(symbol)
        return ticker is not None and ticker.allows_adding_to_existing()

    def get_active_tickers(self) -> List[str]:
        """
        Get list of active ticker symbols.

        Returns:
            List of symbol strings
        """
        return [t.symbol for t in self.list_approved(active_only=True)]

    def get_position_limit(self, symbol: str) -> Optional[float]:
        """
        Get position size limit for a ticker.

        Args:
            symbol: Ticker symbol

        Returns:
            Max position in USD, or None if no limit
        """
        ticker = self.db.get_approved(symbol)
        return ticker.max_position if ticker else None

    def get_profile_override(self, symbol: str) -> Optional[TradingMode]:
        """
        Get profile override for a ticker.

        Args:
            symbol: Ticker symbol

        Returns:
            TradingMode override or None if using default
        """
        ticker = self.db.get_approved(symbol)
        return ticker.profile if ticker else None

    def get_summary(self) -> Dict:
        """
        Get summary of approved tickers.

        Returns:
            Dict with statistics and ticker list
        """
        all_tickers = self.list_approved()

        return {
            "total_approved": len(all_tickers),
            "active_count": len([t for t in all_tickers if t.is_active()]),
            "buy_only_count": len(self.list_by_mode(TickerMode.BUY)),
            "buy_add_count": len(self.list_by_mode(TickerMode.BUY_ADD)),
            "watch_only_count": len(self.list_by_mode(TickerMode.WATCH_ONLY)),
            "disabled_count": len(self.list_by_mode(TickerMode.DISABLED)),
            "profile_overrides": len([t for t in all_tickers if t.profile]),
            "tickers": [
                {
                    "symbol": t.symbol,
                    "mode": t.mode.value,
                    "profile": t.profile.value if t.profile else None,
                    "max_position": t.max_position,
                    "min_confidence": t.min_confidence,
                }
                for t in all_tickers
            ],
        }

    # Metadata and leveraged ETF methods

    def get_ticker_metadata(self, symbol: str) -> Optional[TickerMetadata]:
        """
        Get metadata for a ticker (type, underlying, multiplier).

        Args:
            symbol: Ticker symbol

        Returns:
            TickerMetadata or None if not found
        """
        return self.db.get_ticker_metadata(symbol)

    def add_ticker_metadata(
        self,
        symbol: str,
        name: Optional[str] = None,
        ticker_type=None,
        underlying: Optional[str] = None,
        multiplier: float = 1.0,
        provider: Optional[str] = None,
        expense_ratio: Optional[float] = None,
        notes: str = "",
    ) -> TickerMetadata:
        """
        Add or update ticker metadata.

        Args:
            symbol: Ticker symbol
            name: Full name
            ticker_type: TickerType enum value
            underlying: What it tracks (for ETFs)
            multiplier: Leverage multiplier (1x, 2x, 3x, -2x, -3x)
            provider: ETF provider (e.g., "ProShares", "Direxion")
            expense_ratio: Annual expense ratio (e.g., 0.0095 for 0.95%)
            notes: Additional notes

        Returns:
            TickerMetadata
        """
        metadata = self.db.add_ticker_metadata(
            symbol=symbol,
            name=name,
            ticker_type=ticker_type if ticker_type else TickerType.UNKNOWN,
            underlying=underlying,
            multiplier=multiplier,
            provider=provider,
            expense_ratio=expense_ratio,
            notes=notes,
        )
        logger.info(f"Added metadata for {symbol}: {ticker_type}, {multiplier}x")
        return metadata

    def list_leveraged_etfs(
        self, multiplier: Optional[float] = None, underlying: Optional[str] = None
    ) -> List[TickerMetadata]:
        """
        List leveraged ETFs by multiplier and/or underlying.

        Args:
            multiplier: Filter by leverage (e.g., 2.0 for 2x, 3.0 for 3x)
            underlying: Filter by underlying (e.g., "SPY")

        Returns:
            List of TickerMetadata
        """
        # Database list_leveraged_etfs only takes multiplier
        # We need to combine results and filter manually
        if multiplier is None and underlying is None:
            # Get common leveraged ETFs
            result = []
            for mult in [2.0, 3.0]:
                result.extend(self.db.list_leveraged_etfs(multiplier=mult))
        elif multiplier is not None and underlying is None:
            result = self.db.list_leveraged_etfs(multiplier=multiplier)
        elif underlying is not None:
            # Get all leveraged ETFs and filter by underlying
            result = self.db.list_by_underlying(underlying)
            if multiplier is not None:
                result = [t for t in result if abs(t.multiplier) == abs(multiplier)]
        else:
            # Both filters
            result = self.db.list_by_underlying(underlying)
            result = [t for t in result if abs(t.multiplier) == abs(multiplier)]

        return result

    def seed_common_tickers(self):
        """
        Seed database with common tickers and leveraged ETFs.

        Adds metadata for popular stocks (AAPL, GOOGL, etc.) and
        leveraged ETFs (TQQQ, SPXL, etc.).
        """
        self.db.seed_common_tickers()
        logger.info("Seeded database with common tickers")
