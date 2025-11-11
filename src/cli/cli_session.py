"""
CLI Session - Interactive REPL for trading assistant.

Unified interactive CLI with LLM-driven routing for:
- Trade execution (buy/sell)
- Position alerts
- Scheduler management
- Portfolio status
"""

import asyncio
import logging
from typing import Optional
import sys
import os

from core.trading_orchestrator import TradingOrchestrator
from core.models import Signal

# Add imports for new features
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from src.trading.trading_cycle import CostEfficientTradeCycle
from src.trading.daily_scheduler import DailyScheduler
from src.trading.alpaca_trading_client import AlpacaAccountMonitor


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
        try:
            self.trading_cycle = CostEfficientTradeCycle()
            self.scheduler = DailyScheduler()
            self.account_monitor = AlpacaAccountMonitor(mode="paper")
            logger.info("CLISession initialized with all features")
        except Exception as e:
            logger.warning(f"Some features unavailable: {e}")
            self.trading_cycle = None
            self.scheduler = None
            self.account_monitor = None

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
                mode_indicator = "🤖 AUTO" if self.autonomy_mode == "auto" else "✋ CONFIRM"
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
                print("\n\n👋 Exiting...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.error(f"CLI error: {e}", exc_info=True)
                # Don't show traceback to user - it's logged

    def _print_welcome(self):
        """Print welcome message."""
        print("=" * 70)
        print("   AutoGen Trading Assistant - Unified Interactive CLI")
        print("=" * 70)
        print(f"Mode: {self.autonomy_mode.upper()}")
        print("\nSystem Commands:")
        print("  /help    - Show help")
        print("  /exit    - Exit (or Ctrl+C)")
        print("  /toggle  - Toggle between CONFIRM and AUTO modes")
        print("\nTrading:")
        print("  > buy 10 AAPL")
        print("  > is SPY at 600 a good entry?")
        print("  > sell all TQQQ")
        print("\nMonitoring:")
        print("  > check my alerts")
        print("  > show portfolio")
        print("  > what's my position status?")
        print("\nScheduler:")
        print("  > show scheduler status")
        print("  > show execution history")
        print("\nTip: Just type naturally - the LLM will understand!")
        print("")

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
                print("🤖 Mode switched to: AUTO (trades execute immediately)")
            else:
                self.autonomy_mode = "confirm"
                print("✋ Mode switched to: CONFIRM (asks before executing)")

        else:
            print(f"Unknown command: {command}")
            print("Use /help to see available commands")

        return True

    async def _process_request(self, user_input: str):
        """
        Process user request with intelligent routing.

        Routes to:
        - Alert checker for "alerts", "check position"
        - Scheduler for "scheduler", "execution", "morning", "evening"
        - Portfolio for "portfolio", "account", "status", "positions"
        - Trading orchestrator for buy/sell requests

        Args:
            user_input: User's natural language input
        """
        # Smart routing based on keywords
        input_lower = user_input.lower()

        # Route to appropriate handler
        # Priority 1: Position status queries (before alerts to catch "check position")
        if any(phrase in input_lower for phrase in [
            "any positions", "positions open", "what positions", "show positions",
            "position status", "open trades", "what do i have", "what do i own",
            "show me what", "price target on", "target for", "target on"
        ]):
            await self._handle_portfolio_request(user_input)

        # Priority 2: Alerts (specific position monitoring)
        elif any(word in input_lower for word in ["alert", "approaching", "check alert"]):
            await self._handle_alerts_request(user_input)

        # Priority 3: Scheduler
        elif any(word in input_lower for word in ["scheduler", "schedule", "execution", "morning", "evening", "routine"]):
            await self._handle_scheduler_request(user_input)

        # Priority 4: Portfolio/account queries
        elif any(word in input_lower for word in ["portfolio", "account", "balance", "buying power", "equity", "cash"]):
            await self._handle_portfolio_request(user_input)

        # Default: Trade request
        else:
            await self._handle_trade_request(user_input)

    async def _handle_trade_request(self, user_input: str):
        """
        Process user trade request via orchestrator.

        Args:
            user_input: User's natural language input
        """
        print("\n⏳ Analyzing trade...")

        try:
            # Step 1: Process request via orchestrator
            decision = await self.orchestrator.process_request(user_input, self.user_id)

            # Step 2: Check for SELL signal without position (prevent unintentional shorting)
            if decision.suggestion.signal.value.upper() == "SELL":
                # TODO: Check if we actually hold this position
                # For now, warn the user
                print("\n⚠️  WARNING: SELL signal detected.")
                print("   This system does not support short selling.")
                print("   Only SELL if you currently hold this position.")
                print("   Otherwise, ignore this signal.\n")

            # Step 3: Display suggestion
            self._display_suggestion(decision.suggestion)

            # Step 3: Get user confirmation (if confirm mode)
            if self.autonomy_mode == "confirm":
                approved = self._get_confirmation()
                decision.approved = approved
            else:
                # Auto mode - execute immediately
                decision.approved = True
                print("\n⚡ Auto-executing...")

            # Step 4: Execute if approved
            if decision.approved:
                result = await self.orchestrator.execute_decision(decision)
                self._display_result(result)
            else:
                print("\n❌ Trade cancelled")

        except Exception as e:
            error_msg = str(e)

            # Provide helpful suggestions for common errors
            if "asset" in error_msg.lower() and "not found" in error_msg.lower():
                print(f"\n❌ Invalid ticker symbol")
                print(f"   The ticker you entered was not recognized by the market.")
                print(f"   Please check the spelling and try again.")
                print(f"   Example: AAPL (not APPL), TSLA, SPY, MSFT")
            else:
                print(f"\n❌ Error processing request: {e}")

            logger.error(f"Request processing error: {e}", exc_info=True)
            # Traceback logged but not shown to user

    def _display_suggestion(self, suggestion):
        """
        Display trade suggestion to user.

        Args:
            suggestion: TradeSuggestion object
        """
        print("\n" + "=" * 70)
        print(f"📊 {suggestion.ticker} @ ${suggestion.entry_price:.2f}")
        print("=" * 70)

        # Signal
        signal_emoji = "✅" if suggestion.signal == Signal.BUY else "⬇️"
        print(f"{signal_emoji} {suggestion.signal.value.upper()} SUGGESTED")
        print(f"   Confidence: {suggestion.confidence:.1%}")

        # Technical analysis
        print("\n📈 Analysis:")
        for reason in suggestion.reasoning:
            print(f"   • {reason}")

        # Entry plan
        print("\n💰 Entry Plan:")
        print(f"   Entry:  ${suggestion.entry_price:.2f}")
        print(
            f"   Stop:   ${suggestion.stop_loss:.2f} ({self._calc_pct(suggestion.entry_price, suggestion.stop_loss):+.1f}%)")
        print(
            f"   Target: ${suggestion.take_profit:.2f} ({self._calc_pct(suggestion.entry_price, suggestion.take_profit):+.1f}%)")
        print(f"   Qty:    {suggestion.recommended_quantity} shares")
        print(f"   Order:  {suggestion.time_in_force.value.upper()}")

        # Portfolio impact
        print("\n📊 Portfolio Impact:")
        print(f"   Trade Value: ${suggestion.recommended_quantity * suggestion.entry_price:,.2f}")
        print(f"   Portfolio %: {suggestion.portfolio_pct:.1f}% (after transaction)")
        print(f"   Max Loss:    ${suggestion.max_loss_usd:.2f}")
        print(f"   Risk/Reward: {suggestion.risk_reward_ratio:.2f}")

        # Warnings
        if suggestion.warnings:
            print("\n⚠️  Warnings:")
            for warning in suggestion.warnings:
                print(f"   {warning}")

    def _get_confirmation(self) -> bool:
        """
        Get user confirmation.

        Returns:
            True if user approves, False otherwise
        """
        while True:
            response = input("\nContinue? [yes/no]: ").strip().lower()

            if response in ["yes", "y"]:
                return True
            elif response in ["no", "n"]:
                return False
            else:
                print("Please enter 'yes' or 'no'")

    def _display_result(self, result):
        """
        Display execution result.

        Args:
            result: OrderResult object
        """
        print("\n" + "=" * 70)

        if result.success:
            print("✅ ORDER PLACED SUCCESSFULLY")
            print(f"\n   {result.quantity} shares {result.ticker}")
            print(f"   Entry Order:  {result.entry_order_id}")
            print(f"   Stop Order:   {result.stop_order_id}")
            print(f"   Target Order: {result.target_order_id}")
            print(f"\n   {result.message}")
        else:
            print("❌ ORDER FAILED")
            print(f"\n   {result.message}")
            if result.error:
                print(f"   Error: {result.error}")

        print("=" * 70)

    def _calc_pct(self, base: float, value: float) -> float:
        """Calculate percentage change."""
        return ((value - base) / base) * 100.0

    async def _handle_alerts_request(self, user_input: str):
        """
        Handle position alerts request.

        Args:
            user_input: User's natural language input
        """
        print("\n📊 Checking Position Alerts...")

        try:
            if not self.trading_cycle:
                print("❌ Trading cycle not initialized")
                return

            # Fetch current broker state
            broker_state = self.trading_cycle.fetch_broker_state()

            # Check alerts using position tracker
            alerts = self.trading_cycle.position_tracker.check_alerts(broker_state)

            if not alerts:
                print("✅ No active alerts")
                print(f"   {len(broker_state.get('positions', []))} position(s) monitored")
            else:
                print(f"\n🔔 {len(alerts)} Alert(s) Generated:")
                for alert in alerts:
                    severity_emoji = {"INFO": "📊", "WARNING": "⚠️", "CRITICAL": "🚨"}.get(alert.severity, "⚠️")
                    print(f"   {severity_emoji} {alert.ticker}: {alert.alert_type.value}")
                    print(f"      Current: ${alert.current_price:.2f}")
                    if alert.details:
                        for key, value in alert.details.items():
                            print(f"      {key}: {value}")

            # Show alert history
            history = self.trading_cycle.position_tracker.get_alert_history()
            if history:
                print(f"\n📜 Alert History ({len(history)} total):")
                for alert in history[-5:]:  # Last 5
                    print(f"   • {alert.ticker} - {alert.alert_type.value} at {alert.timestamp.strftime('%H:%M:%S')}")

        except Exception as e:
            print(f"❌ Error checking alerts: {e}")
            logger.error(f"Alerts error: {e}", exc_info=True)

    async def _handle_scheduler_request(self, user_input: str):
        """
        Handle scheduler status/management request.

        Args:
            user_input: User's natural language input
        """
        print("\n🤖 Daily Scheduler Status...")

        try:
            if not self.scheduler:
                print("❌ Scheduler not initialized")
                return

            # Show scheduler configuration
            print(f"\nConfiguration:")
            print(f"   Enabled: {self.scheduler.config.get('enabled', False)}")
            print(f"   Morning routine: {self.scheduler.config.get('morning_routine_time')} ET")
            print(f"   Evening routine: {self.scheduler.config.get('evening_routine_time')} ET")
            print(f"   Max retries: {self.scheduler.config.get('max_retries')}")

            # Show recent execution history
            recent = self.scheduler.get_execution_history(days=1)
            if recent:
                print(f"\n📋 Recent Executions (today):")
                for entry in recent[:5]:
                    status_emoji = {"completed": "✅", "failed": "❌", "retrying": "🔄"}.get(entry.status, "⚠️")
                    print(f"   {status_emoji} {entry.task_name} - {entry.status}")
                    if entry.actual_end_time:
                        print(f"      Completed: {entry.actual_end_time}")
                    if entry.error_message:
                        print(f"      Error: {entry.error_message}")
            else:
                print("\n📋 No executions today")

            # Show what's scheduled next
            print(f"\n⏰ Scheduled Tasks:")
            for task in self.scheduler.tasks:
                print(f"   • {task.name}: {task.scheduled_time.strftime('%H:%M')} ET")

        except Exception as e:
            print(f"❌ Error checking scheduler: {e}")
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

        # Extract ticker if asking about specific position
        if "target on" in input_lower or "target for" in input_lower:
            # Try to extract ticker from query
            words = user_input.upper().split()
            # Common tickers to look for
            common_tickers = ['SPY', 'QQQ', 'TQQQ', 'SQQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA']
            for word in words:
                if word in common_tickers:
                    specific_ticker = word
                    break

        print("\n💼 Portfolio Status...")

        try:
            if not self.account_monitor:
                print("❌ Account monitor not initialized")
                return

            # Get account status (unless querying specific ticker)
            if not specific_ticker:
                account = self.account_monitor.get_account_status()

                print(f"\n💰 Account:")
                print(f"   Equity: ${float(account.get('equity', 0)):,.2f}")
                print(f"   Cash: ${float(account.get('cash', 0)):,.2f}")
                print(f"   Buying Power: ${float(account.get('buying_power', 0)):,.2f}")
                print(f"   Pattern Day Trader: {account.get('pattern_day_trader', False)}")

            # Get positions
            positions = self.account_monitor.get_positions()

            if specific_ticker:
                # Show details for specific position
                position = next((p for p in positions if p.get('symbol') == specific_ticker), None)
                if position:
                    qty = int(position.get('qty', 0))
                    symbol = position.get('symbol')
                    current_price = float(position.get('current_price', 0))
                    avg_entry = float(position.get('avg_entry_price', 0))
                    unrealized_pl = float(position.get('unrealized_pl', 0))
                    unrealized_plpc = float(position.get('unrealized_plpc', 0)) * 100

                    pl_emoji = "🟢" if unrealized_pl >= 0 else "🔴"
                    print(f"\n{pl_emoji} {symbol} Position Details:")
                    print(f"   Quantity: {qty} shares")
                    print(f"   Entry Price: ${avg_entry:.2f}")
                    print(f"   Current Price: ${current_price:.2f}")
                    print(f"   P/L: ${unrealized_pl:,.2f} ({unrealized_plpc:+.2f}%)")

                    # Show targets if available (from position tracker)
                    if self.trading_cycle and self.trading_cycle.position_tracker:
                        position_id = f"{symbol}_{avg_entry}"
                        tracked_pos = self.trading_cycle.position_tracker.positions.get(position_id)
                        if tracked_pos:
                            print(f"\n🎯 Price Targets:")
                            print(f"   Take Profit: ${tracked_pos.take_profit_price:.2f}")
                            print(f"   Stop Loss: ${tracked_pos.stop_loss_price:.2f}")
                            distance_to_tp = ((tracked_pos.take_profit_price - current_price) / current_price) * 100
                            distance_to_sl = ((current_price - tracked_pos.stop_loss_price) / current_price) * 100
                            print(f"   Distance to TP: {distance_to_tp:+.2f}%")
                            print(f"   Distance to SL: {distance_to_sl:+.2f}%")
                        else:
                            print(f"\n💡 No price targets set for {symbol}")
                else:
                    print(f"\n❌ No position found for {specific_ticker}")

            elif positions:
                print(f"\n📊 Positions ({len(positions)}):")
                for pos in positions:
                    qty = int(pos.get('qty', 0))
                    symbol = pos.get('symbol', 'UNKNOWN')
                    current_price = float(pos.get('current_price', 0))
                    market_value = float(pos.get('market_value', 0))
                    unrealized_pl = float(pos.get('unrealized_pl', 0))
                    unrealized_plpc = float(pos.get('unrealized_plpc', 0)) * 100

                    pl_emoji = "🟢" if unrealized_pl >= 0 else "🔴"
                    print(f"   {pl_emoji} {symbol}: {qty} shares @ ${current_price:.2f}")
                    print(f"      Value: ${market_value:,.2f}")
                    print(f"      P/L: ${unrealized_pl:,.2f} ({unrealized_plpc:+.2f}%)")
            else:
                print("\n📊 No open positions")

        except Exception as e:
            print(f"❌ Error checking portfolio: {e}")
            logger.error(f"Portfolio error: {e}", exc_info=True)
