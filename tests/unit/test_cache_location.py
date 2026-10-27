"""
#600: importing the project creates no cache, and the cache follows AUTOTRADER_CACHE_DIR.

The shared caches (cache_adapter, unified_broker_cache) used to open
.cache/trading_data.db in the working directory at import.
"""

import os
import subprocess
import sys
from pathlib import Path

from src.cache import cache_adapter, unified_broker_cache
from src.cache.lazy import LazyInstance
from src.cache.sqlite_cache import TradingCacheManager
from src.cache.unified_broker_cache import UnifiedBrokerCache
from src.utils.db_backup import DBBackupManager
from src.utils.state_paths import DEFAULT_CACHE_DIR, get_cache_db_path

REPO = Path(__file__).resolve().parents[2]


def _import_in(cwd, env):
    code = "import src.trading, src.cli.cli_session, src.autogen_agents"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=cwd, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_importing_creates_nothing_in_the_working_directory(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    env = {**os.environ, "PYTHONPATH": str(REPO), "AUTOTRADER_STATE_DIR": str(tmp_path / "state")}
    env["AUTOTRADER_CACHE_DIR"] = str(tmp_path / "cache")

    _import_in(work, env)

    assert list(work.iterdir()) == []
    assert not (tmp_path / "cache").exists()  # not even the cache dir, until first use


def test_the_shared_caches_are_built_on_first_use_in_the_cache_dir(tmp_path):
    # The conftest points AUTOTRADER_CACHE_DIR at tmp_path / "cache" and drops the instances
    assert cache_adapter._instance is None and unified_broker_cache._instance is None

    cache_adapter.get_cache_stats()
    unified_broker_cache.get_position_history("paper", "SPY")

    db = tmp_path / "cache" / "trading_data.db"
    assert db.exists()
    assert Path(cache_adapter.cache.db_path) == db
    assert Path(unified_broker_cache.db_path) == db


def test_cache_classes_default_to_the_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOTRADER_CACHE_DIR", str(tmp_path / "elsewhere"))
    db = tmp_path / "elsewhere" / "trading_data.db"

    assert Path(TradingCacheManager().db_path) == db
    assert Path(UnifiedBrokerCache().db_path) == db
    assert DBBackupManager().get_db_path("cache") == db


def test_without_the_setting_the_cache_is_the_repositorys(monkeypatch):
    monkeypatch.delenv("AUTOTRADER_CACHE_DIR")

    assert Path(get_cache_db_path()) == REPO / ".cache" / "trading_data.db"
    assert DEFAULT_CACHE_DIR == REPO / ".cache"


def test_an_explicit_project_root_keeps_its_own_cache(tmp_path):
    manager = DBBackupManager(project_root=str(tmp_path))

    assert manager.get_db_path("cache") == tmp_path / ".cache" / "trading_data.db"


def test_a_lazy_instance_is_built_once_and_not_by_repr():
    built = []

    class Thing:
        value = 7

        def __init__(self):
            built.append(self)

    lazy = LazyInstance(Thing)
    assert "not built" in repr(lazy) and built == []

    assert lazy.value == 7 and lazy.value == 7
    assert len(built) == 1 and lazy.get() is built[0]
