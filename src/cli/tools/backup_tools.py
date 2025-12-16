"""
Database Backup CLI Tools - FunctionTool wrappers for DB backup/restore.

Issue #490: /backup command group for database management.
Issue #483: DB Backup/Migration (core implementation).

This module provides FunctionTool wrappers for database backup, restore,
and export operations. When DBBackupManager is available, these tools
will integrate with it. Until then, they provide helpful stubs.

Original Implementation: src/utils/db_backup.py (when available)
Pattern: Pure function wrappers → FunctionTool → Registry
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from autogen_core.tools import FunctionTool

from src.utils.date_utils import get_datetime_now, timestamp_compact

# Default paths
STATE_DB = "state/user.db"
CACHE_DB = ".cache/trading_data.db"
BACKUP_DIR = "backups"


# ============================================================================
# Pure Function Wrappers
# ============================================================================


def _get_backup_manager():
    """Try to get DBBackupManager if available."""
    try:
        from src.utils.db_backup import DBBackupManager

        return DBBackupManager()
    except ImportError:
        return None


def backup_database(db_path: str = STATE_DB) -> str:
    """
    Create a backup of a database file.

    Creates a timestamped backup copy of the specified database.
    Backups are stored in the backups/ directory.

    Args:
        db_path: Path to database file (default: state/user.db)

    Returns:
        Success message with backup path, or error message

    Example:
        >>> backup_database()
        'Backup created: backups/user_20241215_143022.db'
        >>> backup_database('.cache/trading_data.db')
        'Backup created: backups/trading_data_20241215_143022.db'
    """
    manager = _get_backup_manager()

    if manager:
        result = manager.backup_database(db_path)
        if result.success:
            return f"✅ Backup created: {result.backup_path}"
        return f"❌ Backup failed: {result.error}"

    # Stub implementation - manual file copy
    if not os.path.exists(db_path):
        return f"❌ Database not found: {db_path}"

    # Create backup directory
    backup_dir = Path(BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate backup filename
    db_name = Path(db_path).stem
    timestamp = timestamp_compact()
    backup_path = backup_dir / f"{db_name}_{timestamp}.db"

    try:
        import shutil

        shutil.copy2(db_path, backup_path)
        return f"✅ Backup created: {backup_path}"
    except Exception as e:
        return f"❌ Backup failed: {e}"


def list_backups() -> str:
    """
    List all available database backups.

    Shows all backup files in the backups/ directory with
    their creation dates and sizes.

    Returns:
        Formatted list of available backups

    Example:
        >>> list_backups()
        'Available Backups
        user_20241215_143022.db  (1.2 MB)  Dec 15, 2024
        user_20241214_090000.db  (1.1 MB)  Dec 14, 2024'
    """
    backup_dir = Path(BACKUP_DIR)

    if not backup_dir.exists():
        return (
            "📂 No backups directory found.\n\nRun '/backup database' to create your first backup."
        )

    backups = list(backup_dir.glob("*.db"))

    if not backups:
        return "📂 No backups found.\n\nRun '/backup database' to create your first backup."

    # Sort by modification time (newest first)
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    output = "📂 Available Backups\n"
    output += "=" * 60 + "\n\n"

    for backup in backups:
        stat = backup.stat()
        size_mb = stat.st_size / (1024 * 1024)
        mod_time = datetime.fromtimestamp(stat.st_mtime)

        output += f"  {backup.name}\n"
        output += f"    Size: {size_mb:.1f} MB\n"
        output += f"    Date: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    output += "-" * 60 + "\n"
    output += f"Total: {len(backups)} backup(s)\n"

    return output


def restore_backup(backup_name: str, target_db: str = STATE_DB) -> str:
    """
    Restore a database from a backup.

    Replaces the target database with a backup copy.
    WARNING: This will overwrite the current database!

    Args:
        backup_name: Name of backup file (e.g., 'user_20241215_143022.db')
        target_db: Target database path (default: state/user.db)

    Returns:
        Success or error message

    Example:
        >>> restore_backup('user_20241215_143022.db')
        'Database restored from: backups/user_20241215_143022.db'
    """
    backup_path = Path(BACKUP_DIR) / backup_name

    if not backup_path.exists():
        return f"❌ Backup not found: {backup_name}\n\nRun '/backup list' to see available backups."

    manager = _get_backup_manager()

    if manager:
        result = manager.restore_database(str(backup_path), target_db)
        if result.success:
            return f"✅ Database restored from: {backup_path}"
        return f"❌ Restore failed: {result.error}"

    # Stub implementation - manual file copy
    try:
        import shutil

        # Create backup of current before restore
        if os.path.exists(target_db):
            pre_restore = f"{target_db}.pre_restore"
            shutil.copy2(target_db, pre_restore)

        shutil.copy2(backup_path, target_db)
        return f"✅ Database restored from: {backup_path}\n   (Previous DB saved to: {target_db}.pre_restore)"
    except Exception as e:
        return f"❌ Restore failed: {e}"


def export_table(
    table_name: str,
    output_path: str = "",
    db_path: str = STATE_DB,
) -> str:
    """
    Export a database table to JSON.

    Exports all rows from a table to a JSON file for
    backup, analysis, or migration purposes.

    Args:
        table_name: Name of table to export
        output_path: Output JSON file path (auto-generated if empty)
        db_path: Source database path (default: state/user.db)

    Returns:
        Success message with output path, or error message

    Example:
        >>> export_table('voter_ranking_history')
        'Exported 150 rows to: exports/voter_ranking_history_20241215.json'
    """
    manager = _get_backup_manager()

    if manager:
        if not output_path:
            timestamp = get_datetime_now().strftime("%Y%m%d")
            output_path = f"exports/{table_name}_{timestamp}.json"

        result = manager.export_table(db_path, table_name, output_path)
        if result.success:
            return f"✅ Exported {result.row_count} rows to: {output_path}"
        return f"❌ Export failed: {result.error}"

    # Stub implementation using sqlite3
    import json
    import sqlite3

    if not os.path.exists(db_path):
        return f"❌ Database not found: {db_path}"

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cursor.fetchone():
            conn.close()
            # List available tables
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return f"❌ Table not found: {table_name}\n\nAvailable tables: {', '.join(tables)}"

        # Export data
        # Table name is validated above via sqlite_master query
        cursor.execute(f"SELECT * FROM {table_name}")  # noqa: S608  # nosec B608
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Generate output path if not provided
        if not output_path:
            exports_dir = Path("exports")
            exports_dir.mkdir(parents=True, exist_ok=True)
            timestamp = get_datetime_now().strftime("%Y%m%d")
            output_path = str(exports_dir / f"{table_name}_{timestamp}.json")

        # Write JSON
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(rows, f, indent=2, default=str)

        return f"✅ Exported {len(rows)} rows to: {output_path}"
    except Exception as e:
        return f"❌ Export failed: {e}"


def show_backup_info() -> str:
    """
    Show backup system information and status.

    Displays backup configuration, available databases,
    and recent backup activity.

    Returns:
        Formatted backup system information

    Example:
        >>> show_backup_info()
        'Backup System Info
        State DB: state/user.db (2.3 MB)
        Cache DB: .cache/trading_data.db (15.1 MB)
        Backups: 5 files (23.4 MB total)'
    """
    output = "📊 Backup System Info\n"
    output += "=" * 50 + "\n\n"

    # Check databases
    output += "Databases:\n"
    for db_name, db_path in [("State DB", STATE_DB), ("Cache DB", CACHE_DB)]:
        if os.path.exists(db_path):
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            output += f"  {db_name}: {db_path} ({size_mb:.1f} MB)\n"
        else:
            output += f"  {db_name}: {db_path} (not found)\n"

    output += "\n"

    # Check backups
    backup_dir = Path(BACKUP_DIR)
    if backup_dir.exists():
        backups = list(backup_dir.glob("*.db"))
        total_size = sum(b.stat().st_size for b in backups) / (1024 * 1024)
        output += f"Backups Directory: {BACKUP_DIR}\n"
        output += f"  Total Backups: {len(backups)}\n"
        output += f"  Total Size: {total_size:.1f} MB\n"

        if backups:
            newest = max(backups, key=lambda p: p.stat().st_mtime)
            newest_time = datetime.fromtimestamp(newest.stat().st_mtime)
            output += f"  Latest: {newest.name}\n"
            output += f"  Created: {newest_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    else:
        output += "Backups Directory: Not created yet\n"
        output += "  Run '/backup database' to create your first backup\n"

    return output


def cleanup_old_backups(days: int = 30) -> str:
    """
    Clean up backups older than specified days.

    Removes backup files older than the specified number of days
    to free up disk space.

    Args:
        days: Keep backups newer than this many days (default: 30)

    Returns:
        Cleanup result with files removed

    Example:
        >>> cleanup_old_backups(30)
        'Cleanup complete: Removed 3 backups older than 30 days'
    """
    manager = _get_backup_manager()

    if manager:
        result = manager.cleanup_old_backups(days=days)
        if result.success:
            return f"✅ Cleanup complete: Removed {result.files_removed} backup(s) older than {days} days"
        return f"❌ Cleanup failed: {result.error}"

    # Stub implementation
    backup_dir = Path(BACKUP_DIR)

    if not backup_dir.exists():
        return "📂 No backups directory found."

    cutoff = get_datetime_now().timestamp() - (days * 24 * 60 * 60)
    removed = 0

    for backup in backup_dir.glob("*.db"):
        if backup.stat().st_mtime < cutoff:
            try:
                backup.unlink()
                removed += 1
            except Exception:
                pass

    if removed == 0:
        return f"✅ No backups older than {days} days to remove."

    return f"✅ Cleanup complete: Removed {removed} backup(s) older than {days} days"


def get_backup_params() -> Dict[str, Any]:
    """
    Get backup configuration as structured data for agents.

    Provides backup system information in a structured format
    suitable for programmatic consumption.

    Returns:
        Dictionary with backup configuration and status

    Example:
        >>> get_backup_params()
        {'state_db': 'state/user.db', 'backup_count': 5, ...}
    """
    backup_dir = Path(BACKUP_DIR)
    backups: List[Dict[str, Any]] = []

    if backup_dir.exists():
        for backup in backup_dir.glob("*.db"):
            stat = backup.stat()
            backups.append(
                {
                    "name": backup.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    return {
        "state_db": STATE_DB,
        "cache_db": CACHE_DB,
        "backup_dir": BACKUP_DIR,
        "state_db_exists": os.path.exists(STATE_DB),
        "cache_db_exists": os.path.exists(CACHE_DB),
        "backup_count": len(backups),
        "backups": sorted(backups, key=lambda x: x["modified"], reverse=True),
    }


# ============================================================================
# FunctionTool Definitions
# ============================================================================

backup_database_tool = FunctionTool(
    backup_database,
    description=(
        "Create a backup of a database file. Backups are stored with timestamps "
        "in the backups/ directory."
    ),
)

list_backups_tool = FunctionTool(
    list_backups,
    description=("List all available database backups with their dates and sizes."),
)

restore_backup_tool = FunctionTool(
    restore_backup,
    description=(
        "Restore a database from a backup. WARNING: This will overwrite " "the current database."
    ),
)

export_table_tool = FunctionTool(
    export_table,
    description=(
        "Export a database table to JSON for backup or analysis. "
        "Specify table name and optional output path."
    ),
)

show_backup_info_tool = FunctionTool(
    show_backup_info,
    description=(
        "Show backup system information including database sizes, "
        "backup counts, and latest backup details."
    ),
)

cleanup_old_backups_tool = FunctionTool(
    cleanup_old_backups,
    description=(
        "Clean up backups older than specified days to free disk space. " "Default is 30 days."
    ),
)

get_backup_params_tool = FunctionTool(
    get_backup_params,
    description=("Get backup configuration and status as structured data for agents."),
)


# ============================================================================
# Tool Collection for Registry
# ============================================================================

CLI_BACKUP_TOOLS = [
    backup_database_tool,
    list_backups_tool,
    restore_backup_tool,
    export_table_tool,
    show_backup_info_tool,
    cleanup_old_backups_tool,
    get_backup_params_tool,
]

__all__ = [
    # Functions
    "backup_database",
    "list_backups",
    "restore_backup",
    "export_table",
    "show_backup_info",
    "cleanup_old_backups",
    "get_backup_params",
    # Tools
    "backup_database_tool",
    "list_backups_tool",
    "restore_backup_tool",
    "export_table_tool",
    "show_backup_info_tool",
    "cleanup_old_backups_tool",
    "get_backup_params_tool",
    # Collection
    "CLI_BACKUP_TOOLS",
]
