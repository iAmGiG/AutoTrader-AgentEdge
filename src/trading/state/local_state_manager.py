"""
LocalStateManager - JSON persistence for local trading state.

Extracted from trading_cycle.py as part of #439 refactoring.
Handles loading/saving position state including position tracker history.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


class LocalStateManager:
    """
    Manages local JSON state persistence for trading positions.

    JSON is for human reference - broker is always source of truth.
    Persists position tracker state including alert history.
    """

    def __init__(self, state_file: str, position_tracker: Optional[Any] = None):
        """
        Initialize LocalStateManager.

        Args:
            state_file: Path to JSON state file
            position_tracker: Optional PositionTracker for alert history persistence
        """
        self.state_file = state_file
        self.position_tracker = position_tracker

        # Ensure state directory exists
        os.makedirs(os.path.dirname(state_file), exist_ok=True)

        # Load initial state
        self._state: Dict[str, Any] = self._load()

        logger.info(f"LocalStateManager initialized with state file: {state_file}")

    @property
    def state(self) -> Dict[str, Any]:
        """Get current state dict."""
        return self._state

    @state.setter
    def state(self, value: Dict[str, Any]):
        """Set state dict."""
        self._state = value

    @property
    def positions(self) -> Dict[str, Any]:
        """Get positions from state."""
        return self._state.get("positions", {})

    def _load(self) -> Dict[str, Any]:
        """Load local JSON state (for human reference)."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)

                # Restore position tracker with alert history if available
                if self.position_tracker and "position_tracker_state" in state:
                    try:
                        self.position_tracker.restore_from_dict(state["position_tracker_state"])
                        logger.info("Restored position tracker with alert history")
                    except Exception as e:
                        logger.warning(f"Failed to restore position tracker state: {e}")

                return state
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state file: {e}")
                return self._default_state()
        return self._default_state()

    def _default_state(self) -> Dict[str, Any]:
        """Return default empty state."""
        return {"positions": {}, "last_update": None, "discrepancies": []}

    def save(self):
        """Save local state to JSON including position tracker with alert history."""
        self._state["last_update"] = now_iso()

        # Persist position tracker state (including alert history)
        if self.position_tracker:
            self._state["position_tracker_state"] = self.position_tracker.to_dict()

        try:
            with open(self.state_file, "w") as f:
                json.dump(self._state, f, indent=2)

            position_count = len(self.position_tracker.positions) if self.position_tracker else 0
            logger.debug(f"Saved local state with {position_count} tracked positions")
        except IOError as e:
            logger.error(f"Failed to save state: {e}")

    def reload(self) -> Dict[str, Any]:
        """Reload state from disk."""
        self._state = self._load()
        return self._state

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position data for a symbol."""
        return self._state.get("positions", {}).get(symbol)

    def set_position(self, symbol: str, position_data: Dict[str, Any]):
        """Set position data for a symbol."""
        if "positions" not in self._state:
            self._state["positions"] = {}
        self._state["positions"][symbol] = position_data

    def remove_position(self, symbol: str) -> bool:
        """Remove position from state. Returns True if removed."""
        if symbol in self._state.get("positions", {}):
            del self._state["positions"][symbol]
            return True
        return False

    def update_position(self, symbol: str, updates: Dict[str, Any]):
        """Update specific fields in a position."""
        if symbol in self._state.get("positions", {}):
            self._state["positions"][symbol].update(updates)

    def set_discrepancies(self, discrepancies: list):
        """Set discrepancies list."""
        self._state["discrepancies"] = discrepancies

    def reset_for_recovery(self):
        """Reset state for crash recovery."""
        self._state = {
            "positions": {},
            "last_update": now_iso(),
            "discrepancies": [],
            "recovery_timestamp": now_iso(),
        }
