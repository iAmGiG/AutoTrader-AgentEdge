"""
Error handling utilities for Alpaca trading operations.

Issue #437: Extract error handling and API error extraction logic from alpaca_trading_client.py
Provides consistent error response formatting and Alpaca API error extraction.
"""

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_alpaca_error_details(exception: Exception) -> Tuple[Optional[str], Optional[int]]:
    """
    Extract error code and status code from Alpaca APIError.

    Args:
        exception: Exception to extract details from

    Returns:
        Tuple of (error_code, status_code) or (None, None) if not an APIError
    """
    error_code = None
    status_code = None

    try:
        from alpaca.common.exceptions import APIError

        if isinstance(exception, APIError):
            status_code = getattr(exception, "status_code", None)
            error_code = getattr(exception, "code", None)
            logger.debug(f"Alpaca API error: status={status_code}, code={error_code}")
            return error_code, status_code
    except ImportError:
        # alpaca-py not available
        pass
    except Exception as e:
        logger.debug(f"Failed to extract error details: {e}")

    return None, None


def format_order_error_response(
    exception: Exception,
    order_details: Dict[str, Any],
    order_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Format a standardized error response for order operations.

    Args:
        exception: Exception that occurred
        order_details: Original order parameters (for context)
        order_id: Order ID if available

    Returns:
        Standardized error response dict
    """
    error_code, status_code = extract_alpaca_error_details(exception)

    response = {
        "status": "error",
        "message": str(exception),
        "error_code": error_code,
        "status_code": status_code,
        "order_details": order_details,
    }

    if order_id:
        response["order_id"] = order_id

    return response


def format_operation_error_response(
    operation: str,
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Format a standardized error response for generic operations.

    Args:
        operation: Name of operation that failed (e.g., "cancel_order", "modify_order")
        exception: Exception that occurred
        context: Additional context dict (e.g., {"order_id": "123"})

    Returns:
        Standardized error response dict
    """
    error_code, status_code = extract_alpaca_error_details(exception)

    response = {
        "status": "error",
        "operation": operation,
        "message": str(exception),
        "error_code": error_code,
        "status_code": status_code,
    }

    if context:
        response.update(context)

    return response


def is_retriable_error(exception: Exception) -> bool:
    """
    Determine if an exception represents a retriable error.

    Args:
        exception: Exception to check

    Returns:
        True if the error might be retriable (network, timeout, rate limit)
    """
    error_code, status_code = extract_alpaca_error_details(exception)

    # HTTP 429 (rate limit), 503 (service unavailable), 504 (gateway timeout)
    retriable_status_codes = {429, 503, 504}
    if status_code in retriable_status_codes:
        return True

    # Timeout/connection errors
    if "timeout" in str(exception).lower():
        return True

    if "connection" in str(exception).lower():
        return True

    return False


def log_error_with_context(
    operation: str,
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    log_level: str = "error",
) -> None:
    """
    Log an error with context information.

    Args:
        operation: Name of operation that failed
        exception: Exception that occurred
        context: Optional context dict (symbol, order_id, etc.)
        log_level: Logging level ("debug", "info", "warning", "error")
    """
    error_code, status_code = extract_alpaca_error_details(exception)

    log_func = getattr(logger, log_level.lower(), logger.error)

    context_str = ""
    if context:
        context_str = " | " + " | ".join(f"{k}={v}" for k, v in context.items())

    retriable = " [retriable]" if is_retriable_error(exception) else ""

    log_func(
        f"Operation failed: {operation}{context_str} | "
        f"Error: {str(exception)} | "
        f"API Error: {error_code} | Status: {status_code}{retriable}"
    )
