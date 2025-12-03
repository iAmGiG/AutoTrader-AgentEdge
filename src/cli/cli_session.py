"""
CLI Session - Interactive REPL for trading assistant.

Unified interactive CLI with LLM-driven routing for:
- Trade execution (buy/sell)
- Position alerts
- Scheduler management
- Portfolio status
"""

import asyncio
import atexit
import json
import logging
import os
import platform
import re
import sys
from typing import Optional

import yaml

# Add imports for new features
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
# Import CLI messages configuration
from config_defaults.message_loader import CLIMessages as MSG

from src.cli.commands.account_commands import get_account_commands
from src.cli.commands.timeframe_commands import get_timeframe_commands
from src.cli.scheduler_cli import SchedulerCLI

# Issue #459: Import extracted tool functions for Phase 1E integration
from src.cli.tools.alert_tools import show_alerts
from src.cli.tools.execution_mode_tools import (
    confirm_and_set_auto_mode,
    format_mode_change_result,
    set_execution_mode,
    set_orchestrator,
    show_execution_mode,
)
from src.cli.tools.mode_tools import set_mode, show_current_mode, show_mode_comparison
from src.cli.tools.order_tools import (
    cancel_all_orders,
    cancel_order,
    cancel_symbol_orders,
    show_orders,
    show_position_orders,
)
from src.cli.tools.portfolio_tools import show_portfolio
from src.cli.tools.scheduler_tools import show_scheduler
from src.cli.utils.help_system import HelpSystem
from src.cli.utils.input_parser import (
    BUY_INDICATORS,
    SELL_INDICATORS,
    detect_user_intent,
    extract_ticker_from_query,
)
from src.cli.utils.suggestion_display import (
    calc_pct,
    display_position_context,
    display_result,
    display_suggestion,
)
from src.cli.utils.trading_tips import display_trading_tips, get_tips_dict
from src.core.models import Signal
from src.core.trading_orchestrator import TradingOrchestrator
from src.trading.daily_scheduler import DailyScheduler
from src.trading.trading_cycle import CostEfficientTradeCycle
from src.utils.date_utils import now_iso

# Import safe_print for Unicode handling
from src.utils.safe_print import safe_print

logger = logging.getLogger(__name__)


def _sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error messages to remove API keys and sensitive details.

    Returns simple user-friendly messages based on error type.
    Full details are logged separately for debugging.
    """
    error_str = str(error).lower()

    # API key patterns to sanitize
    if "api" in error_str and (
        "key" in error_str or "401" in error_str or "authentication" in error_str
    ):
        return "Configuration error. Nothing done."

    # Parse errors
    if "could not parse" in error_str or "parse error" in error_str:
        return "Didn't understand that. Nothing done."

    # Ticker validation errors - provide actionable feedback
    if "ticker not found" in error_str:
        return "Symbol not found. It may not be available via your broker or data provider."

    if ("asset" in error_str and "not found" in error_str) or "symbol" in error_str:
        return "Symbol not recognized. Check the ticker spelling or try a US-listed stock."

    # Data availability errors
    if (
        "no data" in error_str
        or "insufficient data" in error_str
        or "data unavailable" in error_str
        or "market data may be unavailable" in error_str
        or "invalid entry price" in error_str
    ):
        return "Not enough market data available for analysis. Try a more liquid symbol."

    # Invalid request errors
    if "invalid request" in error_str or "invalid format" in error_str:
        return "Didn't understand that. Nothing done."

    # Format/type errors (likely None values in display)
    if "typeerror" in error_str or "nonetype" in error_str or "unsupported format" in error_str:
        logger.error(f"Display format error: {error}")
        return "Analysis failed - missing price data. Try again or check the ticker."

    # Generic fallback - log the actual error for debugging
    logger.warning(f"Unhandled error type: {type(error).__name__}: {error}")
    return f"Something went wrong. Error: {type(error).__name__}"


# Issue #436: Ticker completer moved to separate module
from src.cli.utils.ticker_completer import (
    READLINE_AVAILABLE,
    get_ticker_completer,
    is_powershell,
    readline,
)

# Global ticker completer instance (from extracted module)
_ticker_completer = get_ticker_completer()


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

        # Issue #459: Set orchestrator for execution mode tools
        set_orchestrator(orchestrator)

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

        # Educational tips for novice users (loaded from config)
        self.trading_tips = get_tips_dict()

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
                sanitized_msg = _sanitize_error_message(e)
                print(f"\n{error_prefix} {sanitized_msg}")
                logger.error(f"CLI error: {e}", exc_info=True)
                # Don't show traceback to user - it's logged

    def _print_welcome(self):
        """Print welcome message."""
        print(MSG.WELCOME_BANNER)
        print(MSG.WELCOME_TITLE)
        print(MSG.WELCOME_BANNER)
        print(f"Mode: {self.autonomy_mode.upper()}")
        print(MSG.HELP_COMMANDS)

        # PowerShell notice - tab completion doesn't work there
        if is_powershell():
            print("\nNote: Tab completion is not available in PowerShell.")
            print("      For tab completion, use cmd.exe or Git Bash.")

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
        """Display educational trading tips. Issue #436: Uses config-based tips."""
        display_trading_tips()

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

        elif (
            any(
                phrase in input_lower
                for phrase in [
                    "list account",
                    "show accounts",  # Plural = list accounts
                    "switch account",
                    "use account",
                    "change account",
                    "current account",
                    "refresh account",
                ]
            )
            or input_lower.strip() == "accounts"
        ):
            # Account management (Issue #401) - multi-account switching/listing
            # Note: "accounts" alone = list accounts, "account" alone = show portfolio
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
            ]
        ) or (
            # Only match standalone timeframe patterns (not "1 zm" where m is part of ticker)
            # Match: "1h", "5m alone", "set 1d", but NOT "1 zm" or "5 msft"
            any(
                input_lower.strip() == tf
                for tf in ["5m", "15m", "30m", "1h", "4h", "1d", "1w", "1m"]
            )
            or any(
                f" {tf}" in input_lower or f"set {tf}" in input_lower
                for tf in ["5m", "15m", "30m", "1h", "4h", "1d", "1w", "1m"]
            )
        ):
            # Timeframe management (Issue #365)
            await self._handle_timeframe_request(user_input)

        elif any(
            phrase in input_lower
            for phrase in [
                "trading mode",
                "risk mode",
                "show mode",
                "current mode",
                "set mode",
                "change mode",
                "conservative",
                "moderate",
                "aggressive",
            ]
        ):
            # Trading mode management (Issue #400)
            await self._handle_trading_mode_request(user_input)

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
            error_prefix = "[ERROR]" if platform.system() == "Windows" else MSG.EMOJI["error"]
            sanitized_msg = _sanitize_error_message(e)
            print(f"\n{error_prefix} {sanitized_msg}")

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
            user_intent = detect_user_intent(original_input)

            # Step 1: Process request via orchestrator
            decision = await self.orchestrator.process_request(user_input, self.user_id)

            # Step 2: Check position context before suggestion
            position = self._check_position_for_ticker(decision.suggestion.ticker)

            # Step 2a: Display position context
            display_position_context(
                decision.suggestion.ticker, position, decision.suggestion.signal.value
            )

            # Step 2b: Check for signal vs user intent mismatch
            # If analyzer suggests SELL but no position exists, check user's explicit intent
            if decision.suggestion.signal.value.upper() == "SELL" and not position:
                # Check if user explicitly wants to BUY/LONG (override signal)
                user_wants_buy = any(
                    indicator in original_input for indicator in BUY_INDICATORS
                )

                # Check if user explicitly wants to SELL/SHORT
                user_wants_sell = any(
                    indicator in original_input for indicator in SELL_INDICATORS
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
                    display_suggestion(
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
                            f"      Stop:   ${decision.suggestion.stop_loss:.2f} ({calc_pct(entry, decision.suggestion.stop_loss):.1f}%)"
                        )
                        print(
                            f"      Target: ${decision.suggestion.take_profit:.2f} ({calc_pct(entry, decision.suggestion.take_profit):.1f}%)"
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
                            f"      Stop:   ${decision.suggestion.stop_loss:.2f} ({calc_pct(entry, decision.suggestion.stop_loss):.1f}%)"
                        )
                        print(
                            f"      Target: ${decision.suggestion.take_profit:.2f} ({calc_pct(entry, decision.suggestion.take_profit):.1f}%)"
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
                        display_suggestion(decision.suggestion, position)
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
            display_suggestion(decision.suggestion, position, override_mode)

            # Step 3a: Check if this is review-only (no execution intent)
            # Parse the original input to see if user explicitly wanted to execute
            parsed_request = await self.orchestrator.parser.parse(user_input, self.user_id)
            is_review_only = parsed_request.action == "review"

            # Step 3b: Get user confirmation (if confirm mode AND user wants to execute)
            if is_review_only:
                # Review-only: Just show analysis, don't prompt for execution
                print("\n📊 Analysis complete. No trade execution requested.")
                decision.approved = False
            elif self.autonomy_mode == "confirm":
                approved = self._get_confirmation()
                decision.approved = approved
            else:
                # Auto mode - execute immediately
                decision.approved = True
                print(MSG.AUTO_EXECUTING)

            # Step 4: Execute if approved
            if decision.approved:
                result = await self.orchestrator.execute_decision(decision)
                display_result(result)

                # Issue #385: Update local state with stop/target immediately after trade
                self._update_local_state_after_trade(decision, result)
            elif not is_review_only:
                # Only show "cancelled" if user was asked to confirm but declined
                # Don't show for review-only requests (nothing to cancel)
                print(MSG.TRADE_CANCELLED)

        except Exception as e:
            # Sanitize error message for user display
            sanitized_msg = _sanitize_error_message(e)
            error_prefix = "[ERROR]" if platform.system() == "Windows" else MSG.EMOJI["error"]
            print(f"\n{error_prefix} {sanitized_msg}")

            # Log full error details for debugging
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
        """Handle position alerts request. Issue #459: Uses show_alerts()."""
        output = show_alerts()
        print(output)

    async def _handle_scheduler_request(self, user_input: str):
        """Handle scheduler status request. Issue #459: Uses show_scheduler()."""
        output = show_scheduler()
        print(output)

    async def _handle_portfolio_request(self, user_input: str):
        """
        Handle portfolio/account status request.

        Issue #459: Refactored to use extracted show_portfolio() from portfolio_tools.

        Args:
            user_input: User's natural language input
        """
        # Extract specific ticker if asking about stop/target
        input_lower = user_input.lower()
        specific_ticker = None

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
            words = user_input.upper().split()
            common_tickers = ["SPY", "QQQ", "TQQQ", "SQQQ", "AAPL", "MSFT", "TSLA", "NVDA", "META"]
            for word in words:
                if word in common_tickers:
                    specific_ticker = word
                    break

        # Use extracted show_portfolio function from portfolio_tools
        output = show_portfolio(
            account_monitor=self.account_monitor,
            trading_cycle=self.trading_cycle,
            specific_ticker=specific_ticker,
            stop_loss_pct=self._get_stop_loss_pct(),
            take_profit_pct=self._get_take_profit_pct(),
        )
        print(output)

    async def _handle_orders_request(self, user_input: str):
        """
        Handle order status request - shows pending/open orders.
        Issue #459: Refactored to use show_orders() from order_tools.
        """
        output = show_orders()
        print(output)

    async def _handle_position_orders(self, user_input: str):
        """
        Show detailed orders for specific position.
        Issue #459: Refactored to use show_position_orders() from order_tools.
        """
        # Extract ticker from query
        ticker = extract_ticker_from_query(user_input)
        if not ticker:
            print("❌ Could not identify symbol in query")
            print("ℹ️  Try: 'show orders for AAPL' or 'stop level on META'")
            return
        output = show_position_orders(ticker)
        print(output)

    async def _handle_cancel_request(self, user_input: str):
        """
        Handle order cancellation requests.

        Issue #360: Order cancellation functionality.
        Issue #436: Restored and refactored to use order_tools functions.

        Supports:
        - cancel all orders
        - cancel order <ID>
        - cancel orders for <SYMBOL>
        """
        input_lower = user_input.lower()

        # Cancel all orders
        if "all" in input_lower:
            print("⚠️  Cancelling ALL open orders...")
            result = cancel_all_orders()

            if result["status"] == "error":
                print(f"❌ Error: {result.get('error', 'Unknown')}")
                return

            cancelled = result.get("cancelled_count", 0)
            failed = result.get("failed_count", 0)

            if cancelled == 0 and failed == 0:
                print("ℹ️  No open orders to cancel")
            else:
                print(f"✅ Cancelled {cancelled} order(s)")
                if failed > 0:
                    print(f"⚠️  Failed to cancel {failed} order(s)")
            return

        # Cancel by symbol
        ticker = extract_ticker_from_query(user_input)
        if ticker:
            print(f"⚠️  Cancelling orders for {ticker}...")
            result = cancel_symbol_orders(ticker)

            if result["status"] == "error":
                print(f"❌ Error: {result.get('error', 'Unknown')}")
                return

            cancelled = result.get("cancelled_count", 0)
            if cancelled == 0:
                print(f"ℹ️  No open orders for {ticker}")
            else:
                print(f"✅ Cancelled {cancelled} order(s) for {ticker}")
            return

        # Cancel by order ID (extract from input)
        id_match = re.search(r"([a-f0-9-]{8,})", input_lower)
        if id_match:
            order_id = id_match.group(1)
            print(f"⚠️  Cancelling order {order_id[:8]}...")
            result = cancel_order(order_id)

            if result["status"] == "success":
                print(f"✅ Cancelled order {result.get('order_id', order_id)[:8]}...")
            elif result["status"] == "not_found":
                print(f"❌ Order not found: {order_id[:8]}...")
            elif result["status"] == "ambiguous":
                print(f"❌ Multiple orders match '{order_id[:8]}...'")
                print("   Please provide more of the order ID")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown')}")
            return

        # No valid target found
        print("❌ Could not determine what to cancel")
        print("ℹ️  Usage:")
        print("   • cancel all orders")
        print("   • cancel orders for AAPL")
        print("   • cancel order <order-id>")

    async def _handle_execution_mode_request(self, user_input: str):
        """
        Handle execution mode view/change requests.
        Issue #332/#459: Uses execution_mode_tools functions.
        """
        input_lower = user_input.lower()

        # Determine if this is a "show" or "set" request
        is_show = any(word in input_lower for word in ["show", "what", "current", "get"])
        is_set = any(word in input_lower for word in ["set", "change", "switch"])

        if is_show and not is_set:
            print(show_execution_mode())
            return

        # Extract target mode from input
        target_mode = None
        for mode in ["confirm", "auto", "paper", "disabled"]:
            if mode in input_lower:
                target_mode = mode
                break

        if not target_mode:
            print(show_execution_mode())
            return

        # Set new mode using tools
        result = set_execution_mode(target_mode)

        if result["status"] == "requires_confirmation":
            # AUTO mode needs user confirmation
            print(format_mode_change_result(result))
            print("\nSwitch to AUTO mode? [yes/no]: ", end="")
            confirm = input().strip().lower()
            if confirm != "yes":
                print("❌ Mode change cancelled")
                return
            result = confirm_and_set_auto_mode()

        print(format_mode_change_result(result))

    async def _handle_trading_mode_request(self, user_input: str):
        """
        Handle trading mode view/change requests.
        Issue #400: Trading Modes Configuration System
        Issue #459: Refactored to use mode_tools functions.

        Supports:
        - show mode / show trading mode / current mode
        - set mode conservative/moderate/aggressive
        - conservative / moderate / aggressive (direct command)

        Args:
            user_input: User's natural language input
        """
        input_lower = user_input.lower()

        # Determine if this is a "show" or "set" request
        is_show = any(word in input_lower for word in ["show", "what", "current", "get", "display"])
        is_set = any(word in input_lower for word in ["set", "change", "switch", "use"])
        mode_name_only = input_lower.strip() in ["conservative", "moderate", "aggressive"]

        # Check for comparison request
        if "compare" in input_lower or "comparison" in input_lower:
            print(show_mode_comparison())
            return

        if (is_show and not is_set) or (not is_show and not is_set and not mode_name_only):
            # Show current trading mode using mode_tools
            print(show_current_mode())
            print("\nTo change mode: set mode {conservative|moderate|aggressive}")
            return

        # Try to extract target mode from input
        target_mode_str = None
        for mode in ["conservative", "moderate", "aggressive"]:
            if mode in input_lower:
                target_mode_str = mode
                break

        if not target_mode_str:
            print("❌ Could not determine trading mode")
            print("ℹ️  Usage: set mode {conservative|moderate|aggressive}")
            return

        # Set new mode using mode_tools
        result = set_mode(target_mode_str)
        print(result)

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
        if any(phrase in input_lower for phrase in ["list account", "show accounts"]):
            # List all accounts (note: "show accounts" plural, not "show account" singular)
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
        - timeframe <TF>  (e.g., "timeframe 1d", "timeframe 1M")
        - list timeframes / show timeframes
        - timeframe recommendations

        Args:
            user_input: User's natural language input
        """

        tf_commands = get_timeframe_commands()
        input_lower = user_input.lower()

        # First: Check if input contains a timeframe value to SET
        # Alpaca supports: 1-59 minutes, 1-23 hours, days, weeks, months
        # Pattern: digits + unit (m=minute, h=hour, d=day, w=week, M=month)
        # Note: 1M = month (uppercase M), 1m = minute (lowercase m)
        tf_match = re.search(r"\b(\d{1,2}[mhdw]|1M)\b", user_input)

        if tf_match:
            # User wants to set a timeframe (e.g., "timeframe 1d", "1h", "set 4h")
            timeframe = tf_match.group(1)
            output = tf_commands.set_timeframe(timeframe)
            safe_print(output)

        elif any(
            phrase in input_lower for phrase in ["list timeframe", "show timeframe", "available"]
        ):
            # List all timeframes
            verbose = (
                "verbose" in input_lower or "detail" in input_lower or "description" in input_lower
            )
            output = tf_commands.list_timeframes(verbose=verbose)
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
