"""
Market Hours Validation - Facade for src.utils.market_hours.

This module is maintained for backward compatibility.
The implementation has been consolidated into src.utils.market_hours.
"""

from datetime import time as dt_time
from typing import Any, Dict

import pytz

from src.utils.date_utils import get_datetime_now
from src.utils.market_hours import get_market_status_detailed, validate_market_hours

EXTENDED_OPEN = dt_time(4, 0)
EXTENDED_CLOSE = dt_time(20, 0)

__all__ = ["is_market_hours", "validate_market_hours"]


def _fmt(t) -> str:
    return t.strftime("%I:%M %p").lstrip("0") if t else "?"


def is_market_hours(extended_hours: bool = False) -> Dict[str, Any]:
    """
    Broker-level market status (keeps the dict return used by the Alpaca tools).

    Built on ``src.utils.market_hours.get_market_status_detailed``, which uses the Alpaca
    calendar, so holidays and early closes are respected. Extended hours are 4:00 AM to
    8:00 PM ET on trading days.

    Args:
        extended_hours: Include pre-market and after-hours

    Returns:
        Dict with is_open, session, current_session, current_time_et, is_weekday,
        is_trading_day, hours_desc and extended_hours (echoed back).
    """
    status = get_market_status_detailed()
    now_et = get_datetime_now(pytz.timezone("America/New_York"))
    is_trading_day = status.get("is_trading_day", now_et.weekday() < 5)
    open_time, close_time = status.get("hours", (None, None))

    if "error" in status:
        is_open = status.get("is_open", True)
    elif extended_hours:
        is_open = bool(is_trading_day) and EXTENDED_OPEN <= now_et.time() < EXTENDED_CLOSE
    else:
        is_open = bool(status.get("is_open", False))

    if extended_hours:
        hours_desc = "4:00 AM - 8:00 PM ET"
    else:
        hours_desc = f"{_fmt(open_time)} - {_fmt(close_time)} ET" if open_time else "closed"

    result = {
        "is_open": is_open,
        "session": "extended" if extended_hours else "regular",
        "current_session": status.get("current_session", "unknown"),
        "current_time_et": status.get("current_time_et", now_et.strftime("%Y-%m-%d %H:%M:%S %Z")),
        "is_weekday": now_et.weekday() < 5,
        "is_trading_day": bool(is_trading_day),
        "hours_desc": hours_desc,
        "extended_hours": extended_hours,
    }
    if "error" in status:
        result["error"] = status["error"]
    return result
