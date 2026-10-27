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

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "utilities" / "cache_manager.py"


@pytest.fixture
def cache_manager():
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


def test_stats_symbols_and_query_read_the_cache(cache_manager, db_path, monkeypatch, capsys):
    assert _run(cache_manager, monkeypatch, "--db-path", db_path, "stats") == 0
    assert _run(cache_manager, monkeypatch, "--db-path", db_path, "symbols") == 0
    assert (
        _run(
            cache_manager,
            monkeypatch,
            "--db-path",
            db_path,
            "query",
            "SPY",
            "--start",
            "2026-10-20",
            "--end",
            "2026-10-22",
        )
        == 0
    )

    out = capsys.readouterr().out
    assert "Total entries: 3" in out
    assert "SPY" in out
    assert "Found 3 days" in out


def test_export_writes_the_rows(cache_manager, db_path, monkeypatch, tmp_path):
    output = tmp_path / "spy.json"

    assert (
        _run(
            cache_manager,
            monkeypatch,
            "--db-path",
            db_path,
            "export",
            "SPY",
            "--start",
            "2026-10-20",
            "--end",
            "2026-10-22",
            "--output",
            str(output),
        )
        == 0
    )

    exported = json.loads(output.read_text())
    assert exported["symbol"] == "SPY"
    assert [row["close"] for row in exported["data"]] == [741.2, 744.47, 743.9]
