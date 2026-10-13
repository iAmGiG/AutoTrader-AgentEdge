"""
Location of the local state directory (state/user.db, backups, exports).

Every manager that persists to state/user.db resolves its default path here, so one
environment variable can redirect all of them. The test suite sets it to a temporary
directory so tests never touch the real saved trading mode, alerts or GTT orders.
"""

import os
from pathlib import Path

STATE_DIR_ENV = "AUTOTRADER_STATE_DIR"
DEFAULT_STATE_DIR = Path(__file__).resolve().parents[2] / "state"


def get_state_dir(create: bool = True) -> Path:
    """State directory: ``$AUTOTRADER_STATE_DIR`` if set, else ``<repo>/state``."""
    override = os.environ.get(STATE_DIR_ENV)
    path = Path(override) if override else DEFAULT_STATE_DIR
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_db_path() -> str:
    """Default path of the user state database (``<state dir>/user.db``)."""
    return str(get_state_dir() / "user.db")
