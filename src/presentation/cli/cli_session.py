"""
CLI Session - Interactive REPL for trading assistant.

MVP: Basic input/output loop with simple formatting.
"""

import asyncio
import logging
from typing import Optional

from core.trading_orchestrator import TradingOrchestrator
from core.models import Signal


logger = logging.getLogger(__name__)


class CLISession:
    """
    Interactive CLI session for trade assistant.

    MVP: Simple input/output loop.
    Future: Rich formatting, better UX.
    """

    def __init__(self, orchestrator: TradingOrchestrator):
        """
        Initialize CLI session.

        Args:
            orchestrator: Wired TradingOrchestrator
        """
        self.orchestrator = orchestrator
        self.autonomy_mode = "confirm"  # or "auto"
        self.user_id = "cli_user"

        logger.info("CLISession initialized")

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
                # Get user input
                user_input = input("\n> ").strip()

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
        print("   AutoGen Trading Assistant")
        print("=" * 70)
        print(f"Mode: {self.autonomy_mode.upper()}")
        print("\nCommands:")
        print("  /help    - Show help")
        print("  /exit    - Exit (or Ctrl+C)")
        print("  /auto    - Enable auto-execute mode")
        print("  /confirm - Enable confirm mode (default)")
        print("\nExample:")
        print("  > is SPY at 600 a good entry?")
        print("  > buy 10 AAPL")
        print("\nNote: In auto mode, you can still exit with /exit or Ctrl+C")
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

        elif cmd == "/auto":
            self.autonomy_mode = "auto"
            print("✅ Auto-execute mode enabled")

        elif cmd == "/confirm":
            self.autonomy_mode = "confirm"
            print("✅ Confirm mode enabled (default)")

        else:
            print(f"Unknown command: {command}")
            print("Use /help to see available commands")

        return True

    async def _process_request(self, user_input: str):
        """
        Process user trade request.

        Args:
            user_input: User's natural language input
        """
        print("\n⏳ Analyzing...")

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
        print(f"   Stop:   ${suggestion.stop_loss:.2f} ({self._calc_pct(suggestion.entry_price, suggestion.stop_loss):+.1f}%)")
        print(f"   Target: ${suggestion.take_profit:.2f} ({self._calc_pct(suggestion.entry_price, suggestion.take_profit):+.1f}%)")
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
