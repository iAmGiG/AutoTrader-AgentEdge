"""/backup CLI tools against a real DBBackupManager in a temporary project root."""

import sqlite3

import pytest

import src.cli.tools.backup_tools as bt
from src.utils.db_backup import DBBackupManager


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "state").mkdir()
    db = tmp_path / "state" / "user.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
    manager = DBBackupManager(project_root=str(tmp_path))
    monkeypatch.setattr(bt, "_get_backup_manager", lambda: manager)
    monkeypatch.setattr(bt, "BACKUP_DIR", str(manager.backup_dir))
    return tmp_path, manager


def _backup_name(manager):
    files = sorted(manager.backup_dir.glob("user_*.db"), key=lambda p: p.stat().st_mtime)
    assert files, "no backup written"
    return files[-1].name


def test_backup_then_list_shows_it(project):
    _, manager = project
    assert "Backup created" in bt.backup_database("user")
    assert _backup_name(manager) in bt.list_backups()


def test_unknown_database_returns_message(project):
    result = bt.backup_database("nonexistent.db")
    assert "failed" in result.lower() and "Unknown database" in result


def test_restore_round_trip(project):
    root, manager = project
    bt.backup_database("user")
    name = _backup_name(manager)
    with sqlite3.connect(root / "state" / "user.db") as conn:
        conn.execute("DELETE FROM t")
    result = bt.restore_backup(name)
    assert "restored" in result.lower()
    with sqlite3.connect(root / "state" / "user.db") as conn:
        assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 1


def test_restore_missing_backup(project):
    assert "not found" in bt.restore_backup("user_19990101_000000.db").lower()


def test_cleanup_reports_count(project):
    bt.backup_database("user")
    result = bt.cleanup_old_backups(days=30)
    assert "Cleanup complete" in result and "Removed 0" in result
