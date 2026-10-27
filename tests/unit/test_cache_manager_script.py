"""
scripts/utilities/cache_manager.py runs against a temporary cache database.

It imported src.data_sources.cache, which no longer exists, so every command failed.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.cache import TradingCacheManager

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "utilities" / "cache_manager.py"


@pytest.fixture
def cache_manager(monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))  # the script prepends the repo root
    spec = importlib.util.spec_from_file_location("cache_manager_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "trading_data.db"
    index = pd.DatetimeIndex(["2026-10-20", "2026-10-21", "2026-10-22"], name="date")
    bars = pd.DataFrame(
        {
            "open": [740.0, 742.0, 744.0],
            "high": [745.0, 746.0, 747.0],
            "low": [738.0, 740.0, 742.0],
            "close": [741.2, 744.47, 743.9],
            "volume": [1000, 1100, 1200],
        },
        index=index,
    )
    TradingCacheManager(db_path=str(path)).set("SPY", bars, source="alpaca", ttl_hours=24 * 365)
    return str(path)


def _run(cache_manager, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["cache_manager.py", *argv])
    return cache_manager.main()


def test_stats_reads_the_cache(cache_manager, db_path, monkeypatch, capsys):
    assert _run(cache_manager, monkeypatch, "--db-path", db_path, "stats") == 0

    out = capsys.readouterr().out
    assert "Total entries: 3" in out
    assert "Unique symbols: 1" in out


def test_symbols_lists_the_cached_symbols(cache_manager, db_path, monkeypatch, capsys):
    assert _run(cache_manager, monkeypatch, "--db-path", db_path, "symbols") == 0

    out = capsys.readouterr().out
    assert "Total: 1" in out and "SPY" in out


def test_query_finds_the_bars(cache_manager, db_path, monkeypatch, capsys):
    argv = ["--db-path", db_path, "query", "SPY", "--start", "2026-10-20", "--end", "2026-10-22"]

    assert _run(cache_manager, monkeypatch, *argv) == 0

    assert "Found 3 days" in capsys.readouterr().out


def test_export_writes_the_rows(cache_manager, db_path, monkeypatch, tmp_path):
    output = tmp_path / "spy.json"
    argv = ["--db-path", db_path, "export", "SPY", "--start", "2026-10-20", "--end", "2026-10-22"]

    assert _run(cache_manager, monkeypatch, *argv, "--output", str(output)) == 0

    exported = json.loads(output.read_text())
    assert exported["symbol"] == "SPY"
    assert [row["close"] for row in exported["data"]] == [741.2, 744.47, 743.9]


def test_no_data_is_a_failed_export(cache_manager, db_path, monkeypatch, tmp_path):
    output = tmp_path / "none.json"
    argv = ["--db-path", db_path, "export", "SPY", "--start", "2030-01-01", "--end", "2030-01-31"]

    assert _run(cache_manager, monkeypatch, *argv, "--output", str(output)) == 1
    assert not output.exists()


def test_the_default_database_is_the_repositorys_cache(cache_manager, monkeypatch):
    monkeypatch.delenv("AUTOTRADER_CACHE_DIR")  # the conftest points it at a temp dir
    seen = {}
    monkeypatch.setattr(
        cache_manager, "cmd_stats", lambda args: seen.setdefault("db", args.db_path)
    )
    monkeypatch.chdir("/")

    _run(cache_manager, monkeypatch, "stats")

    assert Path(seen["db"]) == REPO_ROOT / ".cache" / "trading_data.db"


def test_the_default_database_follows_the_cache_dir(cache_manager, monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOTRADER_CACHE_DIR", str(tmp_path / "elsewhere"))
    seen = {}
    monkeypatch.setattr(
        cache_manager, "cmd_stats", lambda args: seen.setdefault("db", args.db_path)
    )

    _run(cache_manager, monkeypatch, "stats")

    assert Path(seen["db"]) == tmp_path / "elsewhere" / "trading_data.db"
