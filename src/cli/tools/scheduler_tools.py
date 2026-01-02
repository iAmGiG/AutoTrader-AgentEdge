"""
Scheduler Tools - FunctionTool wrappers for daily scheduler.

Issue #433/#458: Extract scheduler display commands from cli_session.py.
Issue #478/#481: Add SQLite-backed scheduler state control.

These tools handle:
- Viewing scheduler status and configuration
- Getting execution history
- Calculating next scheduled run
- Enabling/disabling scheduler (SQLite-backed state)
- Viewing scheduler state from database
"""

import logging
from typing import Any, Dict, Optional

from autogen_core.tools import FunctionTool

from src.utils.date_utils import (
    add_days,
    combine_date_time,
    get_datetime_now,
    parse_time_string,
)
from src.utils.safe_print import get_symbol

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
        from src.trading.scheduling.daily_scheduler import DailyScheduler

        return DailyScheduler()
    except Exception as e:
        logger.error("Failed to get scheduler: %s", e)
        return None


def _get_state_manager():
    """Get SchedulerStateManager instance for SQLite-backed state."""
    try:
        from src.trading.scheduling.scheduler_state import get_scheduler_state_manager

        return get_scheduler_state_manager()
    except Exception as e:
        logger.error("Failed to get scheduler state manager: %s", e)
        return None


# =============================================================================
# FunctionTool Wrapper Functions - Display
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
# FunctionTool Wrapper Functions - Control (Issue #478/#481)
# =============================================================================


def enable_scheduler(enabled: bool = True) -> Dict[str, Any]:
    """
    Enable or disable the scheduler (SQLite-backed state).

    Args:
        enabled: True to enable, False to disable

    Returns:
        Dict with status and new state
    """
    try:
        mgr = _get_state_manager()
        if not mgr:
            return {"status": "error", "message": "Scheduler state manager not available"}

        success = mgr.set_enabled(enabled)
        if success:
            state = "enabled" if enabled else "disabled"
            return {
                "status": "success",
                "enabled": enabled,
                "message": f"Scheduler {state}",
            }
        return {"status": "error", "message": "Failed to update scheduler state"}

    except Exception as e:
        logger.error("Error enabling/disabling scheduler: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def set_routine_enabled(routine: str, enabled: bool) -> Dict[str, Any]:
    """
    Enable or disable a specific routine.

    Args:
        routine: "morning" or "evening"
        enabled: True to enable, False to disable

    Returns:
        Dict with status
    """
    try:
        mgr = _get_state_manager()
        if not mgr:
            return {"status": "error", "message": "Scheduler state manager not available"}

        routine_lower = routine.lower()
        if routine_lower not in ("morning", "evening"):
            return {"status": "error", "message": "Routine must be 'morning' or 'evening'"}

        if routine_lower == "morning":
            success = mgr.set_morning_enabled(enabled)
        else:
            success = mgr.set_evening_enabled(enabled)

        if success:
            state = "enabled" if enabled else "disabled"
            return {
                "status": "success",
                "routine": routine_lower,
                "enabled": enabled,
                "message": f"{routine_lower.title()} routine {state}",
            }
        return {"status": "error", "message": f"Failed to update {routine_lower} routine"}

    except Exception as e:
        logger.error("Error setting routine enabled: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def get_scheduler_db_state() -> Dict[str, Any]:
    """
    Get scheduler state from SQLite database.

    Returns:
        Dict with status and full scheduler state
    """
    try:
        mgr = _get_state_manager()
        if not mgr:
            return {"status": "error", "message": "Scheduler state manager not available"}

        state = mgr.get_state()

        # Get last run times from execution history
        last_morning = mgr.get_last_execution("morning")
        last_evening = mgr.get_last_execution("evening")

        return {
            "status": "success",
            "state": {
                "enabled": state.enabled,
                "morning_enabled": state.morning_enabled,
                "evening_enabled": state.evening_enabled,
                "morning_time": state.morning_time,
                "evening_time": state.evening_time,
                "max_retries": state.max_retries,
                "retry_delay_seconds": state.retry_delay_seconds,
                "timeout_seconds": state.timeout_seconds,
                "updated_at": state.updated_at,
            },
            "last_runs": {
                "morning": last_morning.started_at if last_morning else None,
                "morning_status": last_morning.status if last_morning else None,
                "evening": last_evening.started_at if last_evening else None,
                "evening_status": last_evening.status if last_evening else None,
            },
        }

    except Exception as e:
        logger.error("Error getting scheduler DB state: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def get_db_execution_history(
    routine_type: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Get execution history from SQLite database.

    Args:
        routine_type: Optional filter ("morning" or "evening")
        limit: Maximum entries to return

    Returns:
        Dict with status and execution history
    """
    try:
        mgr = _get_state_manager()
        if not mgr:
            return {"status": "error", "message": "Scheduler state manager not available"}

        history = mgr.get_execution_history(routine_type=routine_type, limit=limit)

        history_data = [
            {
                "id": h.id,
                "routine_type": h.routine_type,
                "started_at": h.started_at,
                "completed_at": h.completed_at,
                "status": h.status,
                "error_message": h.error_message,
                "attempt": h.attempt,
                "api_calls_used": h.api_calls_used,
            }
            for h in history
        ]

        return {
            "status": "success",
            "count": len(history_data),
            "filter_routine": routine_type,
            "history": history_data,
        }

    except Exception as e:
        logger.error("Error getting DB execution history: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def check_routine_run_today(routine_type: str) -> Dict[str, Any]:
    """
    Check if a routine has already run today.

    Args:
        routine_type: "morning" or "evening"

    Returns:
        Dict with status and whether routine ran today
    """
    try:
        mgr = _get_state_manager()
        if not mgr:
            return {"status": "error", "message": "Scheduler state manager not available"}

        routine_lower = routine_type.lower()
        if routine_lower not in ("morning", "evening"):
            return {"status": "error", "message": "Routine must be 'morning' or 'evening'"}

        ran_today = mgr.was_routine_run_today(routine_lower)

        return {
            "status": "success",
            "routine": routine_lower,
            "ran_today": ran_today,
            "message": f"{routine_lower.title()} routine {'has' if ran_today else 'has not'} run today",
        }

    except Exception as e:
        logger.error("Error checking routine run: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


# =============================================================================
# Display Functions (Issue #459)
# =============================================================================


def show_scheduler() -> str:
    """Display scheduler status with formatted output."""
    status = get_scheduler_status()
    if status["status"] == "not_initialized":
        return f"{get_symbol('ERROR')} Scheduler not initialized"
    if status["status"] == "error":
        return f"{get_symbol('ERROR')} Error: {status.get('error', 'Unknown')}"

    lines = [f"{get_symbol('CYCLE')} Daily Scheduler Status", "=" * 40]
    enabled = (
        f"{get_symbol('SUCCESS')} Enabled"
        if status.get("enabled")
        else f"{get_symbol('ERROR')} Disabled"
    )
    lines.append(f"Status: {enabled}")
    lines.append(f"Morning Routine: {status.get('morning_time', '09:20')} ET")
    lines.append(f"Evening Routine: {status.get('evening_time', '15:50')} ET")
    lines.append(f"Max Retries: {status.get('max_retries', 3)}")

    next_run = get_next_scheduled_run()
    if next_run["status"] == "success":
        lines.extend(["", f"{get_symbol('TARGET')} Next Scheduled Run"])
        lines.append(f"   {next_run['next_routine'].title()}: {next_run['next_time_display']} ET")
        lines.append(f"   Time until: {next_run['time_until']}")

    history = get_execution_history(limit=3)
    if history.get("history"):
        lines.extend(["", f"{get_symbol('INFO')} Recent Executions"])
        for entry in history["history"][:3]:
            status_emoji = (
                get_symbol("SUCCESS") if entry["status"] == "completed" else get_symbol("ERROR")
            )
            lines.append(f"   {status_emoji} {entry['task_name']}")

    return "\n".join(lines)


# =============================================================================
# FunctionTool Registration
# =============================================================================


show_scheduler_tool = FunctionTool(
    func=show_scheduler,
    name="show_scheduler",
    description="Display scheduler status with formatted output.",
)

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

# Control tools (Issue #478/#481)
enable_scheduler_tool = FunctionTool(
    func=enable_scheduler,
    name="enable_scheduler",
    description="Enable or disable the scheduler (SQLite-backed state).",
)

set_routine_enabled_tool = FunctionTool(
    func=set_routine_enabled,
    name="set_routine_enabled",
    description="Enable or disable a specific routine (morning or evening).",
)

get_scheduler_db_state_tool = FunctionTool(
    func=get_scheduler_db_state,
    name="get_scheduler_db_state",
    description="Get scheduler state from SQLite database.",
)

get_db_execution_history_tool = FunctionTool(
    func=get_db_execution_history,
    name="get_db_execution_history",
    description="Get scheduler execution history from SQLite database.",
)

check_routine_run_today_tool = FunctionTool(
    func=check_routine_run_today,
    name="check_routine_run_today",
    description="Check if a routine (morning/evening) has already run today.",
)


# Export list for CLI tools registry
CLI_SCHEDULER_TOOLS = [
    # Display tools
    show_scheduler_tool,
    get_scheduler_status_tool,
    get_execution_history_tool,
    get_next_scheduled_run_tool,
    get_routine_description_tool,
    # Control tools (Issue #478/#481)
    enable_scheduler_tool,
    set_routine_enabled_tool,
    get_scheduler_db_state_tool,
    get_db_execution_history_tool,
    check_routine_run_today_tool,
]

__all__ = [
    # Display functions
    "get_scheduler_status",
    "get_execution_history",
    "get_next_scheduled_run",
    "get_routine_description",
    "show_scheduler",
    # Control functions
    "enable_scheduler",
    "set_routine_enabled",
    "get_scheduler_db_state",
    "get_db_execution_history",
    "check_routine_run_today",
    # FunctionTools
    "CLI_SCHEDULER_TOOLS",
    "get_scheduler_status_tool",
    "get_execution_history_tool",
    "get_next_scheduled_run_tool",
    "get_routine_description_tool",
    "enable_scheduler_tool",
    "set_routine_enabled_tool",
    "get_scheduler_db_state_tool",
    "get_db_execution_history_tool",
    "check_routine_run_today_tool",
]
