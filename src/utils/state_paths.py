"""
Location of the local state directory (state/user.db, backups, exports) and of the
market-data and broker cache (.cache/trading_data.db).

Every manager that persists to state/user.db resolves its default path here, so one
environment variable can redirect all of them; the cache has its own. The test suite
sets both to temporary directories so tests never touch the real saved trading mode,
alerts, GTT orders or cache.
"""

import os
from pathlib import Path

STATE_DIR_ENV = "AUTOTRADER_STATE_DIR"
DEFAULT_STATE_DIR = Path(__file__).resolve().parents[2] / "state"
CACHE_DIR_ENV = "AUTOTRADER_CACHE_DIR"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"


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


def get_cache_dir() -> Path:
    """Cache directory: ``$AUTOTRADER_CACHE_DIR`` if set, else ``<repo>/.cache``.

    Not created here: the caches create it when they open their database.
    """
    override = os.environ.get(CACHE_DIR_ENV)
    return Path(override) if override else DEFAULT_CACHE_DIR


def get_cache_db_path() -> str:
    """Default path of the cache database (``<cache dir>/trading_data.db``)."""
    return str(get_cache_dir() / "trading_data.db")
