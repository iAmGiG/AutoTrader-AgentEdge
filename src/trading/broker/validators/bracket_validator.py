"""
Bracket Order Validator - error detection and classification.

Detects bracket order validation failures from Alpaca API responses.
Extracted from alpaca_execution_manager.py (Issue #441).
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BracketOrderValidator:
    """
    Validate and classify bracket order errors from Alpaca API.

    Handles:
    - HTTP 422 validation errors
    - Alpaca error code 42210000 series
    - Message-based heuristic detection
    """

    # Common bracket order error patterns
    BRACKET_ERROR_KEYWORDS = [
        "limit_price",
        "base_price",
        "take_profit",
        "stop_loss",
        "bracket",
        "order_class",
    ]

    # Alpaca error codes for bracket order validation
    BRACKET_ERROR_CODE_PREFIX = "4221"

    @classmethod
    def is_bracket_validation_error(cls, error_data: Dict[str, Any]) -> bool:
        """
        Detect if an error is a bracket order validation failure.

        Uses Alpaca API error codes when available, falls back to heuristics.

        Args:
            error_data: Error dict from order_manager with keys:
                - status: str (e.g., "error")
                - message: str (error message)
                - error_code: Optional[int/str] (Alpaca error code)
                - status_code: Optional[int] (HTTP status code)

        Returns:
            True if this is a bracket order validation error, False otherwise
        """
        # Method 1: Check HTTP status code (most reliable)
        status_code = error_data.get("status_code")
        error_code = error_data.get("error_code")

        if status_code == 422:  # Unprocessable Entity - validation failed
            logger.debug(f"Detected HTTP 422 validation error (error_code={error_code})")
            return True

        # Method 2: Check Alpaca error code (42210000 series)
        if error_code and str(error_code).startswith(cls.BRACKET_ERROR_CODE_PREFIX):
            logger.debug(f"Detected Alpaca error code {error_code} - bracket order validation")
            return True

        # Method 3: Message-based heuristics (fallback)
        return cls._check_message_heuristics(error_data)

    @classmethod
    def _check_message_heuristics(cls, error_data: Dict[str, Any]) -> bool:
        """
        Use message-based heuristics to detect bracket errors.

        Args:
            error_data: Error dict with message field

        Returns:
            True if message patterns suggest bracket order error
        """
        error_msg = error_data.get("message", "").lower()

        # Count matching keywords
        matches = sum(1 for keyword in cls.BRACKET_ERROR_KEYWORDS if keyword in error_msg)

        if matches >= 2:  # Multiple keywords suggest bracket order issue
            logger.debug(
                f"Detected bracket validation via message pattern (matched {matches} keywords)"
            )
            return True

        return False

    @classmethod
    def get_error_category(cls, error_data: Dict[str, Any]) -> str:
        """
        Categorize the bracket order error type.

        Args:
            error_data: Error dict from API

        Returns:
            Category string: "stop_loss_invalid", "take_profit_invalid",
                            "bracket_structure", or "unknown"
        """
        error_msg = error_data.get("message", "").lower()

        if "stop_loss" in error_msg:
            return "stop_loss_invalid"
        elif "take_profit" in error_msg:
            return "take_profit_invalid"
        elif "bracket" in error_msg or "order_class" in error_msg:
            return "bracket_structure"
        else:
            return "unknown"
