"""
Market Hours Validation - Check if market is open for trading.

Extracted from alpaca_trading_client.py for better modularity.
"""

import logging
from datetime import time as dt_time
from typing import Any, Dict

import pytz

from src.utils.date_utils import get_datetime_now, get_default_timezone

logger = logging.getLogger(__name__)


def is_market_hours(extended_hours: bool = False) -> Dict[str, Any]:
    """
    Check if market is currently open.

    Args:
        extended_hours: Include pre-market and after-hours

    Returns:
        Dict with market status information:
        - is_open: bool
        - session: "regular" or "extended"
        - current_session: "pre-market", "market", "after-hours", "closed", "weekend"
        - current_time_et: formatted timestamp
        - is_weekday: bool
        - hours_desc: human-readable hours description
        - extended_hours: bool (input echoed back)
    """
    try:
        # Get current time in Eastern timezone (market timezone)
        market_tz = get_default_timezone()  # Should be "America/New_York"
        et = pytz.timezone(market_tz)
        current_et = get_datetime_now(et)
        current_time = current_et.time()
        current_weekday = current_et.weekday()  # 0=Monday, 6=Sunday

        # Market hours: 9:30 AM - 4:00 PM ET (Monday-Friday)
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)

        # Extended hours: 4:00 AM - 8:00 PM ET
        extended_open = dt_time(4, 0)
        extended_close = dt_time(20, 0)

        # Check if it's a weekday (Monday=0, Friday=4)
        is_weekday = current_weekday < 5

        # Check market hours
        if extended_hours:
            is_open = is_weekday and extended_open <= current_time <= extended_close
            session = "extended"
            hours_desc = "4:00 AM - 8:00 PM ET"
        else:
            is_open = is_weekday and market_open <= current_time <= market_close
            session = "regular"
            hours_desc = "9:30 AM - 4:00 PM ET"

        # Determine current session
        if is_weekday:
            if current_time < dt_time(9, 30):
                current_session = "pre-market"
            elif current_time <= dt_time(16, 0):
                current_session = "market"
            elif current_time <= dt_time(20, 0):
                current_session = "after-hours"
            else:
                current_session = "closed"
        else:
            current_session = "weekend"

        return {
            "is_open": is_open,
            "session": session,
            "current_session": current_session,
            "current_time_et": current_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "is_weekday": is_weekday,
            "hours_desc": hours_desc,
            "extended_hours": extended_hours,
        }

    except Exception as e:
        logger.error(f"Failed to check market hours: {e}")
        return {
            "is_open": True,  # Default to open to avoid blocking trades
            "session": "unknown",
            "current_session": "unknown",
            "error": str(e),
        }


def validate_market_hours(
    symbol: str, extended_hours: bool = False, warn_only: bool = True
) -> bool:
    """
    Validate that market is open for trading.

    Args:
        symbol: Stock symbol (for logging context)
        extended_hours: Allow extended hours trading
        warn_only: If True, warn but don't block; if False, block order

    Returns:
        bool: True if should proceed with order

    Raises:
        ValueError: If market is closed and warn_only=False
    """
    market_status = is_market_hours(extended_hours)

    if not market_status["is_open"]:
        message = (
            f"Market is currently {market_status['current_session']} "
            f"({market_status.get('current_time_et', 'unknown time')}). "
            f"Regular hours: {market_status.get('hours_desc', 'unknown')}"
        )

        if warn_only:
            # Note: We submit immediately to Alpaca - THEY queue it, not us
            # If validation fails, order is rejected (no local queue/retry)
            logger.warning(f"⚠️  {message} - Order will be sent to broker (may fail validation)")
            return True
        else:
            logger.error(f"❌ {message} - Order blocked")
            raise ValueError(message)

    return True


# Convenience aliases for backward compatibility
get_market_status = is_market_hours
check_market_hours = validate_market_hours
