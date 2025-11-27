"""
Market Hours Detection Utility

Detects whether US stock markets (NYSE/NASDAQ) are currently open for trading.
Used to determine whether to fetch live prices or use historical daily closes.
"""

from datetime import time
from typing import Tuple

import pytz

from src.utils.date_utils import get_datetime_now


def is_market_hours() -> bool:
    """
    Check if US stock market is currently open.

    Market Hours (Eastern Time):
    - Regular: 9:30 AM - 4:00 PM ET
    - Pre-market: 4:00 AM - 9:30 AM ET (not counted as open)
    - After-hours: 4:00 PM - 8:00 PM ET (not counted as open)

    Returns:
        bool: True if market is open, False otherwise
    """
    et_tz = pytz.timezone("America/New_York")
    now_et = get_datetime_now(et_tz)

    # Check if weekend
    if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    # Check if within market hours (9:30 AM - 4:00 PM ET)
    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = now_et.time()

    return market_open <= current_time < market_close


def get_market_status() -> Tuple[bool, str]:
    """
    Get detailed market status.

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


def should_use_live_prices() -> bool:
    """
    Determine whether to use live price APIs or historical daily closes.

    Use live prices during market hours (latest trade/quote).
    Use daily close after hours (completed daily bar).

    Returns:
        bool: True if should use live prices, False if should use daily close
    """
    return is_market_hours()
