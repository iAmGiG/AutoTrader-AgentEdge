"""/backup CLI tools against a real DBBackupManager in a temporary project root."""

import os
import sqlite3
import time

import pytest

import src.cli.tools.backup_tools as bt
from src.utils.db_backup import DBBackupManager


def _make_db(path, rows=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(rows)])
    conn.close()


def _count(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT count(*) FROM t").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def project(tmp_path, monkeypatch):
    _make_db(tmp_path / "state" / "user.db", rows=1)
    _make_db(tmp_path / ".cache" / "trading_data.db", rows=3)
    manager = DBBackupManager(project_root=str(tmp_path))
    monkeypatch.setattr(bt, "_get_backup_manager", lambda: manager)
    return tmp_path, manager


def _newest(manager, prefix="user_"):
    files = sorted(manager.backup_dir.glob(f"{prefix}*.db"), key=lambda p: p.stat().st_mtime)
    assert files, "no backup written"
    return files[-1].name


def test_backup_then_list_shows_it(project):
    _, manager = project
    assert "Backup created" in bt.backup_database("user")
    listing = bt.list_backups()
    assert _newest(manager) in listing
    assert "Database: user" in listing


def test_list_does_not_depend_on_cwd(project, tmp_path, monkeypatch):
    _, manager = project
    bt.backup_database("user")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert _newest(manager) in bt.list_backups()


def test_unknown_database_returns_message(project):
    result = bt.backup_database("nonexistent.db")
    assert "Unknown database" in result
    assert "Backup failed: Backup failed" not in result


def test_restore_round_trip(project):
    root, manager = project
    bt.backup_database("user")
    name = _newest(manager)
    with sqlite3.connect(root / "state" / "user.db") as conn:
        conn.execute("DELETE FROM t")
    conn.close()
    result = bt.restore_backup(name)
    assert "restored" in result.lower()
    assert _count(root / "state" / "user.db") == 1


def test_restore_missing_backup(project):
    assert "not found" in bt.restore_backup("user_19990101_000000.db").lower()


@pytest.mark.parametrize("name", ["../user.db", "/tmp/other.db", "sub/user_1.db", "user_1.txt"])
def test_restore_rejects_paths_and_non_db_names(project, name):
    assert "Invalid backup name" in bt.restore_backup(name)


def test_restore_rejects_mismatched_target(project):
    _, manager = project
    bt.backup_database("cache")
    result = bt.restore_backup(_newest(manager, "cache_"), target_db="user")
    assert "backup of the 'cache' database" in result


def test_cache_backup_restores_cache_not_user(project):
    root, manager = project
    bt.backup_database("cache")
    name = _newest(manager, "cache_")
    with sqlite3.connect(root / ".cache" / "trading_data.db") as conn:
        conn.execute("DELETE FROM t")
    conn.close()
    assert "restored" in bt.restore_backup(name).lower()
    assert _count(root / ".cache" / "trading_data.db") == 3
    assert _count(root / "state" / "user.db") == 1  # untouched


def test_empty_backup_refused(project):
    _, manager = project
    (manager.backup_dir / "user_20200101_000000.db").write_bytes(b"")
    assert "empty" in bt.restore_backup("user_20200101_000000.db").lower()


def test_non_sqlite_backup_refused(project):
    _, manager = project
    (manager.backup_dir / "user_20200101_000000.db").write_bytes(b"not a database at all")
    assert "Not a SQLite database backup" in bt.restore_backup("user_20200101_000000.db")


def test_restore_over_damaged_db(project):
    root, manager = project
    bt.backup_database("user")
    name = _newest(manager)
    (root / "state" / "user.db").write_bytes(b"garbage, not sqlite" * 100)
    result = bt.restore_backup(name)
    assert "restored" in result.lower(), result
    assert _count(root / "state" / "user.db") == 1
    assert list(manager.backup_dir.glob("user_*.corrupt")), "damaged DB not set aside"
    assert all(p.stat().st_size > 0 for p in manager.backup_dir.glob("*.db"))


def test_failed_backup_leaves_no_file(project):
    root, manager = project
    (root / "state" / "user.db").write_bytes(b"garbage, not sqlite" * 100)
    before = set(manager.backup_dir.glob("*"))
    assert "failed" in bt.backup_database("user").lower()
    assert set(manager.backup_dir.glob("*")) == before


def test_manager_refuses_restoring_live_db_onto_itself(project):
    root, manager = project
    result = manager.restore_backup(str(root / "state" / "user.db"), "user")
    assert not result.success and "live database" in result.message


def test_cleanup_keeps_newest_per_database(project):
    _, manager = project
    old = time.time() - 90 * 86400
    for i in range(3):
        p = manager.backup_dir / f"user_2020010{i}_000000.db"
        _make_db(p)
        os.utime(p, (old + i, old + i))
    for i in range(6):
        p = manager.backup_dir / f"cache_2020010{i}_000000.db"
        _make_db(p)
        os.utime(p, (old + 10 + i, old + 10 + i))
    result = bt.cleanup_old_backups(days=30)
    assert "Removed 1 backup" in result
    assert len(list(manager.backup_dir.glob("user_*.db"))) == 3
    assert len(list(manager.backup_dir.glob("cache_*.db"))) == 5


def test_exports_do_not_overwrite(project):
    _, manager = project
    first = bt.export_table("t")
    second = bt.export_table("t")
    assert "Exported 1 rows" in first and "Exported 1 rows" in second
    assert len(list(manager.export_dir.glob("t_*.json"))) == 2


def test_export_to_an_existing_file_is_refused(project):
    # The agent tool takes a free-form path; it must not be able to clobber a file
    tmp_path, _ = project
    target = tmp_path / "notes.txt"
    target.write_text("keep me")

    result = bt.export_table("t", output_path=str(target))

    assert "already exists" in result
    assert target.read_text() == "keep me"


def test_default_manager_uses_isolated_state_dir(isolated_state_dir):
    manager = DBBackupManager()
    assert manager.backup_dir == isolated_state_dir / "backups"
    assert manager.get_db_path("user") == isolated_state_dir / "user.db"
