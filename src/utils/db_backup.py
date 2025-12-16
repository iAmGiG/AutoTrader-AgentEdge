#!/usr/bin/env python3
"""
Database Backup and Migration Utilities

Issue #483: Database backup and migration utilities

Provides utilities for:
- Backing up SQLite databases
- Exporting tables to JSON
- Importing from JSON
- Schema migrations
- Cleanup/maintenance
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.date_utils import get_datetime_now, now_iso, timestamp_compact

logger = logging.getLogger(__name__)

# Database paths relative to project root
DB_PATHS = {
    "user": "state/user.db",
    "cache": ".cache/trading_data.db",
}


@dataclass
class BackupResult:
    """Result of a backup operation."""

    success: bool
    source_path: str
    backup_path: Optional[str]
    message: str
    timestamp: str


@dataclass
class ExportResult:
    """Result of an export operation."""

    success: bool
    table_name: str
    output_path: Optional[str]
    row_count: int
    message: str


@dataclass
class ImportResult:
    """Result of an import operation."""

    success: bool
    table_name: str
    source_path: str
    rows_imported: int
    message: str


class DBBackupManager:
    """
    Manages database backup, export, import, and maintenance operations.

    Usage:
        manager = DBBackupManager()
        result = manager.backup_database("user")
        result = manager.export_table("user", "voter_ranking_history", "exports/voter.json")
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize backup manager.

        Args:
            project_root: Path to project root. Defaults to auto-detect.
        """
        if project_root is None:
            # Auto-detect project root (look for state/ directory)
            current = Path(__file__).resolve().parent
            while current != current.parent:
                if (current / "state").exists() or (current / "src").exists():
                    project_root = str(current)
                    break
                current = current.parent
            else:
                project_root = str(Path.cwd())

        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "state" / "backups"
        self.export_dir = self.project_root / "state" / "exports"

        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"DBBackupManager initialized at {self.project_root}")

    def _get_db_path(self, db_name: str) -> Path:
        """Get full path for a database by name."""
        if db_name not in DB_PATHS:
            raise ValueError(f"Unknown database: {db_name}. Available: {list(DB_PATHS.keys())}")
        return self.project_root / DB_PATHS[db_name]

    def _generate_backup_filename(self, db_name: str) -> str:
        """Generate timestamped backup filename."""
        timestamp = timestamp_compact()
        return f"{db_name}_{timestamp}.db"

    def backup_database(self, db_name: str = "user") -> BackupResult:
        """
        Create a backup of the specified database.

        Args:
            db_name: Database name ("user" or "cache")

        Returns:
            BackupResult with backup details
        """
        timestamp = now_iso()

        try:
            source_path = self._get_db_path(db_name)
            if not source_path.exists():
                return BackupResult(
                    success=False,
                    source_path=str(source_path),
                    backup_path=None,
                    message=f"Database not found: {source_path}",
                    timestamp=timestamp,
                )

            backup_filename = self._generate_backup_filename(db_name)
            backup_path = self.backup_dir / backup_filename

            # Use SQLite backup API for consistency
            source_conn = sqlite3.connect(str(source_path))
            backup_conn = sqlite3.connect(str(backup_path))

            with backup_conn:
                source_conn.backup(backup_conn)

            source_conn.close()
            backup_conn.close()

            # Verify backup
            backup_size = backup_path.stat().st_size
            logger.info(f"Backed up {db_name} to {backup_path} ({backup_size} bytes)")

            return BackupResult(
                success=True,
                source_path=str(source_path),
                backup_path=str(backup_path),
                message=f"Successfully backed up to {backup_filename}",
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error(f"Backup failed for {db_name}: {e}")
            return BackupResult(
                success=False,
                source_path=str(self._get_db_path(db_name)),
                backup_path=None,
                message=f"Backup failed: {e}",
                timestamp=timestamp,
            )

    def list_backups(self, db_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available backups.

        Args:
            db_name: Filter by database name (optional)

        Returns:
            List of backup info dicts
        """
        backups = []
        pattern = f"{db_name}_*.db" if db_name else "*.db"

        for backup_file in self.backup_dir.glob(pattern):
            stat = backup_file.stat()
            backups.append(
                {
                    "filename": backup_file.name,
                    "path": str(backup_file),
                    "size_bytes": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        return sorted(backups, key=lambda x: x["created"], reverse=True)

    def restore_backup(self, backup_path: str, db_name: str = "user") -> BackupResult:
        """
        Restore a database from backup.

        Args:
            backup_path: Path to backup file
            db_name: Target database name

        Returns:
            BackupResult with restore details
        """
        timestamp = now_iso()

        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                return BackupResult(
                    success=False,
                    source_path=backup_path,
                    backup_path=None,
                    message=f"Backup file not found: {backup_path}",
                    timestamp=timestamp,
                )

            target_path = self._get_db_path(db_name)

            # Create backup of current before restore
            if target_path.exists():
                pre_restore_backup = self.backup_database(db_name)
                if not pre_restore_backup.success:
                    return BackupResult(
                        success=False,
                        source_path=backup_path,
                        backup_path=None,
                        message="Failed to backup current DB before restore",
                        timestamp=timestamp,
                    )

            # Restore using SQLite backup API
            source_conn = sqlite3.connect(backup_path)
            target_conn = sqlite3.connect(str(target_path))

            with target_conn:
                source_conn.backup(target_conn)

            source_conn.close()
            target_conn.close()

            logger.info(f"Restored {db_name} from {backup_path}")

            return BackupResult(
                success=True,
                source_path=backup_path,
                backup_path=str(target_path),
                message=f"Successfully restored {db_name} from backup",
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return BackupResult(
                success=False,
                source_path=backup_path,
                backup_path=None,
                message=f"Restore failed: {e}",
                timestamp=timestamp,
            )

    def export_table(
        self,
        db_name: str,
        table_name: str,
        output_path: Optional[str] = None,
    ) -> ExportResult:
        """
        Export a table to JSON.

        Args:
            db_name: Database name
            table_name: Table to export
            output_path: Output file path (auto-generated if None)

        Returns:
            ExportResult with export details
        """
        try:
            db_path = self._get_db_path(db_name)
            if not db_path.exists():
                return ExportResult(
                    success=False,
                    table_name=table_name,
                    output_path=None,
                    row_count=0,
                    message=f"Database not found: {db_path}",
                )

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if not cursor.fetchone():
                conn.close()
                return ExportResult(
                    success=False,
                    table_name=table_name,
                    output_path=None,
                    row_count=0,
                    message=f"Table not found: {table_name}",
                )

            # Export data
            cursor.execute(f"SELECT * FROM {table_name}")  # noqa: S608  # nosec B608
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()

            # Generate output path if not provided
            if output_path is None:
                timestamp = timestamp_compact()
                output_path = str(self.export_dir / f"{table_name}_{timestamp}.json")

            # Write JSON
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "table": table_name,
                        "database": db_name,
                        "exported_at": now_iso(),
                        "row_count": len(rows),
                        "data": rows,
                    },
                    f,
                    indent=2,
                    default=str,
                )

            logger.info(f"Exported {len(rows)} rows from {table_name} to {output_path}")

            return ExportResult(
                success=True,
                table_name=table_name,
                output_path=str(output_path),
                row_count=len(rows),
                message=f"Exported {len(rows)} rows to {output_file.name}",
            )

        except Exception as e:
            logger.error(f"Export failed for {table_name}: {e}")
            return ExportResult(
                success=False,
                table_name=table_name,
                output_path=None,
                row_count=0,
                message=f"Export failed: {e}",
            )

    def import_table(
        self,
        source_path: str,
        db_name: str,
        table_name: Optional[str] = None,
        mode: str = "append",
    ) -> ImportResult:
        """
        Import data from JSON into a table.

        Args:
            source_path: Path to JSON file
            db_name: Target database
            table_name: Target table (uses source if None)
            mode: "append" or "replace"

        Returns:
            ImportResult with import details
        """
        try:
            source_file = Path(source_path)
            if not source_file.exists():
                return ImportResult(
                    success=False,
                    table_name=table_name or "unknown",
                    source_path=source_path,
                    rows_imported=0,
                    message=f"Source file not found: {source_path}",
                )

            with open(source_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Get table name from file if not provided
            if table_name is None:
                table_name = data.get("table")
                if not table_name:
                    return ImportResult(
                        success=False,
                        table_name="unknown",
                        source_path=source_path,
                        rows_imported=0,
                        message="No table name in JSON and none provided",
                    )

            rows = data.get("data", [])
            if not rows:
                return ImportResult(
                    success=True,
                    table_name=table_name,
                    source_path=source_path,
                    rows_imported=0,
                    message="No data to import",
                )

            db_path = self._get_db_path(db_name)
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Clear table if replace mode
            if mode == "replace":
                cursor.execute(f"DELETE FROM {table_name}")  # noqa: S608  # nosec B608

            # Get column names from first row
            columns = list(rows[0].keys())
            placeholders = ",".join(["?" for _ in columns])
            col_names = ",".join(columns)

            # Insert rows
            inserted = 0
            for row in rows:
                values = [row.get(col) for col in columns]
                try:
                    cursor.execute(
                        f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",  # noqa: S608  # nosec B608
                        values,
                    )
                    inserted += 1
                except sqlite3.IntegrityError as e:
                    logger.warning(f"Skipping duplicate row: {e}")

            conn.commit()
            conn.close()

            logger.info(f"Imported {inserted} rows into {table_name}")

            return ImportResult(
                success=True,
                table_name=table_name,
                source_path=source_path,
                rows_imported=inserted,
                message=f"Imported {inserted} rows into {table_name}",
            )

        except Exception as e:
            logger.error(f"Import failed: {e}")
            return ImportResult(
                success=False,
                table_name=table_name or "unknown",
                source_path=source_path,
                rows_imported=0,
                message=f"Import failed: {e}",
            )

    def list_tables(self, db_name: str) -> List[Dict[str, Any]]:
        """
        List all tables in a database.

        Args:
            db_name: Database name

        Returns:
            List of table info dicts
        """
        try:
            db_path = self._get_db_path(db_name)
            if not db_path.exists():
                return []

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
            tables = []

            for (table_name,) in cursor.fetchall():
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608  # nosec B608
                count = cursor.fetchone()[0]
                tables.append({"name": table_name, "row_count": count})

            conn.close()
            return tables

        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []

    def cleanup_old_data(
        self,
        db_name: str = "user",
        days: int = 30,
        tables: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """
        Remove old history records from specified tables.

        Args:
            db_name: Database name
            days: Delete records older than this many days
            tables: Tables to clean (auto-detect history tables if None)

        Returns:
            Dict mapping table names to deleted row counts
        """
        results = {}
        cutoff_date = (get_datetime_now() - timedelta(days=days)).isoformat()

        try:
            db_path = self._get_db_path(db_name)
            if not db_path.exists():
                return results

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Auto-detect history tables if not specified
            if tables is None:
                cursor.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name LIKE '%_history'
                    """
                )
                tables = [row[0] for row in cursor.fetchall()]

            for table_name in tables:
                # Look for timestamp column
                cursor.execute(f"PRAGMA table_info({table_name})")  # noqa: S608
                columns = [row[1] for row in cursor.fetchall()]

                timestamp_col = None
                for col in ["timestamp", "created_at", "date", "time"]:
                    if col in columns:
                        timestamp_col = col
                        break

                if timestamp_col:
                    cursor.execute(
                        f"DELETE FROM {table_name} WHERE {timestamp_col} < ?",  # noqa: S608  # nosec B608
                        (cutoff_date,),
                    )
                    results[table_name] = cursor.rowcount

            conn.commit()
            conn.close()

            logger.info(f"Cleanup complete: {results}")
            return results

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return results

    def cleanup_old_backups(self, keep_days: int = 7, keep_count: int = 5) -> int:
        """
        Remove old backup files.

        Args:
            keep_days: Keep backups newer than this
            keep_count: Always keep at least this many backups

        Returns:
            Number of backups deleted
        """
        cutoff_date = get_datetime_now() - timedelta(days=keep_days)
        deleted = 0

        backups = sorted(
            self.backup_dir.glob("*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for i, backup in enumerate(backups):
            if i < keep_count:
                continue

            created = datetime.fromtimestamp(backup.stat().st_ctime)
            if created < cutoff_date:
                backup.unlink()
                deleted += 1
                logger.info(f"Deleted old backup: {backup.name}")

        return deleted


class DBMigrator:
    """
    Schema migration manager for SQLite databases.

    Usage:
        migrator = DBMigrator("state/user.db")
        migrator.register_migration(2, "ALTER TABLE users ADD COLUMN email TEXT")
        migrator.migrate_to_latest()
    """

    def __init__(self, db_path: str):
        """Initialize migrator for a specific database."""
        self.db_path = Path(db_path)
        self._migrations: Dict[int, str] = {}
        self._ensure_version_table()

    def _ensure_version_table(self) -> None:
        """Create schema_version table if not exists."""
        if not self.db_path.exists():
            return

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def get_version(self) -> int:
        """Get current schema version."""
        if not self.db_path.exists():
            return 0

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            return result[0] if result[0] else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def register_migration(self, version: int, sql: str) -> None:
        """
        Register a migration script.

        Args:
            version: Target version number
            sql: SQL to execute for migration
        """
        self._migrations[version] = sql

    def migrate_to(self, target_version: int) -> List[int]:
        """
        Run migrations up to target version.

        Args:
            target_version: Version to migrate to

        Returns:
            List of applied version numbers
        """
        current = self.get_version()
        applied = []

        if current >= target_version:
            logger.info(f"Already at version {current}, nothing to migrate")
            return applied

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            for version in sorted(self._migrations.keys()):
                if version <= current or version > target_version:
                    continue

                logger.info(f"Applying migration {version}...")
                cursor.executescript(self._migrations[version])

                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (version, now_iso()),
                )
                applied.append(version)

            conn.commit()
            logger.info(f"Migration complete. Applied: {applied}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Migration failed at version {version}: {e}")
            raise

        finally:
            conn.close()

        return applied

    def migrate_to_latest(self) -> List[int]:
        """Run all pending migrations."""
        if not self._migrations:
            return []
        return self.migrate_to(max(self._migrations.keys()))


# Singleton instance
_backup_manager: Optional[DBBackupManager] = None


def get_backup_manager() -> DBBackupManager:
    """Get global DBBackupManager instance."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = DBBackupManager()
    return _backup_manager


# Convenience functions
def backup_database(db_name: str = "user") -> BackupResult:
    """Create a backup of the specified database."""
    return get_backup_manager().backup_database(db_name)


def export_table(db_name: str, table_name: str, output_path: Optional[str] = None) -> ExportResult:
    """Export a table to JSON."""
    return get_backup_manager().export_table(db_name, table_name, output_path)


def import_table(source_path: str, db_name: str, table_name: Optional[str] = None) -> ImportResult:
    """Import data from JSON into a table."""
    return get_backup_manager().import_table(source_path, db_name, table_name)


def list_tables(db_name: str = "user") -> List[Dict[str, Any]]:
    """List all tables in a database."""
    return get_backup_manager().list_tables(db_name)


if __name__ == "__main__":
    # Quick test when run directly
    import sys

    logging.basicConfig(level=logging.INFO)

    manager = DBBackupManager()

    print("=== Available Databases ===")
    for name, path in DB_PATHS.items():
        full_path = manager.project_root / path
        exists = "EXISTS" if full_path.exists() else "NOT FOUND"
        print(f"  {name}: {path} [{exists}]")

    print("\n=== Tables in user.db ===")
    tables = manager.list_tables("user")
    for table in tables:
        print(f"  {table['name']}: {table['row_count']} rows")

    if "--backup" in sys.argv:
        print("\n=== Creating Backup ===")
        result = manager.backup_database("user")
        print(f"  {result.message}")

    if "--list-backups" in sys.argv:
        print("\n=== Available Backups ===")
        backups = manager.list_backups()
        for b in backups[:5]:
            print(f"  {b['filename']} ({b['size_bytes']} bytes)")
