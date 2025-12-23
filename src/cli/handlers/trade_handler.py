"""
Trade Handler - Extracted from cli_session.py.

Issue #509: Refactor cli_session.py into modular handlers
Handles trade request processing, signal conflict resolution, and trade execution.
"""

import logging
import platform
from typing import TYPE_CHECKING, Optional

from config_defaults.message_loader import CLIMessages as MSG  # noqa: N814

from src.cli.utils.input_parser import BUY_INDICATORS, SELL_INDICATORS, detect_user_intent
from src.cli.utils.suggestion_display import (
    calc_pct,
    display_position_context,
    display_result,
    display_suggestion,
)
from src.core.models import Signal
from src.utils.date_utils import now_iso

if TYPE_CHECKING:
    from src.core.trading_orchestrator import TradingOrchestrator
    from src.trading.scheduling.trading_cycle import CostEfficientTradeCycle

logger = logging.getLogger(__name__)


def _sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error messages to remove API keys and sensitive details.

    Returns simple user-friendly messages based on error type.
    Full details are logged separately for debugging.
    """
    error_str = str(error).lower()

    if "api" in error_str and (
        "key" in error_str or "401" in error_str or "authentication" in error_str
    ):
        return "Configuration error. Nothing done."

    if "could not parse" in error_str or "parse error" in error_str:
        return "Didn't understand that. Nothing done."

    if "ticker not found" in error_str:
        return "Symbol not found. It may not be available via your broker or data provider."

    if ("asset" in error_str and "not found" in error_str) or "symbol" in error_str:
        return "Symbol not recognized. Check the ticker spelling or try a US-listed stock."

    if (
        "no data" in error_str
        or "insufficient data" in error_str
        or "data unavailable" in error_str
        or "market data may be unavailable" in error_str
        or "invalid entry price" in error_str
    ):
        return "Not enough market data available for analysis. Try a more liquid symbol."

    if "invalid request" in error_str or "invalid format" in error_str:
        return "Didn't understand that. Nothing done."

    if "typeerror" in error_str or "nonetype" in error_str or "unsupported format" in error_str:
        logger.error(f"Display format error: {error}")
        return "Analysis failed - missing price data. Try again or check the ticker."

    logger.warning(f"Unhandled error type: {type(error).__name__}: {error}")
    return f"Something went wrong. Error: {type(error).__name__}"


class TradeHandler:
    """
    Handles trade request processing for CLI session.

    Extracted from CLISession._handle_trade_request for modularity.
    """

    def __init__(
        self,
        orchestrator: "TradingOrchestrator",
        account_monitor,
        trading_cycle: Optional["CostEfficientTradeCycle"],
        autonomy_mode: str = "confirm",
        user_id: str = "cli_user",
    ):
        """
        Initialize trade handler.

        Args:
            orchestrator: TradingOrchestrator instance
            account_monitor: AlpacaAccountMonitor instance
            trading_cycle: CostEfficientTradeCycle instance
            autonomy_mode: "confirm" or "auto"
            user_id: User ID for orchestrator
        """
        self.orchestrator = orchestrator
        self.account_monitor = account_monitor
        self.trading_cycle = trading_cycle
        self.autonomy_mode = autonomy_mode
        self.user_id = user_id

    def set_autonomy_mode(self, mode: str) -> None:
        """Update autonomy mode."""
        self.autonomy_mode = mode

    async def handle_trade_request(self, user_input: str) -> None:
        """
        Process user trade request via orchestrator.

        Issue #347: Respects user intent - when user says "buy", we show "BUY (as requested)"
        and treat signals as context, not override.

        Args:
            user_input: User's natural language input
        """
        print(MSG.ANALYZING_TRADE)

        try:
            original_input = user_input.lower().strip()
            user_intent = detect_user_intent(original_input)

            # Process request via orchestrator
            decision = await self.orchestrator.process_request(user_input, self.user_id)

            # Check position context
            position = self._check_position_for_ticker(decision.suggestion.ticker)
            display_position_context(decision.suggestion.ticker, position)

            # Handle signal conflicts
            decision = await self._handle_signal_conflicts(
                decision, position, original_input, user_intent
            )
            if decision is None:
                return  # User cancelled or request handled

            # Display suggestion
            override_mode = None
            if user_intent == "buy":
                override_mode = "USER_OVERRIDE_LONG"
            elif user_intent == "sell":
                override_mode = "USER_OVERRIDE_SHORT"
            display_suggestion(decision.suggestion, position, override_mode)

            # Check if review-only
            parsed_request = await self.orchestrator.parser.parse(user_input, self.user_id)
            is_review_only = parsed_request.action == "review"

            # Get confirmation
            if is_review_only:
                print("\n📊 Analysis complete. No trade execution requested.")
                decision.approved = False
            elif self.autonomy_mode == "confirm":
                decision.approved = self._get_confirmation()
            else:
                decision.approved = True
                print(MSG.AUTO_EXECUTING)

            # Execute if approved
            if decision.approved:
                result = await self.orchestrator.execute_decision(decision)
                display_result(result)
                self._update_local_state_after_trade(decision, result)
            elif not is_review_only:
                print(MSG.TRADE_CANCELLED)

        except (ValueError, OSError, RuntimeError, AttributeError) as e:
            sanitized_msg = _sanitize_error_message(e)
            error_prefix = "[ERROR]" if platform.system() == "Windows" else MSG.EMOJI["error"]
            print(f"\n{error_prefix} {sanitized_msg}")
            logger.debug(f"Request processing error: {e}", exc_info=True)

    async def _handle_signal_conflicts(
        self, decision, position, original_input: str, user_intent: str
    ):
        """
        Handle conflicts between user intent and technical signals.

        Returns:
            Updated decision or None if cancelled
        """
        suggestion = decision.suggestion
        signal = suggestion.signal.value.upper()

        # SELL signal with no position
        if signal == "SELL" and not position:
            user_wants_buy = any(ind in original_input for ind in BUY_INDICATORS)
            user_wants_sell = any(ind in original_input for ind in SELL_INDICATORS)

            if user_wants_buy:
                return await self._handle_buy_override(decision)
            elif not user_wants_sell:
                return await self._handle_ambiguous_sell(decision)
            else:
                self._show_cannot_sell_message(suggestion.ticker)
                return None

        # SELL signal with position - show warning
        elif signal == "SELL" and position:
            print(f"\n{MSG.EMOJI['warning']} SELL will close your position in {suggestion.ticker}")

        # HOLD signal with explicit user intent
        elif signal == "HOLD":
            user_wants_buy = any(ind in original_input for ind in BUY_INDICATORS)
            user_wants_sell = any(ind in original_input for ind in SELL_INDICATORS)

            if user_wants_buy or user_wants_sell:
                decision = self._handle_hold_with_intent(decision, user_wants_buy)
                if decision is None:
                    return None

        return decision

    async def _handle_buy_override(self, decision):
        """Handle user wanting to BUY despite SELL signal."""
        suggestion = decision.suggestion

        print(f"\n{MSG.EMOJI.get('warning', '⚠️')} SIGNAL CONFLICT DETECTED")
        print("   → You requested: LONG (BUY) position")
        print("   → Technical analysis suggests: SHORT (SELL)")
        print(
            f"\n📊 Technical Indicators (based on {suggestion.reasoning[0] if suggestion.reasoning else 'MACD+RSI'}):"
        )

        display_suggestion(suggestion, None, override_mode="USER_OVERRIDE_LONG")

        print("\n💡 Human-in-Loop Decision:")
        print("   → The system recommends SELL, but you want to go LONG")
        print("   → This could be based on news, fundamentals, or your own analysis")
        print("   → Remember: Technical indicators are backward-looking")

        proceed = (
            input(f"\n   Do you still want to BUY {suggestion.ticker}? [yes/no]: ").strip().lower()
        )

        if proceed in ["yes", "y", "1"]:
            print(f"\n{MSG.EMOJI['info']} ✅ User override confirmed - placing BUY order")
            print("   → Overriding SELL signal from technical analysis")

            # Flip signal to BUY
            decision.suggestion.signal = Signal.BUY
            self._invert_stop_target_for_buy(decision.suggestion)

            self._print_adjusted_trade_plan(decision.suggestion, "BUY")
            return decision
        else:
            print(f"\n{MSG.EMOJI['info']} Order cancelled. You can review alternatives:")
            print(f"   • Type 'review {suggestion.ticker}' for detailed analysis")
            print(f"   • Type 'short {suggestion.ticker}' to follow the SELL signal")
            return None

    async def _handle_ambiguous_sell(self, decision):
        """Handle ambiguous request when SELL signal but no position."""
        suggestion = decision.suggestion

        print(
            f"\n{MSG.EMOJI.get('question', '❓')} The analysis suggests {suggestion.ticker} might go DOWN, but you don't own any shares yet."
        )
        print("\n   What would you like to do?")
        print("   1. BUY shares (bet the stock will go UP)")
        print("   2. SHORT shares (bet the stock will go DOWN - advanced strategy)")
        print("   3. Just see the analysis (don't trade)")

        clarification = input("\n   Your choice [1/2/3 or buy/short/review]: ").strip().lower()

        if clarification in ["1", "buy", "b", "long", "l", "up", "bullish"]:
            print(f"\n{MSG.EMOJI['info']} Got it! Preparing BUY order for {suggestion.ticker}...")

            decision.suggestion.signal = Signal.BUY
            self._invert_stop_target_for_buy(decision.suggestion)
            self._print_adjusted_trade_plan(decision.suggestion, "BUY")
            return decision

        elif clarification in ["2", "short", "s", "down", "bearish", "sell"]:
            print(
                f"\n{MSG.EMOJI['warning']} SHORT SELLING is not currently supported by this system."
            )
            print("   ℹ️  Short selling = betting a stock will go down (advanced/risky)")
            print("   → This system only supports buying stocks (betting they'll go up)")
            print("   → Suggestion cancelled")
            return None

        elif clarification in ["3", "review", "r", "analysis", "just show", "view", "look"]:
            print(
                f"\n{MSG.EMOJI['info']} Showing analysis for {suggestion.ticker} (information only, no trade)"
            )
            display_suggestion(suggestion, None)
            print(
                f"\n   💡 Tip: If you want to trade on this analysis, type 'buy {suggestion.ticker}' or 'short {suggestion.ticker}'"
            )
            return None

        else:
            print(f"\n{MSG.EMOJI['info']} No problem! Cancelled.")
            print(
                f"   💡 Tip: You can be specific next time, e.g., 'buy {suggestion.ticker}' or 'analyze {suggestion.ticker}'"
            )
            return None

    def _show_cannot_sell_message(self, ticker: str) -> None:
        """Show message when user wants to sell but has no position."""
        print(f"\n{MSG.EMOJI['error']} Cannot SELL or CLOSE position in {ticker}")
        print(f"   → You don't currently own any shares of {ticker}")
        print("   → To sell a stock, you must buy it first")
        print(f"\n   💡 Did you mean to SHORT {ticker}? (bet it will go down)")
        print("      Short selling is not currently supported by this system.")

    def _handle_hold_with_intent(self, decision, user_wants_buy: bool):
        """Handle HOLD signal when user explicitly wants to trade."""
        suggestion = decision.suggestion

        print(f"\n{MSG.EMOJI.get('info', 'ℹ️')} SIGNALS INCONCLUSIVE")
        print("   → Technical indicators suggest: HOLD (no clear direction)")
        print(f"   → You requested: {'BUY' if user_wants_buy else 'SELL'}")

        current_price = getattr(suggestion, "current_price", None)
        if current_price is None or current_price <= 0:
            indicators = getattr(suggestion, "indicators", {})
            current_price = indicators.get("current_price", 0.0)

        if not current_price or current_price <= 0:
            print(f"\n{MSG.EMOJI['error']} Cannot determine current price for {suggestion.ticker}")
            print("   → Try refreshing market data or check during market hours")
            return None

        # Get mode params
        try:
            from src.core.trading_modes import get_mode_manager

            mode_params = get_mode_manager().get_parameters()
            stop_pct = mode_params.stop_loss
            target_pct = mode_params.take_profit
            position_size_pct = mode_params.position_size
        except Exception:
            stop_pct = 0.05
            target_pct = 0.10
            position_size_pct = 0.05

        entry_price = round(current_price, 2)

        if user_wants_buy:
            decision.suggestion.signal = Signal.BUY
            stop_loss = round(current_price * (1 - stop_pct), 2)
            take_profit = round(current_price * (1 + target_pct), 2)
        else:
            decision.suggestion.signal = Signal.SELL
            stop_loss = round(current_price * (1 + stop_pct), 2)
            take_profit = round(current_price * (1 - target_pct), 2)

        decision.suggestion.entry_price = entry_price
        decision.suggestion.stop_loss = stop_loss
        decision.suggestion.take_profit = take_profit

        # Calculate quantity if needed
        if decision.suggestion.recommended_quantity == 0:
            self._calculate_quantity(
                decision.suggestion, entry_price, stop_loss, take_profit, position_size_pct
            )

        # Clear stale warnings
        decision.suggestion.warnings = [
            w for w in decision.suggestion.warnings if "No entry price" not in w
        ]

        self._print_adjusted_trade_plan(decision.suggestion, "BUY" if user_wants_buy else "SELL")
        return decision

    def _invert_stop_target_for_buy(self, suggestion) -> None:
        """Invert stop/target for BUY when originally calculated for SELL."""
        entry = suggestion.entry_price
        old_stop = suggestion.stop_loss
        old_target = suggestion.take_profit

        stop_distance = abs(old_stop - entry)
        target_distance = abs(old_target - entry)

        suggestion.stop_loss = round(entry - stop_distance, 2)
        suggestion.take_profit = round(entry + target_distance, 2)

    def _print_adjusted_trade_plan(self, suggestion, direction: str) -> None:
        """Print adjusted trade plan after signal override."""
        print(f"\n   📊 Adjusted for {direction}:")
        print(f"      Entry:  ${suggestion.entry_price:.2f}")
        print(
            f"      Stop:   ${suggestion.stop_loss:.2f} ({calc_pct(suggestion.entry_price, suggestion.stop_loss):.1f}%)"
        )
        print(
            f"      Target: ${suggestion.take_profit:.2f} ({calc_pct(suggestion.entry_price, suggestion.take_profit):.1f}%)"
        )
        print(f"      Quantity: {suggestion.recommended_quantity} shares")

    def _calculate_quantity(
        self, suggestion, entry_price, stop_loss, take_profit, position_size_pct
    ) -> None:
        """Calculate quantity based on buying power and position size."""
        try:
            if self.account_monitor:
                account = self.account_monitor.get_account_info()
                buying_power = float(account.get("buying_power", 0))
                trade_value = buying_power * position_size_pct
                quantity = int(trade_value / entry_price)
                if quantity > 0:
                    suggestion.recommended_quantity = quantity
                    max_loss = quantity * abs(entry_price - stop_loss)
                    suggestion.max_loss_usd = round(max_loss, 2)
                    potential_gain = quantity * abs(take_profit - entry_price)
                    if max_loss > 0:
                        suggestion.risk_reward_ratio = round(potential_gain / max_loss, 2)
        except Exception as e:
            logger.debug(f"Could not calculate quantity: {e}")

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
        except (AttributeError, ValueError, OSError) as e:
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

    def _update_local_state_after_trade(self, decision, result) -> None:
        """
        Update local state after successful trade.

        Issue #385: Bracket Order Stop-Loss Not Logged to Local State on Placement

        Args:
            decision: TradeDecision with suggestion
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

            self.trading_cycle.local_state["positions"][symbol] = {
                "entry_price": suggestion.entry_price,
                "quantity": quantity,
                "entry_time": now_iso(),
                "source": "CLI_TRADE",
                "stop_price": suggestion.stop_loss,
                "target_price": suggestion.take_profit,
                "order_id": result.entry_order_id,
            }

            self.trading_cycle.save_local_state()

            logger.info(
                f"Updated local state for {symbol}: "
                f"stop=${suggestion.stop_loss:.2f}, target=${suggestion.take_profit:.2f}"
            )

        except (AttributeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to update local state after trade: {e}")
