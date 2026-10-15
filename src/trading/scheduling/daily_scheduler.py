#!/usr/bin/env python3
"""
Daily GTC Order Scheduler - Issue #287

Automates daily trading execution with:
- Scheduled morning/evening routines
- Comprehensive retry logic
- Robust error handling
- "Set it and forget it" automation

Foundation: Built on Issue #313 (Order Management System)
Issue #478: State persistence via SQLite (state/user.db)
"""

import argparse
import asyncio
import datetime as datetime_module
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .scheduler_state import SchedulerStateManager, get_scheduler_state_manager
from .trading_cycle import CostEfficientTradeCycle, RoutineType
from src.utils.date_utils import get_datetime_now, now_iso, parse_date_string
from src.utils.market_hours import get_market_hours_for_date
from src.utils.state_paths import get_state_dir

try:
    import yaml
except ImportError:
    yaml = None

try:
    import fcntl
except ImportError:  # Windows: no run lock
    fcntl = None

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

logger = logging.getLogger(__name__)

dt_time = datetime_module.time  # time of day (the time module is imported as time)

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "market_timezone": "America/New_York",
    "morning_routine_time": "09:20:00",
    "evening_routine_time": "15:50:00",
    "morning_routine_enabled": True,
    "evening_routine_enabled": True,
    "max_retries": 3,
    "retry_delay_seconds": 60,
    "timeout_seconds": 300,
    "enable_notifications": False,
    "dry_run": False,
}

# A task runs if the check happens within this long of its scheduled time
RUN_WINDOW = timedelta(minutes=5)


def load_scheduler_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Scheduler settings: DEFAULT_CONFIG updated from the config file (YAML or JSON).

    Args:
        config_file: Path; default config_defaults/scheduler_config.yaml (or .json)
    """
    if config_file is None:
        yaml_file = "config_defaults/scheduler_config.yaml"
        json_file = "config_defaults/scheduler_config.json"
        config_file = (
            json_file if not os.path.exists(yaml_file) and os.path.exists(json_file) else yaml_file
        )

    config = dict(DEFAULT_CONFIG)
    if not os.path.exists(config_file):
        logger.info("Scheduler config %s not found. Using defaults.", config_file)
        return config
    try:
        with open(config_file, "r") as f:
            if config_file.endswith((".yaml", ".yml")):
                if yaml is None:
                    raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
                user_config = yaml.safe_load(f)
            else:
                user_config = json.load(f)
        config.update(user_config or {})
        logger.info("Loaded scheduler config from %s", config_file)
    except Exception as e:
        logger.warning("Failed to load config from %s: %s. Using defaults.", config_file, e)
    return config


def effective_flags(config: Dict[str, Any], state_manager: SchedulerStateManager) -> Dict[str, Any]:
    """
    Whether the scheduler and each routine are enabled.

    Flags saved in state/user.db (by the CLI, the config editor or the setup wizard)
    win. Until any are saved, the config file's flags apply. Routine times always come
    from the config file.

    Returns:
        {"enabled", "morning", "evening": bool, "source": "saved state" | "config"}
    """
    if state_manager.has_saved_state():
        state = state_manager.get_state()
        return {
            "enabled": state.enabled,
            "morning": state.morning_enabled,
            "evening": state.evening_enabled,
            "source": "saved state",
        }
    return {
        "enabled": bool(config.get("enabled", False)),
        "morning": bool(config.get("morning_routine_enabled", True)),
        "evening": bool(config.get("evening_routine_enabled", True)),
        "source": "config",
    }


def save_flags(
    config: Dict[str, Any],
    state_manager: SchedulerStateManager,
    enabled: Optional[bool] = None,
    morning: Optional[bool] = None,
    evening: Optional[bool] = None,
) -> bool:
    """
    Save enable flags to state/user.db; flags not given keep their effective value.

    Returns:
        True if saved
    """
    current = effective_flags(config, state_manager)
    state = state_manager.get_state()
    state.enabled = current["enabled"] if enabled is None else enabled
    state.morning_enabled = current["morning"] if morning is None else morning
    state.evening_enabled = current["evening"] if evening is None else evening
    return state_manager.save_state(state)


def configure_scheduler_logging(level: int = logging.INFO) -> Path:
    """
    Log to stdout and to scheduler.log in the state directory (rotated at 5 MB, five
    kept), so a background daemon leaves a record. Safe to call more than once.

    Returns:
        The log file path
    """
    log_path = get_state_dir() / "scheduler.log"
    root = logging.getLogger()
    root.setLevel(level)
    already = any(
        isinstance(h, RotatingFileHandler) and h.baseFilename == os.path.abspath(log_path)
        for h in root.handlers
    )
    if not already:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler = RotatingFileHandler(
            log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        # stdout, so a daemon's stderr holds only crashes (see DaemonManager.start)
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        root.addHandler(console)
    return log_path


class ScheduleStatus(Enum):
    """Status of scheduled task execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ScheduledTask:
    """Represents a scheduled trading routine"""

    name: str
    routine_type: RoutineType
    scheduled_time: dt_time  # e.g., time(9, 20) for 9:20 AM
    timezone: str = "America/New_York"  # ET timezone for market hours
    retry_count: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 300  # 5 minutes max per routine


@dataclass
class ExecutionLog:
    """Log entry for task execution"""

    task_name: str
    scheduled_time: str
    actual_start_time: str
    actual_end_time: Optional[str] = None
    status: str = ScheduleStatus.PENDING.value
    attempt: int = 1
    error_message: Optional[str] = None
    report_path: Optional[str] = None
    api_calls_used: int = 0


class DailyScheduler:
    """
    Automated daily trading scheduler with retry logic and error handling.

    Features:
    - Two daily routines: morning (9:20 AM ET), evening (3:50 PM ET)
    - Automatic retry with exponential backoff
    - Comprehensive error handling and logging
    - Crash recovery and state persistence
    - Minimal API calls (3-5 per routine)
    """

    def __init__(self, config_file: str = None, trading_cycle=None, state_manager=None):
        """
        Initialize the daily scheduler.

        Args:
            config_file: Path to scheduler configuration file (YAML or JSON)
            trading_cycle: Optional CostEfficientTradeCycle instance to reuse
                (reduces client instantiation)
            state_manager: Optional SchedulerStateManager (default: the shared one)
        """
        # Load paths configuration
        paths_config_file = "config_defaults/paths_config.yaml"
        try:
            with open(paths_config_file) as f:
                self.paths = yaml.safe_load(f) if yaml else {}
                logger.info(f"Loaded paths config from {paths_config_file}")
        except (FileNotFoundError, TypeError):
            logger.warning(
                f"Paths config not found at {paths_config_file}, using hardcoded defaults"
            )
            self.paths = {
                "state_files": {"scheduler_log": "state/scheduler_execution_log.json"},
                "log_files": {"scheduler": "state/scheduler.log"},
            }

        self.config = load_scheduler_config(config_file)
        # Reuse provided trading_cycle, else create one when a routine first needs it
        self._trading_cycle = trading_cycle
        self.execution_log: List[ExecutionLog] = []

        # Execution log file name from config, kept in the state directory
        log_file_path = self.paths.get("state_files", {}).get(
            "scheduler_log", "state/scheduler_execution_log.json"
        )
        self.log_file = get_state_dir() / Path(log_file_path).name

        # Initialize state manager for SQLite persistence (#478)
        self.state_manager = state_manager or get_scheduler_state_manager()

        # Define scheduled tasks
        self.tasks = self._create_default_tasks()

        # Load previous execution log (migrates from JSON to SQLite if needed)
        self._load_execution_log()

        logger.info("DailyScheduler initialized with %d tasks", len(self.tasks))

    @property
    def trading_cycle(self) -> CostEfficientTradeCycle:
        """The trading cycle, created on first use: a check with nothing due needs none."""
        if self._trading_cycle is None:
            self._trading_cycle = CostEfficientTradeCycle()
        return self._trading_cycle

    @trading_cycle.setter
    def trading_cycle(self, value: CostEfficientTradeCycle) -> None:
        self._trading_cycle = value

    def _create_default_tasks(self) -> List[ScheduledTask]:
        """Create default morning and evening tasks"""
        # Parse times from config
        morning_time = dt_time.fromisoformat(self.config["morning_routine_time"])
        evening_time = dt_time.fromisoformat(self.config["evening_routine_time"])

        return [
            ScheduledTask(
                name="morning_routine",
                routine_type=RoutineType.MORNING,
                scheduled_time=morning_time,
                timezone=self.config["market_timezone"],
                retry_count=self.config["max_retries"],
                retry_delay_seconds=self.config["retry_delay_seconds"],
                timeout_seconds=self.config["timeout_seconds"],
            ),
            ScheduledTask(
                name="evening_routine",
                routine_type=RoutineType.EVENING,
                scheduled_time=evening_time,
                timezone=self.config["market_timezone"],
                retry_count=self.config["max_retries"],
                retry_delay_seconds=self.config["retry_delay_seconds"],
                timeout_seconds=self.config["timeout_seconds"],
            ),
        ]

    def _load_execution_log(self):
        """Load execution log from disk"""
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    log_data = json.load(f)
                    self.execution_log = [ExecutionLog(**entry) for entry in log_data]
                logger.info("Loaded %d execution log entries", len(self.execution_log))
            except Exception as e:
                logger.warning("Failed to load execution log: %s", e)
                self.execution_log = []

    def _save_execution_log(self):
        """Save execution log to disk"""
        try:
            with open(self.log_file, "w") as f:
                log_data = [asdict(entry) for entry in self.execution_log]
                json.dump(log_data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save execution log: %s", e)

    def _execute_task_with_retry(self, task: ScheduledTask) -> ExecutionLog:
        """
        Execute a scheduled task with retry logic.

        Args:
            task: The scheduled task to execute

        Returns:
            ExecutionLog with execution results
        """
        log_entry = ExecutionLog(
            task_name=task.name,
            scheduled_time=task.scheduled_time.isoformat(),
            actual_start_time=now_iso(),
            status=ScheduleStatus.RUNNING.value,
        )

        max_attempts = task.retry_count + 1  # Initial attempt + retries
        base_delay = task.retry_delay_seconds

        # Record execution start in SQLite (#478), under the trading day it runs for
        routine_type = task.name.replace("_routine", "")
        market_date = self._market_now().date().isoformat()
        execution_id = self.state_manager.record_execution_start(
            routine_type, attempt=1, market_date=market_date
        )

        for attempt in range(1, max_attempts + 1):
            log_entry.attempt = attempt

            try:
                logger.info("Executing %s (attempt %d/%d)", task.name, attempt, max_attempts)

                # Execute the appropriate routine; failures raise RoutineError, including
                # protective stops that couldn't be checked, placed or renewed
                if task.routine_type == RoutineType.MORNING:
                    self.trading_cycle.morning_routine(raise_errors=True)
                elif task.routine_type == RoutineType.EVENING:
                    self.trading_cycle.evening_routine(raise_errors=True)
                elif task.routine_type == RoutineType.RECOVERY:
                    self.trading_cycle.recover_from_crash(raise_errors=True)
                else:
                    raise ValueError(f"Unknown routine type: {task.routine_type}")

                # Success!
                log_entry.status = ScheduleStatus.COMPLETED.value
                log_entry.actual_end_time = now_iso()
                log_entry.api_calls_used = 3  # Typical API calls per routine

                report_path = getattr(self.trading_cycle, "last_report_path", None)
                log_entry.report_path = report_path

                # Record completion in SQLite (#478)
                self.state_manager.record_execution_complete(
                    execution_id,
                    status="completed",
                    report_path=report_path,
                    api_calls_used=log_entry.api_calls_used,
                )

                logger.info("✅ %s completed successfully", task.name)
                break

            except Exception as e:
                error_msg = f"Attempt {attempt} failed: {str(e)}"
                logger.error("❌ %s - %s", task.name, error_msg)

                log_entry.error_message = error_msg

                if attempt < max_attempts:
                    # Calculate exponential backoff with jitter
                    delay = base_delay * (2 ** (attempt - 1))
                    jitter = delay * 0.1  # 10% jitter
                    actual_delay = delay + (time.time() % jitter)

                    log_entry.status = ScheduleStatus.RETRYING.value
                    logger.info("Retrying in %.1f seconds...", actual_delay)
                    time.sleep(actual_delay)
                else:
                    # All attempts failed
                    log_entry.status = ScheduleStatus.FAILED.value
                    log_entry.actual_end_time = now_iso()
                    logger.error("❌ %s failed after %d attempts", task.name, max_attempts)

                    # Record failure in SQLite (#478)
                    self.state_manager.record_execution_complete(
                        execution_id,
                        status="failed",
                        error_message=log_entry.error_message,
                    )

        return log_entry

    def _market_now(self) -> datetime:
        """Current time in the market timezone (ET by default), whatever the host's."""
        return datetime.now(ZoneInfo(self.config["market_timezone"]))

    def effective_settings(self) -> Dict[str, Any]:
        """Enable flags in force (see effective_flags())."""
        return effective_flags(self.config, self.state_manager)

    def save_flags(self, **flags: Optional[bool]) -> bool:
        """Save enable flags (enabled / morning / evening) to state/user.db."""
        return save_flags(self.config, self.state_manager, **flags)

    def should_run_task(self, task: ScheduledTask, now: Optional[datetime] = None) -> bool:
        """
        Check if a task should run now: the scheduler and the routine are enabled, it's
        within 5 minutes of the routine's time in the market timezone, the market is open
        that day, and the routine hasn't completed for that day yet.

        Args:
            task: The scheduled task to check
            now: Current time (default: now in the task's timezone)

        Returns:
            True if the task should run now
        """
        routine_type = task.name.replace("_routine", "")
        settings = self.effective_settings()
        if not settings["enabled"] or not settings.get(routine_type, True):
            return False

        now = now or datetime.now(ZoneInfo(task.timezone))
        scheduled = datetime.combine(now.date(), task.scheduled_time, tzinfo=now.tzinfo)
        if abs(now - scheduled) > RUN_WINDOW:
            return False

        _, _, trading_day = get_market_hours_for_date(now.date())
        if not trading_day:
            logger.debug("Skipping %s: %s is not a trading day", task.name, now.date())
            return False

        if self.state_manager.was_routine_run_today(routine_type, now.date().isoformat()):
            logger.debug("Task %s already completed today (from DB)", task.name)
            return False

        return True

    def next_run(self, now: Optional[datetime] = None) -> Optional[Tuple[ScheduledTask, datetime]]:
        """
        The next enabled routine on a trading day and when it runs (market timezone), or
        None if the scheduler or every routine is disabled.
        """
        settings = self.effective_settings()
        tasks = [t for t in self.tasks if settings.get(t.name.replace("_routine", ""), True)]
        if not settings["enabled"] or not tasks:
            return None

        now = now or self._market_now()
        for offset in range(15):  # covers any run of holidays and weekends
            day = (now + timedelta(days=offset)).date()
            if not get_market_hours_for_date(day)[2]:
                continue
            for task in sorted(tasks, key=lambda t: t.scheduled_time):
                when = datetime.combine(day, task.scheduled_time, tzinfo=now.tzinfo)
                done = self.state_manager.was_routine_run_today(
                    task.name.replace("_routine", ""), day.isoformat()
                )
                if when + RUN_WINDOW >= now and not done:
                    return task, when
        return None

    @contextmanager
    def _run_lock(self):
        """
        Exclusive lock while routines run, so a daemon, a cron run and a manual run (or
        two cron runs during a long retry) never run them at the same time.

        Yields:
            True if acquired, False if another process holds it
        """
        if fcntl is None:
            yield True
            return
        with open(get_state_dir() / "scheduler.lock", "a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _run_task(self, task: ScheduledTask) -> ExecutionLog:
        """Execute a task with retries, then log and save the result."""
        log_entry = self._execute_task_with_retry(task)
        self.execution_log.append(log_entry)
        self._save_execution_log()
        self._log_execution_summary(log_entry)
        return log_entry

    def run_scheduled_tasks(self):
        """
        Run any tasks that are due now.
        This should be called periodically (e.g., every minute).
        """
        with self._run_lock() as acquired:
            if not acquired:
                logger.info("Another scheduler run is in progress; skipping this check")
                return
            for task in self.tasks:
                if self.should_run_task(task):
                    logger.info("🚀 Starting scheduled task: %s", task.name)
                    self._run_task(task)

    def _log_execution_summary(self, log_entry: ExecutionLog):
        """Log execution summary for monitoring"""
        duration = "N/A"
        if log_entry.actual_end_time:
            start = parse_date_string(log_entry.actual_start_time)
            end = parse_date_string(log_entry.actual_end_time)
            duration = f"{(end - start).total_seconds():.1f}s"

        status_emoji = {
            ScheduleStatus.COMPLETED.value: "✅",
            ScheduleStatus.FAILED.value: "❌",
            ScheduleStatus.RETRYING.value: "🔄",
        }.get(log_entry.status, "⚠️")

        logger.info(
            "%s Task: %s | Status: %s | Duration: %s | Attempt: %d | API Calls: %d",
            status_emoji,
            log_entry.task_name,
            log_entry.status,
            duration,
            log_entry.attempt,
            log_entry.api_calls_used,
        )

        if log_entry.error_message:
            logger.error("Error: %s", log_entry.error_message)

    async def run_daemon(self, check_interval_seconds: int = 60):
        """
        Run scheduler as a daemon process.

        Args:
            check_interval_seconds: How often to check for scheduled tasks (default: 60s)
        """
        logger.info(
            "🤖 Starting DailyScheduler daemon (check interval: %ds)", check_interval_seconds
        )
        settings = self.effective_settings()
        logger.info(
            "Scheduler %s (%s); trading days only, times in %s",
            "enabled" if settings["enabled"] else "DISABLED",
            settings["source"],
            self.config["market_timezone"],
        )
        for task in self.tasks:
            routine_on = settings.get(task.name.replace("_routine", ""), True)
            logger.info(
                "  - %s at %s%s",
                task.name,
                task.scheduled_time.strftime("%H:%M:%S"),
                "" if routine_on else " (disabled)",
            )

        try:
            while True:
                try:
                    # Check and run scheduled tasks
                    self.run_scheduled_tasks()

                    # Sleep until next check
                    await asyncio.sleep(check_interval_seconds)

                except KeyboardInterrupt:
                    logger.info("Received shutdown signal")
                    break
                except Exception as e:
                    logger.error("Error in daemon loop: %s", e)
                    # Continue running despite errors
                    await asyncio.sleep(check_interval_seconds)

        finally:
            logger.info("DailyScheduler daemon stopped")

    def run_once(self, task_name: Optional[str] = None):
        """
        Run a specific task once (for testing/manual execution).

        Args:
            task_name: Name of task to run, or None to run all pending tasks
        """
        if task_name:
            # Run specific task
            task = next((t for t in self.tasks if t.name == task_name), None)
            if not task:
                logger.error("Task not found: %s", task_name)
                return

            # A manual run ignores the schedule and calendar, but not another run
            with self._run_lock() as acquired:
                if not acquired:
                    logger.error("Another scheduler run is in progress; not running %s", task_name)
                    return
                logger.info("Running task once: %s", task_name)
                self._run_task(task)
        else:
            # Run all pending tasks
            logger.info("Running all scheduled tasks once")
            self.run_scheduled_tasks()

    def get_execution_history(self, days: int = 7) -> List[ExecutionLog]:
        """
        Get execution history for the last N days.

        Args:
            days: Number of days to retrieve

        Returns:
            List of ExecutionLog entries
        """
        cutoff = get_datetime_now() - timedelta(days=days)

        history = [
            entry
            for entry in self.execution_log
            if parse_date_string(entry.actual_start_time) >= cutoff
        ]

        return sorted(history, key=lambda x: x.actual_start_time, reverse=True)

    def generate_status_report(self) -> str:
        """Generate a status report of recent executions"""
        recent = self.get_execution_history(days=7)

        if not recent:
            return "No execution history available"

        lines = [
            "# Daily Scheduler Status Report",
            f"Generated: {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Recent Executions (Last 7 Days)",
            "",
        ]

        # Group by task
        by_task: Dict[str, List[ExecutionLog]] = {}
        for entry in recent:
            if entry.task_name not in by_task:
                by_task[entry.task_name] = []
            by_task[entry.task_name].append(entry)

        for task_name, entries in by_task.items():
            lines.append(f"### {task_name}")
            lines.append(f"Total executions: {len(entries)}")

            completed = sum(1 for e in entries if e.status == ScheduleStatus.COMPLETED.value)
            failed = sum(1 for e in entries if e.status == ScheduleStatus.FAILED.value)

            lines.append(f"✅ Completed: {completed}")
            lines.append(f"❌ Failed: {failed}")
            lines.append(f"Success rate: {(completed / len(entries) * 100):.1f}%")
            lines.append("")

        lines.extend(
            [
                "## Configuration",
                f"Morning routine: {self.config['morning_routine_time']} ET",
                f"Evening routine: {self.config['evening_routine_time']} ET",
                f"Max retries: {self.config['max_retries']}",
                f"Enabled: {self.effective_settings()['enabled']}",
                "",
            ]
        )

        return "\n".join(lines)


def main():
    """Main entry point for the daily scheduler"""
    parser = argparse.ArgumentParser(description="AutoGen Daily Trading Scheduler")
    parser.add_argument(
        "--mode",
        choices=["daemon", "once", "status", "test"],
        default="daemon",
        help="Execution mode",
    )
    parser.add_argument(
        "--task",
        choices=["morning_routine", "evening_routine", "all"],
        help="Specific task to run (for 'once' mode)",
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="Check interval in seconds (for daemon mode)"
    )

    args = parser.parse_args()

    configure_scheduler_logging()

    # Create scheduler
    scheduler = DailyScheduler()

    if args.mode == "daemon":
        # Run as daemon
        print("Starting scheduler daemon...")
        print("Press Ctrl+C to stop")
        asyncio.run(scheduler.run_daemon(check_interval_seconds=args.interval))

    elif args.mode == "once":
        # Run once
        task_name = args.task if args.task != "all" else None
        scheduler.run_once(task_name)

    elif args.mode == "status":
        # Show status report
        report = scheduler.generate_status_report()
        print(report)

    elif args.mode == "test":
        # Test mode - run morning routine immediately
        print("Test mode: Running morning routine...")
        scheduler.run_once("morning_routine")


if __name__ == "__main__":
    main()
