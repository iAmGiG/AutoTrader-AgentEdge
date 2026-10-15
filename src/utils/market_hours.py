"""
Market Hours Detection Utility

Detects whether US stock markets (NYSE/NASDAQ) are currently open for trading.
Uses Alpaca's Market Calendar API to handle holidays, early closes, and half-days.
Reference: https://docs.alpaca.markets/reference/getcalendar-1

Issue #437: Enhanced with extended_hours support and validation utilities.
"""

import logging
import os
from datetime import date, datetime, time, timedelta
from time import monotonic
from typing import Any, Dict, Optional, Set, Tuple

import pytz

try:
    import yaml
except ImportError:
    yaml = None

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetCalendarRequest
except ImportError:
    TradingClient = None
    GetCalendarRequest = None

from src.utils.config_loader import ConfigLoader
from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)

# Default market hours (fallback when API unavailable)
DEFAULT_MARKET_OPEN = time(9, 30)
DEFAULT_MARKET_CLOSE = time(16, 0)
EARLY_MARKET_CLOSE = time(13, 0)  # NYSE early-close days

# Cache for loaded config
_MARKET_CONFIG = None

# Alpaca calendar client (built once) and its answers per day
_UNSET = object()
_CALENDAR_CLIENT: Any = _UNSET
_CALENDAR_CACHE: Dict[date, Tuple[time, time, bool]] = {}
# After a calendar failure, skip the API (use NYSE rules) until this monotonic time
_CALENDAR_RETRY_SECONDS = 300
_CALENDAR_DOWN_UNTIL = 0.0


def _load_market_config() -> Dict[str, Any]:
    """Load market configuration from YAML for fallbacks."""
    global _MARKET_CONFIG
    if _MARKET_CONFIG is not None:
        return _MARKET_CONFIG

    if yaml is None:
        return {}

    try:
        # Path relative to this file: ../../config_defaults/market_hours.yaml
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        config_path = os.path.join(base_dir, "config_defaults", "market_hours.yaml")

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                _MARKET_CONFIG = yaml.safe_load(f)
                logger.debug(f"Loaded market hours config from {config_path}")
                return _MARKET_CONFIG
    except Exception as e:
        logger.warning(f"Failed to load market hours config: {e}")

    return {}


def _get_alpaca_calendar():
    """
    Get an Alpaca trading client for calendar lookups (cached).

    The market calendar is the same for paper and live, so the paper keys are used
    (falling back to generic key names).

    Returns:
        Alpaca trading client or None if unavailable
    """
    global _CALENDAR_CLIENT
    if _CALENDAR_CLIENT is not _UNSET:
        return _CALENDAR_CLIENT
    if TradingClient is None:
        _CALENDAR_CLIENT = None
        return None
    if monotonic() < _CALENDAR_DOWN_UNTIL:
        return None

    try:
        config_loader = ConfigLoader()
        api_key = config_loader.get("ALPACA_PAPER_API_KEY") or config_loader.get("ALPACA_API_KEY")
        secret = config_loader.get("ALPACA_PAPER_SECRET") or config_loader.get("ALPACA_SECRET_KEY")
        if not (api_key and secret):
            logger.warning(
                "No Alpaca keys for the market calendar; using NYSE rules "
                "(one-off closures are not covered)"
            )
            _CALENDAR_CLIENT = None
            return None
        _CALENDAR_CLIENT = TradingClient(api_key=api_key, secret_key=secret, paper=True)
    except Exception as e:
        _calendar_failed(e)  # built again after the back-off
        return None
    return _CALENDAR_CLIENT


def _calendar_failed(error: Exception) -> None:
    """Back off from the calendar API for a while after a failure."""
    global _CALENDAR_DOWN_UNTIL
    _CALENDAR_DOWN_UNTIL = monotonic() + _CALENDAR_RETRY_SECONDS
    logger.warning(
        f"Alpaca market calendar unavailable ({error}); using NYSE rules for "
        f"{_CALENDAR_RETRY_SECONDS // 60} min (one-off closures are not covered)"
    )


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th given weekday (Mon=0) of a month; n=-1 is the last one."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    """NYSE observance: a Saturday holiday moves to Friday, a Sunday one to Monday."""
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter(year: int) -> date:
    """Western Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nyse_holidays(year: int) -> Set[date]:
    """
    Regular NYSE full-day holidays for a year, by rule.

    One-off closures (e.g. a national day of mourning) aren't predictable; only the
    Alpaca calendar or the YAML extra closures know them.
    """
    holidays = {
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Presidents Day
        _easter(year) - timedelta(days=2),  # Good Friday
        _nth_weekday(year, 5, 0, -1),  # Memorial Day
        _observed(date(year, 7, 4)),  # Independence Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),  # Christmas
    }
    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:  # a Saturday New Year's Day isn't observed on Dec 31
        holidays.add(_observed(new_year))
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))  # Juneteenth
    return holidays


def nyse_early_closes(year: int) -> Set[date]:
    """NYSE 1:00 PM early closes for a year, by rule."""
    closes = {_nth_weekday(year, 11, 3, 4) + timedelta(days=1)}  # day after Thanksgiving
    for day in (date(year, 7, 3), date(year, 12, 24)):
        if day.weekday() < 4:  # Mon-Thu, so the holiday itself falls on a weekday
            closes.add(day)
    return closes


def _extra_closures() -> Set[str]:
    """One-off closures from config_defaults/market_hours.yaml (when enabled)."""
    holidays = _load_market_config().get("holidays", {})
    if not holidays.get("enabled", False):
        return set()
    return set(holidays.get("fixed_holidays", []) + holidays.get("observed_holidays", []))


def nyse_closures(start: date, end: date) -> Set[date]:
    """Weekday NYSE closures between two dates: holidays by rule and configured one-offs."""
    closed = {d for year in range(start.year, end.year + 1) for d in nyse_holidays(year)}
    closed |= {date.fromisoformat(d) for d in _extra_closures()}
    return {d for d in closed if start <= d <= end and d.weekday() < 5}


def is_nyse_trading_day(day: date) -> bool:
    """
    Whether NYSE trades on a day, by its rules (offline and deterministic, for dates in
    research and validation; get_market_hours_for_date() asks the Alpaca calendar).
    """
    return _rule_based_hours(day)[2]


def _rule_based_hours(day: date) -> Tuple[time, time, bool]:
    """Market hours by NYSE rules, for when the Alpaca calendar is unavailable."""
    if day.weekday() >= 5 or day in nyse_holidays(day.year) or day.isoformat() in _extra_closures():
        return DEFAULT_MARKET_OPEN, DEFAULT_MARKET_CLOSE, False
    if day in nyse_early_closes(day.year):
        return DEFAULT_MARKET_OPEN, EARLY_MARKET_CLOSE, True
    return DEFAULT_MARKET_OPEN, DEFAULT_MARKET_CLOSE, True


def get_market_hours_for_date(
    date: Optional[object] = None,
) -> Tuple[time, time, bool]:
    """
    Get market open/close times for a specific date from Alpaca calendar.

    Handles:
    - Market holidays (closed)
    - Early closes (e.g., Black Friday at 1 PM)
    - Regular trading days (9:30 AM - 4:00 PM)

    Falls back to NYSE rules when the calendar can't be reached, and after a failure
    skips the API for a few minutes. Calendar answers are cached per day.

    Args:
        date: Date or datetime to check (defaults to today in ET)

    Returns:
        Tuple of (open_time, close_time, is_trading_day)
    """
    et_tz = pytz.timezone("America/New_York")

    if date is None:
        date = get_datetime_now(et_tz)
    day = date.date() if isinstance(date, datetime) else date

    if day in _CALENDAR_CACHE:
        return _CALENDAR_CACHE[day]

    client = _get_alpaca_calendar()
    if not client or monotonic() < _CALENDAR_DOWN_UNTIL:
        return _rule_based_hours(day)

    try:
        calendar = client.get_calendar(GetCalendarRequest(start=day, end=day))
    except Exception as e:
        _calendar_failed(e)
        return _rule_based_hours(day)

    if not calendar:
        # Market is closed (holiday or weekend)
        hours = (DEFAULT_MARKET_OPEN, DEFAULT_MARKET_CLOSE, False)
    else:
        cal_day = calendar[0]
        # Alpaca returns ET open/close as naive datetimes
        open_time = cal_day.open.time() if hasattr(cal_day.open, "time") else DEFAULT_MARKET_OPEN
        close_time = (
            cal_day.close.time() if hasattr(cal_day.close, "time") else DEFAULT_MARKET_CLOSE
        )
        hours = (open_time, close_time, True)

    _CALENDAR_CACHE[day] = hours
    return hours


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


def validate_market_hours(
    symbol: Optional[str] = None, extended_hours: bool = False, warn_only: bool = True
) -> bool:
    """
    Validate that market is open for trading.

    Args:
        symbol: Optional symbol for logging context
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
        symbol_msg = f" for {symbol}" if symbol else ""
        message = f"Market is {status_msg}. Trading{symbol_msg} may be restricted."

        if warn_only:
            logger.warning(f"⚠️  {message} - Order will be sent to broker (may fail validation)")
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
