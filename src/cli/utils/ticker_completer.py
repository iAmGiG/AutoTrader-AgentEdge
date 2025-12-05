"""
Ticker Completer - Tab completion for stock ticker symbols.

Issue #399: Tab completion for tickers in CLI.
Issue #362: Arrow key history navigation.
Issue #436: Extracted from cli_session.py for modularity.

Provides autocomplete functionality for:
- Recently used tickers (persisted across sessions)
- Current position tickers
- Seed tickers from scanner_config.yaml

Works with readline/pyreadline3 for cross-platform support.
Note: Tab completion works in cmd.exe and Git Bash, NOT in PowerShell.
"""

import logging
import os
from typing import List, Optional

import yaml

logger = logging.getLogger(__name__)


# ============================================================================
# Environment Detection
# ============================================================================


def is_powershell() -> bool:
    """
    Detect if running in PowerShell (where readline doesn't work).

    PowerShell uses PSReadLine which has its own completion system.

    Returns:
        True if running in PowerShell
    """
    ps_indicators = [
        os.environ.get("PSModulePath"),
        os.environ.get("POWERSHELL_DISTRIBUTION_CHANNEL"),
    ]
    return any(ps_indicators)


# ============================================================================
# Readline Setup
# ============================================================================

READLINE_AVAILABLE = False
readline = None

try:
    import readline as _readline

    readline = _readline
    READLINE_AVAILABLE = True
except ImportError:
    # Windows may need pyreadline3
    try:
        import pyreadline3 as _readline

        readline = _readline
        READLINE_AVAILABLE = True
    except ImportError:
        pass

# Disable readline in PowerShell (it doesn't work there)
if READLINE_AVAILABLE and is_powershell():
    READLINE_AVAILABLE = False
    readline = None


# ============================================================================
# TickerCompleter Class
# ============================================================================


class TickerCompleter:
    """
    Tab completion for stock tickers.

    Provides autocomplete for:
    - Recently used tickers (persisted across sessions, auto-growing)
    - Current position tickers
    - Seed tickers from config (loaded from scanner_config.yaml on first run)

    All tickers are file-based for dynamic management.

    Usage:
        completer = TickerCompleter()
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")
    """

    # Fallback seed tickers if config loading fails
    _FALLBACK_SEED_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]

    def __init__(self, ticker_file: Optional[str] = None):
        """
        Initialize ticker completer.

        Args:
            ticker_file: Path to file for persisting recent tickers.
                        Defaults to ~/.autotrader_tickers
        """
        self.recent_tickers: List[str] = []
        self.position_tickers: List[str] = []
        self._completions: List[str] = []
        self._ticker_file = ticker_file or os.path.expanduser("~/.autotrader_tickers")
        self._seed_tickers = self._load_seed_tickers_from_config()
        self._load_recent_tickers()

    def _load_seed_tickers_from_config(self) -> List[str]:
        """
        Load seed tickers from scanner_config.yaml watchlist.

        Returns:
            List of seed ticker symbols
        """
        try:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "config_defaults",
                "scanner_config.yaml",
            )
            config_path = os.path.normpath(config_path)

            if not os.path.exists(config_path):
                return list(self._FALLBACK_SEED_TICKERS)

            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Extract all tickers from default_watchlist categories
            tickers = []
            watchlist = config.get("default_watchlist", {})
            for symbols in watchlist.values():
                if isinstance(symbols, list):
                    tickers.extend(symbols)

            return tickers if tickers else list(self._FALLBACK_SEED_TICKERS)

        except Exception as e:
            logger.debug(f"Could not load seed tickers from config: {e}")
            return list(self._FALLBACK_SEED_TICKERS)

    def _load_recent_tickers(self) -> None:
        """Load recently used tickers from file, seeding if first run."""
        try:
            if os.path.exists(self._ticker_file):
                with open(self._ticker_file, "r", encoding="utf-8") as f:
                    lines = [line.strip().upper() for line in f if line.strip()]
                    self.recent_tickers = lines[:100]  # Keep up to 100 tickers
            else:
                # First run - seed with tickers from scanner_config.yaml
                self.recent_tickers = list(self._seed_tickers)
                self.save_recent_tickers()
        except Exception as e:
            logger.debug(f"Could not load recent tickers: {e}")
            self.recent_tickers = list(self._seed_tickers)

    def save_recent_tickers(self) -> None:
        """Save recently used tickers to file."""
        try:
            with open(self._ticker_file, "w", encoding="utf-8") as f:
                for ticker in self.recent_tickers[:100]:  # Keep up to 100
                    f.write(f"{ticker}\n")
        except Exception as e:
            logger.debug(f"Could not save recent tickers: {e}")

    def add_ticker(self, ticker: str) -> None:
        """
        Add a ticker to recent list (moves to front if exists).

        Args:
            ticker: Stock ticker symbol to add
        """
        ticker = ticker.upper().strip()
        if not ticker or len(ticker) > 5 or not ticker.isalpha():
            return
        if ticker in self.recent_tickers:
            self.recent_tickers.remove(ticker)
        self.recent_tickers.insert(0, ticker)
        self.recent_tickers = self.recent_tickers[:100]
        # Auto-save when ticker is added
        self.save_recent_tickers()

    def set_position_tickers(self, tickers: List[str]) -> None:
        """
        Update list of tickers from current positions.

        Args:
            tickers: List of ticker symbols from positions
        """
        self.position_tickers = [t.upper() for t in tickers if t]

    def get_completions(self, text: str) -> List[str]:
        """
        Get ticker completions for given text.

        Args:
            text: Partial ticker text to complete

        Returns:
            List of matching ticker symbols
        """
        text = text.upper()
        # Combine recent + positions (no hardcoded list)
        all_tickers = set(self.recent_tickers + self.position_tickers)
        if not text:
            # Return recent + position tickers first (most relevant)
            return self.recent_tickers[:10]
        return sorted([t for t in all_tickers if t.startswith(text)])

    def complete(self, text: str, state: int) -> Optional[str]:
        """
        Readline completer function.

        This is called by readline for tab completion.

        Args:
            text: Current text being completed
            state: Completion state (0 for first match, etc.)

        Returns:
            Next completion match or None if exhausted
        """
        if state == 0:
            self._completions = self.get_completions(text)
        try:
            return self._completions[state]
        except IndexError:
            return None


# ============================================================================
# Module-level Instance
# ============================================================================

# Global ticker completer instance (created only if readline available)
_ticker_completer: Optional[TickerCompleter] = None

if READLINE_AVAILABLE:
    _ticker_completer = TickerCompleter()


def get_ticker_completer() -> Optional[TickerCompleter]:
    """
    Get the global ticker completer instance.

    Returns:
        TickerCompleter instance or None if readline unavailable
    """
    return _ticker_completer


def setup_readline_completion() -> bool:
    """
    Set up readline with ticker completion.

    Returns:
        True if setup succeeded, False otherwise
    """
    if not READLINE_AVAILABLE or not _ticker_completer:
        return False

    try:
        readline.set_completer(_ticker_completer.complete)
        readline.parse_and_bind("tab: complete")
        return True
    except Exception as e:
        logger.debug(f"Could not set up readline completion: {e}")
        return False


__all__ = [
    # Classes
    "TickerCompleter",
    # Functions
    "is_powershell",
    "get_ticker_completer",
    "setup_readline_completion",
    # State
    "READLINE_AVAILABLE",
    "readline",
]
