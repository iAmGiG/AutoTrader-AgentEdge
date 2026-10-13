"""
API Error Translator - user-friendly error message conversion.

Translates Alpaca API errors into human-readable messages.
Extracted from alpaca_execution_manager.py (Issue #441).
"""

import json
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Import message loader for user-facing messages
try:
    from config_defaults.message_loader import MessageLoader

    _MSG = MessageLoader()
    MESSAGE_LOADER_AVAILABLE = True
except ImportError:
    MESSAGE_LOADER_AVAILABLE = False


class APIErrorTranslator:
    """
    Translate Alpaca API errors into user-friendly messages.

    Handles:
    - JSON error parsing
    - Bracket order validation errors (42210000 series)
    - Buying power errors
    - Symbol validation errors
    - Market hours errors
    """

    # Error code to category mapping
    ERROR_CATEGORIES = {
        42210000: "bracket_validation",
        40310000: "insufficient_funds",
        40410000: "invalid_symbol",
    }

    @classmethod
    def translate(
        cls,
        error_str: str,
        ticker: str,
        entry: Optional[float] = None,
        stop: Optional[float] = None,
        target: Optional[float] = None,
    ) -> Tuple[str, str]:
        """
        Translate Alpaca API errors into user-friendly messages.

        Args:
            error_str: The raw error string from the API
            ticker: Stock ticker symbol
            entry: Entry price (for context in messages)
            stop: Stop loss price (for context in messages)
            target: Take profit price (for context in messages)

        Returns:
            Tuple of (user_message, user_error):
                - user_message: Brief message for display
                - user_error: Detailed explanation for help text
        """
        # Try to parse JSON error from Alpaca
        parsed = cls._parse_json_error(error_str)

        if parsed:
            code = parsed.get("code")
            base_price = parsed.get("base_price")
            api_message = parsed.get("message", "")

            # Handle specific error codes
            result = cls._handle_bracket_errors(code, api_message, entry, stop, target, base_price)
            if result:
                return result

            result = cls._handle_buying_power_error(api_message)
            if result:
                return result

            result = cls._handle_symbol_error(api_message, ticker)
            if result:
                return result

            result = cls._handle_market_hours_error(api_message)
            if result:
                return result

        if MESSAGE_LOADER_AVAILABLE:
            return (
                _MSG.get("errors.generic.title", ticker=ticker),
                _MSG.get("errors.generic.desc"),
            )

        # Generic fallback
        return (
            f"Order failed for {ticker}",
            "Please try again during market hours or contact support if the issue persists.",
        )

    @classmethod
    def _parse_json_error(cls, error_str: str) -> Optional[dict]:
        """
        Parse JSON error data from error string.

        Args:
            error_str: Raw error string that may contain embedded JSON

        Returns:
            Parsed JSON dict or None if not parseable
        """
        try:
            # Extract JSON if embedded in error string
            json_match = re.search(r"\{.*\}", error_str)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass
        return None

    @classmethod
    def _handle_bracket_errors(
        cls,
        code: Optional[int],
        api_message: str,
        entry: Optional[float],
        stop: Optional[float],
        target: Optional[float],
        base_price: Optional[float],
    ) -> Optional[Tuple[str, str]]:
        """Handle bracket order validation errors (42210000 series)."""
        if code != 42210000:
            return None

        # Build price context string for better error messages
        entry_str = f"${entry:.2f}" if entry else "N/A"

        if "stop_loss" in api_message and "must be <=" in api_message:
            stop_str = f"${stop:.2f}" if stop else "N/A"
            base_str = f"${base_price}" if base_price else "unknown"

            if MESSAGE_LOADER_AVAILABLE:
                return (
                    _MSG.get("errors.bracket.stop_loss.title", stop=stop_str),
                    _MSG.get(
                        "errors.bracket.stop_loss.desc",
                        entry=entry_str,
                        stop=stop_str,
                        base=base_str,
                    ),
                )
            return (
                f"Order rejected: Stop loss price ({stop_str}) doesn't match market price",
                f"The market is closed and price data may be stale. "
                f"Entry: {entry_str}, Stop: {stop_str}, Alpaca expects stop={base_str}. "
                "Try again during market hours (9:30 AM - 4:00 PM ET) for accurate pricing.",
            )

        if "take_profit" in api_message and "must be >=" in api_message:
            target_str = f"${target:.2f}" if target else "N/A"
            base_str = f"${base_price}" if base_price else "unknown"

            if MESSAGE_LOADER_AVAILABLE:
                return (
                    _MSG.get("errors.bracket.take_profit.title", target=target_str),
                    _MSG.get(
                        "errors.bracket.take_profit.desc",
                        entry=entry_str,
                        target=target_str,
                        base=base_str,
                    ),
                )
            return (
                f"Order rejected: Take profit price ({target_str}) doesn't match market price",
                f"The market is closed and price data may be stale. "
                f"Entry: {entry_str}, Target: {target_str}, Alpaca expects target>={base_str}. "
                "Try again during market hours (9:30 AM - 4:00 PM ET) for accurate pricing.",
            )

        return None

    @classmethod
    def _handle_buying_power_error(cls, api_message: str) -> Optional[Tuple[str, str]]:
        """Handle insufficient buying power errors."""
        msg_lower = api_message.lower()
        if "buying power" in msg_lower or "insufficient" in msg_lower:
            if MESSAGE_LOADER_AVAILABLE:
                return (_MSG.get("errors.buying_power.title"), _MSG.get("errors.buying_power.desc"))
            return (
                "Order rejected: Not enough cash available",
                "Check your account balance and reduce the order size.",
            )
        return None

    @classmethod
    def _handle_symbol_error(cls, api_message: str, ticker: str) -> Optional[Tuple[str, str]]:
        """Handle invalid symbol errors."""
        msg_lower = api_message.lower()
        if "symbol" in msg_lower and ("invalid" in msg_lower or "not found" in msg_lower):
            if MESSAGE_LOADER_AVAILABLE:
                return (
                    _MSG.get("errors.invalid_symbol.title", ticker=ticker),
                    _MSG.get("errors.invalid_symbol.desc"),
                )
            return (
                f"Order rejected: {ticker} is not a valid or tradeable symbol",
                "Double-check the ticker symbol. It may be delisted or not supported by Alpaca.",
            )
        return None

    @classmethod
    def _handle_market_hours_error(cls, api_message: str) -> Optional[Tuple[str, str]]:
        """Handle market hours errors."""
        msg_lower = api_message.lower()
        if "market" in msg_lower and "closed" in msg_lower:
            if MESSAGE_LOADER_AVAILABLE:
                return (
                    _MSG.get("errors.market_closed.title"),
                    _MSG.get("errors.market_closed.desc"),
                )
            return (
                "Order rejected: Market is closed",
                "Regular market hours: 9:30 AM - 4:00 PM ET. "
                "Your order may execute when the market opens.",
            )
        return None

    @classmethod
    def get_error_category(cls, error_str: str) -> str:
        """
        Get the category of an API error.

        Args:
            error_str: Raw error string

        Returns:
            Category string: "bracket_validation", "insufficient_funds",
                            "invalid_symbol", "market_hours", or "unknown"
        """
        parsed = cls._parse_json_error(error_str)
        if not parsed:
            return "unknown"

        code = parsed.get("code")
        if code in cls.ERROR_CATEGORIES:
            return cls.ERROR_CATEGORIES[code]

        api_message = parsed.get("message", "").lower()
        if "buying power" in api_message or "insufficient" in api_message:
            return "insufficient_funds"
        if "symbol" in api_message:
            return "invalid_symbol"
        if "market" in api_message and "closed" in api_message:
            return "market_hours"

        return "unknown"
