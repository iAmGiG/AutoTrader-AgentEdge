"""
Utilities for dynamic date handling in data tools.
"""

import datetime
from typing import Tuple, Optional


def get_default_date_range(days_back: int = 5) -> Tuple[str, str]:
    """
    Calculate a default date range based on the current date.
    Returns (start_date, end_date) as strings in YYYY-MM-DD format.

    Args:
        days_back: Number of trading days to look back (default: 5)

    Returns:
        Tuple of (start_date, end_date) strings in YYYY-MM-DD format
    """
    # Get today's date, ensuring we use the current system time
    end_date = datetime.datetime.now()

    # Log the actual date being used (for debugging)
    print(
        f"Current date used for calculations: {end_date.strftime('%Y-%m-%d')}")

    # Calculate start date (approximately days_back trading days)
    # Add extra days to account for weekends and holidays
    # Rough estimate to get N trading days
    calendar_days = int(days_back * 1.4)
    start_date = end_date - datetime.timedelta(days=calendar_days)

    # Format dates as strings
    end_date_str = end_date.strftime("%Y-%m-%d")
    start_date_str = start_date.strftime("%Y-%m-%d")

    print(f"Date range generated: {start_date_str} to {end_date_str}")

    return (start_date_str, end_date_str)


def process_date_param(date_param: Optional[str]) -> Optional[str]:
    """
    Process a date parameter that might be a relative date string.
    Handles special strings like "today", "yesterday", "-7d", etc.

    Args:
        date_param: Date string to process, can be:
                   - None (will return None)
                   - YYYY-MM-DD (will return as-is)
                   - "today", "yesterday"
                   - "-Nd" (N days ago)
                   - "-Nw" (N weeks ago)
                   - "-Nm" (N months ago)
                   - "ytd" (year to date)

    Returns:
        Processed date string in YYYY-MM-DD format or None
    """
    if date_param is None:
        return None

    # If it's already a YYYY-MM-DD format, return as-is
    if isinstance(date_param, str) and len(date_param) == 10 and date_param[4] == "-" and date_param[7] == "-":
        return date_param

    today = datetime.datetime.now()

    # Handle special string formats
    if date_param == "today":
        return today.strftime("%Y-%m-%d")

    if date_param == "yesterday":
        yesterday = today - datetime.timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")

    if date_param == "ytd":  # Year to date
        start_of_year = datetime.datetime(today.year, 1, 1)
        return start_of_year.strftime("%Y-%m-%d")

    # Handle relative formats like "-7d", "-4w", "-2m", "+30d"
    if isinstance(date_param, str) and (date_param.startswith("-") or date_param.startswith("+")):
        try:
            # Extract the numeric part and unit
            sign = 1 if date_param.startswith("+") else -1
            value = int(date_param[1:-1])
            unit = date_param[-1].lower()

            if unit == "d":  # Days
                result_date = today + datetime.timedelta(days=sign * value)
            elif unit == "w":  # Weeks
                result_date = today + datetime.timedelta(weeks=sign * value)
            elif unit == "m":  # Months (approximate)
                # Create a date with months added/subtracted
                month = today.month + (sign * value)
                year = today.year

                # Handle month/year rollover
                while month <= 0:
                    month += 12
                    year -= 1
                while month > 12:
                    month -= 12
                    year += 1

                # Create new date with same day but adjusted month/year
                result_date = today.replace(year=year, month=month)
            elif unit == "y":  # Years
                result_date = today.replace(year=today.year + (sign * value))
            else:
                # Unrecognized unit, return None
                return None

            return result_date.strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            # If parsing fails, return None
            return None

    # If we get here, the format wasn't recognized
    return None


def get_processed_date_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    default_days_back: int = 5
) -> Tuple[str, str]:
    """
    Process start and end date parameters, applying defaults if needed.

    Args:
        start_date: Optional start date string (YYYY-MM-DD or relative)
        end_date: Optional end date string (YYYY-MM-DD or relative)
        default_days_back: Default number of days to look back if no dates provided

    Returns:
        Tuple of processed (start_date, end_date) strings in YYYY-MM-DD format
    """
    # Process any relative date strings
    processed_start = process_date_param(start_date)
    processed_end = process_date_param(end_date)

    # If both dates are provided and valid, use them
    if processed_start and processed_end:
        return (processed_start, processed_end)

    # If only end_date is provided, calculate start_date based on default_days_back
    if not processed_start and processed_end:
        end_dt = datetime.datetime.strptime(processed_end, "%Y-%m-%d")
        calendar_days = int(default_days_back * 1.4)
        start_dt = end_dt - datetime.timedelta(days=calendar_days)
        return (start_dt.strftime("%Y-%m-%d"), processed_end)

    # If only start_date is provided, use today as end_date
    if processed_start and not processed_end:
        return (processed_start, datetime.datetime.now().strftime("%Y-%m-%d"))

    # If neither is provided, use default range
    return get_default_date_range(default_days_back)
