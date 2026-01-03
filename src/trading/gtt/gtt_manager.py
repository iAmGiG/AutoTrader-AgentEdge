"""
GTT Manager - Persistent price trigger management.

Issue #340: GTT (Good-Till-Triggered) implementation.

Provides:
- SQLite persistence for triggers
- CRUD operations (create, read, update, delete)
- Trigger state management
- OCO group handling
- Expiration management
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from src.utils.config_loader import ConfigLoader
from src.utils.date_utils import get_datetime_now, now_iso, parse_date_string

logger = logging.getLogger(__name__)


class ConditionType(Enum):
    """Types of trigger conditions."""

    # Price-based conditions (Phase 1)
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PCT_GAIN = "pct_gain"
    PCT_LOSS = "pct_loss"
    TRAILING_STOP = "trailing_stop"

    # Time-based conditions (Phase 2)
    TIME_WINDOW = "time_window"  # Active only during specific hours

    # Volume-based conditions (Phase 2)
    VOLUME_ABOVE = "volume_above"  # Volume exceeds threshold
    VOLUME_SPIKE = "volume_spike"  # Volume spike vs average


class ActionType(Enum):
    """Types of actions when trigger fires."""

    ALERT = "alert"
    PLACE_ORDER = "place_order"
    CANCEL_ORDER = "cancel_order"


@dataclass
class GTTTrigger:
    """A persistent GTT trigger."""

    id: Optional[int] = None
    symbol: str = ""
    condition_type: str = ConditionType.PRICE_ABOVE.value
    trigger_value: float = 0.0
    action_type: str = ActionType.ALERT.value
    action_config: Optional[Dict[str, Any]] = None
    expiration_date: Optional[str] = None
    max_triggers: Optional[int] = None  # None = unlimited
    trigger_count: int = 0
    last_triggered_at: Optional[str] = None
    enabled: bool = True
    oco_group_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.action_config is None:
            self.action_config = {}

    @property
    def is_expired(self) -> bool:
        """Check if trigger has expired."""
        if not self.expiration_date:
            return False
        try:
            exp = parse_date_string(self.expiration_date)
            return get_datetime_now() > exp
        except Exception:
            return False

    @property
    def is_maxed_out(self) -> bool:
        """Check if trigger has reached max triggers."""
        if self.max_triggers is None:
            return False
        return self.trigger_count >= self.max_triggers

    @property
    def is_active(self) -> bool:
        """Check if trigger is active (enabled, not expired, not maxed)."""
        return self.enabled and not self.is_expired and not self.is_maxed_out

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "condition_type": self.condition_type,
            "trigger_value": self.trigger_value,
            "action_type": self.action_type,
            "action_config": self.action_config,
            "expiration_date": self.expiration_date,
            "max_triggers": self.max_triggers,
            "trigger_count": self.trigger_count,
            "last_triggered_at": self.last_triggered_at,
            "enabled": self.enabled,
            "oco_group_id": self.oco_group_id,
            "notes": self.notes,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
        }


class GTTManager:
    """
    Manages GTT triggers in SQLite.

    Provides persistence for:
    - Price-based triggers (above/below)
    - Percentage-based triggers (gain/loss)
    - Trailing stop triggers
    - OCO trigger groups
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize GTT manager.

        Args:
            db_path: Path to SQLite database (default: from config or state/user.db)
        """
        if db_path is None:
            config = ConfigLoader()
            state_dir = config.get("paths.state_dir", "state")
            os.makedirs(state_dir, exist_ok=True)
            db_path = os.path.join(state_dir, "user.db")

        self._db_path = db_path
        self._init_database()
        logger.debug(f"GTTManager initialized with db: {db_path}")

    def _init_database(self) -> None:
        """Initialize SQLite tables for GTT triggers."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS gtt_triggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    condition_type TEXT NOT NULL,
                    trigger_value REAL NOT NULL,
                    action_type TEXT NOT NULL,
                    action_config TEXT,
                    expiration_date TEXT,
                    max_triggers INTEGER,
                    trigger_count INTEGER DEFAULT 0,
                    last_triggered_at TEXT,
                    enabled BOOLEAN DEFAULT TRUE,
                    oco_group_id INTEGER,
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
            """
            )

            # Index for symbol lookup
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gtt_symbol
                ON gtt_triggers(symbol)
            """
            )

            # Index for active triggers
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gtt_enabled
                ON gtt_triggers(enabled)
            """
            )

            # Index for OCO groups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gtt_oco
                ON gtt_triggers(oco_group_id)
            """
            )

            conn.commit()
            conn.close()
            logger.debug("GTT triggers table initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GTT database: {e}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_trigger(
        self,
        symbol: str,
        condition_type: ConditionType,
        trigger_value: float,
        action_type: ActionType = ActionType.ALERT,
        action_config: Optional[Dict[str, Any]] = None,
        expiration_days: Optional[int] = None,
        max_triggers: Optional[int] = None,
        oco_group_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[GTTTrigger]:
        """
        Create a new GTT trigger.

        Args:
            symbol: Stock symbol
            condition_type: Type of condition (PRICE_ABOVE, PRICE_BELOW, etc.)
            trigger_value: Value that triggers the action
            action_type: Action to take when triggered (ALERT, PLACE_ORDER)
            action_config: Configuration for the action (e.g., order details)
            expiration_days: Days until trigger expires (None = no expiration)
            max_triggers: Maximum times to fire (None = unlimited)
            oco_group_id: ID for OCO group (linked triggers)
            notes: Optional notes

        Returns:
            Created GTTTrigger or None on failure
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Calculate expiration date
            expiration_date = None
            if expiration_days:
                exp = get_datetime_now() + timedelta(days=expiration_days)
                expiration_date = exp.isoformat()

            # Serialize action config
            action_config_json = json.dumps(action_config) if action_config else None

            cursor.execute(
                """
                INSERT INTO gtt_triggers (
                    symbol, condition_type, trigger_value, action_type,
                    action_config, expiration_date, max_triggers,
                    oco_group_id, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    symbol.upper(),
                    condition_type.value,
                    trigger_value,
                    action_type.value,
                    action_config_json,
                    expiration_date,
                    max_triggers,
                    oco_group_id,
                    notes,
                    now_iso(),
                ),
            )

            trigger_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"Created GTT trigger: {symbol} {condition_type.value} {trigger_value}")

            return GTTTrigger(
                id=trigger_id,
                symbol=symbol.upper(),
                condition_type=condition_type.value,
                trigger_value=trigger_value,
                action_type=action_type.value,
                action_config=action_config or {},
                expiration_date=expiration_date,
                max_triggers=max_triggers,
                trigger_count=0,
                enabled=True,
                oco_group_id=oco_group_id,
                notes=notes,
                created_at=now_iso(),
            )

        except Exception as e:
            logger.error(f"Failed to create GTT trigger: {e}")
            return None

    def get_trigger(self, trigger_id: int) -> Optional[GTTTrigger]:
        """Get a specific trigger by ID."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gtt_triggers WHERE id = ?", (trigger_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._row_to_trigger(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get trigger {trigger_id}: {e}")
            return None

    def get_triggers(
        self,
        symbol: Optional[str] = None,
        enabled_only: bool = True,
        active_only: bool = True,
    ) -> List[GTTTrigger]:
        """
        Get triggers, optionally filtered.

        Args:
            symbol: Filter by symbol
            enabled_only: Only return enabled triggers
            active_only: Only return active triggers (enabled, not expired, not maxed)

        Returns:
            List of matching triggers
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM gtt_triggers WHERE 1=1"
            params: List[Any] = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())

            if enabled_only:
                query += " AND enabled = TRUE"

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            triggers = [self._row_to_trigger(row) for row in rows]

            # Filter active if requested
            if active_only:
                triggers = [t for t in triggers if t.is_active]

            return triggers

        except Exception as e:
            logger.error(f"Failed to get triggers: {e}")
            return []

    def get_all_triggers(self, include_disabled: bool = False) -> List[GTTTrigger]:
        """Get all triggers (for listing purposes)."""
        return self.get_triggers(enabled_only=not include_disabled, active_only=False)

    def update_trigger(
        self,
        trigger_id: int,
        **kwargs,
    ) -> bool:
        """
        Update a trigger.

        Args:
            trigger_id: ID of trigger to update
            **kwargs: Fields to update

        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build update query
            updates = []
            params = []

            for key, value in kwargs.items():
                if key == "action_config":
                    value = json.dumps(value) if value else None
                updates.append(f"{key} = ?")
                params.append(value)

            if not updates:
                return True

            params.append(trigger_id)
            # Safe: updates list comes from internal dict, values are parameterized
            query = f"UPDATE gtt_triggers SET {', '.join(updates)} WHERE id = ?"  # nosec: B608

            cursor.execute(query, params)
            conn.commit()
            conn.close()

            logger.debug(f"Updated GTT trigger {trigger_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update trigger {trigger_id}: {e}")
            return False

    def delete_trigger(self, trigger_id: int) -> bool:
        """Delete a trigger."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM gtt_triggers WHERE id = ?", (trigger_id,))
            conn.commit()
            conn.close()
            logger.info(f"Deleted GTT trigger {trigger_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete trigger {trigger_id}: {e}")
            return False

    def enable_trigger(self, trigger_id: int) -> bool:
        """Enable a trigger."""
        return self.update_trigger(trigger_id, enabled=True)

    def disable_trigger(self, trigger_id: int) -> bool:
        """Disable a trigger."""
        return self.update_trigger(trigger_id, enabled=False)

    # =========================================================================
    # Trigger State Management
    # =========================================================================

    def record_trigger_fire(self, trigger_id: int) -> bool:
        """
        Record that a trigger has fired.

        Increments trigger_count and sets last_triggered_at.
        Auto-disables if max_triggers reached.
        Cancels OCO group partners if applicable.

        Args:
            trigger_id: ID of trigger that fired

        Returns:
            True if successful
        """
        try:
            trigger = self.get_trigger(trigger_id)
            if not trigger:
                return False

            new_count = trigger.trigger_count + 1

            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE gtt_triggers
                SET trigger_count = ?, last_triggered_at = ?
                WHERE id = ?
            """,
                (new_count, now_iso(), trigger_id),
            )
            conn.commit()
            conn.close()

            # OCO: Cancel partner triggers in same group
            if trigger.oco_group_id:
                disabled_count = self.disable_oco_group(
                    trigger.oco_group_id, except_trigger_id=trigger_id
                )
                if disabled_count > 0:
                    logger.info(
                        f"GTT trigger {trigger_id} fired - cancelled {disabled_count} OCO partner(s)"
                    )

            # Auto-disable if max reached
            if trigger.max_triggers and new_count >= trigger.max_triggers:
                self.disable_trigger(trigger_id)
                logger.info(
                    f"GTT trigger {trigger_id} auto-disabled (max_triggers={trigger.max_triggers})"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to record trigger fire: {e}")
            return False

    def update_trailing_stop(self, trigger_id: int, new_highest: float, new_stop: float) -> bool:
        """
        Update trailing stop trigger with new highest price.

        Args:
            trigger_id: ID of trailing stop trigger
            new_highest: New highest price achieved
            new_stop: New calculated stop level

        Returns:
            True if successful
        """
        try:
            trigger = self.get_trigger(trigger_id)
            if not trigger:
                return False

            config = trigger.action_config or {}
            config["highest_price"] = new_highest
            config["current_stop"] = new_stop

            return self.update_trigger(trigger_id, action_config=config)

        except Exception as e:
            logger.error(f"Failed to update trailing stop: {e}")
            return False

    # =========================================================================
    # OCO Group Management
    # =========================================================================

    def get_next_oco_group_id(self) -> int:
        """Get next available OCO group ID."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MAX(oco_group_id) FROM gtt_triggers WHERE oco_group_id IS NOT NULL"
            )
            row = cursor.fetchone()
            conn.close()

            max_id = row[0] if row[0] else 0
            return max_id + 1
        except Exception:
            return 1

    def get_oco_group(self, oco_group_id: int) -> List[GTTTrigger]:
        """Get all triggers in an OCO group."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gtt_triggers WHERE oco_group_id = ?", (oco_group_id,))
            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_trigger(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get OCO group {oco_group_id}: {e}")
            return []

    def disable_oco_group(self, oco_group_id: int, except_trigger_id: int = None) -> int:
        """
        Disable all triggers in an OCO group.

        Args:
            oco_group_id: OCO group to disable
            except_trigger_id: Optional trigger to exclude (the one that fired)

        Returns:
            Number of triggers disabled
        """
        try:
            triggers = self.get_oco_group(oco_group_id)
            disabled = 0

            for trigger in triggers:
                if except_trigger_id and trigger.id == except_trigger_id:
                    continue
                if self.disable_trigger(trigger.id):
                    disabled += 1
                    logger.info(
                        f"OCO: Disabled trigger {trigger.id} (partner of {except_trigger_id})"
                    )

            return disabled

        except Exception as e:
            logger.error(f"Failed to disable OCO group: {e}")
            return 0

    def create_oco_pair(
        self,
        symbol: str,
        condition_a: ConditionType,
        value_a: float,
        condition_b: ConditionType,
        value_b: float,
        action_type: ActionType = ActionType.ALERT,
        action_config: Optional[Dict[str, Any]] = None,
        expiration_days: Optional[int] = None,
        notes_a: Optional[str] = None,
        notes_b: Optional[str] = None,
    ) -> tuple[Optional[GTTTrigger], Optional[GTTTrigger]]:
        """
        Create an OCO trigger pair.

        Args:
            symbol: Stock symbol
            condition_a: Condition for first trigger
            value_a: Value for first trigger
            condition_b: Condition for second trigger
            value_b: Value for second trigger
            action_type: Action for both triggers
            action_config: Config for both triggers
            expiration_days: Expiration for both
            notes_a: Notes for first trigger
            notes_b: Notes for second trigger

        Returns:
            Tuple of (trigger_a, trigger_b) or (None, None) on failure
        """
        oco_group_id = self.get_next_oco_group_id()

        trigger_a = self.create_trigger(
            symbol=symbol,
            condition_type=condition_a,
            trigger_value=value_a,
            action_type=action_type,
            action_config=action_config,
            expiration_days=expiration_days,
            max_triggers=1,  # OCO triggers fire once
            oco_group_id=oco_group_id,
            notes=notes_a,
        )

        if not trigger_a:
            return None, None

        trigger_b = self.create_trigger(
            symbol=symbol,
            condition_type=condition_b,
            trigger_value=value_b,
            action_type=action_type,
            action_config=action_config,
            expiration_days=expiration_days,
            max_triggers=1,
            oco_group_id=oco_group_id,
            notes=notes_b,
        )

        if not trigger_b:
            # Clean up trigger_a if trigger_b failed
            self.delete_trigger(trigger_a.id)
            return None, None

        logger.info(f"Created OCO pair (group {oco_group_id}): {trigger_a.id}, {trigger_b.id}")
        return trigger_a, trigger_b

    # =========================================================================
    # Helpers
    # =========================================================================

    def _row_to_trigger(self, row: sqlite3.Row) -> GTTTrigger:
        """Convert database row to GTTTrigger."""
        action_config = None
        if row["action_config"]:
            try:
                action_config = json.loads(row["action_config"])
            except Exception:
                action_config = {}

        return GTTTrigger(
            id=row["id"],
            symbol=row["symbol"],
            condition_type=row["condition_type"],
            trigger_value=row["trigger_value"],
            action_type=row["action_type"],
            action_config=action_config,
            expiration_date=row["expiration_date"],
            max_triggers=row["max_triggers"],
            trigger_count=row["trigger_count"],
            last_triggered_at=row["last_triggered_at"],
            enabled=bool(row["enabled"]),
            oco_group_id=row["oco_group_id"],
            notes=row["notes"],
            created_at=row["created_at"],
        )

    def get_symbols_with_triggers(self) -> List[str]:
        """Get list of symbols that have active triggers."""
        triggers = self.get_triggers(active_only=True)
        return sorted({t.symbol for t in triggers})

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of GTT triggers."""
        all_triggers = self.get_all_triggers(include_disabled=True)
        active = [t for t in all_triggers if t.is_active]
        expired = [t for t in all_triggers if t.is_expired]

        return {
            "total_triggers": len(all_triggers),
            "active_triggers": len(active),
            "expired_triggers": len(expired),
            "symbols_monitored": len(self.get_symbols_with_triggers()),
            "oco_groups": len({t.oco_group_id for t in all_triggers if t.oco_group_id}),
        }


# Global instance
_gtt_manager: Optional[GTTManager] = None


def get_gtt_manager() -> GTTManager:
    """Get global GTT manager instance."""
    global _gtt_manager
    if _gtt_manager is None:
        _gtt_manager = GTTManager()
    return _gtt_manager
