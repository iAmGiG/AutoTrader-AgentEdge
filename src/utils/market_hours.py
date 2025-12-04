"""
Market Hours Detection Utility

Detects whether US stock markets (NYSE/NASDAQ) are currently open for trading.
Uses Alpaca's Market Calendar API to handle holidays, early closes, and half-days.
Reference: https://docs.alpaca.markets/reference/getcalendar-1

Issue #437: Enhanced with extended_hours support and validation utilities.
"""

import logging
from datetime import time
from typing import Any, Dict, Optional, Tuple

import pytz
from alpaca.trading.client import TradingClient

from src.utils.config_loader import ConfigLoader
from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)

# Default market hours (fallback when API unavailable)
DEFAULT_MARKET_OPEN = time(9, 30)
DEFAULT_MARKET_CLOSE = time(16, 0)


def _get_alpaca_calendar():
    """
    Get market calendar from Alpaca API.

    Returns:
        Alpaca trading client or None if unavailable
    """
    try:
        config_loader = ConfigLoader()
        client = TradingClient(
            api_key=config_loader.get("ALPACA_API_KEY"),
            secret_key=config_loader.get("ALPACA_SECRET_KEY"),
        )
        return client
    except Exception as e:
        logger.debug(f"Could not initialize Alpaca calendar client: {e}")
        return None


def get_market_hours_for_date(
    date: Optional[object] = None,
) -> Tuple[time, time, bool]:
    """
    Get market open/close times for a specific date from Alpaca calendar.

    Handles:
    - Market holidays (closed)
    - Early closes (e.g., Black Friday at 3 PM)
    - Regular trading days (9:30 AM - 4:00 PM)

    Args:
        date: Date to check (defaults to today)

    Returns:
        Tuple of (open_time, close_time, is_trading_day)
    """
    et_tz = pytz.timezone("America/New_York")

    if date is None:
        date = get_datetime_now(et_tz)

    try:
        client = _get_alpaca_calendar()
        if not client:
            # Fallback to hardcoded defaults
            return DEFAULT_MARKET_OPEN, DEFAULT_MARKET_CLOSE, True

        # Get calendar for the date (Alpaca expects YYYY-MM-DD strings)
        date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)
        # pylint: disable=unexpected-keyword-arg
        calendar = client.get_calendar(start=date_str, end=date_str)

        if not calendar:
            # Market is closed (holiday)
            return DEFAULT_MARKET_OPEN, DEFAULT_MARKET_CLOSE, False

        cal_day = calendar[0]
        # Alpaca returns times as datetime objects
        open_time = cal_day.open.time() if hasattr(cal_day.open, "time") else DEFAULT_MARKET_OPEN
        close_time = (
            cal_day.close.time() if hasattr(cal_day.close, "time") else DEFAULT_MARKET_CLOSE
        )

        return open_time, close_time, True

    except Exception as e:
        # Fallback to hardcoded defaults if API fails
        logger.debug(f"Error fetching market hours from Alpaca: {e}")
        return DEFAULT_MARKET_OPEN, DEFAULT_MARKET_CLOSE, True


def is_market_hours() -> bool:
    """
    Check if US stock market is currently open.

    Uses Alpaca's market calendar to account for:
    - Holidays (market closed)
    - Early closes (e.g., Black Friday at 3 PM instead of 4 PM)
    - Regular trading days (9:30 AM - 4:00 PM ET)

    Returns:
        bool: True if market is open, False otherwise
    """
    et_tz = pytz.timezone("America/New_York")
    now_et = get_datetime_now(et_tz)

    # Check if weekend (calendar API won't have data for weekends)
    if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    # Get today's market hours from Alpaca calendar
    open_time, close_time, is_trading_day = get_market_hours_for_date(now_et)

    if not is_trading_day:
        return False

    current_time = now_et.time()
    return open_time <= current_time < close_time


def get_market_status() -> Tuple[bool, str]:
    """
    Get detailed market status including half-days and early closes.

    Returns:
        Tuple of (is_open: bool, status_message: str)
    """
    et_tz = pytz.timezone("America/New_York")
    now_et = get_datetime_now(et_tz)

    # Check weekend
    if now_et.weekday() >= 5:
        return False, "Market closed (Weekend)"

    # Get today's market hours from Alpaca calendar
    open_time, close_time, is_trading_day = get_market_hours_for_date(now_et)

    if not is_trading_day:
        return False, "Market closed (Holiday)"

    current_time = now_et.time()
    pre_market_start = time(4, 0)
    after_hours_end = time(20, 0)

    # Check if it's an early close day
    is_early_close = close_time < time(16, 0)

    if open_time <= current_time < close_time:
        status = "Market open (Regular hours)"
        if is_early_close:
            status = f"Market open (Early close at {close_time.strftime('%I:%M %p')} ET)"
        return True, status
    elif pre_market_start <= current_time < open_time:
        return (
            False,
            f"Market closed (Pre-market, opens at {open_time.strftime('%I:%M %p')} ET)",
        )
    elif close_time <= current_time < after_hours_end:
        return False, "Market closed (After-hours)"
    else:
        return False, "Market closed"


def validate_market_hours(extended_hours: bool = False, warn_only: bool = True) -> bool:
    """
    Validate that market is open for trading.

    Args:
        extended_hours: Allow extended hours trading (pre-market/after-hours)
        warn_only: If True, warn but don't block; if False, raise ValueError

    Returns:
        bool: True if should proceed with trading

    Raises:
        ValueError: If market is closed and warn_only=False
    """
    is_open = is_market_hours()

    # For extended hours, use simple fallback check (4 AM - 8 PM ET)
    if extended_hours and not is_open:
        et_tz = pytz.timezone("America/New_York")
        now_et = get_datetime_now(et_tz)
        current_time = now_et.time()
        extended_open = time(4, 0)
        extended_close = time(20, 0)
        is_open = now_et.weekday() < 5 and extended_open <= current_time <= extended_close

    if not is_open:
        status_open, status_msg = get_market_status()
        message = f"Market is {status_msg}. Trading may be restricted."

        if warn_only:
            logger.warning(f"⚠️  {message} - Proceeding anyway (broker will validate)")
            return True
        else:
            logger.error(f"❌ {message} - Order blocked")
            raise ValueError(message)

    return True


def get_market_status_detailed() -> Dict[str, Any]:
    """
    Get comprehensive market status information.

    Returns:
        Dict with market status details:
        - is_open: Whether market is open
        - current_session: "pre-market", "market", "after-hours", "closed", "weekend"
        - hours: (open_time, close_time) as time objects
        - is_trading_day: Whether market is trading today
        - current_time_et: Current time in ET timezone
    """
    try:
        et_tz = pytz.timezone("America/New_York")
        now_et = get_datetime_now(et_tz)
        current_time = now_et.time()

        if now_et.weekday() >= 5:
            return {
                "is_open": False,
                "current_session": "weekend",
                "hours": (None, None),
                "is_trading_day": False,
                "current_time_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
            }

        open_time, close_time, is_trading_day = get_market_hours_for_date(now_et)

        if not is_trading_day:
            return {
                "is_open": False,
                "current_session": "closed",
                "hours": (None, None),
                "is_trading_day": False,
                "current_time_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
            }

        after_hours_end = time(20, 0)

        if current_time < open_time:
            current_session = "pre-market"
        elif current_time < close_time:
            current_session = "market"
        elif current_time < after_hours_end:
            current_session = "after-hours"
        else:
            current_session = "closed"

        return {
            "is_open": open_time <= current_time < close_time,
            "current_session": current_session,
            "hours": (open_time, close_time),
            "is_trading_day": True,
            "current_time_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
        }

    except Exception as e:
        logger.error(f"Failed to get detailed market status: {e}")
        return {
            "is_open": True,  # Default to open to avoid blocking
            "current_session": "unknown",
            "hours": (None, None),
            "error": str(e),
        }


def should_use_live_prices() -> bool:
    """
    Determine whether to use live price APIs or historical daily closes.

    Use live prices during market hours (latest trade/quote).
    Use daily close after hours (completed daily bar).

    Returns:
        bool: True if should use live prices, False if should use daily close
    """
    return is_market_hours()
