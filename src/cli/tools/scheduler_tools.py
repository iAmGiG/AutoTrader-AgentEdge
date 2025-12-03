"""
Scheduler Display Tools - FunctionTool wrappers for daily scheduler.

Issue #433/#458: Extract scheduler display commands from cli_session.py.

These tools handle:
- Viewing scheduler status and configuration
- Getting execution history
- Calculating next scheduled run

Note: These are read-only display tools. Scheduler control (start/stop)
is handled by the scheduler_cli.py module.
"""

import logging
from typing import Any, Dict

from autogen_core.tools import FunctionTool

from src.utils.date_utils import (
    add_days,
    combine_date_time,
    get_datetime_now,
    parse_time_string,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def _get_scheduler():
    """
    Get DailyScheduler instance.

    Returns singleton or creates new instance.
    """
    try:
        from src.trading.daily_scheduler import DailyScheduler

        return DailyScheduler()
    except Exception as e:
        logger.error("Failed to get scheduler: %s", e)
        return None


# =============================================================================
# FunctionTool Wrapper Functions
# =============================================================================


def get_scheduler_status() -> Dict[str, Any]:
    """
    Get current scheduler status and configuration.

    Returns:
        Dict with:
        - status: "success" or "error"
        - enabled: Whether scheduler is enabled
        - morning_time: Morning routine time (e.g., "09:20")
        - evening_time: Evening routine time (e.g., "15:50")
        - max_retries: Maximum retry attempts
        - timezone: Market timezone
    """
    try:
        scheduler = _get_scheduler()
        if not scheduler:
            return {"status": "not_initialized", "message": "Scheduler not available"}

        config = scheduler.config

        return {
            "status": "success",
            "enabled": config.get("enabled", False),
            "morning_time": config.get("morning_routine_time", "09:20:00")[:5],
            "evening_time": config.get("evening_routine_time", "15:50:00")[:5],
            "max_retries": config.get("max_retries", 3),
            "retry_delay_seconds": config.get("retry_delay_seconds", 60),
            "timeout_seconds": config.get("timeout_seconds", 300),
            "timezone": config.get("market_timezone", "America/New_York"),
            "dry_run": config.get("dry_run", False),
        }

    except Exception as e:
        logger.error("Error getting scheduler status: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def get_execution_history(days: int = 7, limit: int = 10) -> Dict[str, Any]:
    """
    Get scheduler execution history.

    Args:
        days: Number of days to retrieve (default 7)
        limit: Maximum entries to return (default 10)

    Returns:
        Dict with:
        - status: "success" or "error"
        - history: List of execution log entries
        - summary: Statistics (completed, failed, success_rate)
    """
    try:
        scheduler = _get_scheduler()
        if not scheduler:
            return {"status": "not_initialized", "message": "Scheduler not available"}

        history = scheduler.get_execution_history(days=days)
        history = history[:limit]

        history_dicts = [
            {
                "task_name": entry.task_name,
                "scheduled_time": entry.scheduled_time,
                "actual_start_time": entry.actual_start_time,
                "actual_end_time": entry.actual_end_time,
                "status": entry.status,
                "attempt": entry.attempt,
                "error_message": entry.error_message,
                "api_calls_used": entry.api_calls_used,
            }
            for entry in history
        ]

        total = len(history)
        completed = sum(1 for h in history_dicts if h["status"] == "completed")
        failed = sum(1 for h in history_dicts if h["status"] == "failed")
        success_rate = (completed / total * 100) if total > 0 else 0

        return {
            "status": "success",
            "history": history_dicts,
            "total_entries": total,
            "summary": {
                "completed": completed,
                "failed": failed,
                "retrying": total - completed - failed,
                "success_rate": round(success_rate, 1),
            },
        }

    except Exception as e:
        logger.error("Error getting execution history: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def get_next_scheduled_run() -> Dict[str, Any]:
    """
    Calculate the next scheduled routine run time.

    Returns:
        Dict with:
        - status: "success" or "error"
        - next_routine: "morning" or "evening"
        - next_time: Next run time as ISO string
        - time_until: Human-readable time until next run
        - minutes_until: Minutes until next run
    """
    try:
        scheduler = _get_scheduler()
        if not scheduler:
            return {"status": "not_initialized", "message": "Scheduler not available"}

        config = scheduler.config
        if not config.get("enabled", False):
            return {"status": "disabled", "message": "Scheduler is disabled"}

        morning_str = config.get("morning_routine_time", "09:20:00")
        evening_str = config.get("evening_routine_time", "15:50:00")

        morning_time = parse_time_string(morning_str)
        evening_time = parse_time_string(evening_str)

        if not morning_time or not evening_time:
            return {"status": "error", "error": "Invalid time configuration"}

        # Use date_utils for timezone-aware current time
        now = get_datetime_now(tz="America/New_York")
        current_time = now.time()

        # Determine next routine
        if current_time < morning_time:
            next_routine = "morning"
            next_time_of_day = morning_time
            next_date = now.date()
        elif current_time < evening_time:
            next_routine = "evening"
            next_time_of_day = evening_time
            next_date = now.date()
        else:
            next_routine = "morning"
            next_time_of_day = morning_time
            # Add one day using date_utils
            next_date = add_days(now, 1).date()

        next_datetime = combine_date_time(next_date, next_time_of_day)
        time_diff = next_datetime - now.replace(tzinfo=None)
        total_minutes = int(time_diff.total_seconds() / 60)
        hours, minutes = divmod(total_minutes, 60)

        time_until = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        return {
            "status": "success",
            "next_routine": next_routine,
            "next_time": next_datetime.isoformat(),
            "next_time_display": next_time_of_day.strftime("%H:%M"),
            "time_until": time_until,
            "minutes_until": total_minutes,
            "current_time_et": now.strftime("%H:%M:%S"),
        }

    except Exception as e:
        logger.error("Error calculating next run: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def get_routine_description(routine: str = "both") -> Dict[str, Any]:
    """
    Get description of what each routine does.

    Args:
        routine: "morning", "evening", or "both"

    Returns:
        Dict with:
        - status: "success" or "error"
        - routines: Dict with routine descriptions
    """
    descriptions = {
        "morning": {
            "name": "Morning Routine",
            "time": "09:20 ET",
            "actions": [
                "Fetch current broker state (positions, orders)",
                "Reconcile with local state",
                "Check for overnight fills",
                "Generate morning report",
                "Update trailing stops if applicable",
            ],
        },
        "evening": {
            "name": "Evening Routine",
            "time": "15:50 ET",
            "actions": [
                "Fetch end-of-day broker state",
                "Record daily P&L snapshot",
                "Check for position alerts",
                "Generate evening report",
                "Prepare for next trading day",
            ],
        },
    }

    routine_lower = routine.lower()
    if routine_lower == "morning":
        return {"status": "success", "routines": {"morning": descriptions["morning"]}}
    if routine_lower == "evening":
        return {"status": "success", "routines": {"evening": descriptions["evening"]}}
    return {"status": "success", "routines": descriptions}


# =============================================================================
# FunctionTool Registration
# =============================================================================


get_scheduler_status_tool = FunctionTool(
    func=get_scheduler_status,
    name="get_scheduler_status",
    description=(
        "Get scheduler status and configuration including enabled state, "
        "routine times, and retry settings."
    ),
)

get_execution_history_tool = FunctionTool(
    func=get_execution_history,
    name="get_execution_history",
    description="Get scheduler execution history with success/failure statistics.",
)

get_next_scheduled_run_tool = FunctionTool(
    func=get_next_scheduled_run,
    name="get_next_scheduled_run",
    description="Calculate when the next scheduled routine will run and time remaining.",
)

get_routine_description_tool = FunctionTool(
    func=get_routine_description,
    name="get_routine_description",
    description="Get description of what morning and evening routines do.",
)


# Export list for CLI tools registry
CLI_SCHEDULER_TOOLS = [
    get_scheduler_status_tool,
    get_execution_history_tool,
    get_next_scheduled_run_tool,
    get_routine_description_tool,
]

__all__ = [
    # Functions
    "get_scheduler_status",
    "get_execution_history",
    "get_next_scheduled_run",
    "get_routine_description",
    # FunctionTools
    "CLI_SCHEDULER_TOOLS",
    "get_scheduler_status_tool",
    "get_execution_history_tool",
    "get_next_scheduled_run_tool",
    "get_routine_description_tool",
]
