#!/usr/bin/env python3
"""
Error handling utilities for trading system.

Provides decorators and context managers for safe state modifications.
"""

import functools
import logging
from typing import Any, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def safe_state_modification(rollback_on_error: bool = True):
    """
    Decorator that ensures state modifications are atomic.

    If an error occurs after state is modified but before the operation
    completes, the state can be rolled back.

    Args:
        rollback_on_error: Whether to rollback state on error
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Save current state for potential rollback
            if hasattr(self, 'state') and hasattr(self, 'save_state'):
                original_state = self.state.copy() if hasattr(self.state, 'copy') else None
            else:
                original_state = None

            try:
                # Execute the function
                result = func(self, *args, **kwargs)
                return result

            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")

                # Rollback state if needed
                if rollback_on_error and original_state is not None:
                    try:
                        self.state = original_state
                        self.save_state()
                        logger.info(f"State rolled back after error in {func.__name__}")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback state: {rollback_error}")

                raise

        return wrapper
    return decorator


@contextmanager
def safe_order_placement(state_manager, symbol: str):
    """
    Context manager for safe order placement.

    Ensures state is only modified after order is confirmed.

    Usage:
        with safe_order_placement(state_manager, 'AAPL') as context:
            # Place order
            order_result = place_order(...)
            if order_result['status'] == 'success':
                context.commit_state(order_data)
    """
    class OrderContext:
        def __init__(self, state_mgr, sym):
            self.state_manager = state_mgr
            self.symbol = sym
            self.committed = False

        def commit_state(self, order_data: Dict[str, Any]):
            """Commit the state change after order is confirmed."""
            self.state_manager.add_position(self.symbol, order_data)
            self.committed = True

    context = OrderContext(state_manager, symbol)

    try:
        yield context
    finally:
        if not context.committed:
            logger.warning(f"Order for {symbol} was not committed to state")


def validate_order_response(response: Any) -> bool:
    """
    Validate that an order response indicates success.

    Args:
        response: Order response from broker

    Returns:
        True if order was successfully placed
    """
    if not response:
        return False

    if isinstance(response, dict):
        # Check for success indicators
        status = response.get('status', '').lower()
        if status in ['submitted', 'accepted', 'pending_new', 'new']:
            return True

        # Check for error indicators
        if 'error' in response or 'message' in response:
            error_msg = response.get('error') or response.get('message')
            logger.error(f"Order failed: {error_msg}")
            return False

    return False
