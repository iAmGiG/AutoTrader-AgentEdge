"""
CLI Session - Interactive REPL for trading assistant.

Unified interactive CLI with LLM-driven routing for:
- Trade execution (buy/sell)
- Position alerts
- Scheduler management
- Portfolio status
"""

import logging
from typing import Optional
import sys
import os

from core.trading_orchestrator import TradingOrchestrator

# Add imports for new features
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from src.trading.trading_cycle import CostEfficientTradeCycle
from src.trading.daily_scheduler import DailyScheduler

# Import CLI messages configuration
from config_defaults.message_loader import (
    CLIMessages as MSG,
    get_signal_emoji,
    get_pl_emoji,
    get_side_emoji,
    get_status_emoji,
    get_alert_severity_emoji
)


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
            'buy_vs_short': (
                "BUY = You think the stock will go UP in value\n"
                "   Example: Buy META at $500, sell later at $550 → $50 profit per share\n\n"
                "SHORT = You think the stock will go DOWN in value (advanced/risky)\n"
                "   Example: Short META at $500, buy back at $450 → $50 profit per share\n"
                "   ⚠️  Warning: If stock goes UP while shorted, you lose money!"
            ),
            'position_required': (
                "To SELL a stock, you must own it first (have an open position).\n"
                "Think of it like selling your car - you can't sell what you don't own!"
            ),
            'signals': (
                "The analysis gives a signal based on technical indicators:\n"
                "  📈 BUY signal = indicators suggest price may go UP\n"
                "  📉 SELL signal = indicators suggest price may go DOWN\n\n"
                "⚠️  Remember: These are suggestions, not guarantees!"
            )
        }

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

            with open(config_path, 'r') as f:
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
                mode_indicator = f"{MSG.EMOJI['auto_mode']} AUTO" if self.autonomy_mode == "auto" else f"{MSG.EMOJI['confirm_mode']} CONFIRM"
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
                print(f"\n{MSG.EMOJI['error']} Error: {e}")
                logger.error(f"CLI error: {e}", exc_info=True)
                # Don't show traceback to user - it's logged

    def _print_welcome(self):
        """Print welcome message."""
        print(MSG.WELCOME_BANNER)
        print(MSG.WELCOME_TITLE)
        print(MSG.WELCOME_BANNER)
        print(f"Mode: {self.autonomy_mode.upper()}")
        print(MSG.HELP_COMMANDS)

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

        elif cmd == "/help":
            self._print_welcome()

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
        print("\n" + "=" * 70)
        print("📚 TRADING BASICS FOR BEGINNERS")
        print("=" * 70)

        print("\n1️⃣  BUY vs SHORT (Long vs Short)")
        print("-" * 70)
        print(self.trading_tips['buy_vs_short'])

        print("\n2️⃣  Understanding Signals")
        print("-" * 70)
        print(self.trading_tips['signals'])

        print("\n3️⃣  Why You Need a Position to SELL")
        print("-" * 70)
        print(self.trading_tips['position_required'])

        print("\n💡 QUICK TIPS:")
        print("-" * 70)
        print("• Start small: Test with small amounts until you understand")
        print("• Use CONFIRM mode: Always review before executing trades")
        print("• Ask questions: Type naturally, the system will understand")
        print("• Check analysis: Choose 'review' to see analysis without trading")
        print("\n" + "=" * 70)

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

        if any(word in input_lower for word in ["scheduler", "schedule", "execution", "morning", "evening", "routine"]):
            # Scheduler queries
            await self._handle_scheduler_request(user_input)

        elif any(word in input_lower for word in ["alert", "approaching"]) and "check" in input_lower:
            # Alert queries
            await self._handle_alerts_request(user_input)

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

                if any(word in input_lower for word in ["order", "orders"]):
                    await self._handle_orders_request(user_input)
                elif any(phrase in input_lower for phrase in ["stop", "target", "take profit", "exit level", "stop loss"]):
                    # Stop/target queries → show portfolio with exit levels
                    await self._handle_portfolio_request(user_input)
                elif any(word in input_lower for word in ["position", "positions", "holding", "holdings"]):
                    await self._handle_portfolio_request(user_input)
                elif any(word in input_lower for word in ["portfolio", "account", "balance", "buying power", "equity", "cash"]):
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

        Args:
            user_input: User's natural language input
        """
        print(MSG.ANALYZING_TRADE)

        try:
            # Step 1: Process request via orchestrator
            decision = await self.orchestrator.process_request(user_input, self.user_id)

            # Step 2: Check position context before suggestion
            position = self._check_position_for_ticker(decision.suggestion.ticker)

            # Step 2a: Display position context
            self._display_position_context(decision.suggestion.ticker,
                                           position, decision.suggestion.signal.value)

            # Step 2b: Check for signal vs user intent mismatch
            # If analyzer suggests SELL but no position exists, check user's explicit intent
            if decision.suggestion.signal.value.upper() == "SELL" and not position:
                original_input = user_input.lower().strip()

                # Check if user explicitly wants to BUY/LONG (override signal)
                explicit_buy_indicators = [
                    'buy', 'long', 'go long', 'going long', 'bullish',
                    'bet it goes up', 'think it will rise', 'upside',
                    # Note: 'get ' with space to avoid 'target', 'forget'
                    'get ', 'acquire', 'purchase', 'pick up', 'grab'
                ]
                user_wants_buy = any(
                    indicator in original_input for indicator in explicit_buy_indicators)

                # Check if user explicitly wants to SELL/SHORT
                explicit_sell_indicators = [
                    # Trading terms
                    'sell', 'short', 'shorting', 'go short', 'exit',
                    # Layman terms for selling/closing
                    'close', 'get out', 'dump', 'liquidate', 'cash out',
                    # Explicit bearish intent
                    'bet against', 'profit from decline', 'make money when it falls'
                ]
                user_wants_sell = any(
                    indicator in original_input for indicator in explicit_sell_indicators)

                if user_wants_buy:
                    # User explicitly wants to go LONG despite SELL signal
                    # Human-in-loop: respect their intent but show them the conflict
                    print(f"\n{MSG.EMOJI.get('warning', '⚠️')} SIGNAL CONFLICT DETECTED")
                    print(f"   → You requested: LONG (BUY) position")
                    print(f"   → Technical analysis suggests: SHORT (SELL)")
                    print(
                        f"\n📊 Technical Indicators (based on {decision.suggestion.reasoning[0] if decision.suggestion.reasoning else 'MACD+RSI'}):")

                    # Show the actual technical analysis
                    self._display_suggestion(decision.suggestion, position,
                                             override_mode="USER_OVERRIDE_LONG")

                    print(f"\n💡 Human-in-Loop Decision:")
                    print(f"   → The system recommends SELL, but you want to go LONG")
                    print(f"   → This could be based on news, fundamentals, or your own analysis")
                    print(f"   → Remember: Technical indicators are backward-looking")

                    proceed = input(
                        f"\n   Do you still want to BUY {decision.suggestion.ticker}? [yes/no]: ").strip().lower()

                    if proceed in ['yes', 'y', '1']:
                        # User confirms override
                        # Don't reprocess! That causes infinite loop. Instead, flip the signal and continue.
                        print(
                            f"\n{MSG.EMOJI['info']} ✅ User override confirmed - placing BUY order")
                        print(f"   → Overriding SELL signal from technical analysis")

                        # Flip the signal to BUY (user override)
                        from core.models import Signal
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

                        print(f"\n   📊 Adjusted for BUY:")
                        print(f"      Entry:  ${entry:.2f}")
                        print(
                            f"      Stop:   ${decision.suggestion.stop_loss:.2f} ({self._calc_pct(entry, decision.suggestion.stop_loss):.1f}%)")
                        print(
                            f"      Target: ${decision.suggestion.take_profit:.2f} ({self._calc_pct(entry, decision.suggestion.take_profit):.1f}%)")
                        print(f"      Quantity: {decision.suggestion.recommended_quantity} shares")

                        # Continue to display and confirmation (no return, fall through)
                    else:
                        print(
                            f"\n{MSG.EMOJI['info']} Order cancelled. You can review alternatives:")
                        print(
                            f"   • Type 'review {decision.suggestion.ticker}' for detailed analysis")
                        print(
                            f"   • Type 'short {decision.suggestion.ticker}' to follow the SELL signal")
                        return

                elif not user_wants_sell:
                    # User didn't explicitly ask to sell - they likely asked for analysis
                    # Examples: "pltr", "review pltr", "analyze pltr at market price", "is pltr good?"
                    # Ask for clarification using simple language
                    print(
                        f"\n{MSG.EMOJI.get('question', '❓')} The analysis suggests {decision.suggestion.ticker} might go DOWN, but you don't own any shares yet.")
                    print(f"\n   What would you like to do?")
                    print(f"   1. BUY shares (bet the stock will go UP)")
                    print(f"   2. SHORT shares (bet the stock will go DOWN - advanced strategy)")
                    print(f"   3. Just see the analysis (don't trade)")

                    clarification = input(
                        "\n   Your choice [1/2/3 or buy/short/review]: ").strip().lower()

                    # Accept various formats: numbers, keywords, or full words
                    if clarification in ['1', 'buy', 'b', 'long', 'l', 'up', 'bullish']:
                        # User wants to buy - flip signal in place (don't reprocess!)
                        print(
                            f"\n{MSG.EMOJI['info']} Got it! Preparing BUY order for {decision.suggestion.ticker}...")

                        # Flip the signal to BUY
                        from core.models import Signal
                        decision.suggestion.signal = Signal.BUY

                        # Invert stop/target for BUY (were calculated for SELL)
                        entry = decision.suggestion.entry_price
                        old_stop = decision.suggestion.stop_loss
                        old_target = decision.suggestion.take_profit

                        stop_distance = abs(old_stop - entry)
                        target_distance = abs(old_target - entry)

                        decision.suggestion.stop_loss = round(entry - stop_distance, 2)
                        decision.suggestion.take_profit = round(entry + target_distance, 2)

                        print(f"\n   📊 Adjusted for BUY:")
                        print(f"      Entry:  ${entry:.2f}")
                        print(
                            f"      Stop:   ${decision.suggestion.stop_loss:.2f} ({self._calc_pct(entry, decision.suggestion.stop_loss):.1f}%)")
                        print(
                            f"      Target: ${decision.suggestion.take_profit:.2f} ({self._calc_pct(entry, decision.suggestion.take_profit):.1f}%)")
                        print(f"      Quantity: {decision.suggestion.recommended_quantity} shares")

                        # Continue to display and confirmation (no return, fall through)
                    elif clarification in ['2', 'short', 's', 'down', 'bearish', 'sell']:
                        # User explicitly wants to short - explain limitation
                        print(
                            f"\n{MSG.EMOJI['warning']} SHORT SELLING is not currently supported by this system.")
                        print(f"   ℹ️  Short selling = betting a stock will go down (advanced/risky)")
                        print(f"   → This system only supports buying stocks (betting they'll go up)")
                        print(f"   → Suggestion cancelled")
                        return
                    elif clarification in ['3', 'review', 'r', 'analysis', 'just show', 'view', 'look']:
                        # Just show the analysis, don't execute
                        print(
                            f"\n{MSG.EMOJI['info']} Showing analysis for {decision.suggestion.ticker} (information only, no trade)")
                        self._display_suggestion(decision.suggestion, position)
                        print(
                            f"\n   💡 Tip: If you want to trade on this analysis, type 'buy {decision.suggestion.ticker}' or 'short {decision.suggestion.ticker}'")
                        return
                    else:
                        # Unclear response or cancel
                        print(f"\n{MSG.EMOJI['info']} No problem! Cancelled.")
                        print(
                            f"   💡 Tip: You can be specific next time, e.g., 'buy {decision.suggestion.ticker}' or 'analyze {decision.suggestion.ticker}'")
                        return
                else:
                    # User explicitly asked to sell/close - block it since no position exists
                    print(
                        f"\n{MSG.EMOJI['error']} Cannot SELL or CLOSE position in {decision.suggestion.ticker}")
                    print(
                        f"   → You don't currently own any shares of {decision.suggestion.ticker}")
                    print(f"   → To sell a stock, you must buy it first")
                    print(
                        f"\n   💡 Did you mean to SHORT {decision.suggestion.ticker}? (bet it will go down)")
                    print(f"      Short selling is not currently supported by this system.")
                    return  # Exit early

            elif decision.suggestion.signal.value.upper() == "SELL" and position:
                # Position exists - show brief warning reminder
                print(
                    f"\n{MSG.EMOJI['warning']} SELL will close your position in {decision.suggestion.ticker}")

            # Step 3: Display suggestion
            self._display_suggestion(decision.suggestion, position)

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
            return next((p for p in positions if p.get('symbol') == ticker), None)
        except Exception as e:
            logger.warning(f"Failed to check position for {ticker}: {e}")
            return None

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
            qty = int(position.get('qty', 0))
            avg_entry = float(position.get('avg_entry_price', 0))
            market_value = float(position.get('market_value', 0))
            current_price = (market_value / qty) if qty > 0 else 0.0
            unrealized_pl = float(position.get('unrealized_pl', 0))
            unrealized_plpc = float(position.get('unrealized_plpc', 0)) * 100

            # Use fallback for entry price if needed
            if avg_entry == 0.0:
                cost_basis = float(position.get('cost_basis', 0))
                avg_entry = (cost_basis / qty) if qty > 0 else 0.0

            pl_emoji = get_pl_emoji(unrealized_pl)

            print(f"   Current Position: {qty} shares @ ${avg_entry:.2f} (avg entry)")
            print(f"   Current Price: ${current_price:.2f}")
            print(f"   {pl_emoji} Unrealized P/L: ${unrealized_pl:+.2f} ({unrealized_plpc:+.2f}%)")
            print(f"   Market Value: ${market_value:,.2f}")
        else:
            print(f"   ℹ️  No position in {ticker} (0 shares)")

        print(f"{'='*60}\n")

    def _display_suggestion(self, suggestion, position: Optional[dict] = None, override_mode: Optional[str] = None):
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

        # Signal (with override warning if applicable)
        signal_emoji = get_signal_emoji(suggestion.signal.value)
        if override_mode == "USER_OVERRIDE_LONG":
            print(f"⚠️  SYSTEM RECOMMENDS: {signal_emoji} {suggestion.signal.value.upper()}")
            print(f"👤 USER INTENT: ⬆️ BUY (LONG)")
        elif override_mode == "USER_OVERRIDE_SHORT":
            print(f"⚠️  SYSTEM RECOMMENDS: {signal_emoji} {suggestion.signal.value.upper()}")
            print(f"👤 USER INTENT: ⬇️ SELL (SHORT)")
        else:
            print(MSG.SIGNAL_DISPLAY.format(emoji=signal_emoji, signal=suggestion.signal.value.upper()))

        print(MSG.CONFIDENCE_DISPLAY.format(confidence=suggestion.confidence))

        # Technical analysis
        print(MSG.ANALYSIS_HEADER)
        for reason in suggestion.reasoning:
            print(MSG.ANALYSIS_ITEM.format(reason=reason))

        # Entry plan
        print(MSG.ENTRY_PLAN_HEADER)
        print(MSG.ENTRY_PLAN.format(
            entry=suggestion.entry_price,
            stop=suggestion.stop_loss,
            stop_pct=self._calc_pct(suggestion.entry_price, suggestion.stop_loss),
            target=suggestion.take_profit,
            target_pct=self._calc_pct(suggestion.entry_price, suggestion.take_profit),
            qty=suggestion.recommended_quantity,
            tif=suggestion.time_in_force.value.upper()
        ))

        # Portfolio impact
        print(MSG.PORTFOLIO_IMPACT_HEADER)
        print(MSG.PORTFOLIO_IMPACT.format(
            trade_value=suggestion.recommended_quantity * suggestion.entry_price,
            portfolio_pct=suggestion.portfolio_pct,
            max_loss=suggestion.max_loss_usd,
            risk_reward=suggestion.risk_reward_ratio
        ))

        # Warnings
        if suggestion.warnings:
            print(MSG.WARNINGS_HEADER)
            for warning in suggestion.warnings:
                print(MSG.WARNING_ITEM.format(warning=warning))

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
            print(MSG.ORDER_SUCCESS.format(
                qty=result.quantity,
                ticker=result.ticker,
                entry_id=result.entry_order_id,
                stop_id=result.stop_order_id,
                target_id=result.target_order_id,
                message=result.message
            ))
        else:
            print(MSG.ORDER_FAILED_HEADER)
            print(MSG.ORDER_FAILED.format(message=result.message))
            if result.error:
                print(MSG.ORDER_ERROR.format(error=result.error))

        print(MSG.RESULT_SEPARATOR)

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
                print(MSG.POSITIONS_MONITORED(count=len(broker_state.get('positions', []))))
            else:
                print(MSG.ALERTS_HEADER(count=len(alerts)))
                for alert in alerts:
                    severity_emoji = get_alert_severity_emoji(alert.severity)
                    print(MSG.ALERT_ITEM(
                        emoji=severity_emoji,
                        ticker=alert.ticker,
                        alert_type=alert.alert_type.value,
                        price=alert.current_price
                    ))
                    if alert.details:
                        for key, value in alert.details.items():
                            print(MSG.ALERT_DETAIL(key=key, value=value))

            # Show alert history
            history = self.trading_cycle.position_tracker.get_alert_history()
            if history:
                print(MSG.ALERT_HISTORY_HEADER(count=len(history)))
                for alert in history[-5:]:  # Last 5
                    print(MSG.ALERT_HISTORY_ITEM(
                        ticker=alert.ticker,
                        alert_type=alert.alert_type.value,
                        time=alert.timestamp.strftime('%H:%M:%S')
                    ))

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
            enabled = self.scheduler.config.get('enabled', False)
            status_emoji = MSG.EMOJI["profit"] if enabled else MSG.EMOJI["loss"]
            status_text = 'ENABLED' if enabled else 'DISABLED'
            print(MSG.SCHEDULER_STATUS(emoji=status_emoji, status=status_text))

            print(MSG.SCHEDULER_CONFIG_HEADER)
            print(MSG.SCHEDULER_CONFIG(
                morning=self.scheduler.config.get('morning_routine_time', '09:20'),
                evening=self.scheduler.config.get('evening_routine_time', '15:50'),
                retries=self.scheduler.config.get('max_retries', 3)
            ))

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

                    print(MSG.SCHEDULER_HISTORY_ITEM(
                        emoji=status_emoji,
                        task=entry.task_name,
                        status=entry.status.upper(),
                        time=time_str
                    ))

                    if entry.error_message:
                        print(MSG.SCHEDULER_ERROR(error=entry.error_message[:80]))

                    # Show retry info if applicable
                    if hasattr(entry, 'retry_count') and entry.retry_count > 0:
                        print(MSG.SCHEDULER_RETRIES(count=entry.retry_count))
            else:
                print(MSG.SCHEDULER_NO_HISTORY)

            # Calculate next scheduled run
            print(MSG.SCHEDULER_NEXT_HEADER)
            try:
                from datetime import datetime, time
                import pytz
                et = pytz.timezone('US/Eastern')
                now = datetime.now(et)

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

                print(MSG.SCHEDULER_NEXT(
                    task=next_task,
                    time=next_run.strftime('%H:%M %p'),
                    hours=hours,
                    minutes=minutes
                ))
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
        keywords = ["target on", "target for", "stop on", "stop for", "stop level on",
                    "stop loss on", "exit level", "take profit"]

        if any(keyword in input_lower for keyword in keywords):
            # Try to extract ticker from query
            words = user_input.upper().split()
            # Common tickers to look for
            common_tickers = ['SPY', 'QQQ', 'TQQQ', 'SQQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'META']
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
                print(MSG.ACCOUNT_INFO(
                    equity=float(account.get('equity', 0)),
                    cash=float(account.get('cash', 0)),
                    buying_power=float(account.get('buying_power', 0)),
                    pdt=account.get('pattern_day_trader', False)
                ))

            # Get positions
            positions = self.account_monitor.get_positions()

            if specific_ticker:
                # Show details for specific position
                position = next((p for p in positions if p.get('symbol') == specific_ticker), None)
                if position:
                    qty = int(position.get('qty', 0))
                    symbol = position.get('symbol')
                    avg_entry = float(position.get('avg_entry_price', 0))

                    # Calculate current price from market value
                    market_value = float(position.get('market_value', 0))
                    current_price = (market_value / qty) if qty > 0 else 0.0

                    # Use cost_basis as fallback if avg_entry_price is 0
                    if avg_entry == 0.0:
                        cost_basis = float(position.get('cost_basis', 0))
                        avg_entry = (cost_basis / qty) if qty > 0 else 0.0

                    unrealized_pl = float(position.get('unrealized_pl', 0))
                    unrealized_plpc = float(position.get('unrealized_plpc', 0)) * 100

                    pl_emoji = get_pl_emoji(unrealized_pl)
                    print(MSG.POSITION_DETAILS_HEADER(emoji=pl_emoji, symbol=symbol))
                    print(MSG.POSITION_DETAILS(
                        qty=qty,
                        entry=avg_entry,
                        current=current_price,
                        pl=unrealized_pl,
                        pl_pct=unrealized_plpc
                    ))

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

                            print(f"\n📍 Exit Levels:")
                            if stop_price:
                                distance = ((current_price - stop_price) / current_price) * 100
                                print(
                                    f"   🔴 Stop Loss: ${stop_price:.2f} (-{stop_loss_pct*100:.0f}% from entry, {distance:+.1f}% away)")
                            else:
                                print(f"   🔴 Stop Loss: Not set")

                            if target_price:
                                distance = ((target_price - current_price) / current_price) * 100
                                print(
                                    f"   🟢 Take Profit: ${target_price:.2f} (+{take_profit_pct*100:.0f}% from entry, {distance:+.1f}% away)")
                            else:
                                print(f"   🟢 Take Profit: Not set")

                            # Note about calculated stops (Alpaca API limitation)
                            if stop_price and not target_price:
                                print(
                                    f"\n   ℹ️  Note: Stop calculated from entry (Alpaca hides bracket order legs)")
                                print(f"      Verify stop order exists on Alpaca dashboard")
                        else:
                            print(MSG.NO_TARGETS(symbol=symbol))
                else:
                    print(MSG.NO_POSITION(ticker=specific_ticker))

            elif positions:
                print(MSG.POSITIONS_HEADER(count=len(positions)))
                for pos in positions:
                    qty = int(pos.get('qty', 0))
                    symbol = pos.get('symbol', 'UNKNOWN')
                    avg_entry = float(pos.get('avg_entry_price', 0))

                    # Calculate current price from market value (Alpaca doesn't provide current_price directly)
                    market_value = float(pos.get('market_value', 0))
                    current_price = (market_value / qty) if qty > 0 else 0.0

                    # Use cost_basis as fallback if avg_entry_price is 0
                    if avg_entry == 0.0:
                        cost_basis = float(pos.get('cost_basis', 0))
                        avg_entry = (cost_basis / qty) if qty > 0 else 0.0

                    unrealized_pl = float(pos.get('unrealized_pl', 0))
                    unrealized_plpc = float(pos.get('unrealized_plpc', 0)) * 100

                    pl_emoji = get_pl_emoji(unrealized_pl)
                    print(MSG.POSITION_ITEM(
                        emoji=pl_emoji,
                        symbol=symbol,
                        qty=qty,
                        entry=avg_entry,
                        current=current_price,
                        value=market_value,
                        pl=unrealized_pl,
                        pl_pct=unrealized_plpc
                    ))
            else:
                print(MSG.NO_POSITIONS)

        except Exception as e:
            print(MSG.ERROR_CHECKING_PORTFOLIO(error=e))
            logger.error(f"Portfolio error: {e}", exc_info=True)

    async def _handle_orders_request(self, user_input: str):
        """
        Handle order status request - shows pending/open orders.

        Args:
            user_input: User's natural language input
        """
        print(MSG.CHECKING_ORDERS)

        try:
            if not self.account_monitor:
                print(MSG.ORDERS_NOT_INITIALIZED)
                return

            # Get open orders
            orders = self.account_monitor.get_orders(status="open")

            if not orders:
                print(MSG.NO_ORDERS)
            else:
                print(MSG.ORDERS_HEADER(count=len(orders)))
                for order in orders:
                    symbol = order.get('symbol', 'UNKNOWN')
                    side = order.get('side', 'UNKNOWN')
                    qty = order.get('qty', 0)
                    order_type = order.get('type', 'UNKNOWN')
                    status = order.get('status', 'UNKNOWN')
                    order_id = order.get('id', 'N/A')

                    # Extract enum values if needed (Alpaca returns enums)
                    if hasattr(side, 'value'):
                        side = side.value
                    if hasattr(order_type, 'value'):
                        order_type = order_type.value
                    if hasattr(status, 'value'):
                        status = status.value

                    # Get price info based on order type
                    if order_type == 'limit':
                        price_str = f"@ ${float(order.get('limit_price', 0)):.2f}"
                    elif order_type == 'stop':
                        price_str = f"stop ${float(order.get('stop_price', 0)):.2f}"
                    elif order_type == 'stop_limit':
                        price_str = f"stop ${float(order.get('stop_price', 0)):.2f}, limit ${float(order.get('limit_price', 0)):.2f}"
                    else:
                        price_str = "market"

                    side_emoji = get_side_emoji(side)
                    print(MSG.ORDER_ITEM(
                        emoji=side_emoji,
                        side=side.upper(),
                        qty=qty,
                        symbol=symbol,
                        price=price_str,
                        type=order_type.upper(),
                        status=status.upper(),
                        order_id=order_id[:8]
                    ))

        except Exception as e:
            print(MSG.ERROR_CHECKING_ORDERS(error=e))
            logger.error(f"Orders error: {e}", exc_info=True)
