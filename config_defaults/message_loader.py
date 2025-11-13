"""
Message Loader for CLI
Loads messages from YAML configuration with backward compatibility.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any


class MessageLoader:
    """Loads and provides access to CLI messages from YAML config."""

    def __init__(self, config_file: str = None):
        """
        Initialize message loader.

        Args:
            config_file: Path to YAML config file (defaults to cli_messages.yaml)
        """
        if config_file is None:
            # Default to cli_messages.yaml in same directory
            config_dir = Path(__file__).parent
            config_file = config_dir / "cli_messages.yaml"

        self.config_file = config_file
        self._messages = self._load_messages()

    def _load_messages(self) -> Dict[str, Any]:
        """Load messages from YAML file."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            # Fallback to empty dict if loading fails
            print(f"⚠️  Warning: Could not load messages from {self.config_file}: {e}")
            print(f"   Using minimal fallback messages.")
            return self._get_fallback_messages()

    def _get_fallback_messages(self) -> Dict[str, Any]:
        """Minimal fallback messages if YAML fails to load."""
        return {
            'emojis': {
                'error': '❌',
                'success': '✅',
                'warning': '⚠️',
                'info': '📊'
            },
            'errors': {
                'processing': "❌ Error: {error}",
                'garbage_input': "❌ Invalid input. Type /help for commands."
            }
        }

    def get(self, path: str, **kwargs) -> str:
        """
        Get message by dot-notation path with formatting.

        Args:
            path: Dot-separated path (e.g., 'errors.invalid_ticker')
            **kwargs: Format parameters for the message

        Returns:
            Formatted message string

        Examples:
            >>> loader.get('errors.invalid_ticker')
            >>> loader.get('suggestion.header', ticker='AAPL', price=150.25)
        """
        keys = path.split('.')
        value = self._messages

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return f"[Missing message: {path}]"
            else:
                return f"[Invalid path: {path}]"

        # Format if string and kwargs provided
        if isinstance(value, str) and kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as e:
                return f"[Format error in {path}: missing {e}]"

        return value if isinstance(value, str) else str(value)

    def emoji(self, name: str) -> str:
        """
        Get emoji by name.

        Args:
            name: Emoji name (e.g., 'success', 'error', 'buy')

        Returns:
            Emoji character
        """
        return self._messages.get('emojis', {}).get(name, '•')

    def reload(self):
        """Reload messages from YAML file (useful for hot-reloading)."""
        self._messages = self._load_messages()


# ========================================================================
# Backward Compatibility Layer
# ========================================================================

class CLIMessages:
    """
    Backward-compatible wrapper around MessageLoader.
    Provides same interface as old cli_messages.py
    """

    _loader = MessageLoader()

    # Emojis - provides dict-like access
    class _EmojiProxy:
        def __getitem__(self, key):
            return CLIMessages._loader.emoji(key)

        def get(self, key, default=None):
            """Dict-like .get() method with default."""
            try:
                return CLIMessages._loader.emoji(key)
            except:
                return default if default is not None else '•'

    EMOJI = _EmojiProxy()

    # Welcome / Help
    WELCOME_BANNER = "=" * 70
    WELCOME_TITLE = _loader.get('welcome.title')
    HELP_COMMANDS = _loader.get('help.commands')

    # Mode toggle
    MODE_SWITCHED_AUTO = _loader.get('mode.switched_auto')
    MODE_SWITCHED_CONFIRM = _loader.get('mode.switched_confirm')

    # Exit
    EXIT_MESSAGE = _loader.get('exit.message')

    # Commands
    UNKNOWN_COMMAND = _loader.get('commands.unknown')  # Template for .format()
    USE_HELP = _loader.get('commands.use_help')

    # Trade requests
    ANALYZING_TRADE = _loader.get('trade.analyzing')
    AUTO_EXECUTING = _loader.get('trade.auto_executing')
    TRADE_CANCELLED = _loader.get('trade.cancelled')
    SELL_WARNING = _loader.get('trade.sell_warning')

    # Errors - all templates for .format()
    ERROR_PROCESSING = _loader.get('errors.processing')
    ERROR_INVALID_TICKER = _loader.get('errors.invalid_ticker')
    ERROR_GARBAGE_INPUT = _loader.get('errors.garbage_input')
    ERROR_EMPTY_TICKER = _loader.get('errors.empty_ticker')

    # Suggestion display - all templates for .format()
    SUGGESTION_SEPARATOR = _loader.get('suggestion.separator')
    SUGGESTION_HEADER = _loader.get('suggestion.header')
    SIGNAL_DISPLAY = _loader.get('suggestion.signal_display')
    CONFIDENCE_DISPLAY = _loader.get('suggestion.confidence')
    ANALYSIS_HEADER = _loader.get('suggestion.analysis_header')
    ANALYSIS_ITEM = _loader.get('suggestion.analysis_item')
    ENTRY_PLAN_HEADER = _loader.get('suggestion.entry_plan_header')
    ENTRY_PLAN = _loader.get('suggestion.entry_plan')
    PORTFOLIO_IMPACT_HEADER = _loader.get('suggestion.portfolio_impact_header')
    PORTFOLIO_IMPACT = _loader.get('suggestion.portfolio_impact')
    WARNINGS_HEADER = _loader.get('suggestion.warnings_header')
    WARNING_ITEM = _loader.get('suggestion.warning_item')

    # Confirmation
    CONFIRM_PROMPT = _loader.get('confirmation.prompt')
    CONFIRM_INVALID = _loader.get('confirmation.invalid')

    # Order results - all templates for .format()
    RESULT_SEPARATOR = _loader.get('order_result.separator')
    ORDER_SUCCESS_HEADER = _loader.get('order_result.success_header')
    ORDER_SUCCESS = _loader.get('order_result.success')
    ORDER_FAILED_HEADER = _loader.get('order_result.failed_header')
    ORDER_FAILED = _loader.get('order_result.failed')
    ORDER_ERROR = _loader.get('order_result.error_detail')

    # Alerts
    CHECKING_ALERTS = _loader.get('alerts.checking')
    ALERTS_NOT_INITIALIZED = _loader.get('alerts.not_initialized')
    NO_ALERTS = _loader.get('alerts.no_alerts')

    @staticmethod
    def POSITIONS_MONITORED(count):
        return CLIMessages._loader.get('alerts.positions_monitored', count=count)

    @staticmethod
    def ALERTS_HEADER(count):
        return CLIMessages._loader.get('alerts.header', count=count)

    @staticmethod
    def ALERT_ITEM(emoji, ticker, alert_type, price):
        return CLIMessages._loader.get(
            'alerts.alert_item',
            emoji=emoji, ticker=ticker, alert_type=alert_type, price=price
        )

    @staticmethod
    def ALERT_DETAIL(key, value):
        return CLIMessages._loader.get('alerts.alert_detail', key=key, value=value)

    @staticmethod
    def ALERT_HISTORY_HEADER(count):
        return CLIMessages._loader.get('alerts.history_header', count=count)

    @staticmethod
    def ALERT_HISTORY_ITEM(ticker, alert_type, time):
        return CLIMessages._loader.get(
            'alerts.history_item',
            ticker=ticker, alert_type=alert_type, time=time
        )

    @staticmethod
    def ERROR_CHECKING_ALERTS(error):
        return CLIMessages._loader.get('alerts.error', error=error)

    # Scheduler
    SCHEDULER_HEADER = _loader.get('scheduler.header')
    SCHEDULER_SEPARATOR = _loader.get('scheduler.separator')
    SCHEDULER_NOT_INITIALIZED = _loader.get('scheduler.not_initialized')

    @staticmethod
    def SCHEDULER_STATUS(emoji, status):
        return CLIMessages._loader.get('scheduler.status', emoji=emoji, status=status)

    SCHEDULER_CONFIG_HEADER = _loader.get('scheduler.config_header')

    @staticmethod
    def SCHEDULER_CONFIG(morning, evening, retries):
        return CLIMessages._loader.get(
            'scheduler.config',
            morning=morning, evening=evening, retries=retries
        )

    SCHEDULER_ROUTINES_HEADER = _loader.get('scheduler.routines_header')
    MORNING_ROUTINE = _loader.get('scheduler.morning_routine')
    EVENING_ROUTINE = _loader.get('scheduler.evening_routine')
    SCHEDULER_HISTORY_HEADER = _loader.get('scheduler.history_header')

    @staticmethod
    def SCHEDULER_HISTORY_ITEM(emoji, task, status, time):
        return CLIMessages._loader.get(
            'scheduler.history_item',
            emoji=emoji, task=task, status=status, time=time
        )

    @staticmethod
    def SCHEDULER_ERROR(error):
        return CLIMessages._loader.get('scheduler.error_detail', error=error)

    @staticmethod
    def SCHEDULER_RETRIES(count):
        return CLIMessages._loader.get('scheduler.retries', count=count)

    SCHEDULER_NO_HISTORY = _loader.get('scheduler.no_history')
    SCHEDULER_NEXT_HEADER = _loader.get('scheduler.next_header')

    @staticmethod
    def SCHEDULER_NEXT(task, time, hours, minutes):
        return CLIMessages._loader.get(
            'scheduler.next',
            task=task, time=time, hours=hours, minutes=minutes
        )

    @staticmethod
    def SCHEDULER_NEXT_ERROR(error):
        return CLIMessages._loader.get('scheduler.next_error', error=error)

    SCHEDULER_COMMANDS = _loader.get('scheduler.commands')

    @staticmethod
    def ERROR_CHECKING_SCHEDULER(error):
        return CLIMessages._loader.get('scheduler.error', error=error)

    # Portfolio
    PORTFOLIO_HEADER = _loader.get('portfolio.header')
    PORTFOLIO_NOT_INITIALIZED = _loader.get('portfolio.not_initialized')
    ACCOUNT_HEADER = _loader.get('portfolio.account_header')

    @staticmethod
    def ACCOUNT_INFO(equity, cash, buying_power, pdt):
        return CLIMessages._loader.get(
            'portfolio.account_info',
            equity=equity, cash=cash, buying_power=buying_power, pdt=pdt
        )

    @staticmethod
    def POSITIONS_HEADER(count):
        return CLIMessages._loader.get('portfolio.positions_header', count=count)

    @staticmethod
    def POSITION_ITEM(emoji, symbol, qty, entry, current, value, pl, pl_pct):
        return CLIMessages._loader.get(
            'portfolio.position_item',
            emoji=emoji, symbol=symbol, qty=qty, entry=entry,
            current=current, value=value, pl=pl, pl_pct=pl_pct
        )

    @staticmethod
    def POSITION_DETAILS_HEADER(emoji, symbol):
        return CLIMessages._loader.get(
            'portfolio.position_details_header',
            emoji=emoji, symbol=symbol
        )

    @staticmethod
    def POSITION_DETAILS(qty, entry, current, pl, pl_pct):
        return CLIMessages._loader.get(
            'portfolio.position_details',
            qty=qty, entry=entry, current=current, pl=pl, pl_pct=pl_pct
        )

    PRICE_TARGETS_HEADER = _loader.get('portfolio.price_targets_header')

    @staticmethod
    def PRICE_TARGETS(tp, sl, tp_dist, sl_dist):
        return CLIMessages._loader.get(
            'portfolio.price_targets',
            tp=tp, sl=sl, tp_dist=tp_dist, sl_dist=sl_dist
        )

    @staticmethod
    def NO_TARGETS(symbol):
        return CLIMessages._loader.get('portfolio.no_targets', symbol=symbol)

    @staticmethod
    def NO_POSITION(ticker):
        return CLIMessages._loader.get('portfolio.no_position', ticker=ticker)

    NO_POSITIONS = _loader.get('portfolio.no_positions')

    @staticmethod
    def ERROR_CHECKING_PORTFOLIO(error):
        return CLIMessages._loader.get('portfolio.error', error=error)

    # Orders
    CHECKING_ORDERS = _loader.get('orders.checking')
    ORDERS_NOT_INITIALIZED = _loader.get('orders.not_initialized')
    NO_ORDERS = _loader.get('orders.no_orders')

    @staticmethod
    def ORDERS_HEADER(count):
        return CLIMessages._loader.get('orders.header', count=count)

    @staticmethod
    def ORDER_ITEM(emoji, side, qty, symbol, price, type, status, order_id):
        return CLIMessages._loader.get(
            'orders.order_item',
            emoji=emoji, side=side, qty=qty, symbol=symbol,
            price=price, type=type, status=status, order_id=order_id
        )

    @staticmethod
    def ERROR_CHECKING_ORDERS(error):
        return CLIMessages._loader.get('orders.error', error=error)


# ========================================================================
# Helper Functions (remain the same)
# ========================================================================

def get_signal_emoji(signal_value: str) -> str:
    """Get emoji for trading signal."""
    signal_upper = signal_value.upper()
    if signal_upper == "BUY":
        return CLIMessages.EMOJI["buy"]
    elif signal_upper == "SELL":
        return CLIMessages.EMOJI["sell"]
    elif signal_upper == "HOLD":
        return CLIMessages.EMOJI["hold"]
    return CLIMessages.EMOJI["check"]


def get_pl_emoji(pl_value: float) -> str:
    """Get emoji for profit/loss."""
    if pl_value > 0:
        return CLIMessages.EMOJI["profit"]
    elif pl_value < 0:
        return CLIMessages.EMOJI["loss"]
    return CLIMessages.EMOJI["neutral"]


def get_side_emoji(side: str) -> str:
    """Get emoji for order side."""
    if side.upper() == "BUY":
        return CLIMessages.EMOJI["profit"]
    elif side.upper() == "SELL":
        return CLIMessages.EMOJI["loss"]
    return CLIMessages.EMOJI["neutral"]


def get_status_emoji(status: str) -> str:
    """Get emoji for scheduler execution status."""
    status_map = {
        "completed": CLIMessages.EMOJI["success"],
        "failed": CLIMessages.EMOJI["error"],
        "retrying": CLIMessages.EMOJI["retry"],
        "partial": CLIMessages.EMOJI["warning"],
    }
    return status_map.get(status.lower(), CLIMessages.EMOJI["neutral"])


def get_alert_severity_emoji(severity: str) -> str:
    """Get emoji for alert severity."""
    severity_map = {
        "INFO": CLIMessages.EMOJI["info"],
        "WARNING": CLIMessages.EMOJI["warning"],
        "CRITICAL": CLIMessages.EMOJI["critical"],
    }
    return severity_map.get(severity.upper(), CLIMessages.EMOJI["warning"])
