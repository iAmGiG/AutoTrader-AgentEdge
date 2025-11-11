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

# Import CLI messages configuration
from config_defaults.cli_messages import (
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

        else:
            print(MSG.UNKNOWN_COMMAND.format(command=command))
            print(MSG.USE_HELP)

        return True

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
            # Let LLM parser classify the request type
            request = await self.orchestrator.parser.parse(user_input, self.user_id)

            if request.request_type == "status_query":
                # Status query detected - route based on content
                input_lower = user_input.lower()

                if any(word in input_lower for word in ["order", "orders"]):
                    await self._handle_orders_request(user_input)
                elif any(word in input_lower for word in ["position", "positions", "holding", "holdings"]):
                    await self._handle_portfolio_request(user_input)
                elif any(word in input_lower for word in ["portfolio", "account", "balance", "buying power", "equity", "cash"]):
                    await self._handle_portfolio_request(user_input)
                else:
                    # Default status query → show portfolio
                    await self._handle_portfolio_request(user_input)
            else:
                # Trade request → process through orchestrator
                await self._handle_trade_request(user_input)

        except Exception as e:
            logger.error(f"Error routing request: {e}", exc_info=True)
            # Fallback to trade handler
            await self._handle_trade_request(user_input)

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

            # Step 2: Check for SELL signal without position (prevent unintentional shorting)
            if decision.suggestion.signal.value.upper() == "SELL":
                # TODO: Check if we actually hold this position
                # For now, warn the user
                print(MSG.SELL_WARNING)

            # Step 3: Display suggestion
            self._display_suggestion(decision.suggestion)

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
            else:
                print(MSG.ERROR_PROCESSING.format(error=e))

            logger.error(f"Request processing error: {e}", exc_info=True)
            # Traceback logged but not shown to user

    def _display_suggestion(self, suggestion):
        """
        Display trade suggestion to user.

        Args:
            suggestion: TradeSuggestion object
        """
        print("\n" + MSG.SUGGESTION_SEPARATOR)
        print(MSG.SUGGESTION_HEADER.format(ticker=suggestion.ticker, price=suggestion.entry_price))
        print(MSG.SUGGESTION_SEPARATOR)

        # Signal
        signal_emoji = get_signal_emoji(suggestion.signal.value)
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
                print(MSG.POSITIONS_MONITORED.format(count=len(broker_state.get('positions', []))))
            else:
                print(MSG.ALERTS_HEADER.format(count=len(alerts)))
                for alert in alerts:
                    severity_emoji = get_alert_severity_emoji(alert.severity)
                    print(MSG.ALERT_ITEM.format(
                        emoji=severity_emoji,
                        ticker=alert.ticker,
                        alert_type=alert.alert_type.value,
                        price=alert.current_price
                    ))
                    if alert.details:
                        for key, value in alert.details.items():
                            print(MSG.ALERT_DETAIL.format(key=key, value=value))

            # Show alert history
            history = self.trading_cycle.position_tracker.get_alert_history()
            if history:
                print(MSG.ALERT_HISTORY_HEADER.format(count=len(history)))
                for alert in history[-5:]:  # Last 5
                    print(MSG.ALERT_HISTORY_ITEM.format(
                        ticker=alert.ticker,
                        alert_type=alert.alert_type.value,
                        time=alert.timestamp.strftime('%H:%M:%S')
                    ))

        except Exception as e:
            print(MSG.ERROR_CHECKING_ALERTS.format(error=e))
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
            print(MSG.SCHEDULER_STATUS.format(emoji=status_emoji, status=status_text))

            print(MSG.SCHEDULER_CONFIG_HEADER)
            print(MSG.SCHEDULER_CONFIG.format(
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

                    print(MSG.SCHEDULER_HISTORY_ITEM.format(
                        emoji=status_emoji,
                        task=entry.task_name,
                        status=entry.status.upper(),
                        time=time_str
                    ))

                    if entry.error_message:
                        print(MSG.SCHEDULER_ERROR.format(error=entry.error_message[:80]))

                    # Show retry info if applicable
                    if hasattr(entry, 'retry_count') and entry.retry_count > 0:
                        print(MSG.SCHEDULER_RETRIES.format(count=entry.retry_count))
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

                print(MSG.SCHEDULER_NEXT.format(
                    task=next_task,
                    time=next_run.strftime('%H:%M %p'),
                    hours=hours,
                    minutes=minutes
                ))
            except Exception as calc_error:
                print(MSG.SCHEDULER_NEXT_ERROR.format(error=calc_error))

            # Usage instructions
            print(MSG.SCHEDULER_COMMANDS)

        except Exception as e:
            print(MSG.ERROR_CHECKING_SCHEDULER.format(error=e))
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

        print(MSG.PORTFOLIO_HEADER)

        try:
            if not self.account_monitor:
                print(MSG.PORTFOLIO_NOT_INITIALIZED)
                return

            # Get account status (unless querying specific ticker)
            if not specific_ticker:
                account = self.account_monitor.get_account_status()

                print(MSG.ACCOUNT_HEADER)
                print(MSG.ACCOUNT_INFO.format(
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
                    print(MSG.POSITION_DETAILS_HEADER.format(emoji=pl_emoji, symbol=symbol))
                    print(MSG.POSITION_DETAILS.format(
                        qty=qty,
                        entry=avg_entry,
                        current=current_price,
                        pl=unrealized_pl,
                        pl_pct=unrealized_plpc
                    ))

                    # Show targets if available (from position tracker)
                    if self.trading_cycle and self.trading_cycle.position_tracker:
                        position_id = f"{symbol}_{avg_entry}"
                        tracked_pos = self.trading_cycle.position_tracker.positions.get(position_id)
                        if tracked_pos:
                            distance_to_tp = ((tracked_pos.take_profit_price - current_price) / current_price) * 100
                            distance_to_sl = ((current_price - tracked_pos.stop_loss_price) / current_price) * 100
                            print(MSG.PRICE_TARGETS_HEADER)
                            print(MSG.PRICE_TARGETS.format(
                                tp=tracked_pos.take_profit_price,
                                sl=tracked_pos.stop_loss_price,
                                tp_dist=distance_to_tp,
                                sl_dist=distance_to_sl
                            ))
                        else:
                            print(MSG.NO_TARGETS.format(symbol=symbol))
                else:
                    print(MSG.NO_POSITION.format(ticker=specific_ticker))

            elif positions:
                print(MSG.POSITIONS_HEADER.format(count=len(positions)))
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
                    print(MSG.POSITION_ITEM.format(
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
            print(MSG.ERROR_CHECKING_PORTFOLIO.format(error=e))
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
                print(MSG.ORDERS_HEADER.format(count=len(orders)))
                for order in orders:
                    symbol = order.get('symbol', 'UNKNOWN')
                    side = order.get('side', 'UNKNOWN')
                    qty = order.get('qty', 0)
                    order_type = order.get('type', 'UNKNOWN')
                    status = order.get('status', 'UNKNOWN')
                    order_id = order.get('id', 'N/A')

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
                    print(MSG.ORDER_ITEM.format(
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
            print(MSG.ERROR_CHECKING_ORDERS.format(error=e))
            logger.error(f"Orders error: {e}", exc_info=True)
