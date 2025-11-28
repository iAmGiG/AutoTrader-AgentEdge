"""
CLI Session - Interactive REPL for trading assistant.

Unified interactive CLI with LLM-driven routing for:
- Trade execution (buy/sell)
- Position alerts
- Scheduler management
- Portfolio status
"""

import asyncio
import json
import logging
import os
import platform
import sys
from typing import Optional

# Import safe_print for Unicode handling
from src.utils.safe_print import safe_print

# Arrow key history navigation (#362) and advanced readline features (#399)
try:
    import atexit
    import readline

    READLINE_AVAILABLE = True
except ImportError:
    # Windows may need pyreadline3
    try:
        import atexit

        import pyreadline3 as readline

        READLINE_AVAILABLE = True
    except ImportError:
        READLINE_AVAILABLE = False
        readline = None


# Issue #399: Ticker completer for tab completion
class TickerCompleter:
    """
    Tab completion for stock tickers.

    Provides autocomplete for:
    - Common tickers (SPY, QQQ, AAPL, etc.)
    - Recently used tickers (persisted across sessions)
    - Current position tickers
    """

    # Common tickers for quick access
    COMMON_TICKERS = [
        "SPY",
        "QQQ",
        "TQQQ",
        "SQQQ",
        "IWM",
        "DIA",
        "AAPL",
        "MSFT",
        "GOOGL",
        "GOOG",
        "AMZN",
        "META",
        "NVDA",
        "TSLA",
        "AMD",
        "INTC",
        "CRM",
        "ORCL",
        "ADBE",
        "NFLX",
        "JPM",
        "BAC",
        "GS",
        "MS",
        "V",
        "MA",
        "XOM",
        "CVX",
        "COP",
        "SLB",
        "UNH",
        "JNJ",
        "PFE",
        "ABBV",
        "MRK",
        "HD",
        "LOW",
        "TGT",
        "WMT",
        "COST",
        "DIS",
        "CMCSA",
        "T",
        "VZ",
    ]

    def __init__(self):
        self.recent_tickers = []
        self.position_tickers = []
        self._completions = []
        self._load_recent_tickers()

    def _load_recent_tickers(self):
        """Load recently used tickers from file."""
        ticker_file = os.path.expanduser("~/.autotrader_tickers")
        try:
            if os.path.exists(ticker_file):
                with open(ticker_file, "r") as f:
                    self.recent_tickers = [line.strip().upper() for line in f if line.strip()][
                        :20
                    ]  # Keep last 20
        except Exception:
            pass

    def save_recent_tickers(self):
        """Save recently used tickers to file."""
        ticker_file = os.path.expanduser("~/.autotrader_tickers")
        try:
            with open(ticker_file, "w") as f:
                for ticker in self.recent_tickers[:20]:
                    f.write(f"{ticker}\n")
        except Exception:
            pass

    def add_ticker(self, ticker: str):
        """Add a ticker to recent list (moves to front if exists)."""
        ticker = ticker.upper().strip()
        if not ticker or len(ticker) > 5:
            return
        if ticker in self.recent_tickers:
            self.recent_tickers.remove(ticker)
        self.recent_tickers.insert(0, ticker)
        self.recent_tickers = self.recent_tickers[:20]

    def set_position_tickers(self, tickers: list):
        """Update list of tickers from current positions."""
        self.position_tickers = [t.upper() for t in tickers if t]

    def get_completions(self, text: str) -> list:
        """Get ticker completions for given text."""
        text = text.upper()
        all_tickers = set(self.recent_tickers + self.position_tickers + self.COMMON_TICKERS)
        if not text:
            # Return recent + position tickers first
            return self.recent_tickers[:5] + self.position_tickers[:5]
        return sorted([t for t in all_tickers if t.startswith(text)])

    def complete(self, text: str, state: int):
        """Readline completer function."""
        if state == 0:
            self._completions = self.get_completions(text)
        try:
            return self._completions[state]
        except IndexError:
            return None


# Global ticker completer instance
_ticker_completer = TickerCompleter() if READLINE_AVAILABLE else None


# Add imports for new features
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
# Import CLI messages configuration
from config_defaults.message_loader import CLIMessages as MSG
from config_defaults.message_loader import (
    get_alert_severity_emoji,
    get_pl_emoji,
    get_signal_emoji,
    get_status_emoji,
)

from src.cli.account_commands import get_account_commands
from src.cli.help_system import HelpSystem
from src.core.trading_orchestrator import TradingOrchestrator
from src.trading.daily_scheduler import DailyScheduler
from src.trading.trading_cycle import CostEfficientTradeCycle

logger = logging.getLogger(__name__)


class CLISession:
    """
    Interactive CLI session for unified trading assistant.

    Handles:
    - Trade execution via TradingOrchestrator
    - Position alerts via PositionTracker
    - Scheduler management via DailyScheduler
    - Portfolio status via AlpacaAccountMonitor
    """

    def __init__(self, orchestrator: TradingOrchestrator):
        """
        Initialize CLI session with all features.

        Args:
            orchestrator: Wired TradingOrchestrator
        """
        self.orchestrator = orchestrator
        self.autonomy_mode = "confirm"  # or "auto"
        self.user_id = "cli_user"

        # Initialize help system (Issue #369)
        self.help_system = HelpSystem()

        # Initialize account commands (Issue #401)
        self.account_commands = get_account_commands()

        # Set up command history (#362)
        self._setup_history()

        # Initialize additional components for unified CLI
        # Share instances to reduce Alpaca client instantiations
        try:
            self.trading_cycle = CostEfficientTradeCycle()
            # Reuse trading_cycle's account_monitor instead of creating new one
            self.account_monitor = self.trading_cycle.account_monitor
            # Pass trading_cycle to scheduler to reuse instead of creating new one
            self.scheduler = DailyScheduler(trading_cycle=self.trading_cycle)

            logger.info("CLISession initialized with all features (shared instances)")
        except Exception as e:
            logger.warning(f"Some features unavailable: {e}")
            self.trading_cycle = None
            self.scheduler = None
            self.account_monitor = None

        # Load trading configuration for stop/target display
        self.trading_config = self._load_trading_config()

        # Educational tips for novice users
        self.trading_tips = {
            "buy_vs_short": (
                "BUY = You think the stock will go UP in value\n"
                "   Example: Buy META at $500, sell later at $550 → $50 profit per share\n\n"
                "SHORT = You think the stock will go DOWN in value (advanced/risky)\n"
                "   Example: Short META at $500, buy back at $450 → $50 profit per share\n"
                "   ⚠️  Warning: If stock goes UP while shorted, you lose money!"
            ),
            "position_required": (
                "To SELL a stock, you must own it first (have an open position).\n"
                "Think of it like selling your car - you can't sell what you don't own!"
            ),
            "signals": (
                "The analysis gives a signal based on technical indicators:\n"
                "  📈 BUY signal = indicators suggest price may go UP\n"
                "  📉 SELL signal = indicators suggest price may go DOWN\n\n"
                "⚠️  Remember: These are suggestions, not guarantees!"
            ),
            "entry_timing": (
                "NEW: You can specify WHEN you want to enter a trade:\n"
                "  'buy QQQ at a pullback' → Enters 2.5% below current price\n"
                "  'buy SPY on a dip' → Same as pullback, waits for lower price\n"
                "  'buy NVDA at a breakout' → Enters 1.5% above current (momentum)\n\n"
                "This helps you get better entry prices instead of buying at the current price!"
            ),
        }

    def _setup_history(self):
        """
        Set up readline features for CLI.

        Issue #362: Arrow key command history navigation
        Issue #399: Advanced readline features (tab completion, word deletion)

        Features enabled:
        - Up/down arrow keys for command history
        - Tab completion for stock tickers
        - Word deletion keybindings (Ctrl+W, Alt+Backspace)
        - History persisted to ~/.autotrader_history
        - Recent tickers persisted to ~/.autotrader_tickers
        """
        if not READLINE_AVAILABLE:
            logger.info("Readline not available - advanced CLI features disabled")
            return

        # Set up history file
        history_file = os.path.expanduser("~/.autotrader_history")

        # Load existing history
        if os.path.exists(history_file):
            try:
                readline.read_history_file(history_file)
                logger.debug(f"Loaded command history from {history_file}")
            except Exception as e:
                logger.warning(f"Could not load history file: {e}")

        # Set history length (default: 1000 commands)
        readline.set_history_length(1000)

        # Issue #399: Set up tab completion for tickers
        if _ticker_completer:
            readline.set_completer(_ticker_completer.complete)
            # Use tab for completion
            readline.parse_and_bind("tab: complete")
            # Show all completions on double-tab
            readline.parse_and_bind("set show-all-if-ambiguous on")
            # Case-insensitive completion
            readline.parse_and_bind("set completion-ignore-case on")
            logger.debug("Tab completion for tickers enabled")

        # Issue #399: Word deletion keybindings
        # Note: Some keybindings may not work on all terminals/platforms
        try:
            # Ctrl+W: Delete word backward (unix-word-rubout)
            readline.parse_and_bind('"\\C-w": unix-word-rubout')
            # Alt+Backspace: Delete word backward
            readline.parse_and_bind('"\\e\\C-h": backward-kill-word')
            # Alt+d: Delete word forward
            readline.parse_and_bind('"\\ed": kill-word')
            # Ctrl+U: Delete to beginning of line
            readline.parse_and_bind('"\\C-u": unix-line-discard')
            # Ctrl+K: Delete to end of line
            readline.parse_and_bind('"\\C-k": kill-line')
            logger.debug("Word deletion keybindings configured")
        except Exception as e:
            logger.debug(f"Some keybindings may not be available: {e}")

        # Save history and recent tickers on exit
        def save_on_exit():
            try:
                readline.write_history_file(history_file)
                logger.debug(f"Saved command history to {history_file}")
            except Exception as e:
                logger.warning(f"Could not save history file: {e}")
            if _ticker_completer:
                _ticker_completer.save_recent_tickers()

        atexit.register(save_on_exit)

        logger.info("Advanced CLI features enabled (history, tab completion)")

    def _load_trading_config(self) -> Optional[dict]:
        """
        Load trading configuration from YAML for stop/target calculations.

        Returns:
            Config dict or None if failed to load
        """
        try:
            import yaml

            # Get path to config_defaults/trading_config.yaml
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "..", "config_defaults", "trading_config.yaml")
            config_path = os.path.normpath(config_path)

            if not os.path.exists(config_path):
                logger.warning(f"Trading config not found at {config_path}")
                return None

            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded trading config from {config_path}")
                return config
        except Exception as e:
            logger.warning(f"Failed to load trading config: {e}")
            return None

    async def run(self):
        """
        Main REPL loop.

        Handles:
        - User input
        - Processing via orchestrator
        - Display suggestions
        - User confirmation
        - Execution
        """
        self._print_welcome()

        while True:
            try:
                # Get user input with mode indicator
                # Use ASCII on Windows to avoid encoding issues
                if platform.system() == "Windows":
                    mode_indicator = "AUTO" if self.autonomy_mode == "auto" else "CONFIRM"
                else:
                    mode_indicator = (
                        f"{MSG.EMOJI['auto_mode']} AUTO"
                        if self.autonomy_mode == "auto"
                        else f"{MSG.EMOJI['confirm_mode']} CONFIRM"
                    )
                user_input = input(f"\n({mode_indicator}) > ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    if not await self._handle_command(user_input):
                        break  # Exit
                    continue

                # Process trade request
                await self._process_request(user_input)

            except KeyboardInterrupt:
                print(MSG.EXIT_MESSAGE)
                break
            except Exception as e:
                # Use ASCII error prefix on Windows
                error_prefix = "[ERROR]" if platform.system() == "Windows" else MSG.EMOJI["error"]
                print(f"\n{error_prefix} Error: {e}")
                logger.error(f"CLI error: {e}", exc_info=True)
                # Don't show traceback to user - it's logged

    def _print_welcome(self):
        """Print welcome message."""
        print(MSG.WELCOME_BANNER)
        print(MSG.WELCOME_TITLE)
        print(MSG.WELCOME_BANNER)
        print(f"Mode: {self.autonomy_mode.upper()}")
        print(MSG.HELP_COMMANDS)

        # Issue #399: Update ticker completer with current positions
        self._update_position_tickers()

    def _update_position_tickers(self):
        """Update ticker completer with tickers from current positions."""
        if not _ticker_completer or not self.account_monitor:
            return
        try:
            positions = self.account_monitor.get_positions()
            tickers = [p.get("symbol") for p in positions if p.get("symbol")]
            _ticker_completer.set_position_tickers(tickers)
            logger.debug(f"Updated position tickers: {tickers}")
        except Exception as e:
            logger.debug(f"Could not update position tickers: {e}")

    async def _handle_command(self, command: str) -> bool:
        """
        Handle CLI commands.

        Args:
            command: Command string (starts with /)

        Returns:
            True to continue, False to exit
        """
        cmd = command.lower()

        if cmd == "/exit" or cmd == "/quit":
            return False

        elif cmd.startswith("/help"):
            # Issue #369: Interactive help system
            help_output = self.help_system.handle_help_command(command)
            safe_print(help_output)

        elif cmd == "/toggle":
            # Toggle between confirm and auto modes
            if self.autonomy_mode == "confirm":
                self.autonomy_mode = "auto"
                print(MSG.MODE_SWITCHED_AUTO)
            else:
                self.autonomy_mode = "confirm"
                print(MSG.MODE_SWITCHED_CONFIRM)

        elif cmd == "/schedule":
            # Enter scheduler management mode
            from src.cli.scheduler_cli import SchedulerCLI

            scheduler_cli = SchedulerCLI(self.scheduler)
            await scheduler_cli.run()

        elif cmd == "/tips" or cmd == "/learn":
            # Show educational trading tips
            self._show_trading_tips()

        else:
            print(MSG.UNKNOWN_COMMAND.format(command=command))
            print(MSG.USE_HELP)

        return True

    def _show_trading_tips(self):
        """Display educational trading tips for beginners."""
        safe_print("\n" + "=" * 70)
        safe_print("📚 TRADING BASICS FOR BEGINNERS")
        safe_print("=" * 70)

        safe_print("\n1️⃣  BUY vs SHORT (Long vs Short)")
        safe_print("-" * 70)
        safe_print(self.trading_tips["buy_vs_short"])

        safe_print("\n2️⃣  Understanding Signals")
        safe_print("-" * 70)
        safe_print(self.trading_tips["signals"])

        safe_print("\n3️⃣  Why You Need a Position to SELL")
        safe_print("-" * 70)
        safe_print(self.trading_tips["position_required"])

        safe_print("\n4️⃣  Entry Timing (NEW!)")
        safe_print("-" * 70)
        safe_print(self.trading_tips["entry_timing"])

        safe_print("\n💡 QUICK TIPS:")
        safe_print("-" * 70)
        safe_print("• Start small: Test with small amounts until you understand")
        safe_print("• Use CONFIRM mode: Always review before executing trades")
        safe_print("• Ask questions: Type naturally, the system will understand")
        safe_print("• Check analysis: Choose 'review' to see analysis without trading")
        safe_print("• Try timing: 'buy at a pullback' for better entry prices")
        safe_print("\n" + "=" * 70)

    async def _classify_intent(self, user_input: str) -> dict:
        """
        Use LLM to classify user intent and resolve company names to tickers dynamically.

        Returns:
            {
                'intent': 'trade_request' | 'portfolio_status' | 'open_orders' | 'alerts' | 'scheduler',
                'ticker': str | None,
                'company_name': str | None,
                'action': 'buy' | 'sell' | 'status' | None,
                'confidence': float
            }

        Issue #361: LLM-based intent classification with company name resolution
        Uses gpt-4o-mini (cheapest model) for structured output.
        """

        try:
            lower_input = user_input.lower()

            # Check if this looks like a trade request with a company/ticker name
            has_buy = any(
                word in lower_input for word in ["buy", "purchase", "long", "sell", "short"]
            )

            intent = "unknown"
            action = None
            ticker = None
            company_name = None
            confidence = 0.0

            # First pass: Pattern detection for intent (fast)
            if any(word in lower_input for word in ["buy", "purchase", "long"]):
                intent = "trade_request"
                action = "buy"
                confidence = 0.7

            elif any(word in lower_input for word in ["sell", "short"]):
                intent = "trade_request"
                action = "sell"
                confidence = 0.7

            elif any(
                word in lower_input
                for word in [
                    "position",
                    "holding",
                    "portfolio",
                    "account",
                    "check",
                    "show",
                    "status",
                ]
            ):
                intent = "portfolio_status"
                confidence = 0.85

            elif any(word in lower_input for word in ["order", "pending", "open"]):
                intent = "open_orders"
                confidence = 0.85

            elif any(word in lower_input for word in ["alert", "watch"]):
                intent = "alerts"
                confidence = 0.85

            elif any(
                word in lower_input for word in ["schedule", "scheduler", "daemon", "background"]
            ):
                intent = "scheduler"
                confidence = 0.85

            elif any(
                word in lower_input
                for word in ["account", "switch", "list account", "change account", "accounts"]
            ):
                # Issue #401: Account management
                intent = "account_management"
                confidence = 0.85

            elif any(
                word in lower_input
                for word in [
                    "timeframe",
                    "interval",
                    "change timeframe",
                    "set timeframe",
                    "5m",
                    "15m",
                    "30m",
                    "1h",
                    "4h",
                    "1d",
                    "1w",
                    "1m",
                ]
            ):
                # Issue #365: Timeframe management
                intent = "timeframe_management"
                confidence = 0.85

            elif any(word in lower_input for word in ["help", "what", "how", "command"]):
                intent = "help"
                confidence = 0.85

            # If it's a trade request, use LLM to extract/resolve ticker
            if intent == "trade_request" and (action or has_buy):
                ticker, company_name = await self._resolve_ticker_with_llm(user_input)
                if ticker:
                    confidence = 0.95  # High confidence if LLM resolved it
                else:
                    confidence = 0.7  # Lower if couldn't resolve

            logger.debug(
                f"Classified intent: {intent} (action={action}, ticker={ticker}, "
                f"company={company_name}, confidence={confidence})"
            )

            return {
                "intent": intent,
                "ticker": ticker,
                "company_name": company_name,
                "action": action,
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"Error classifying intent: {e}", exc_info=True)
            return {
                "intent": "unknown",
                "ticker": None,
                "company_name": None,
                "action": None,
                "confidence": 0.0,
            }

    async def _resolve_ticker_with_llm(self, user_input: str) -> tuple:
        """
        Use LLM (gpt-4o-mini) to extract company name and resolve to ticker.

        Uses cheap model to dynamically resolve any company name to ticker.
        Cost: ~$0.15 per 1M tokens with gpt-4o-mini.

        Args:
            user_input: User's command (e.g., "buy apple at $150")

        Returns:
            (ticker, company_name) tuple. Both None if couldn't resolve.
        """
        try:
            # Construct a lean prompt for the cheap LLM
            system_prompt = """You are a stock ticker resolver. Extract the company name from the user's input
and resolve it to its stock ticker symbol.

Return ONLY valid JSON with no extra text:
{
    "company_name": "Apple Inc.",
    "ticker": "AAPL",
    "found": true
}

If no company/ticker found:
{
    "company_name": null,
    "ticker": null,
    "found": false
}

Scope: Only resolve to real, tradable companies. Return found=false for ambiguous/invalid inputs."""

            user_prompt = f"Extract ticker from: {user_input}"

            # Call the LLM through the orchestrator
            if self.orchestrator and self.orchestrator.input_parser:
                try:
                    # Use the parser's LLM service with gpt-4o-mini (cheapest)
                    llm_service = self.orchestrator.input_parser.llm_service

                    response = await llm_service.call_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model="gpt-4o-mini",  # Cheapest OpenAI model
                        timeout=2.0,  # 2 second timeout
                    )

                    # Parse the response
                    if isinstance(response, str):
                        data = json.loads(response)
                    else:
                        data = response

                    if data.get("found"):
                        ticker = data.get("ticker")
                        # Issue #399: Track resolved ticker for autocomplete
                        if ticker and _ticker_completer:
                            _ticker_completer.add_ticker(ticker)
                        return ticker, data.get("company_name")

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM response as JSON: {response}")
                except asyncio.TimeoutError:
                    logger.warning("LLM call timed out, falling back to pattern matching")
                except Exception as e:
                    logger.warning(f"LLM resolution failed: {e}")

            # Fallback: Try pattern matching for common formats
            # User might type "$AAPL" or just "AAPL"
            import re

            ticker_match = re.search(r"([A-Z]{1,5})", user_input)
            if ticker_match:
                potential_ticker = ticker_match.group(1)
                # Basic validation: 1-5 letters
                if 1 <= len(potential_ticker) <= 5 and potential_ticker.isalpha():
                    # Issue #399: Track resolved ticker for autocomplete
                    if _ticker_completer:
                        _ticker_completer.add_ticker(potential_ticker)
                    return potential_ticker, None

            return None, None

        except Exception as e:
            logger.error(f"Error resolving ticker with LLM: {e}")
            return None, None

    async def _process_request(self, user_input: str):
        """
        Process user request with LLM-based intelligent routing.

        The LLM parser determines if this is a status_query or trade request.
        We use minimal keyword hints only for scheduler/alerts (system features).

        Args:
            user_input: User's natural language input
        """
        input_lower = user_input.lower()

        # Only use keyword routing for system-specific features (scheduler, alerts)
        # Let LLM parser handle trade vs status_query distinction

        if any(
            word in input_lower
            for word in ["scheduler", "schedule", "execution", "morning", "evening", "routine"]
        ):
            # Scheduler queries
            await self._handle_scheduler_request(user_input)

        elif (
            any(word in input_lower for word in ["alert", "approaching"]) and "check" in input_lower
        ):
            # Alert queries
            await self._handle_alerts_request(user_input)

        elif any(word in input_lower for word in ["cancel", "delete", "remove"]) and any(
            word in input_lower for word in ["order", "all"]
        ):
            # Order cancellation (Issue #360)
            await self._handle_cancel_request(user_input)

        elif any(
            phrase in input_lower
            for phrase in ["execution mode", "execution-mode", "set execution", "show execution"]
        ):
            # Execution mode management (Issue #332)
            await self._handle_execution_mode_request(user_input)

        elif any(
            phrase in input_lower
            for phrase in [
                "list account",
                "show account",
                "switch account",
                "use account",
                "change account",
                "current account",
                "refresh account",
            ]
        ):
            # Account management (Issue #401)
            await self._handle_account_request(user_input)

        elif any(
            phrase in input_lower
            for phrase in [
                "timeframe",
                "interval",
                "change timeframe",
                "set timeframe",
                "current timeframe",
                "show timeframe",
                "list timeframe",
                "5m",
                "15m",
                "30m",
                "1h",
                "4h",
                "1d",
                "1w",
                "1m",
            ]
        ):
            # Timeframe management (Issue #365)
            await self._handle_timeframe_request(user_input)

        else:
            # For everything else, let LLM parser decide: trade vs status_query
            # This includes: orders, positions, portfolio, and actual trades
            await self._handle_trade_or_status_request(user_input)

    def _reformat_bare_ticker(self, user_input: str) -> str:
        """
        Check if input is a bare ticker symbol and reformat if needed.

        Args:
            user_input: User input string

        Returns:
            Reformatted string (e.g., "meta" → "analyze META") or original input
        """
        input_stripped = user_input.strip().upper()
        if input_stripped.isalpha() and 1 <= len(input_stripped) <= 5:
            # Looks like a bare ticker - reformat as explicit trade request
            return f"analyze {input_stripped}"
        return user_input

    async def _handle_trade_or_status_request(self, user_input: str):
        """
        Use LLM parser to determine if this is a trade or status query.

        The LLM will classify as:
        - "trade" → buy/sell/analyze specific ticker (e.g., "buy AAPL", "is SPY good?")
        - "status_query" → asking about orders/positions/portfolio (e.g., "any open orders?")

        Args:
            user_input: User's natural language input
        """
        try:
            # Check if input looks like a bare ticker symbol (e.g., "ibm", "meta", "SPY")
            # Reformat to explicit request to prevent LLM parser misclassification
            formatted_input = self._reformat_bare_ticker(user_input)
            if formatted_input != user_input:
                # Was a bare ticker, now reformatted
                await self._handle_trade_request(formatted_input)
                return

            # Let LLM parser classify the request type
            request = await self.orchestrator.parser.parse(user_input, self.user_id)

            if request.request_type == "status_query":
                # Status query detected - route based on content
                input_lower = user_input.lower()

                # Issue #348: Route stop/target queries with symbols to order details
                if any(
                    phrase in input_lower
                    for phrase in [
                        "stop level on",
                        "stop price on",
                        "stop loss on",
                        "stop on",
                        "target price on",
                        "take profit on",
                        "tp on",
                        "exit orders on",
                        "bracket orders on",
                        "orders for",
                        "show orders for",
                    ]
                ):
                    # Specific symbol stop/target query → show detailed orders
                    await self._handle_position_orders(user_input)
                elif any(word in input_lower for word in ["order", "orders"]):
                    await self._handle_orders_request(user_input)
                elif any(
                    phrase in input_lower
                    for phrase in ["stop", "target", "take profit", "exit level", "stop loss"]
                ):
                    # Generic stop/target queries → show portfolio with exit levels
                    await self._handle_portfolio_request(user_input)
                elif any(
                    word in input_lower for word in ["position", "positions", "holding", "holdings"]
                ):
                    await self._handle_portfolio_request(user_input)
                elif any(
                    word in input_lower
                    for word in [
                        "portfolio",
                        "account",
                        "balance",
                        "buying power",
                        "equity",
                        "cash",
                    ]
                ):
                    await self._handle_portfolio_request(user_input)
                else:
                    # Parser said status_query but no keywords matched
                    # Likely just a ticker (e.g., "ibm") - treat as trade request
                    await self._handle_trade_request(user_input)
            else:
                # Trade request → process through orchestrator
                await self._handle_trade_request(user_input)

        except Exception as e:
            logger.error(f"Error routing request: {e}", exc_info=True)
            # Fallback to trade handler (reformat bare tickers first)
            formatted_input = self._reformat_bare_ticker(user_input)
            await self._handle_trade_request(formatted_input)

    async def _handle_trade_request(self, user_input: str):
        """
        Process user trade request via orchestrator.

        Issue #347: Respects user intent - when user says "buy", we show "BUY (as requested)"
        and treat signals as context, not override.

        Args:
            user_input: User's natural language input
        """
        print(MSG.ANALYZING_TRADE)

        try:
            # Issue #347: Detect user intent EARLY so we can respect it
            original_input = user_input.lower().strip()
            user_intent = self._detect_user_intent(original_input)

            # Step 1: Process request via orchestrator
            decision = await self.orchestrator.process_request(user_input, self.user_id)

            # Step 2: Check position context before suggestion
            position = self._check_position_for_ticker(decision.suggestion.ticker)

            # Step 2a: Display position context
            self._display_position_context(
                decision.suggestion.ticker, position, decision.suggestion.signal.value
            )

            # Step 2b: Check for signal vs user intent mismatch
            # If analyzer suggests SELL but no position exists, check user's explicit intent
            if decision.suggestion.signal.value.upper() == "SELL" and not position:
                # Check if user explicitly wants to BUY/LONG (override signal)
                explicit_buy_indicators = [
                    "buy",
                    "long",
                    "go long",
                    "going long",
                    "bullish",
                    "bet it goes up",
                    "think it will rise",
                    "upside",
                    # Note: 'get ' with space to avoid 'target', 'forget'
                    "get ",
                    "acquire",
                    "purchase",
                    "pick up",
                    "grab",
                ]
                user_wants_buy = any(
                    indicator in original_input for indicator in explicit_buy_indicators
                )

                # Check if user explicitly wants to SELL/SHORT
                explicit_sell_indicators = [
                    # Trading terms
                    "sell",
                    "short",
                    "shorting",
                    "go short",
                    "exit",
                    # Layman terms for selling/closing
                    "close",
                    "get out",
                    "dump",
                    "liquidate",
                    "cash out",
                    # Explicit bearish intent
                    "bet against",
                    "profit from decline",
                    "make money when it falls",
                ]
                user_wants_sell = any(
                    indicator in original_input for indicator in explicit_sell_indicators
                )

                if user_wants_buy:
                    # User explicitly wants to go LONG despite SELL signal
                    # Human-in-loop: respect their intent but show them the conflict
                    print(f"\n{MSG.EMOJI.get('warning', '⚠️')} SIGNAL CONFLICT DETECTED")
                    print("   → You requested: LONG (BUY) position")
                    print("   → Technical analysis suggests: SHORT (SELL)")
                    print(
                        f"\n📊 Technical Indicators (based on {decision.suggestion.reasoning[0] if decision.suggestion.reasoning else 'MACD+RSI'}):"
                    )

                    # Show the actual technical analysis
                    self._display_suggestion(
                        decision.suggestion, position, override_mode="USER_OVERRIDE_LONG"
                    )

                    print("\n💡 Human-in-Loop Decision:")
                    print("   → The system recommends SELL, but you want to go LONG")
                    print("   → This could be based on news, fundamentals, or your own analysis")
                    print("   → Remember: Technical indicators are backward-looking")

                    proceed = (
                        input(
                            f"\n   Do you still want to BUY {decision.suggestion.ticker}? [yes/no]: "
                        )
                        .strip()
                        .lower()
                    )

                    if proceed in ["yes", "y", "1"]:
                        # User confirms override
                        # Don't reprocess! That causes infinite loop. Instead, flip the signal and continue.
                        print(
                            f"\n{MSG.EMOJI['info']} ✅ User override confirmed - placing BUY order"
                        )
                        print("   → Overriding SELL signal from technical analysis")

                        # Flip the signal to BUY (user override)
                        from src.core.models import Signal

                        decision.suggestion.signal = Signal.BUY

                        # Invert stop/target for BUY (were calculated for SELL)
                        # For BUY: stop < entry, target > entry
                        # For SELL: stop > entry, target < entry
                        entry = decision.suggestion.entry_price
                        old_stop = decision.suggestion.stop_loss
                        old_target = decision.suggestion.take_profit

                        # Calculate BUY stop/target (inverse of SELL)
                        stop_distance = abs(old_stop - entry)
                        target_distance = abs(old_target - entry)

                        decision.suggestion.stop_loss = round(entry - stop_distance, 2)
                        decision.suggestion.take_profit = round(entry + target_distance, 2)

                        print("\n   📊 Adjusted for BUY:")
                        print(f"      Entry:  ${entry:.2f}")
                        print(
                            f"      Stop:   ${decision.suggestion.stop_loss:.2f} ({self._calc_pct(entry, decision.suggestion.stop_loss):.1f}%)"
                        )
                        print(
                            f"      Target: ${decision.suggestion.take_profit:.2f} ({self._calc_pct(entry, decision.suggestion.take_profit):.1f}%)"
                        )
                        print(f"      Quantity: {decision.suggestion.recommended_quantity} shares")

                        # Continue to display and confirmation (no return, fall through)
                    else:
                        print(
                            f"\n{MSG.EMOJI['info']} Order cancelled. You can review alternatives:"
                        )
                        print(
                            f"   • Type 'review {decision.suggestion.ticker}' for detailed analysis"
                        )
                        print(
                            f"   • Type 'short {decision.suggestion.ticker}' to follow the SELL signal"
                        )
                        return

                elif not user_wants_sell:
                    # User didn't explicitly ask to sell - they likely asked for analysis
                    # Examples: "pltr", "review pltr", "analyze pltr at market price", "is pltr good?"
                    # Ask for clarification using simple language
                    print(
                        f"\n{MSG.EMOJI.get('question', '❓')} The analysis suggests {decision.suggestion.ticker} might go DOWN, but you don't own any shares yet."
                    )
                    print("\n   What would you like to do?")
                    print("   1. BUY shares (bet the stock will go UP)")
                    print("   2. SHORT shares (bet the stock will go DOWN - advanced strategy)")
                    print("   3. Just see the analysis (don't trade)")

                    clarification = (
                        input("\n   Your choice [1/2/3 or buy/short/review]: ").strip().lower()
                    )

                    # Accept various formats: numbers, keywords, or full words
                    if clarification in ["1", "buy", "b", "long", "l", "up", "bullish"]:
                        # User wants to buy - flip signal in place (don't reprocess!)
                        print(
                            f"\n{MSG.EMOJI['info']} Got it! Preparing BUY order for {decision.suggestion.ticker}..."
                        )

                        # Flip the signal to BUY
                        from src.core.models import Signal

                        decision.suggestion.signal = Signal.BUY

                        # Invert stop/target for BUY (were calculated for SELL)
                        entry = decision.suggestion.entry_price
                        old_stop = decision.suggestion.stop_loss
                        old_target = decision.suggestion.take_profit

                        stop_distance = abs(old_stop - entry)
                        target_distance = abs(old_target - entry)

                        decision.suggestion.stop_loss = round(entry - stop_distance, 2)
                        decision.suggestion.take_profit = round(entry + target_distance, 2)

                        print("\n   📊 Adjusted for BUY:")
                        print(f"      Entry:  ${entry:.2f}")
                        print(
                            f"      Stop:   ${decision.suggestion.stop_loss:.2f} ({self._calc_pct(entry, decision.suggestion.stop_loss):.1f}%)"
                        )
                        print(
                            f"      Target: ${decision.suggestion.take_profit:.2f} ({self._calc_pct(entry, decision.suggestion.take_profit):.1f}%)"
                        )
                        print(f"      Quantity: {decision.suggestion.recommended_quantity} shares")

                        # Continue to display and confirmation (no return, fall through)
                    elif clarification in ["2", "short", "s", "down", "bearish", "sell"]:
                        # User explicitly wants to short - explain limitation
                        print(
                            f"\n{MSG.EMOJI['warning']} SHORT SELLING is not currently supported by this system."
                        )
                        print("   ℹ️  Short selling = betting a stock will go down (advanced/risky)")
                        print(
                            "   → This system only supports buying stocks (betting they'll go up)"
                        )
                        print("   → Suggestion cancelled")
                        return
                    elif clarification in [
                        "3",
                        "review",
                        "r",
                        "analysis",
                        "just show",
                        "view",
                        "look",
                    ]:
                        # Just show the analysis, don't execute
                        print(
                            f"\n{MSG.EMOJI['info']} Showing analysis for {decision.suggestion.ticker} (information only, no trade)"
                        )
                        self._display_suggestion(decision.suggestion, position)
                        print(
                            f"\n   💡 Tip: If you want to trade on this analysis, type 'buy {decision.suggestion.ticker}' or 'short {decision.suggestion.ticker}'"
                        )
                        return
                    else:
                        # Unclear response or cancel
                        print(f"\n{MSG.EMOJI['info']} No problem! Cancelled.")
                        print(
                            f"   💡 Tip: You can be specific next time, e.g., 'buy {decision.suggestion.ticker}' or 'analyze {decision.suggestion.ticker}'"
                        )
                        return
                else:
                    # User explicitly asked to sell/close - block it since no position exists
                    print(
                        f"\n{MSG.EMOJI['error']} Cannot SELL or CLOSE position in {decision.suggestion.ticker}"
                    )
                    print(
                        f"   → You don't currently own any shares of {decision.suggestion.ticker}"
                    )
                    print("   → To sell a stock, you must buy it first")
                    print(
                        f"\n   💡 Did you mean to SHORT {decision.suggestion.ticker}? (bet it will go down)"
                    )
                    print("      Short selling is not currently supported by this system.")
                    return  # Exit early

            elif decision.suggestion.signal.value.upper() == "SELL" and position:
                # Position exists - show brief warning reminder
                print(
                    f"\n{MSG.EMOJI['warning']} SELL will close your position in {decision.suggestion.ticker}"
                )

            # Step 3: Display suggestion
            # Issue #347: Determine override mode based on user intent
            override_mode = None
            if user_intent == "buy":
                override_mode = "USER_OVERRIDE_LONG"
            elif user_intent == "sell":
                override_mode = "USER_OVERRIDE_SHORT"
            self._display_suggestion(decision.suggestion, position, override_mode)

            # Step 3: Get user confirmation (if confirm mode)
            if self.autonomy_mode == "confirm":
                approved = self._get_confirmation()
                decision.approved = approved
            else:
                # Auto mode - execute immediately
                decision.approved = True
                print(MSG.AUTO_EXECUTING)

            # Step 4: Execute if approved
            if decision.approved:
                result = await self.orchestrator.execute_decision(decision)
                self._display_result(result)

                # Issue #385: Update local state with stop/target immediately after trade
                self._update_local_state_after_trade(decision, result)
            else:
                print(MSG.TRADE_CANCELLED)

        except Exception as e:
            error_msg = str(e)

            # Provide helpful suggestions for common errors
            if "asset" in error_msg.lower() and "not found" in error_msg.lower():
                print(MSG.ERROR_INVALID_TICKER)
            elif "invalid request" in error_msg.lower() and "ticker=''" in error_msg.lower():
                # Empty ticker from garbage input
                print(MSG.ERROR_GARBAGE_INPUT)
            else:
                print(MSG.ERROR_PROCESSING.format(error=e))

            # Log error at DEBUG level only (not shown to users)
            logger.debug(f"Request processing error: {e}", exc_info=True)

    def _check_position_for_ticker(self, ticker: str) -> Optional[dict]:
        """
        Check if user currently holds a position in the ticker.

        Args:
            ticker: Stock symbol to check

        Returns:
            Position dict if found, None otherwise
        """
        try:
            if not self.account_monitor:
                return None

            positions = self.account_monitor.get_positions()
            return next((p for p in positions if p.get("symbol") == ticker), None)
        except Exception as e:
            logger.warning(f"Failed to check position for {ticker}: {e}")
            return None

    def _detect_user_intent(self, user_input: str) -> Optional[str]:
        """
        Issue #347: Detect explicit user intent from input.

        Returns:
            "buy" if user explicitly wants to buy/go long
            "sell" if user explicitly wants to sell/close
            None if no explicit intent (just querying/analyzing)
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
            "get ",
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

    def _display_position_context(self, ticker: str, position: Optional[dict], signal: str):
        """
        Display current position context before showing suggestion.

        Args:
            ticker: Stock symbol
            position: Position dict if exists, None otherwise
            signal: Signal type (BUY/SELL/HOLD)
        """
        print(f"\n{'='*60}")
        print(f"📊 Position Context: {ticker}")
        print(f"{'='*60}")

        if position:
            # Calculate metrics
            qty = int(position.get("qty", 0))
            avg_entry = float(position.get("avg_entry_price", 0))
            market_value = float(position.get("market_value", 0))
            current_price = (market_value / qty) if qty > 0 else 0.0
            unrealized_pl = float(position.get("unrealized_pl", 0))
            unrealized_plpc = float(position.get("unrealized_plpc", 0)) * 100

            # Use fallback for entry price if needed
            if avg_entry == 0.0:
                cost_basis = float(position.get("cost_basis", 0))
                avg_entry = (cost_basis / qty) if qty > 0 else 0.0

            pl_emoji = get_pl_emoji(unrealized_pl)

            print(f"   Current Position: {qty} shares @ ${avg_entry:.2f} (avg entry)")
            print(f"   Current Price: ${current_price:.2f}")
            print(f"   {pl_emoji} Unrealized P/L: ${unrealized_pl:+.2f} ({unrealized_plpc:+.2f}%)")
            print(f"   Market Value: ${market_value:,.2f}")
        else:
            print(f"   ℹ️  No position in {ticker} (0 shares)")

        print(f"{'='*60}\n")

    def _display_suggestion(
        self, suggestion, position: Optional[dict] = None, override_mode: Optional[str] = None
    ):
        """
        Display trade suggestion to user.

        Args:
            suggestion: TradeSuggestion object
            position: Optional position dict for additional context
            override_mode: Optional override indicator ("USER_OVERRIDE_LONG", "USER_OVERRIDE_SHORT")
        """
        print("\n" + MSG.SUGGESTION_SEPARATOR)
        print(MSG.SUGGESTION_HEADER.format(ticker=suggestion.ticker, price=suggestion.entry_price))
        print(MSG.SUGGESTION_SEPARATOR)

        # Issue #347: Respect user intent when signals disagree
        # Signal display prioritizes user's explicit request
        signal_emoji = get_signal_emoji(suggestion.signal.value)

        if override_mode == "USER_OVERRIDE_LONG":
            # User wants BUY but signals say something else
            print("👤 ACTION: ⬆️ BUY (as requested)")
            if suggestion.signal.value.upper() != "BUY":
                print(f"   📊 Signals suggest: {signal_emoji} {suggestion.signal.value.upper()}")
                print("   ℹ️  Proceeding with your requested action")
        elif override_mode == "USER_OVERRIDE_SHORT":
            # User wants SELL but signals say something else
            print("👤 ACTION: ⬇️ SELL (as requested)")
            if suggestion.signal.value.upper() != "SELL":
                print(f"   📊 Signals suggest: {signal_emoji} {suggestion.signal.value.upper()}")
                print("   ℹ️  Proceeding with your requested action")
        else:
            # No explicit user intent - show signal recommendation
            print(
                MSG.SIGNAL_DISPLAY.format(
                    emoji=signal_emoji, signal=suggestion.signal.value.upper()
                )
            )

        print(MSG.CONFIDENCE_DISPLAY.format(confidence=suggestion.confidence))

        # Get current timeframe for display (Issue #365)
        from src.cli.timeframe_commands import get_timeframe_commands

        try:
            timeframe = get_timeframe_commands().manager.get_current_timeframe()
        except Exception:
            timeframe = "1d"  # Fallback to default

        # Technical analysis
        print(MSG.ANALYSIS_HEADER.format(timeframe=timeframe))
        for reason in suggestion.reasoning:
            print(MSG.ANALYSIS_ITEM.format(reason=reason))

        # Determine trade direction
        direction = self._get_trade_direction(suggestion.signal)

        # Entry plan
        print(MSG.ENTRY_PLAN_HEADER)
        print(
            MSG.ENTRY_PLAN.format(
                direction=direction,
                entry=suggestion.entry_price,
                stop=suggestion.stop_loss,
                stop_pct=self._calc_pct(suggestion.entry_price, suggestion.stop_loss),
                target=suggestion.take_profit,
                target_pct=self._calc_pct(suggestion.entry_price, suggestion.take_profit),
                qty=suggestion.recommended_quantity,
                tif=suggestion.time_in_force.value.upper(),
            )
        )

        # Portfolio impact
        print(MSG.PORTFOLIO_IMPACT_HEADER)
        print(
            MSG.PORTFOLIO_IMPACT.format(
                trade_value=suggestion.recommended_quantity * suggestion.entry_price,
                portfolio_pct=suggestion.portfolio_pct,
                max_loss=suggestion.max_loss_usd,
                risk_reward=suggestion.risk_reward_ratio,
            )
        )

        # Warnings
        if suggestion.warnings:
            print(MSG.WARNINGS_HEADER)
            for warning in suggestion.warnings:
                print(MSG.WARNING_ITEM.format(warning=warning))

    def _get_trade_direction(self, signal: "Signal") -> str:
        """
        Format trade direction for display.

        Args:
            signal: Trading signal (BUY/SELL/HOLD)

        Returns:
            Formatted direction string (e.g., "BUY (LONG)", "SELL (SHORT)")
        """
        from src.core.models import Signal

        if signal == Signal.BUY:
            return "BUY (LONG)"
        elif signal == Signal.SELL:
            return "SELL (SHORT)"
        else:
            return "HOLD"

    def _get_confirmation(self) -> bool:
        """
        Get user confirmation.

        Returns:
            True if user approves, False otherwise
        """
        while True:
            response = input(MSG.CONFIRM_PROMPT).strip().lower()

            if response in ["yes", "y"]:
                return True
            elif response in ["no", "n"]:
                return False
            else:
                print(MSG.CONFIRM_INVALID)

    def _display_result(self, result):
        """
        Display execution result.

        Args:
            result: OrderResult object
        """
        print("\n" + MSG.RESULT_SEPARATOR)

        if result.success:
            print(MSG.ORDER_SUCCESS_HEADER)
            print(
                MSG.ORDER_SUCCESS.format(
                    qty=result.quantity,
                    ticker=result.ticker,
                    entry_id=result.entry_order_id,
                    stop_id=result.stop_order_id,
                    target_id=result.target_order_id,
                    message=result.message,
                )
            )
        else:
            print(MSG.ORDER_FAILED_HEADER)
            print(MSG.ORDER_FAILED.format(message=result.message))
            if result.error:
                print(MSG.ORDER_ERROR.format(error=result.error))

        print(MSG.RESULT_SEPARATOR)

    def _update_local_state_after_trade(self, decision, result):
        """
        Update local state (cost_efficient_positions.json) after successful trade.

        This ensures stop/target prices are immediately visible in CLI order displays,
        rather than waiting for the next reconciliation routine.

        Issue #385: Bracket Order Stop-Loss Not Logged to Local State on Placement

        Args:
            decision: TradeDecision with suggestion containing stop/target prices
            result: OrderResult from execution
        """
        if not result.success:
            return

        if not self.trading_cycle:
            logger.warning("No trading_cycle available - cannot update local state")
            return

        try:
            from src.utils.date_utils import now_iso

            suggestion = decision.suggestion
            symbol = suggestion.ticker
            quantity = result.quantity or suggestion.recommended_quantity

            # Add or update position in local state
            self.trading_cycle.local_state["positions"][symbol] = {
                "entry_price": suggestion.entry_price,
                "quantity": quantity,
                "entry_time": now_iso(),
                "source": "CLI_TRADE",
                "stop_price": suggestion.stop_loss,
                "target_price": suggestion.take_profit,
                "order_id": result.entry_order_id,
            }

            # Save state immediately
            self.trading_cycle.save_local_state()

            logger.info(
                f"Updated local state for {symbol}: "
                f"stop=${suggestion.stop_loss:.2f}, target=${suggestion.take_profit:.2f}"
            )

        except Exception as e:
            logger.warning(f"Failed to update local state after trade: {e}")

    def _calc_pct(self, base: float, value: float) -> float:
        """Calculate percentage change."""
        return ((value - base) / base) * 100.0

    def _get_stop_loss_pct(self) -> float:
        """
        Get configured stop loss percentage from trading config.

        Returns:
            Stop loss percentage (default: 0.05 = 5%)
        """
        if not self.trading_config:
            return 0.05  # Default fallback

        try:
            exits = self.trading_config.get("strategy_parameters", {}).get("exits", {})
            default_strategy = exits.get("default", "balanced")
            strategy_config = exits.get(default_strategy, {})
            return strategy_config.get("stop_loss", 0.05)
        except Exception as e:
            logger.warning(f"Failed to get stop_loss from config: {e}")
            return 0.05

    def _get_take_profit_pct(self) -> float:
        """
        Get configured take profit percentage from trading config.

        Returns:
            Take profit percentage (default: 0.08 = 8%)
        """
        if not self.trading_config:
            return 0.08  # Default fallback

        try:
            exits = self.trading_config.get("strategy_parameters", {}).get("exits", {})
            default_strategy = exits.get("default", "balanced")
            strategy_config = exits.get(default_strategy, {})
            return strategy_config.get("take_profit", 0.08)
        except Exception as e:
            logger.warning(f"Failed to get take_profit from config: {e}")
            return 0.08

    async def _handle_alerts_request(self, user_input: str):
        """
        Handle position alerts request.

        Args:
            user_input: User's natural language input
        """
        print(MSG.CHECKING_ALERTS)

        try:
            if not self.trading_cycle:
                print(MSG.ALERTS_NOT_INITIALIZED)
                return

            # Fetch current broker state
            broker_state = self.trading_cycle.fetch_broker_state()

            # Check alerts using position tracker
            alerts = self.trading_cycle.position_tracker.check_alerts(broker_state)

            if not alerts:
                print(MSG.NO_ALERTS)
                print(MSG.POSITIONS_MONITORED(count=len(broker_state.get("positions", []))))
            else:
                print(MSG.ALERTS_HEADER(count=len(alerts)))
                for alert in alerts:
                    severity_emoji = get_alert_severity_emoji(alert.severity)
                    print(
                        MSG.ALERT_ITEM(
                            emoji=severity_emoji,
                            ticker=alert.ticker,
                            alert_type=alert.alert_type.value,
                            price=alert.current_price,
                        )
                    )
                    if alert.details:
                        for key, value in alert.details.items():
                            print(MSG.ALERT_DETAIL(key=key, value=value))

            # Show alert history
            history = self.trading_cycle.position_tracker.get_alert_history()
            if history:
                print(MSG.ALERT_HISTORY_HEADER(count=len(history)))
                for alert in history[-5:]:  # Last 5
                    print(
                        MSG.ALERT_HISTORY_ITEM(
                            ticker=alert.ticker,
                            alert_type=alert.alert_type.value,
                            time=alert.timestamp.strftime("%H:%M:%S"),
                        )
                    )

        except Exception as e:
            print(MSG.ERROR_CHECKING_ALERTS(error=e))
            logger.error(f"Alerts error: {e}", exc_info=True)

    async def _handle_scheduler_request(self, user_input: str):
        """
        Handle scheduler status/management request with detailed information.

        Args:
            user_input: User's natural language input
        """
        print(MSG.SCHEDULER_HEADER)
        print(MSG.SCHEDULER_SEPARATOR)

        try:
            if not self.scheduler:
                print(MSG.SCHEDULER_NOT_INITIALIZED)
                return

            # Show scheduler configuration with clear status
            enabled = self.scheduler.config.get("enabled", False)
            status_emoji = MSG.EMOJI["profit"] if enabled else MSG.EMOJI["loss"]
            status_text = "ENABLED" if enabled else "DISABLED"
            print(MSG.SCHEDULER_STATUS(emoji=status_emoji, status=status_text))

            print(MSG.SCHEDULER_CONFIG_HEADER)
            print(
                MSG.SCHEDULER_CONFIG(
                    morning=self.scheduler.config.get("morning_routine_time", "09:20"),
                    evening=self.scheduler.config.get("evening_routine_time", "15:50"),
                    retries=self.scheduler.config.get("max_retries", 3),
                )
            )

            # Show what each routine does
            print(MSG.SCHEDULER_ROUTINES_HEADER)
            print(MSG.MORNING_ROUTINE)
            print(MSG.EVENING_ROUTINE)

            # Show recent execution history with more detail
            recent = self.scheduler.get_execution_history(days=7)
            if recent:
                print(MSG.SCHEDULER_HISTORY_HEADER)

                for entry in recent[:10]:
                    status_emoji = get_status_emoji(entry.status)

                    # Format timestamp
                    if entry.actual_end_time:
                        time_str = entry.actual_end_time.strftime("%Y-%m-%d %H:%M")
                    else:
                        time_str = "In Progress"

                    print(
                        MSG.SCHEDULER_HISTORY_ITEM(
                            emoji=status_emoji,
                            task=entry.task_name,
                            status=entry.status.upper(),
                            time=time_str,
                        )
                    )

                    if entry.error_message:
                        print(MSG.SCHEDULER_ERROR(error=entry.error_message[:80]))

                    # Show retry info if applicable
                    if hasattr(entry, "retry_count") and entry.retry_count > 0:
                        print(MSG.SCHEDULER_RETRIES(count=entry.retry_count))
            else:
                print(MSG.SCHEDULER_NO_HISTORY)

            # Calculate next scheduled run
            print(MSG.SCHEDULER_NEXT_HEADER)
            try:
                from datetime import time

                import pytz

                from src.utils.date_utils import get_datetime_now

                et = pytz.timezone("US/Eastern")
                now = get_datetime_now(et)

                morning_time = time(9, 20)
                evening_time = time(15, 50)

                morning_today = now.replace(hour=9, minute=20, second=0, microsecond=0)
                evening_today = now.replace(hour=15, minute=50, second=0, microsecond=0)

                if now.time() < morning_time:
                    next_run = morning_today
                    next_task = "Morning Routine"
                elif now.time() < evening_time:
                    next_run = evening_today
                    next_task = "Evening Routine"
                else:
                    # After evening, next is tomorrow morning
                    from datetime import timedelta

                    next_run = morning_today + timedelta(days=1)
                    next_task = "Morning Routine (tomorrow)"

                time_until = next_run - now
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)

                print(
                    MSG.SCHEDULER_NEXT(
                        task=next_task,
                        time=next_run.strftime("%H:%M %p"),
                        hours=hours,
                        minutes=minutes,
                    )
                )
            except Exception as calc_error:
                print(MSG.SCHEDULER_NEXT_ERROR(error=calc_error))

            # Usage instructions
            print(MSG.SCHEDULER_COMMANDS)

        except Exception as e:
            print(MSG.ERROR_CHECKING_SCHEDULER(error=e))
            logger.error(f"Scheduler error: {e}", exc_info=True)

    async def _handle_portfolio_request(self, user_input: str):
        """
        Handle portfolio/account status request.

        Also handles specific position queries like "target on SPY"

        Args:
            user_input: User's natural language input
        """
        # Check if querying specific ticker
        input_lower = user_input.lower()
        specific_ticker = None

        # Extract ticker if asking about specific position or stop/target
        keywords = [
            "target on",
            "target for",
            "stop on",
            "stop for",
            "stop level on",
            "stop loss on",
            "exit level",
            "take profit",
        ]

        if any(keyword in input_lower for keyword in keywords):
            # Try to extract ticker from query
            words = user_input.upper().split()
            # Common tickers to look for
            common_tickers = ["SPY", "QQQ", "TQQQ", "SQQQ", "AAPL", "MSFT", "TSLA", "NVDA", "META"]
            for word in words:
                if word in common_tickers:
                    specific_ticker = word
                    break

        print(MSG.PORTFOLIO_HEADER)

        try:
            if not self.account_monitor:
                print(MSG.PORTFOLIO_NOT_INITIALIZED)
                return

            # Get account status (unless querying specific ticker)
            if not specific_ticker:
                account = self.account_monitor.get_account_status()

                print(MSG.ACCOUNT_HEADER)
                print(
                    MSG.ACCOUNT_INFO(
                        equity=float(account.get("equity", 0)),
                        cash=float(account.get("cash", 0)),
                        buying_power=float(account.get("buying_power", 0)),
                        pdt=account.get("pattern_day_trader", False),
                    )
                )

            # Get positions
            positions = self.account_monitor.get_positions()

            if specific_ticker:
                # Show details for specific position
                position = next((p for p in positions if p.get("symbol") == specific_ticker), None)
                if position:
                    qty = int(position.get("qty", 0))
                    symbol = position.get("symbol")
                    avg_entry = float(position.get("avg_entry_price", 0))

                    # Calculate current price from market value
                    market_value = float(position.get("market_value", 0))
                    current_price = (market_value / qty) if qty > 0 else 0.0

                    # Use cost_basis as fallback if avg_entry_price is 0
                    if avg_entry == 0.0:
                        cost_basis = float(position.get("cost_basis", 0))
                        avg_entry = (cost_basis / qty) if qty > 0 else 0.0

                    unrealized_pl = float(position.get("unrealized_pl", 0))
                    unrealized_plpc = float(position.get("unrealized_plpc", 0)) * 100

                    pl_emoji = get_pl_emoji(unrealized_pl)
                    print(MSG.POSITION_DETAILS_HEADER(emoji=pl_emoji, symbol=symbol))
                    print(
                        MSG.POSITION_DETAILS(
                            qty=qty,
                            entry=avg_entry,
                            current=current_price,
                            pl=unrealized_pl,
                            pl_pct=unrealized_plpc,
                        )
                    )

                    # Show stop/target levels from trading_cycle local_state
                    # This uses the new _extract_stop_target_from_orders() with calculated fallback
                    if self.trading_cycle:
                        local_pos = self.trading_cycle.local_state.get("positions", {}).get(symbol)
                        if local_pos:
                            stop_price = local_pos.get("stop_price")
                            target_price = local_pos.get("target_price")

                            # Get configured stop loss percentage
                            stop_loss_pct = self._get_stop_loss_pct()
                            take_profit_pct = self._get_take_profit_pct()

                            print("\n📍 Exit Levels:")
                            if stop_price:
                                distance = ((current_price - stop_price) / current_price) * 100
                                print(
                                    f"   🔴 Stop Loss: ${stop_price:.2f} (-{stop_loss_pct*100:.0f}% from entry, {distance:+.1f}% away)"
                                )
                            else:
                                print("   🔴 Stop Loss: Not set")

                            if target_price:
                                distance = ((target_price - current_price) / current_price) * 100
                                print(
                                    f"   🟢 Take Profit: ${target_price:.2f} (+{take_profit_pct*100:.0f}% from entry, {distance:+.1f}% away)"
                                )
                            else:
                                print("   🟢 Take Profit: Not set")

                            # Note about calculated stops (Alpaca API limitation)
                            if stop_price and not target_price:
                                print(
                                    "\n   ℹ️  Note: Stop calculated from entry (Alpaca hides bracket order legs)"
                                )
                                print("      Verify stop order exists on Alpaca dashboard")
                        else:
                            print(MSG.NO_TARGETS(symbol=symbol))
                else:
                    print(MSG.NO_POSITION(ticker=specific_ticker))

            elif positions:
                print(MSG.POSITIONS_HEADER(count=len(positions)))
                for pos in positions:
                    qty = int(pos.get("qty", 0))
                    symbol = pos.get("symbol", "UNKNOWN")
                    avg_entry = float(pos.get("avg_entry_price", 0))

                    # Calculate current price from market value (Alpaca doesn't provide current_price directly)
                    market_value = float(pos.get("market_value", 0))
                    current_price = (market_value / qty) if qty > 0 else 0.0

                    # Use cost_basis as fallback if avg_entry_price is 0
                    if avg_entry == 0.0:
                        cost_basis = float(pos.get("cost_basis", 0))
                        avg_entry = (cost_basis / qty) if qty > 0 else 0.0

                    unrealized_pl = float(pos.get("unrealized_pl", 0))
                    unrealized_plpc = float(pos.get("unrealized_plpc", 0)) * 100

                    pl_emoji = get_pl_emoji(unrealized_pl)
                    print(
                        MSG.POSITION_ITEM(
                            emoji=pl_emoji,
                            symbol=symbol,
                            qty=qty,
                            entry=avg_entry,
                            current=current_price,
                            value=market_value,
                            pl=unrealized_pl,
                            pl_pct=unrealized_plpc,
                        )
                    )
            else:
                print(MSG.NO_POSITIONS)

        except Exception as e:
            print(MSG.ERROR_CHECKING_PORTFOLIO(error=e))
            logger.error(f"Portfolio error: {e}", exc_info=True)

    async def _handle_orders_request(self, user_input: str):
        """
        Handle order status request - shows pending/open orders.
        Groups orders by symbol and enriches with local state data.

        Issue #371: Displays orders with visual hierarchy:
        - Entry orders first
        - Profit targets (PT1, PT2) by price
        - Stop-loss orders last
        - Visual connectors and emojis for quick scanning

        Args:
            user_input: User's natural language input
        """
        print(MSG.CHECKING_ORDERS)

        try:
            if not self.account_monitor:
                print(MSG.ORDERS_NOT_INITIALIZED)
                return

            # Get open orders from broker
            orders = self.account_monitor.get_orders(status="open")

            # Load local state to get stop/target prices
            local_state = self._load_local_state()

            if not orders and not local_state.get("positions"):
                print(MSG.NO_ORDERS)
                return

            # Group orders by symbol
            grouped_orders = self._group_orders_by_symbol(orders, local_state)

            if not grouped_orders:
                print(MSG.NO_ORDERS)
                return

            # Display header with total count
            total_count = sum(
                len(group["api_orders"]) + len(group["local_orders"])
                for group in grouped_orders.values()
            )
            print(MSG.ORDERS_HEADER(count=total_count))

            # Use new hierarchical formatting
            has_local_orders = False
            for idx, (symbol, group) in enumerate(grouped_orders.items()):
                direction = group["direction"]
                all_orders = group["api_orders"] + group["local_orders"]

                if not all_orders:
                    continue

                # Position header with box drawing
                if idx == 0:
                    header_prefix = "┌─"
                else:
                    print()  # Blank line between positions
                    header_prefix = "┌─"

                position_header = (
                    f"{header_prefix} ${symbol} Position ({len(all_orders)} orders) - {direction}"
                )
                print(position_header)

                # Separate and sort orders
                entry_orders = []
                profit_targets = []
                stop_loss_orders = []
                other_orders = []

                for order in all_orders:
                    label = order.get("label", "")
                    order_type = order.get("order_type", "").lower()

                    # Categorize orders
                    if label == "PT" or (
                        order_type == "limit" and order.get("side") in ["sell", "buy"]
                    ):
                        profit_targets.append(order)
                    elif label == "SL" or order_type == "stop":
                        stop_loss_orders.append(order)
                    elif order_type == "market" or (not label and not order_type):
                        entry_orders.append(order)
                    else:
                        other_orders.append(order)

                    # Check if local order for footer
                    if order.get("id", "").startswith("local"):
                        has_local_orders = True

                # Sort profit targets by price (ascending for LONG, descending for SHORT)
                if direction == "LONG":
                    profit_targets.sort(key=lambda o: float(o.get("price", 0)))
                else:
                    profit_targets.sort(key=lambda o: float(o.get("price", 0)), reverse=True)

                # Display entry orders
                for i, order in enumerate(entry_orders):
                    is_last = (
                        i == len(entry_orders) - 1
                        and not profit_targets
                        and not stop_loss_orders
                        and not other_orders
                    )
                    connector = "└─" if is_last else "├─"
                    self._print_hierarchical_order(order, connector, is_entry=True)

                # Display profit targets with numbering
                for i, order in enumerate(profit_targets):
                    is_last = (
                        i == len(profit_targets) - 1 and not stop_loss_orders and not other_orders
                    )
                    connector = "└─" if is_last else "├─"
                    pt_num = i + 1
                    self._print_hierarchical_order(order, connector, pt_label=f"PT{pt_num}")

                # Display stop-loss
                for i, order in enumerate(stop_loss_orders):
                    is_last = i == len(stop_loss_orders) - 1 and not other_orders
                    connector = "└─" if is_last else "├─"
                    self._print_hierarchical_order(order, connector, is_stop_loss=True)

                # Display other orders
                for i, order in enumerate(other_orders):
                    is_last = i == len(other_orders) - 1
                    connector = "└─" if is_last else "├─"
                    self._print_hierarchical_order(order, connector)

            # Footer with explanation
            if has_local_orders:
                print("\n" + "─" * 60)
                print("* Orders marked with * were sent to broker and logged locally.")
                print("  Please verify on broker portal for confirmation.")

        except Exception as e:
            print(MSG.ERROR_CHECKING_ORDERS(error=e))
            logger.error(f"Orders error: {e}", exc_info=True)

    def _load_local_state(self) -> dict:
        """Load local state from cost_efficient_positions.json"""
        import json

        state_file = "state/cost_efficient_positions.json"
        try:
            if os.path.exists(state_file):
                with open(state_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load local state: {e}")
        return {"positions": {}}

    def _group_orders_by_symbol(self, api_orders: list, local_state: dict) -> dict:
        """
        Group orders by symbol and enrich with local state data.

        Returns:
            Dict with structure: {symbol: {
                'direction': 'LONG/SHORT',
                'api_orders': [...],
                'local_orders': [...]
            }}
        """
        grouped = {}

        # Process API orders
        for order in api_orders:
            symbol = order.get("symbol", "UNKNOWN")
            side = self._extract_value(order.get("side"))

            if symbol not in grouped:
                grouped[symbol] = {
                    "direction": "LONG" if side == "buy" else "SHORT",
                    "api_orders": [],
                    "local_orders": [],
                }

            # Normalize order data
            normalized = self._normalize_order(order)
            grouped[symbol]["api_orders"].append(normalized)

        # Add local state stop/target orders (not visible in API due to "held" status)
        positions = local_state.get("positions", {})
        for symbol, position_data in positions.items():
            if symbol not in grouped:
                # Position exists but no API orders - might be entry filled, exits pending
                grouped[symbol] = {
                    "direction": "LONG",  # Default assumption
                    "api_orders": [],
                    "local_orders": [],
                }

            # Add stop order from local state if exists
            if position_data.get("stop_price"):
                stop_order = {
                    "symbol": symbol,
                    "side": "sell" if grouped[symbol]["direction"] == "LONG" else "buy",
                    "qty": position_data.get("quantity", 0),
                    "price": position_data["stop_price"],
                    "order_type": "stop",
                    "label": "SL",
                    "id": "local-stop",
                }
                grouped[symbol]["local_orders"].append(stop_order)

        return grouped

    def _normalize_order(self, order: dict) -> dict:
        """Normalize order data from API"""
        side = self._extract_value(order.get("side"))
        order_type = self._extract_value(order.get("order_type"))
        status = self._extract_value(order.get("status"))

        # Determine price based on order type
        if order_type == "limit":
            price = float(order.get("limit_price", 0))
        elif order_type == "stop":
            price = float(order.get("stop_price", 0))
        elif order_type == "stop_limit":
            price = float(order.get("stop_price", 0))
        else:
            price = None  # Market order

        # Determine label (PT/SL/Entry)
        label = None
        if order_type == "stop":
            label = "SL"
        elif order_type == "limit" and side == "sell":
            label = "PT"

        return {
            "symbol": order.get("symbol"),
            "side": side,
            "qty": order.get("qty", 0),
            "price": price,
            "order_type": order_type,
            "status": status,
            "time_in_force": self._extract_value(order.get("time_in_force", "")),
            "id": order.get("id", "N/A"),
            "label": label,
        }

    def _extract_value(self, field) -> str:
        """Extract value from enum or return as string"""
        if hasattr(field, "value"):
            return field.value
        return str(field).lower() if field else ""

    def _print_hierarchical_order(
        self,
        order: dict,
        connector: str,
        is_entry: bool = False,
        is_stop_loss: bool = False,
        pt_label: str = None,
    ):
        """
        Print a single order with hierarchical formatting.

        Args:
            order: Order data dict
            connector: Box drawing connector (├─, └─)
            is_entry: Whether this is an entry order
            is_stop_loss: Whether this is a stop-loss order
            pt_label: Label for profit target (e.g., "PT1", "PT2")
        """
        side = order.get("side", "?").lower()
        qty = order.get("qty", 0)
        price = order.get("price")
        status = order.get("status", "").lower()
        order_id = order.get("id", "N/A")

        # Format price
        if price:
            price_str = f"${price:.2f}"
        else:
            price_str = "market"

        # Emoji selection
        if is_entry:
            emoji = "🟢" if side == "buy" else "⚪"
            label = ""
        elif is_stop_loss:
            emoji = "🛑"
            label = "SL: "
        elif pt_label:
            emoji = "🎯"
            label = f"{pt_label}: "
        else:
            emoji = "📌"
            label = ""

        # Format: │ [connector] [emoji] [label] [side] [qty] @ [price] - [status] ([id])
        order_line = (
            f"│ {connector} {emoji} {label}{side} {qty} @ {price_str} - "
            f"{status.upper()} ({order_id[:8]})"
        )
        print(order_line)

    async def _handle_cancel_request(self, user_input: str):
        """
        Handle order cancellation request.
        Issue #360: Add order cancellation functionality to CLI

        Supports:
        - cancel all orders
        - cancel order <id>
        - cancel <symbol> orders

        Args:
            user_input: User's natural language input
        """
        input_lower = user_input.lower()

        try:
            # Get open orders from broker
            if not self.account_monitor:
                print("❌ Order management not initialized")
                return

            orders = self.account_monitor.get_orders(status="open")

            if not orders:
                print("ℹ️  No open orders to cancel")
                return

            # Determine what to cancel
            if "all" in input_lower:
                # Cancel all orders
                await self._cancel_all_orders(orders)

            elif any(char.isdigit() for char in user_input):
                # Extract order ID (contains digits)
                import re

                id_match = re.search(r"[a-f0-9-]{8,}", user_input, re.IGNORECASE)
                if id_match:
                    order_id = id_match.group(0)
                    await self._cancel_order_by_id(order_id, orders)
                else:
                    print("❌ Could not find order ID in input")

            else:
                # Try to extract symbol
                import re

                symbol_match = re.search(r"\b([A-Z]{1,5})\b", user_input.upper())
                if symbol_match:
                    symbol = symbol_match.group(1)
                    await self._cancel_orders_by_symbol(symbol, orders)
                else:
                    print("❌ Could not determine what to cancel")
                    print(
                        "ℹ️  Usage: 'cancel all orders' | 'cancel order <id>' | 'cancel <SYMBOL> orders'"
                    )

        except Exception as e:
            print(f"❌ Error cancelling orders: {e}")
            logger.error(f"Cancel error: {e}", exc_info=True)

    async def _cancel_all_orders(self, orders: list):
        """Cancel all open orders with confirmation."""
        print(f"\n📋 Found {len(orders)} open order(s):")
        for idx, order in enumerate(orders, 1):
            symbol = order.get("symbol", "?")
            side = order.get("side", "?").upper()
            qty = order.get("qty", "?")
            order_id = order.get("id", "?")
            print(f"   {idx}. {side} {qty} {symbol} (ID: {order_id[:8]}...)")

        # Confirmation
        print(f"\n⚠️  Cancel all {len(orders)} orders? [yes/no]: ", end="")
        confirm = input().strip().lower()

        if confirm != "yes":
            print("❌ Cancelled - no changes made")
            return

        # Cancel orders via executor
        print("\n🔄 Cancelling orders...")
        executor = self.orchestrator.executor

        cancelled_count = 0
        for order in orders:
            order_id = order.get("id")
            symbol = order.get("symbol")
            try:
                success = executor.cancel_order(order_id)
                if success:
                    print(f"✅ Cancelled {order_id[:8]}... ({symbol})")
                    cancelled_count += 1
                else:
                    print(f"❌ Failed to cancel {order_id[:8]}... ({symbol})")
            except Exception as e:
                print(f"❌ Error cancelling {order_id[:8]}...: {e}")

        print(f"\n✅ Cancelled {cancelled_count}/{len(orders)} orders successfully")

    async def _cancel_order_by_id(self, order_id: str, orders: list):
        """Cancel specific order by ID."""
        # Find matching order (partial ID match)
        matching = [o for o in orders if o.get("id", "").startswith(order_id)]

        if not matching:
            print(f"❌ Order '{order_id}' not found")
            return

        if len(matching) > 1:
            print(f"❌ Ambiguous: '{order_id}' matches multiple orders")
            return

        order = matching[0]
        full_order_id = order.get("id")
        symbol = order.get("symbol")
        side = order.get("side", "?").upper()
        qty = order.get("qty", "?")

        print("\n📋 Order to cancel:")
        print(f"   {side} {qty} {symbol} (ID: {full_order_id[:8]}...)")
        print("\nCancel this order? [yes/no]: ", end="")
        confirm = input().strip().lower()

        if confirm != "yes":
            print("❌ Cancelled - no changes made")
            return

        # Cancel via executor
        print("\n🔄 Cancelling order...")
        executor = self.orchestrator.executor

        try:
            success = executor.cancel_order(full_order_id)
            if success:
                print(f"✅ Cancelled order {full_order_id[:8]}... ({qty} {symbol})")
            else:
                print(f"❌ Failed to cancel order {full_order_id[:8]}...")
        except Exception as e:
            print(f"❌ Error cancelling order: {e}")
            logger.error(f"Cancel order error: {e}", exc_info=True)

    async def _cancel_orders_by_symbol(self, symbol: str, orders: list):
        """Cancel all orders for a specific symbol."""
        # Filter orders by symbol
        symbol_orders = [o for o in orders if o.get("symbol", "").upper() == symbol.upper()]

        if not symbol_orders:
            print(f"ℹ️  No open orders found for {symbol}")
            return

        print(f"\n📋 Found {len(symbol_orders)} {symbol} order(s):")
        for idx, order in enumerate(symbol_orders, 1):
            side = order.get("side", "?").upper()
            qty = order.get("qty", "?")
            order_id = order.get("id", "?")
            print(f"   {idx}. {side} {qty} (ID: {order_id[:8]}...)")

        # Confirmation
        count_str = f"all {len(symbol_orders)}" if len(symbol_orders) > 1 else "this"
        print(f"\nCancel {count_str} {symbol} order(s)? [yes/no]: ", end="")
        confirm = input().strip().lower()

        if confirm != "yes":
            print("❌ Cancelled - no changes made")
            return

        # Cancel orders via executor
        print("\n🔄 Cancelling orders...")
        executor = self.orchestrator.executor

        cancelled_count = 0
        for order in symbol_orders:
            order_id = order.get("id")
            try:
                success = executor.cancel_order(order_id)
                if success:
                    print(f"✅ Cancelled {order_id[:8]}... ({symbol})")
                    cancelled_count += 1
                else:
                    print(f"❌ Failed to cancel {order_id[:8]}...")
            except Exception as e:
                print(f"❌ Error cancelling {order_id[:8]}...: {e}")

        print(f"\n✅ Cancelled {cancelled_count}/{len(symbol_orders)} {symbol} orders successfully")

    async def _handle_position_orders(self, user_input: str):
        """
        Show detailed orders for specific position (stops, targets, entry).
        Issue #348: Enhanced order details when asking about stops/targets

        Supports queries like:
        - "what is my stop level on META"
        - "show orders for AAPL"
        - "target price on SPY"

        Args:
            user_input: User's natural language input
        """
        # Extract ticker from query
        ticker = self._extract_ticker_from_query(user_input)

        if not ticker:
            print("❌ Could not identify symbol in query")
            print("ℹ️  Try: 'show orders for AAPL' or 'stop level on META'")
            return

        try:
            if not self.account_monitor:
                print(MSG.PORTFOLIO_NOT_INITIALIZED)
                return

            # Get all orders for this ticker (open and filled recently)
            all_orders = self.account_monitor.get_orders(status="all")
            ticker_orders = [o for o in all_orders if o.get("symbol", "").upper() == ticker.upper()]

            # Also check local state for stop/target info
            local_state = self._load_local_state()
            position_data = local_state.get("positions", {}).get(ticker)

            if not ticker_orders and not position_data:
                print(f"❌ No orders or positions found for {ticker}")
                return

            # Display header
            print(f"\n📋 {ticker} Orders:")

            # Group orders by status
            filled_orders = [
                o for o in ticker_orders if self._extract_value(o.get("status")) == "filled"
            ]
            open_orders = [
                o
                for o in ticker_orders
                if self._extract_value(o.get("status"))
                in ["new", "pending_new", "accepted", "open"]
            ]

            # Show filled entry orders (most recent 3)
            if filled_orders:
                print("\n✅ ENTRY (Filled)")
                for order in filled_orders[:3]:  # Limit to 3 most recent
                    side = self._extract_value(order.get("side")).upper()
                    qty = order.get("qty", 0)
                    filled_price = order.get("filled_avg_price", 0)
                    filled_at = order.get("filled_at", "")

                    # Format timestamp
                    time_str = ""
                    if filled_at:
                        try:
                            from datetime import datetime

                            dt = datetime.fromisoformat(filled_at.replace("Z", "+00:00"))
                            time_str = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            time_str = filled_at[:16]

                    print(f"   {side} {qty} shares @ ${filled_price:.2f}")
                    if time_str:
                        print(f"   Filled: {time_str}")

            # Calculate entry price for reference (from filled orders or position data)
            entry_price = None
            if filled_orders:
                entry_price = filled_orders[0].get("filled_avg_price")
            elif position_data:
                entry_price = position_data.get("entry_price", 0)

            # Show open stop/target orders from API
            stop_shown = False
            target_shown = False

            if open_orders:
                print("\n🟡 OPEN Exit Orders")
                for order in open_orders:
                    order_type = self._extract_value(order.get("order_type"))
                    order_id = order.get("id", "N/A")
                    status = self._extract_value(order.get("status"))

                    if order_type == "stop":
                        stop_price = float(order.get("stop_price", 0))
                        pct_from_entry = ""
                        if entry_price and stop_price:
                            pct = ((stop_price - entry_price) / entry_price) * 100
                            pct_from_entry = f" ({pct:+.1f}% from entry)"

                        print(f"   🔴 STOP LOSS: ${stop_price:.2f}{pct_from_entry}")
                        print(f"      Order ID: {order_id[:12]}...")
                        print(f"      Status: {status.upper()}")
                        stop_shown = True

                    elif order_type == "limit":
                        limit_price = float(order.get("limit_price", 0))
                        pct_from_entry = ""
                        if entry_price and limit_price:
                            pct = ((limit_price - entry_price) / entry_price) * 100
                            pct_from_entry = f" ({pct:+.1f}% from entry)"

                        print(f"   🟢 TAKE PROFIT: ${limit_price:.2f}{pct_from_entry}")
                        print(f"      Order ID: {order_id[:12]}...")
                        print(f"      Status: {status.upper()}")
                        target_shown = True

            # Supplement with local state data (Alpaca often hides bracket legs)
            if position_data:
                stop_price = position_data.get("stop_price")
                target_price = position_data.get("target_price")

                if stop_price and not stop_shown:
                    print("\n🟡 OPEN Exit Orders (from local state)")
                    pct_from_entry = ""
                    if entry_price and stop_price:
                        pct = ((stop_price - entry_price) / entry_price) * 100
                        pct_from_entry = f" ({pct:+.1f}% from entry)"

                    print(f"   🔴 STOP LOSS: ${stop_price:.2f}{pct_from_entry}")
                    print("      Status: PENDING (bracket order)")
                    print("      * Logged locally - verify on broker dashboard")

                if target_price and not target_shown:
                    if not stop_shown and not stop_price:
                        print("\n🟡 OPEN Exit Orders (from local state)")

                    pct_from_entry = ""
                    if entry_price and target_price:
                        pct = ((target_price - entry_price) / entry_price) * 100
                        pct_from_entry = f" ({pct:+.1f}% from entry)"

                    print(f"   🟢 TAKE PROFIT: ${target_price:.2f}{pct_from_entry}")
                    print("      Status: PENDING (bracket order)")
                    print("      * Logged locally - verify on broker dashboard")

            # Show current price and distance to exits
            try:
                positions = self.account_monitor.get_positions()
                current_position = next(
                    (p for p in positions if p.get("symbol") == ticker.upper()), None
                )

                if current_position:
                    current_price = float(current_position.get("current_price", 0))
                    unrealized_pl_pct = float(current_position.get("unrealized_plpc", 0)) * 100

                    print(
                        f"\n📊 Current: {ticker} @ ${current_price:.2f} ({unrealized_pl_pct:+.2f}%)"
                    )

                    # Calculate distance to stop/target
                    stop_price = position_data.get("stop_price") if position_data else None
                    target_price = position_data.get("target_price") if position_data else None

                    # Try to get from open orders if not in local state
                    for order in open_orders:
                        order_type = self._extract_value(order.get("order_type"))
                        if order_type == "stop" and not stop_price:
                            stop_price = float(order.get("stop_price", 0))
                        elif order_type == "limit" and not target_price:
                            target_price = float(order.get("limit_price", 0))

                    if stop_price:
                        dist_to_stop = ((stop_price - current_price) / current_price) * 100
                        print(f"   Distance to stop: {dist_to_stop:+.1f}%")

                    if target_price:
                        dist_to_target = ((target_price - current_price) / current_price) * 100
                        print(f"   Distance to target: {dist_to_target:+.1f}%")

            except Exception as e:
                logger.debug(f"Could not fetch current price for {ticker}: {e}")

        except Exception as e:
            print(f"❌ Error fetching orders for {ticker}: {e}")
            logger.error(f"Position orders error: {e}", exc_info=True)

    def _extract_ticker_from_query(self, user_input: str) -> str:
        """
        Extract ticker symbol from user query.

        Handles queries like:
        - "stop level on META"
        - "show orders for AAPL"
        - "what's my target price on spy"

        Returns:
            Ticker symbol (uppercase) or empty string if not found
        """
        import re

        # Try regex pattern for ticker symbols (1-5 uppercase letters)
        # Look for words that are all caps or look like tickers
        words = user_input.upper().split()

        # Common prepositions that come before tickers
        prepositions = ["ON", "FOR", "IN", "OF", "WITH"]

        for i, word in enumerate(words):
            # Check if previous word was a preposition
            if i > 0 and words[i - 1] in prepositions:
                # Clean word (remove punctuation)
                clean_word = re.sub(r"[^A-Z]", "", word)
                if clean_word.isalpha() and 1 <= len(clean_word) <= 5:
                    return clean_word

        # Fallback: look for any word that's all caps and 1-5 letters
        for word in words:
            clean_word = re.sub(r"[^A-Z]", "", word)
            if clean_word.isalpha() and 1 <= len(clean_word) <= 5:
                # Avoid common words
                if clean_word not in [
                    "ON",
                    "FOR",
                    "IN",
                    "OF",
                    "WITH",
                    "THE",
                    "A",
                    "AN",
                    "MY",
                    "IS",
                    "ARE",
                ]:
                    return clean_word

        return ""

    async def _handle_execution_mode_request(self, user_input: str):
        """
        Handle execution mode view/change requests.
        Issue #332: Add execution mode switching commands

        Supports:
        - show execution mode
        - set execution mode {confirm|auto|paper|disabled}
        - execution-mode confirm/auto/paper/disabled

        Args:
            user_input: User's natural language input
        """
        from src.autogen_agents.trading_orchestrator import ExecutionMode

        input_lower = user_input.lower()

        # Determine if this is a "show" or "set" request
        is_show = any(word in input_lower for word in ["show", "what", "current", "get"])
        is_set = any(word in input_lower for word in ["set", "change", "switch"])

        if is_show and not is_set:
            # Show current execution mode
            current_mode = self.orchestrator.execution_mode
            print(f"\n📋 Current Execution Mode: {current_mode.value.upper()}")
            print("\nMode Descriptions:")
            print("  • CONFIRM - Requires human approval for each trade")
            print("  • AUTO    - Executes trades automatically (within risk limits)")
            print("  • PAPER   - Paper trading only, no real money")
            print("  • DISABLED - Trading completely disabled")
            print("\nTo change mode: set execution mode {confirm|auto|paper|disabled}")
            return

        # Try to extract target mode from input
        target_mode = None
        for mode in ["confirm", "auto", "paper", "disabled"]:
            if mode in input_lower:
                target_mode = mode
                break

        if not target_mode:
            print("❌ Could not determine execution mode")
            print("ℹ️  Usage: set execution mode {confirm|auto|paper|disabled}")
            print("\nAvailable modes:")
            print("  • confirm  - Human approval required")
            print("  • auto     - Autonomous execution")
            print("  • paper    - Paper trading only")
            print("  • disabled - Trading disabled")
            return

        # Validate and set new mode
        try:
            new_mode = ExecutionMode(target_mode)

            # Safety confirmation for AUTO mode
            if (
                new_mode == ExecutionMode.AUTO
                and self.orchestrator.execution_mode != ExecutionMode.AUTO
            ):
                print("\n⚠️  WARNING: Switching to AUTO mode")
                print("   This will execute trades automatically without confirmation.")
                print("   Risk limits and position sizing will still apply.")
                print("\nSwitch to AUTO mode? [yes/no]: ", end="")
                confirm = input().strip().lower()

                if confirm != "yes":
                    print("❌ Mode change cancelled")
                    return

            # Set new mode
            old_mode = self.orchestrator.execution_mode
            self.orchestrator.execution_mode = new_mode

            # Confirmation message
            print(
                f"\n✅ Execution mode changed: {old_mode.value.upper()} → {new_mode.value.upper()}"
            )

            # Mode-specific guidance
            if new_mode == ExecutionMode.CONFIRM:
                print("   • Trades will require your approval before execution")
            elif new_mode == ExecutionMode.AUTO:
                print("   • Trades will execute automatically (within risk limits)")
                print("   • Use 'cancel all orders' to stop pending trades")
            elif new_mode == ExecutionMode.PAPER:
                print("   • All trades will be simulated (no real money)")
            elif new_mode == ExecutionMode.DISABLED:
                print("   • Trading is now disabled")
                print("   • No trades will be executed")

        except ValueError:
            print(f"❌ Invalid execution mode: {target_mode}")
            print("ℹ️  Valid modes: confirm, auto, paper, disabled")

    async def _handle_account_request(self, user_input: str):
        """
        Handle account management requests.
        Issue #401: Multi-account portfolio management

        Supports:
        - list accounts / show accounts
        - switch to account <ID>
        - use account <ID>
        - show current account
        - refresh accounts

        Args:
            user_input: User's natural language input
        """
        input_lower = user_input.lower()

        # Determine intent from input
        if any(phrase in input_lower for phrase in ["list account", "show account"]):
            # List all accounts
            verbose = "verbose" in input_lower or "detail" in input_lower
            self.account_commands.list_accounts(verbose=verbose)

        elif any(phrase in input_lower for phrase in ["switch", "use", "change"]):
            # Extract account ID from input
            # Try to find account ID after key phrases
            account_id = None
            for phrase in ["switch to", "use account", "change to", "switch account", "use"]:
                if phrase in input_lower:
                    # Get text after the phrase
                    idx = input_lower.find(phrase)
                    remaining = user_input[idx + len(phrase) :].strip()
                    # Take first word as account ID
                    if remaining:
                        account_id = remaining.split()[0].strip()
                        break

            if account_id:
                result = self.account_commands.switch_account(account_id)
                if result["status"] == "success":
                    # Update orchestrator if needed
                    print("\n💡 Tip: Restart trading assistant to use new account for trades")
            else:
                print("❌ Please specify an account ID")
                print("ℹ️  Usage: switch to account <ACCOUNT_ID>")
                print("   Example: switch to account paper_main")

        elif any(phrase in input_lower for phrase in ["current account", "active account"]):
            # Show current account
            self.account_commands.show_current_account()

        elif "refresh" in input_lower:
            # Refresh account data
            self.account_commands.refresh_accounts()

        else:
            # Default: show account list
            self.account_commands.list_accounts()

    async def _handle_timeframe_request(self, user_input: str):
        """
        Handle timeframe management requests.
        Issue #365: Timeframe specification for multi-timeframe analysis

        Supports:
        - list timeframes / show timeframes
        - change timeframe to <TF> / set timeframe <TF>
        - current timeframe
        - timeframe recommendations

        Args:
            user_input: User's natural language input
        """
        from src.cli.timeframe_commands import get_timeframe_commands

        tf_commands = get_timeframe_commands()
        input_lower = user_input.lower()

        # Determine intent from input
        if any(
            phrase in input_lower for phrase in ["list timeframe", "show timeframe", "available"]
        ):
            # List all timeframes
            verbose = (
                "verbose" in input_lower or "detail" in input_lower or "description" in input_lower
            )
            output = tf_commands.list_timeframes(verbose=verbose)
            safe_print(output)

        elif any(
            phrase in input_lower for phrase in ["change timeframe", "set timeframe", "switch to"]
        ):
            # Extract timeframe from input
            # Look for timeframe patterns: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M
            import re

            tf_patterns = [r"\b(1m|5m|15m|30m|1h|2h|4h|1d|1w|1M)\b"]
            timeframe = None

            for pattern in tf_patterns:
                match = re.search(pattern, input_lower)
                if match:
                    timeframe = match.group(1)
                    break

            if timeframe:
                output = tf_commands.set_timeframe(timeframe)
                safe_print(output)
            else:
                safe_print(
                    "❌ Please specify a timeframe\n"
                    "ℹ️  Usage: change timeframe to <TF>\n"
                    "   Examples: change timeframe to 1h, set timeframe 4h"
                )
                safe_print(tf_commands.list_timeframes(verbose=False))

        elif any(
            phrase in input_lower
            for phrase in ["current timeframe", "active timeframe", "which timeframe"]
        ):
            # Show current timeframe
            output = tf_commands.show_current_timeframe()
            safe_print(output)

        elif any(
            phrase in input_lower for phrase in ["recommendation", "suggest", "best timeframe"]
        ):
            # Show recommendations
            output = tf_commands.show_timeframe_recommendations()
            safe_print(output)

        else:
            # Default: show current timeframe
            output = tf_commands.show_current_timeframe()
            safe_print(output)
