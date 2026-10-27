"""
LocalStateManager - JSON persistence for local trading state.

Extracted from trading_cycle.py as part of #439 refactoring.
Handles loading/saving position state including position tracker history.
"""

import contextlib
import json
import logging
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.trading.positions.position_tracker import position_key
from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


def write_json_atomic(path: str, data: Dict[str, Any]) -> None:
    """Write JSON to a temp file beside path, then rename it over path, so a crash or a
    full disk mid-write leaves the old file whole. An existing file keeps its mode."""
    directory = os.path.dirname(path) or "."
    try:
        mode: Optional[int] = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        mode = None
    fd, tmp_path = tempfile.mkstemp(
        dir=directory, prefix=f".{os.path.basename(path)}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    # Make the rename itself durable (best effort: not every platform can open a directory)
    with contextlib.suppress(OSError):
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def _has_old_tracker_keys(state: Dict[str, Any]) -> bool:
    """Whether the saved tracker has entries under keys other than position_key(ticker)."""
    tracked = (state.get("position_tracker_state") or {}).get("positions") or {}
    return any(key != position_key(str(pos.get("ticker", ""))) for key, pos in tracked.items())


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
        # Set when the file on disk holds tracker entries the next save drops (old keys)
        self._backup_before_save = False

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
                self._backup_before_save = _has_old_tracker_keys(state)

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
        """
        Save local state to JSON including position tracker with alert history.

        The write is atomic. The first save after loading a file whose tracker has entries
        under old keys (which the routines now drop, #599) first copies that file to
        <state dir>/backups/. That copy is best effort: the routines never read those
        entries, and the state must still be saved.
        """
        self._state["last_update"] = now_iso()

        # Persist position tracker state (including alert history)
        if self.position_tracker:
            self._state["position_tracker_state"] = self.position_tracker.to_dict()

        if self._backup_before_save:
            self._backup_before_save = False
            try:
                self._backup_state_file("pre_tracker_prune")
            except OSError as e:
                logger.error(f"State file not backed up before dropping old tracker entries: {e}")

        try:
            write_json_atomic(self.state_file, self._state)

            position_count = len(self.position_tracker.positions) if self.position_tracker else 0
            logger.debug(f"Saved local state with {position_count} tracked positions")
        except IOError as e:
            logger.error(f"Failed to save state: {e}")

    def _backup_state_file(self, tag: str) -> Optional[str]:
        """Copy the state file on disk to <state dir>/backups/<name>.<UTC time>.<tag>.json."""
        if not os.path.exists(self.state_file):
            return None
        backup_dir = os.path.join(os.path.dirname(self.state_file) or ".", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(self.state_file))[0]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = os.path.join(backup_dir, f"{stem}.{stamp}.{tag}.json")
        shutil.copy2(self.state_file, backup)
        logger.info(f"Backed up {self.state_file} to {backup} before saving")
        return backup

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
