#!/usr/bin/env python3
"""
Daily GTC Order Scheduler - Issue #287

Automates daily trading execution with:
- Scheduled morning/evening routines
- Comprehensive retry logic
- Robust error handling
- "Set it and forget it" automation

Foundation: Built on Issue #313 (Order Management System)
"""

import asyncio
import logging
import sys
import time
from datetime import datetime, time as dt_time, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.trading.trading_cycle import CostEfficientTradeCycle, RoutineType

logger = logging.getLogger(__name__)


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

    def __init__(self, config_file: str = None, trading_cycle=None):
        """
        Initialize the daily scheduler.

        Args:
            config_file: Path to scheduler configuration file (YAML or JSON)
            trading_cycle: Optional CostEfficientTradeCycle instance to reuse (reduces client instantiation)
        """
        if config_file is None:
            # Try YAML first, fallback to JSON
            yaml_file = "config_defaults/scheduler_config.yaml"
            json_file = "config_defaults/scheduler_config.json"
            if os.path.exists(yaml_file):
                config_file = yaml_file
            elif os.path.exists(json_file):
                config_file = json_file
            else:
                config_file = yaml_file  # Default to YAML

        self.config = self._load_config(config_file)
        # Reuse provided trading_cycle or create new one
        self.trading_cycle = trading_cycle if trading_cycle is not None else CostEfficientTradeCycle()
        self.execution_log: List[ExecutionLog] = []
        self.log_file = Path("state/scheduler_execution_log.json")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Define scheduled tasks
        self.tasks = self._create_default_tasks()

        # Load previous execution log
        self._load_execution_log()

        logger.info("DailyScheduler initialized with %d tasks", len(self.tasks))

    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load scheduler configuration or create defaults"""
        default_config = {
            "enabled": True,
            "market_timezone": "America/New_York",
            "morning_routine_time": "09:20:00",
            "evening_routine_time": "15:50:00",
            "max_retries": 3,
            "retry_delay_seconds": 60,
            "timeout_seconds": 300,
            "enable_notifications": False,
            "dry_run": False
        }

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                        if yaml is None:
                            raise ImportError(
                                "PyYAML not installed. Install with: pip install pyyaml")
                        user_config = yaml.safe_load(f)
                    else:
                        user_config = json.load(f)
                    default_config.update(user_config)
                    logger.info("Loaded scheduler config from %s", config_file)
            except Exception as e:
                logger.warning("Failed to load config from %s: %s. Using defaults.", config_file, e)
        else:
            logger.info("Config file not found. Using default configuration.")
            # Save default config
            try:
                os.makedirs(os.path.dirname(config_file), exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                logger.info("Saved default config to %s", config_file)
            except Exception as e:
                logger.warning("Failed to save default config: %s", e)

        return default_config

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
                timeout_seconds=self.config["timeout_seconds"]
            ),
            ScheduledTask(
                name="evening_routine",
                routine_type=RoutineType.EVENING,
                scheduled_time=evening_time,
                timezone=self.config["market_timezone"],
                retry_count=self.config["max_retries"],
                retry_delay_seconds=self.config["retry_delay_seconds"],
                timeout_seconds=self.config["timeout_seconds"]
            )
        ]

    def _load_execution_log(self):
        """Load execution log from disk"""
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r') as f:
                    log_data = json.load(f)
                    self.execution_log = [ExecutionLog(**entry) for entry in log_data]
                logger.info("Loaded %d execution log entries", len(self.execution_log))
            except Exception as e:
                logger.warning("Failed to load execution log: %s", e)
                self.execution_log = []

    def _save_execution_log(self):
        """Save execution log to disk"""
        try:
            with open(self.log_file, 'w') as f:
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
            actual_start_time=datetime.now().isoformat(),
            status=ScheduleStatus.RUNNING.value
        )

        max_attempts = task.retry_count + 1  # Initial attempt + retries
        base_delay = task.retry_delay_seconds

        for attempt in range(1, max_attempts + 1):
            log_entry.attempt = attempt

            try:
                logger.info("Executing %s (attempt %d/%d)", task.name, attempt, max_attempts)

                # Execute the appropriate routine
                if task.routine_type == RoutineType.MORNING:
                    report = self.trading_cycle.morning_routine()
                elif task.routine_type == RoutineType.EVENING:
                    report = self.trading_cycle.evening_routine()
                elif task.routine_type == RoutineType.RECOVERY:
                    report = self.trading_cycle.recover_from_crash()
                else:
                    raise ValueError(f"Unknown routine type: {task.routine_type}")

                # Success!
                log_entry.status = ScheduleStatus.COMPLETED.value
                log_entry.actual_end_time = datetime.now().isoformat()
                log_entry.api_calls_used = 3  # Typical API calls per routine

                # Extract report path from report if available
                # Report path is typically mentioned in the trading_cycle output
                # Use human-readable format: 2025-11-11_morning.md (or _2.md, _3.md for multiple runs)
                now = datetime.now()
                date_str = now.strftime('%Y-%m-%d')
                # Extract routine type from task name (e.g., "morning_routine" -> "morning")
                routine_type = task.name.replace('_routine', '')
                base_path = f"reports/daily/{date_str}_{routine_type}"

                # Check if file exists and find the right counter
                report_path = f"{base_path}.md"
                counter = 1
                while os.path.exists(report_path):
                    counter += 1
                    report_path = f"{base_path}_{counter}.md"

                log_entry.report_path = report_path

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
                    log_entry.actual_end_time = datetime.now().isoformat()
                    logger.error("❌ %s failed after %d attempts", task.name, max_attempts)

        return log_entry

    def should_run_task(self, task: ScheduledTask) -> bool:
        """
        Check if a task should run now.

        Args:
            task: The scheduled task to check

        Returns:
            True if the task should run now
        """
        if not self.config.get("enabled", True):
            return False

        now = datetime.now()
        current_time = now.time()

        # Check if we're within the scheduled time window (± 5 minutes)
        scheduled_dt = datetime.combine(now.date(), task.scheduled_time)
        window_start = (scheduled_dt - timedelta(minutes=5)).time()
        window_end = (scheduled_dt + timedelta(minutes=5)).time()

        # Check if current time is in window
        if not (window_start <= current_time <= window_end):
            return False

        # Check if already executed today
        today_str = now.strftime("%Y-%m-%d")
        for entry in reversed(self.execution_log):
            entry_date = datetime.fromisoformat(entry.actual_start_time).strftime("%Y-%m-%d")
            if entry.task_name == task.name and entry_date == today_str:
                if entry.status == ScheduleStatus.COMPLETED.value:
                    logger.debug("Task %s already completed today", task.name)
                    return False

        return True

    def run_scheduled_tasks(self):
        """
        Run any tasks that are due now.
        This should be called periodically (e.g., every minute).
        """
        for task in self.tasks:
            if self.should_run_task(task):
                logger.info("🚀 Starting scheduled task: %s", task.name)

                # Execute task with retry
                log_entry = self._execute_task_with_retry(task)

                # Save log entry
                self.execution_log.append(log_entry)
                self._save_execution_log()

                # Generate summary
                self._log_execution_summary(log_entry)

    def _log_execution_summary(self, log_entry: ExecutionLog):
        """Log execution summary for monitoring"""
        duration = "N/A"
        if log_entry.actual_end_time:
            start = datetime.fromisoformat(log_entry.actual_start_time)
            end = datetime.fromisoformat(log_entry.actual_end_time)
            duration = f"{(end - start).total_seconds():.1f}s"

        status_emoji = {
            ScheduleStatus.COMPLETED.value: "✅",
            ScheduleStatus.FAILED.value: "❌",
            ScheduleStatus.RETRYING.value: "🔄"
        }.get(log_entry.status, "⚠️")

        logger.info(
            "%s Task: %s | Status: %s | Duration: %s | Attempt: %d | API Calls: %d",
            status_emoji,
            log_entry.task_name,
            log_entry.status,
            duration,
            log_entry.attempt,
            log_entry.api_calls_used
        )

        if log_entry.error_message:
            logger.error("Error: %s", log_entry.error_message)

    async def run_daemon(self, check_interval_seconds: int = 60):
        """
        Run scheduler as a daemon process.

        Args:
            check_interval_seconds: How often to check for scheduled tasks (default: 60s)
        """
        logger.info("🤖 Starting DailyScheduler daemon (check interval: %ds)", check_interval_seconds)
        logger.info("Scheduled tasks:")
        for task in self.tasks:
            logger.info("  - %s at %s ET", task.name, task.scheduled_time.strftime("%H:%M:%S"))

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

            logger.info("Running task once: %s", task_name)
            log_entry = self._execute_task_with_retry(task)
            self.execution_log.append(log_entry)
            self._save_execution_log()
            self._log_execution_summary(log_entry)
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
        cutoff = datetime.now() - timedelta(days=days)

        history = [
            entry for entry in self.execution_log
            if datetime.fromisoformat(entry.actual_start_time) >= cutoff
        ]

        return sorted(history, key=lambda x: x.actual_start_time, reverse=True)

    def generate_status_report(self) -> str:
        """Generate a status report of recent executions"""
        recent = self.get_execution_history(days=7)

        if not recent:
            return "No execution history available"

        lines = [
            "# Daily Scheduler Status Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Recent Executions (Last 7 Days)",
            ""
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

        lines.extend([
            "## Configuration",
            f"Morning routine: {self.config['morning_routine_time']} ET",
            f"Evening routine: {self.config['evening_routine_time']} ET",
            f"Max retries: {self.config['max_retries']}",
            f"Enabled: {self.config['enabled']}",
            ""
        ])

        return "\n".join(lines)


def main():
    """Main entry point for the daily scheduler"""
    import argparse

    parser = argparse.ArgumentParser(description="AutoGen Daily Trading Scheduler")
    parser.add_argument(
        "--mode",
        choices=["daemon", "once", "status", "test"],
        default="daemon",
        help="Execution mode"
    )
    parser.add_argument(
        "--task",
        choices=["morning_routine", "evening_routine", "all"],
        help="Specific task to run (for 'once' mode)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in seconds (for daemon mode)"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('state/scheduler.log'),
            logging.StreamHandler()
        ]
    )

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
