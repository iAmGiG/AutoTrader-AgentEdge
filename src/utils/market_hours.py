"""
Market Hours Detection Utility

Detects whether US stock markets (NYSE/NASDAQ) are currently open for trading.
Used to determine whether to fetch live prices or use historical daily closes.

Issue #437: Consolidated from alpaca_trading_client.py for reusability.
"""

import logging
from datetime import time
from typing import Any, Dict, Tuple

import pytz

from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)


def is_market_hours(extended_hours: bool = False) -> bool:
    """
    Check if US stock market is currently open.

    Market Hours (Eastern Time):
    - Regular: 9:30 AM - 4:00 PM ET
    - Extended: 4:00 AM - 8:00 PM ET (pre-market + regular + after-hours)

    Args:
        extended_hours: Include pre-market (4-9:30 AM) and after-hours (4-8 PM)

    Returns:
        bool: True if market is open, False otherwise
    """
    et_tz = pytz.timezone("America/New_York")
    now_et = get_datetime_now(et_tz)

    # Check if weekend
    if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    current_time = now_et.time()

    if extended_hours:
        # Extended hours: 4:00 AM - 8:00 PM ET
        extended_open = time(4, 0)
        extended_close = time(20, 0)
        return extended_open <= current_time <= extended_close
    else:
        # Regular hours: 9:30 AM - 4:00 PM ET
        market_open = time(9, 30)
        market_close = time(16, 0)
        return market_open <= current_time < market_close


def get_market_status_detailed(extended_hours: bool = False) -> Dict[str, Any]:
    """
    Get comprehensive market status information.

    Args:
        extended_hours: Include extended hours in "is_open" determination

    Returns:
        Dict with market status details:
        - is_open: Whether market is open (considering extended_hours flag)
        - session: "regular" or "extended"
        - current_session: "pre-market", "market", "after-hours", "closed", "weekend"
        - current_time_et: Current time in ET timezone
        - is_weekday: Whether it's a trading day
        - hours_desc: Human-readable hours description
        - extended_hours: Value of extended_hours parameter
    """
    try:
        et_tz = pytz.timezone("America/New_York")
        now_et = get_datetime_now(et_tz)
        current_time = now_et.time()
        current_weekday = now_et.weekday()  # 0=Monday, 6=Sunday

        # Market hours definitions
        market_open = time(9, 30)
        market_close = time(16, 0)
        extended_open = time(4, 0)
        extended_close = time(20, 0)

        # Check if it's a weekday (Monday=0, Friday=4)
        is_weekday = current_weekday < 5

        # Determine current session
        if is_weekday:
            if current_time < time(9, 30):
                current_session = "pre-market"
            elif current_time <= time(16, 0):
                current_session = "market"
            elif current_time <= time(20, 0):
                current_session = "after-hours"
            else:
                current_session = "closed"
        else:
            current_session = "weekend"

        # Determine if market is "open" based on extended_hours flag
        if extended_hours:
            is_open = is_weekday and extended_open <= current_time <= extended_close
            session = "extended"
            hours_desc = "4:00 AM - 8:00 PM ET"
        else:
            is_open = is_weekday and market_open <= current_time <= market_close
            session = "regular"
            hours_desc = "9:30 AM - 4:00 PM ET"

        return {
            "is_open": is_open,
            "session": session,
            "current_session": current_session,
            "current_time_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
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


def get_market_status() -> Tuple[bool, str]:
    """
    Get simple market status (backward compatible).

    Returns:
        Tuple of (is_open: bool, status_message: str)
    """
    et_tz = pytz.timezone("America/New_York")
    now_et = get_datetime_now(et_tz)

    # Check weekend
    if now_et.weekday() >= 5:
        return False, "Market closed (Weekend)"

    # Check time
    market_open = time(9, 30)
    market_close = time(16, 0)
    pre_market_start = time(4, 0)
    after_hours_end = time(20, 0)
    current_time = now_et.time()

    if market_open <= current_time < market_close:
        return True, "Market open (Regular hours)"
    elif pre_market_start <= current_time < market_open:
        return False, "Market closed (Pre-market)"
    elif market_close <= current_time < after_hours_end:
        return False, "Market closed (After-hours)"
    else:
        return False, "Market closed"


def validate_market_hours(extended_hours: bool = False, warn_only: bool = True) -> bool:
    """
    Validate that market is open for trading.

    Args:
        extended_hours: Allow extended hours trading
        warn_only: If True, warn but don't block; if False, raise ValueError

    Returns:
        bool: True if should proceed

    Raises:
        ValueError: If market is closed and warn_only=False
    """
    market_status = get_market_status_detailed(extended_hours)

    if not market_status["is_open"]:
        message = (
            f"Market is currently {market_status['current_session']} "
            f"({market_status.get('current_time_et', 'unknown time')}). "
            f"Regular hours: {market_status.get('hours_desc', 'unknown')}"
        )

        if warn_only:
            logger.warning(f"⚠️  {message} - Proceeding anyway (broker will validate)")
            return True
        else:
            logger.error(f"❌ {message} - Order blocked")
            raise ValueError(message)

    return True


def should_use_live_prices() -> bool:
    """
    Determine whether to use live price APIs or historical daily closes.

    Use live prices during market hours (latest trade/quote).
    Use daily close after hours (completed daily bar).

    Returns:
        bool: True if should use live prices, False if should use daily close
    """
    return is_market_hours()
