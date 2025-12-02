#!/usr/bin/env python3
"""
Ticker Database - SQLite-based Ticker Metadata and Approved List

Issue #415: Approved Ticker List with Entry Modes

Provides:
- Ticker metadata storage (name, type, underlying, multiplier)
- Ticker classification (stock, ETF 1x/2x/3x, inverse)
- Approved tickers management
- Efficient lookup tables for leveraged ETFs

Database Schema:
- ticker_metadata: Symbol info (name, type, underlying, etc.)
- approved_tickers: Entry modes, limits, profile overrides
"""

import logging
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from src.core.trading_modes import TradingMode

logger = logging.getLogger(__name__)


class TickerType(str, Enum):
    """Type of ticker/security."""

    STOCK = "stock"
    ETF_1X = "etf_1x"  # Standard ETF (1x tracking)
    ETF_2X_BULL = "etf_2x_bull"  # 2x leveraged bull
    ETF_3X_BULL = "etf_3x_bull"  # 3x leveraged bull
    ETF_2X_BEAR = "etf_2x_bear"  # 2x leveraged inverse
    ETF_3X_BEAR = "etf_3x_bear"  # 3x leveraged inverse
    INDEX = "index"
    UNKNOWN = "unknown"


class TickerMode(str, Enum):
    """Entry mode for an approved ticker."""

    BUY = "buy"  # Only open new positions
    BUY_ADD = "buy_add"  # Buy or add to existing
    WATCH_ONLY = "watch_only"  # Alert but don't execute
    DISABLED = "disabled"  # Ignore completely


@dataclass
class TickerMetadata:
    """Metadata about a ticker."""

    symbol: str
    name: Optional[str] = None  # Company/ETF name
    ticker_type: TickerType = TickerType.UNKNOWN
    underlying: Optional[str] = None  # What it tracks (e.g., SPY for SPXL)
    multiplier: float = 1.0  # Leverage multiplier (1x, 2x, 3x, -1x, -2x, -3x)
    provider: Optional[str] = None  # ETF provider (e.g., Direxion, ProShares)
    expense_ratio: Optional[float] = None  # Annual expense ratio
    notes: str = ""


@dataclass
class ApprovedTicker:
    """Approved ticker configuration."""

    symbol: str
    mode: TickerMode = TickerMode.BUY_ADD
    profile: Optional[TradingMode] = None
    max_position: Optional[float] = None  # USD limit
    max_shares: Optional[int] = None  # Share count limit
    min_confidence: float = 0.65  # Min signal confidence
    notes: str = ""

    def __post_init__(self):
        """Validate configuration."""
        if isinstance(self.mode, str):
            self.mode = TickerMode(self.mode)
        if isinstance(self.profile, str):
            self.profile = TradingMode.from_string(self.profile)

    def allows_new_positions(self) -> bool:
        """Check if this ticker allows opening new positions."""
        return self.mode in (TickerMode.BUY, TickerMode.BUY_ADD)

    def allows_adding_to_existing(self) -> bool:
        """Check if this ticker allows adding to existing positions."""
        return self.mode == TickerMode.BUY_ADD

    def is_active(self) -> bool:
        """Check if this ticker is active (not disabled)."""
        return self.mode != TickerMode.DISABLED

    def is_watch_only(self) -> bool:
        """Check if this ticker is watch-only."""
        return self.mode == TickerMode.WATCH_ONLY


class TickerDatabase:
    """
    SQLite-based ticker metadata and approved list management.

    Issue #415: Approved Ticker List with Entry Modes

    Features:
    - Persistent ticker metadata storage
    - Efficient lookup by type (2x ETFs, 3x ETFs, etc.)
    - Approved tickers with entry modes
    - Simple schema, easy to extend
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize ticker database.

        Args:
            db_path: Path to SQLite database file (default: data/tickers.db)
        """
        if db_path is None:
            db_path = "data/tickers.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Dict-like access

        self._create_schema()
        logger.info(f"TickerDatabase initialized: {self.db_path}")

    def _create_schema(self):
        """Create database schema if not exists."""
        cursor = self.conn.cursor()

        # Ticker metadata table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ticker_metadata (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                ticker_type TEXT NOT NULL DEFAULT 'unknown',
                underlying TEXT,
                multiplier REAL DEFAULT 1.0,
                provider TEXT,
                expense_ratio REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Approved tickers table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS approved_tickers (
                symbol TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'buy_add',
                profile TEXT,
                max_position REAL,
                max_shares INTEGER,
                min_confidence REAL DEFAULT 0.65,
                notes TEXT,
                approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (symbol) REFERENCES ticker_metadata(symbol)
            )
        """
        )

        # Indexes for efficient lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticker_type ON ticker_metadata(ticker_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_underlying ON ticker_metadata(underlying)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mode ON approved_tickers(mode)")

        self.conn.commit()

    def add_ticker_metadata(
        self,
        symbol: str,
        name: Optional[str] = None,
        ticker_type: TickerType = TickerType.UNKNOWN,
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
            name: Company/ETF name
            ticker_type: Type classification
            underlying: What it tracks
            multiplier: Leverage multiplier
            provider: ETF provider
            expense_ratio: Annual expense ratio
            notes: Additional notes

        Returns:
            TickerMetadata object
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO ticker_metadata
            (symbol, name, ticker_type, underlying, multiplier, provider, expense_ratio, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                symbol,
                name,
                ticker_type.value,
                underlying,
                multiplier,
                provider,
                expense_ratio,
                notes,
            ),
        )

        self.conn.commit()
        logger.info(f"Added ticker metadata: {symbol} ({ticker_type.value})")

        return TickerMetadata(
            symbol=symbol,
            name=name,
            ticker_type=ticker_type,
            underlying=underlying,
            multiplier=multiplier,
            provider=provider,
            expense_ratio=expense_ratio,
            notes=notes,
        )

    def get_ticker_metadata(self, symbol: str) -> Optional[TickerMetadata]:
        """
        Get metadata for a ticker.

        Args:
            symbol: Ticker symbol

        Returns:
            TickerMetadata or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM ticker_metadata WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()

        if row:
            return TickerMetadata(
                symbol=row["symbol"],
                name=row["name"],
                ticker_type=TickerType(row["ticker_type"]),
                underlying=row["underlying"],
                multiplier=row["multiplier"],
                provider=row["provider"],
                expense_ratio=row["expense_ratio"],
                notes=row["notes"] or "",
            )
        return None

    def list_by_type(self, ticker_type: TickerType) -> List[TickerMetadata]:
        """
        Get all tickers of a specific type.

        Args:
            ticker_type: Type to filter by

        Returns:
            List of TickerMetadata
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM ticker_metadata WHERE ticker_type = ? ORDER BY symbol",
            (ticker_type.value,),
        )

        return [
            TickerMetadata(
                symbol=row["symbol"],
                name=row["name"],
                ticker_type=TickerType(row["ticker_type"]),
                underlying=row["underlying"],
                multiplier=row["multiplier"],
                provider=row["provider"],
                expense_ratio=row["expense_ratio"],
                notes=row["notes"] or "",
            )
            for row in cursor.fetchall()
        ]

    def list_leveraged_etfs(self, multiplier: float = 2.0) -> List[TickerMetadata]:
        """
        Get leveraged ETFs by multiplier.

        Args:
            multiplier: Leverage level (2.0 for 2x, 3.0 for 3x, -2.0 for -2x)

        Returns:
            List of TickerMetadata
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM ticker_metadata
            WHERE ABS(multiplier) = ? AND ticker_type LIKE 'etf_%'
            ORDER BY symbol
        """,
            (abs(multiplier),),
        )

        return [
            TickerMetadata(
                symbol=row["symbol"],
                name=row["name"],
                ticker_type=TickerType(row["ticker_type"]),
                underlying=row["underlying"],
                multiplier=row["multiplier"],
                provider=row["provider"],
                expense_ratio=row["expense_ratio"],
                notes=row["notes"] or "",
            )
            for row in cursor.fetchall()
        ]

    def list_by_underlying(self, underlying: str) -> List[TickerMetadata]:
        """
        Get all tickers tracking a specific underlying.

        Example: Get all SPY-based leveraged ETFs (SPXL, SPXU, SSO, SDS)

        Args:
            underlying: Underlying asset symbol

        Returns:
            List of TickerMetadata
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM ticker_metadata WHERE underlying = ? ORDER BY multiplier DESC",
            (underlying,),
        )

        return [
            TickerMetadata(
                symbol=row["symbol"],
                name=row["name"],
                ticker_type=TickerType(row["ticker_type"]),
                underlying=row["underlying"],
                multiplier=row["multiplier"],
                provider=row["provider"],
                expense_ratio=row["expense_ratio"],
                notes=row["notes"] or "",
            )
            for row in cursor.fetchall()
        ]

    def approve_ticker(
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
        Approve a ticker for trading.

        Args:
            symbol: Ticker symbol
            mode: Entry mode
            profile: Profile override
            max_position: Max position in USD
            max_shares: Max position in shares
            min_confidence: Min confidence threshold
            notes: User notes

        Returns:
            ApprovedTicker object
        """
        cursor = self.conn.cursor()

        # Ensure ticker metadata exists
        if self.get_ticker_metadata(symbol) is None:
            # Create basic metadata
            self.add_ticker_metadata(symbol)

        cursor.execute(
            """
            INSERT OR REPLACE INTO approved_tickers
            (symbol, mode, profile, max_position, max_shares, min_confidence, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                symbol,
                mode.value,
                profile.value if profile else None,
                max_position,
                max_shares,
                min_confidence,
                notes,
            ),
        )

        self.conn.commit()
        logger.info(f"Approved ticker: {symbol} (mode={mode.value})")

        return ApprovedTicker(
            symbol=symbol,
            mode=mode,
            profile=profile,
            max_position=max_position,
            max_shares=max_shares,
            min_confidence=min_confidence,
            notes=notes,
        )

    def remove_approved(self, symbol: str) -> bool:
        """
        Remove ticker from approved list.

        Args:
            symbol: Ticker symbol

        Returns:
            True if removed, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM approved_tickers WHERE symbol = ?", (symbol,))
        deleted = cursor.rowcount > 0
        self.conn.commit()

        if deleted:
            logger.info(f"Removed {symbol} from approved list")
        return deleted

    def get_approved(self, symbol: str) -> Optional[ApprovedTicker]:
        """
        Get approved ticker configuration.

        Args:
            symbol: Ticker symbol

        Returns:
            ApprovedTicker or None if not approved
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM approved_tickers WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()

        if row:
            return ApprovedTicker(
                symbol=row["symbol"],
                mode=TickerMode(row["mode"]),
                profile=TradingMode.from_string(row["profile"]) if row["profile"] else None,
                max_position=row["max_position"],
                max_shares=row["max_shares"],
                min_confidence=row["min_confidence"],
                notes=row["notes"] or "",
            )
        return None

    def list_approved(self, mode: Optional[TickerMode] = None) -> List[ApprovedTicker]:
        """
        List approved tickers.

        Args:
            mode: Optional filter by mode

        Returns:
            List of ApprovedTicker
        """
        cursor = self.conn.cursor()

        if mode:
            cursor.execute(
                "SELECT * FROM approved_tickers WHERE mode = ? ORDER BY symbol", (mode.value,)
            )
        else:
            cursor.execute("SELECT * FROM approved_tickers ORDER BY symbol")

        return [
            ApprovedTicker(
                symbol=row["symbol"],
                mode=TickerMode(row["mode"]),
                profile=TradingMode.from_string(row["profile"]) if row["profile"] else None,
                max_position=row["max_position"],
                max_shares=row["max_shares"],
                min_confidence=row["min_confidence"],
                notes=row["notes"] or "",
            )
            for row in cursor.fetchall()
        ]

    def get_active_symbols(self) -> List[str]:
        """
        Get list of active (non-disabled) approved ticker symbols.

        Returns:
            List of symbol strings
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT symbol FROM approved_tickers WHERE mode != 'disabled' ORDER BY symbol"
        )
        return [row["symbol"] for row in cursor.fetchall()]

    def seed_common_tickers(self):
        """Seed database with common stocks and leveraged ETFs."""
        # Common stocks
        stocks = [
            ("AAPL", "Apple Inc.", TickerType.STOCK),
            ("GOOGL", "Alphabet Inc.", TickerType.STOCK),
            ("MSFT", "Microsoft Corporation", TickerType.STOCK),
            ("TSLA", "Tesla Inc.", TickerType.STOCK),
            ("NVDA", "NVIDIA Corporation", TickerType.STOCK),
        ]

        for symbol, name, ticker_type in stocks:
            self.add_ticker_metadata(symbol=symbol, name=name, ticker_type=ticker_type)

        # Standard ETFs (1x)
        etfs_1x = [
            ("SPY", "SPDR S&P 500 ETF", "SPX", "State Street"),
            ("QQQ", "Invesco QQQ Trust", "NDX", "Invesco"),
            ("IWM", "iShares Russell 2000 ETF", "RUT", "iShares"),
            ("DIA", "SPDR Dow Jones Industrial Average ETF", "DJI", "State Street"),
        ]

        for symbol, name, underlying, provider in etfs_1x:
            self.add_ticker_metadata(
                symbol=symbol,
                name=name,
                ticker_type=TickerType.ETF_1X,
                underlying=underlying,
                multiplier=1.0,
                provider=provider,
            )

        # 2x Bull ETFs
        etfs_2x_bull = [
            ("SSO", "ProShares Ultra S&P500", "SPY", "ProShares"),
            ("QLD", "ProShares Ultra QQQ", "QQQ", "ProShares"),
            ("UWM", "ProShares Ultra Russell2000", "IWM", "ProShares"),
        ]

        for symbol, name, underlying, provider in etfs_2x_bull:
            self.add_ticker_metadata(
                symbol=symbol,
                name=name,
                ticker_type=TickerType.ETF_2X_BULL,
                underlying=underlying,
                multiplier=2.0,
                provider=provider,
            )

        # 3x Bull ETFs
        etfs_3x_bull = [
            ("UPRO", "ProShares UltraPro S&P500", "SPY", "ProShares"),
            ("TQQQ", "ProShares UltraPro QQQ", "QQQ", "ProShares"),
            ("SPXL", "Direxion Daily S&P 500 Bull 3X", "SPY", "Direxion"),
            ("TNA", "Direxion Daily Small Cap Bull 3X", "IWM", "Direxion"),
        ]

        for symbol, name, underlying, provider in etfs_3x_bull:
            self.add_ticker_metadata(
                symbol=symbol,
                name=name,
                ticker_type=TickerType.ETF_3X_BULL,
                underlying=underlying,
                multiplier=3.0,
                provider=provider,
            )

        # 2x Bear ETFs (inverse)
        etfs_2x_bear = [
            ("SDS", "ProShares UltraShort S&P500", "SPY", "ProShares"),
            ("QID", "ProShares UltraShort QQQ", "QQQ", "ProShares"),
        ]

        for symbol, name, underlying, provider in etfs_2x_bear:
            self.add_ticker_metadata(
                symbol=symbol,
                name=name,
                ticker_type=TickerType.ETF_2X_BEAR,
                underlying=underlying,
                multiplier=-2.0,
                provider=provider,
            )

        # 3x Bear ETFs (inverse)
        etfs_3x_bear = [
            ("SPXU", "ProShares UltraPro Short S&P500", "SPY", "ProShares"),
            ("SQQQ", "ProShares UltraPro Short QQQ", "QQQ", "ProShares"),
        ]

        for symbol, name, underlying, provider in etfs_3x_bear:
            self.add_ticker_metadata(
                symbol=symbol,
                name=name,
                ticker_type=TickerType.ETF_3X_BEAR,
                underlying=underlying,
                multiplier=-3.0,
                provider=provider,
            )

        self.conn.commit()
        logger.info("Seeded common tickers into database")

    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info("TickerDatabase connection closed")
