#!/usr/bin/env python3
"""
Portfolio Config Runtime Override - SQLite-backed configuration overrides.

Issue #479: Allow runtime override of portfolio config values via SQLite.

This module provides:
- Runtime overrides for portfolio configuration (max positions, limits, etc.)
- Optional expiration for temporary overrides
- Audit trail of changes
- Fallback to YAML defaults when no override exists

Uses state/user.db for persistence (same as trading_modes.py and scheduler_state.py).
"""

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

try:
    import yaml
except ImportError:
    yaml = None

from src.utils.date_utils import get_datetime_now, now_iso, parse_date_string

logger = logging.getLogger(__name__)


@dataclass
class PortfolioOverride:
    """A single portfolio configuration override."""

    id: Optional[int] = None
    config_key: str = ""  # e.g., 'limits.max_open_positions'
    override_value: str = ""  # Stored as string, converted on read
    value_type: str = "string"  # string, int, float, bool
    reason: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None  # None = never expires
    is_active: bool = True


class PortfolioOverrideManager:
    """
    Manages portfolio configuration overrides in SQLite.

    Overrides take precedence over YAML defaults. Supports:
    - Temporary overrides with expiration
    - Reason tracking for audit
    - Type-safe value conversion
    """

    def __init__(self, db_path: Optional[str] = None, config_path: Optional[str] = None):
        """
        Initialize portfolio override manager.

        Args:
            db_path: Path to SQLite database (default: state/user.db)
            config_path: Path to portfolio_config.yaml for defaults
        """
        if db_path is None:
            state_dir = os.path.join(os.path.dirname(__file__), "../../state")
            os.makedirs(state_dir, exist_ok=True)
            db_path = os.path.join(state_dir, "user.db")

        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "../../config_defaults/portfolio_config.yaml"
            )

        self._db_path = db_path
        self._config_path = config_path
        self._defaults: Dict[str, Any] = {}

        self._init_database()
        self._load_defaults()

        logger.debug(f"PortfolioOverrideManager initialized with db: {db_path}")

    def _init_database(self) -> None:
        """Initialize SQLite table for portfolio overrides."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT UNIQUE NOT NULL,
                    override_value TEXT NOT NULL,
                    value_type TEXT DEFAULT 'string',
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """
            )

            # Create index for faster lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_portfolio_overrides_key
                ON portfolio_overrides(config_key)
            """
            )

            # History table for audit trail
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_override_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    action TEXT NOT NULL,
                    reason TEXT,
                    changed_at TEXT NOT NULL
                )
            """
            )

            conn.commit()
            conn.close()
            logger.debug("Portfolio override tables initialized")
        except Exception as e:
            logger.error(f"Failed to initialize portfolio override database: {e}")

    def _load_defaults(self) -> None:
        """Load default values from YAML configuration."""
        if not os.path.exists(self._config_path):
            logger.warning(f"Portfolio config not found: {self._config_path}")
            return

        if yaml is None:
            logger.warning("PyYAML not installed, cannot load portfolio defaults")
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Flatten nested config to dot-notation keys
            self._defaults = self._flatten_config(config)
            logger.debug(f"Loaded {len(self._defaults)} portfolio config defaults")
        except Exception as e:
            logger.error(f"Failed to load portfolio config: {e}")

    def _flatten_config(
        self, config: Dict[str, Any], prefix: str = ""
    ) -> Dict[str, Any]:
        """Flatten nested config dict to dot-notation keys."""
        result = {}
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(self._flatten_config(value, full_key))
            else:
                result[full_key] = value
        return result

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _convert_value(self, value: str, value_type: str) -> Any:
        """Convert string value to appropriate type."""
        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        return value

    def _infer_type(self, value: Any) -> str:
        """Infer value type for storage."""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        return "string"

    # =========================================================================
    # Override Management
    # =========================================================================

    def set_override(
        self,
        key: str,
        value: Any,
        reason: Optional[str] = None,
        expires_in_hours: Optional[float] = None,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """
        Set a configuration override.

        Args:
            key: Config key in dot notation (e.g., 'limits.max_open_positions')
            value: Override value
            reason: Reason for the override (for audit)
            expires_in_hours: Hours until expiration (convenience param)
            expires_at: Specific expiration datetime

        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Determine expiration
            expiration = None
            if expires_at:
                expiration = expires_at.isoformat()
            elif expires_in_hours:
                expiration = (
                    get_datetime_now() + timedelta(hours=expires_in_hours)
                ).isoformat()

            # Get old value for history
            cursor.execute(
                "SELECT override_value FROM portfolio_overrides WHERE config_key = ?",
                (key,),
            )
            row = cursor.fetchone()
            old_value = row["override_value"] if row else self._defaults.get(key)

            # Upsert override
            value_type = self._infer_type(value)
            cursor.execute(
                """
                INSERT INTO portfolio_overrides
                (config_key, override_value, value_type, reason, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, TRUE)
                ON CONFLICT(config_key) DO UPDATE SET
                    override_value = excluded.override_value,
                    value_type = excluded.value_type,
                    reason = excluded.reason,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    is_active = TRUE
            """,
                (key, str(value), value_type, reason, now_iso(), expiration),
            )

            # Record in history
            cursor.execute(
                """
                INSERT INTO portfolio_override_history
                (config_key, old_value, new_value, action, reason, changed_at)
                VALUES (?, ?, ?, 'set', ?, ?)
            """,
                (key, str(old_value), str(value), reason, now_iso()),
            )

            conn.commit()
            conn.close()

            exp_msg = f" (expires: {expiration})" if expiration else ""
            logger.info(f"Portfolio override set: {key} = {value}{exp_msg}")
            return True
        except Exception as e:
            logger.error(f"Failed to set portfolio override: {e}")
            return False

    def clear_override(self, key: str, reason: Optional[str] = None) -> bool:
        """
        Clear (deactivate) an override.

        Args:
            key: Config key to clear
            reason: Reason for clearing

        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get current value for history
            cursor.execute(
                "SELECT override_value FROM portfolio_overrides WHERE config_key = ? AND is_active = TRUE",
                (key,),
            )
            row = cursor.fetchone()

            if not row:
                logger.debug(f"No active override for {key}")
                return True

            # Deactivate
            cursor.execute(
                "UPDATE portfolio_overrides SET is_active = FALSE WHERE config_key = ?",
                (key,),
            )

            # Record in history
            cursor.execute(
                """
                INSERT INTO portfolio_override_history
                (config_key, old_value, new_value, action, reason, changed_at)
                VALUES (?, ?, NULL, 'clear', ?, ?)
            """,
                (key, row["override_value"], reason, now_iso()),
            )

            conn.commit()
            conn.close()

            logger.info(f"Portfolio override cleared: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear portfolio override: {e}")
            return False

    def clear_all_overrides(self, reason: Optional[str] = None) -> int:
        """
        Clear all active overrides.

        Args:
            reason: Reason for clearing

        Returns:
            Number of overrides cleared
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get all active overrides
            cursor.execute(
                "SELECT config_key, override_value FROM portfolio_overrides WHERE is_active = TRUE"
            )
            rows = cursor.fetchall()

            if not rows:
                return 0

            # Deactivate all
            cursor.execute("UPDATE portfolio_overrides SET is_active = FALSE")

            # Record each in history
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO portfolio_override_history
                    (config_key, old_value, new_value, action, reason, changed_at)
                    VALUES (?, ?, NULL, 'clear_all', ?, ?)
                """,
                    (row["config_key"], row["override_value"], reason, now_iso()),
                )

            conn.commit()
            conn.close()

            logger.info(f"Cleared {len(rows)} portfolio overrides")
            return len(rows)
        except Exception as e:
            logger.error(f"Failed to clear all portfolio overrides: {e}")
            return 0

    def _cleanup_expired(self) -> int:
        """Deactivate expired overrides."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = now_iso()

            # Find expired overrides
            cursor.execute(
                """
                SELECT config_key, override_value FROM portfolio_overrides
                WHERE is_active = TRUE AND expires_at IS NOT NULL AND expires_at < ?
            """,
                (now,),
            )
            expired = cursor.fetchall()

            if not expired:
                conn.close()
                return 0

            # Deactivate expired
            cursor.execute(
                """
                UPDATE portfolio_overrides
                SET is_active = FALSE
                WHERE is_active = TRUE AND expires_at IS NOT NULL AND expires_at < ?
            """,
                (now,),
            )

            # Record in history
            for row in expired:
                cursor.execute(
                    """
                    INSERT INTO portfolio_override_history
                    (config_key, old_value, new_value, action, reason, changed_at)
                    VALUES (?, ?, NULL, 'expired', 'Auto-expired', ?)
                """,
                    (row["config_key"], row["override_value"], now),
                )

            conn.commit()
            conn.close()

            logger.info(f"Cleaned up {len(expired)} expired portfolio overrides")
            return len(expired)
        except Exception as e:
            logger.error(f"Failed to cleanup expired overrides: {e}")
            return 0

    # =========================================================================
    # Value Retrieval
    # =========================================================================

    def get_effective_value(self, key: str, default: Any = None) -> Any:
        """
        Get effective config value (override if exists, else default).

        Args:
            key: Config key in dot notation
            default: Default if neither override nor YAML default exists

        Returns:
            Effective configuration value
        """
        # Cleanup expired overrides first
        self._cleanup_expired()

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT override_value, value_type FROM portfolio_overrides
                WHERE config_key = ? AND is_active = TRUE
            """,
                (key,),
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._convert_value(row["override_value"], row["value_type"])

            # Fall back to YAML default
            if key in self._defaults:
                return self._defaults[key]

            return default
        except Exception as e:
            logger.error(f"Failed to get effective value for {key}: {e}")
            return self._defaults.get(key, default)

    def get_all_active_overrides(self) -> List[PortfolioOverride]:
        """Get all currently active overrides."""
        self._cleanup_expired()

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM portfolio_overrides WHERE is_active = TRUE
                ORDER BY config_key
            """
            )
            rows = cursor.fetchall()
            conn.close()

            return [
                PortfolioOverride(
                    id=row["id"],
                    config_key=row["config_key"],
                    override_value=row["override_value"],
                    value_type=row["value_type"],
                    reason=row["reason"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    is_active=bool(row["is_active"]),
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get active overrides: {e}")
            return []

    def get_override_history(
        self, key: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get override history.

        Args:
            key: Optional filter by config key
            limit: Max records to return

        Returns:
            List of history records
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if key:
                cursor.execute(
                    """
                    SELECT * FROM portfolio_override_history
                    WHERE config_key = ?
                    ORDER BY changed_at DESC
                    LIMIT ?
                """,
                    (key, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM portfolio_override_history
                    ORDER BY changed_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get override history: {e}")
            return []

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current override status."""
        overrides = self.get_all_active_overrides()
        return {
            "active_overrides": len(overrides),
            "overrides": {o.config_key: o.override_value for o in overrides},
            "expiring_soon": sum(
                1
                for o in overrides
                if o.expires_at
                and parse_date_string(o.expires_at)
                < get_datetime_now() + timedelta(hours=1)
            ),
        }

    def reload_defaults(self) -> None:
        """Reload YAML defaults."""
        self._load_defaults()
        logger.info("Portfolio config defaults reloaded")


# Global instance for easy access
_portfolio_override_manager: Optional[PortfolioOverrideManager] = None


def get_portfolio_override_manager() -> PortfolioOverrideManager:
    """Get global portfolio override manager instance."""
    global _portfolio_override_manager
    if _portfolio_override_manager is None:
        _portfolio_override_manager = PortfolioOverrideManager()
    return _portfolio_override_manager
