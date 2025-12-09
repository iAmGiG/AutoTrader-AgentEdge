#!/usr/bin/env python3
"""
Scheduler State Persistence - SQLite-backed state management.

Issue #478: Migrate scheduler runtime state to SQLite for persistence across restarts.

This module provides:
- Scheduler enable/disable state persistence
- Execution history tracking (replaces JSON log file)
- Last run timestamps for each routine type

Uses the same state/user.db as trading_modes.py for consistency.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.date_utils import get_datetime_now, now_iso

logger = logging.getLogger(__name__)


@dataclass
class SchedulerState:
    """Current scheduler state."""

    enabled: bool = False
    morning_enabled: bool = True
    evening_enabled: bool = False
    morning_time: str = "09:20:00"
    evening_time: str = "15:50:00"
    max_retries: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 300
    updated_at: Optional[str] = None


@dataclass
class SchedulerExecution:
    """Record of a scheduler execution."""

    id: Optional[int] = None
    routine_type: str = ""  # 'morning', 'evening', 'recovery'
    started_at: str = ""
    completed_at: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed, retrying
    attempt: int = 1
    error_message: Optional[str] = None
    report_path: Optional[str] = None
    api_calls_used: int = 0


class SchedulerStateManager:
    """
    Manages scheduler state persistence in SQLite.

    Uses state/user.db (same as TradingModeManager) for consistency.
    Provides methods for:
    - Getting/setting scheduler enabled state
    - Recording execution history
    - Querying last run times
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize scheduler state manager.

        Args:
            db_path: Path to SQLite database (default: state/user.db)
        """
        if db_path is None:
            state_dir = os.path.join(os.path.dirname(__file__), "../../../state")
            os.makedirs(state_dir, exist_ok=True)
            db_path = os.path.join(state_dir, "user.db")

        self._db_path = db_path
        self._init_database()
        logger.debug(f"SchedulerStateManager initialized with db: {db_path}")

    def _init_database(self) -> None:
        """Initialize SQLite tables for scheduler state."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Scheduler state table (single row for current state)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    enabled BOOLEAN DEFAULT FALSE,
                    morning_enabled BOOLEAN DEFAULT TRUE,
                    evening_enabled BOOLEAN DEFAULT FALSE,
                    morning_time TEXT DEFAULT '09:20:00',
                    evening_time TEXT DEFAULT '15:50:00',
                    max_retries INTEGER DEFAULT 3,
                    retry_delay_seconds INTEGER DEFAULT 60,
                    timeout_seconds INTEGER DEFAULT 300,
                    updated_at TEXT
                )
            """
            )

            # Scheduler execution history (replaces JSON log)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    routine_type TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT DEFAULT 'pending',
                    attempt INTEGER DEFAULT 1,
                    error_message TEXT,
                    report_path TEXT,
                    api_calls_used INTEGER DEFAULT 0
                )
            """
            )

            # Create index for faster queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_scheduler_history_routine_date
                ON scheduler_history(routine_type, started_at)
            """
            )

            conn.commit()
            conn.close()
            logger.debug("Scheduler state tables initialized")
        except Exception as e:
            logger.error(f"Failed to initialize scheduler database: {e}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # State Management
    # =========================================================================

    def get_state(self) -> SchedulerState:
        """
        Get current scheduler state.

        Returns:
            SchedulerState with current configuration
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scheduler_state WHERE id = 1")
            row = cursor.fetchone()
            conn.close()

            if row:
                return SchedulerState(
                    enabled=bool(row["enabled"]),
                    morning_enabled=bool(row["morning_enabled"]),
                    evening_enabled=bool(row["evening_enabled"]),
                    morning_time=row["morning_time"],
                    evening_time=row["evening_time"],
                    max_retries=row["max_retries"],
                    retry_delay_seconds=row["retry_delay_seconds"],
                    timeout_seconds=row["timeout_seconds"],
                    updated_at=row["updated_at"],
                )
            else:
                # Return defaults if no state exists
                return SchedulerState()
        except Exception as e:
            logger.error(f"Failed to get scheduler state: {e}")
            return SchedulerState()

    def save_state(self, state: SchedulerState) -> bool:
        """
        Save scheduler state.

        Args:
            state: SchedulerState to persist

        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Upsert (insert or replace)
            cursor.execute(
                """
                INSERT OR REPLACE INTO scheduler_state
                (id, enabled, morning_enabled, evening_enabled, morning_time,
                 evening_time, max_retries, retry_delay_seconds, timeout_seconds, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    state.enabled,
                    state.morning_enabled,
                    state.evening_enabled,
                    state.morning_time,
                    state.evening_time,
                    state.max_retries,
                    state.retry_delay_seconds,
                    state.timeout_seconds,
                    now_iso(),
                ),
            )

            conn.commit()
            conn.close()
            logger.info(f"Scheduler state saved: enabled={state.enabled}")
            return True
        except Exception as e:
            logger.error(f"Failed to save scheduler state: {e}")
            return False

    def set_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable the scheduler.

        Args:
            enabled: True to enable, False to disable

        Returns:
            True if successful
        """
        state = self.get_state()
        state.enabled = enabled
        return self.save_state(state)

    def is_enabled(self) -> bool:
        """Check if scheduler is enabled."""
        return self.get_state().enabled

    def set_morning_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable the morning routine.

        Args:
            enabled: True to enable, False to disable

        Returns:
            True if successful
        """
        state = self.get_state()
        state.morning_enabled = enabled
        return self.save_state(state)

    def set_evening_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable the evening routine.

        Args:
            enabled: True to enable, False to disable

        Returns:
            True if successful
        """
        state = self.get_state()
        state.evening_enabled = enabled
        return self.save_state(state)

    def update_times(
        self, morning_time: Optional[str] = None, evening_time: Optional[str] = None
    ) -> bool:
        """
        Update routine times.

        Args:
            morning_time: New morning time (HH:MM:SS format)
            evening_time: New evening time (HH:MM:SS format)

        Returns:
            True if successful
        """
        state = self.get_state()
        if morning_time:
            state.morning_time = morning_time
        if evening_time:
            state.evening_time = evening_time
        return self.save_state(state)

    # =========================================================================
    # Execution History
    # =========================================================================

    def record_execution_start(self, routine_type: str, attempt: int = 1) -> int:
        """
        Record the start of a scheduler execution.

        Args:
            routine_type: Type of routine (morning, evening, recovery)
            attempt: Attempt number (1 = first attempt)

        Returns:
            Execution ID for later updates
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scheduler_history
                (routine_type, started_at, status, attempt)
                VALUES (?, ?, 'running', ?)
            """,
                (routine_type, now_iso(), attempt),
            )
            execution_id = cursor.lastrowid
            conn.commit()
            conn.close()
            logger.debug(f"Recorded execution start: {routine_type} (id={execution_id})")
            return execution_id
        except Exception as e:
            logger.error(f"Failed to record execution start: {e}")
            return -1

    def record_execution_complete(
        self,
        execution_id: int,
        status: str,
        report_path: Optional[str] = None,
        api_calls_used: int = 0,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Record execution completion or failure.

        Args:
            execution_id: ID from record_execution_start
            status: Final status (completed, failed, retrying)
            report_path: Path to generated report
            api_calls_used: Number of API calls made
            error_message: Error message if failed

        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE scheduler_history
                SET completed_at = ?, status = ?, report_path = ?,
                    api_calls_used = ?, error_message = ?
                WHERE id = ?
            """,
                (now_iso(), status, report_path, api_calls_used, error_message, execution_id),
            )
            conn.commit()
            conn.close()
            logger.debug(f"Recorded execution complete: id={execution_id}, status={status}")
            return True
        except Exception as e:
            logger.error(f"Failed to record execution complete: {e}")
            return False

    def get_execution_history(
        self,
        days: int = 7,
        routine_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[SchedulerExecution]:
        """
        Get execution history for the last N days.

        Args:
            days: Number of days to retrieve
            routine_type: Optional filter by routine type
            limit: Optional max records to return

        Returns:
            List of SchedulerExecution records
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cutoff = get_datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff = cutoff.isoformat()

            query = """
                SELECT * FROM scheduler_history
                WHERE started_at >= date(?, '-' || ? || ' days')
            """
            params: List[Any] = [cutoff, days]

            if routine_type:
                query += " AND routine_type = ?"
                params.append(routine_type)

            query += " ORDER BY started_at DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [
                SchedulerExecution(
                    id=row["id"],
                    routine_type=row["routine_type"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    status=row["status"],
                    attempt=row["attempt"],
                    error_message=row["error_message"],
                    report_path=row["report_path"],
                    api_calls_used=row["api_calls_used"],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get execution history: {e}")
            return []

    def get_last_execution(self, routine_type: str) -> Optional[SchedulerExecution]:
        """
        Get the most recent execution of a routine type.

        Args:
            routine_type: Type of routine

        Returns:
            Most recent SchedulerExecution or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM scheduler_history
                WHERE routine_type = ?
                ORDER BY started_at DESC
                LIMIT 1
            """,
                (routine_type,),
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return SchedulerExecution(
                    id=row["id"],
                    routine_type=row["routine_type"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    status=row["status"],
                    attempt=row["attempt"],
                    error_message=row["error_message"],
                    report_path=row["report_path"],
                    api_calls_used=row["api_calls_used"],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get last execution: {e}")
            return None

    def was_routine_run_today(self, routine_type: str) -> bool:
        """
        Check if a routine was successfully run today.

        Args:
            routine_type: Type of routine (morning, evening)

        Returns:
            True if routine completed successfully today
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            today = get_datetime_now().strftime("%Y-%m-%d")

            cursor.execute(
                """
                SELECT COUNT(*) FROM scheduler_history
                WHERE routine_type = ?
                AND date(started_at) = ?
                AND status = 'completed'
            """,
                (routine_type, today),
            )
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception as e:
            logger.error(f"Failed to check if routine run today: {e}")
            return False

    def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get execution statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with success rates, counts, etc.
        """
        history = self.get_execution_history(days)

        if not history:
            return {"total": 0, "message": "No execution history"}

        stats: Dict[str, Any] = {
            "total": len(history),
            "completed": sum(1 for e in history if e.status == "completed"),
            "failed": sum(1 for e in history if e.status == "failed"),
            "by_routine": {},
        }

        stats["success_rate"] = (
            (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        )

        # Group by routine type
        for routine in ["morning", "evening", "recovery"]:
            routine_history = [e for e in history if e.routine_type == routine]
            if routine_history:
                completed = sum(1 for e in routine_history if e.status == "completed")
                stats["by_routine"][routine] = {
                    "total": len(routine_history),
                    "completed": completed,
                    "success_rate": completed / len(routine_history) * 100,
                }

        return stats


# Global instance for easy access
_scheduler_state_manager: Optional[SchedulerStateManager] = None


def get_scheduler_state_manager() -> SchedulerStateManager:
    """Get global scheduler state manager instance."""
    global _scheduler_state_manager
    if _scheduler_state_manager is None:
        _scheduler_state_manager = SchedulerStateManager()
    return _scheduler_state_manager
