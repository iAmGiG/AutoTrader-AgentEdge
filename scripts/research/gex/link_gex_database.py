#!/usr/bin/env python3
"""Link or copy GEX research database from gex-llm-patterns project.

This script connects AutoTrader to the options_historical.db created by
the gex-llm-patterns data collection process.

Options:
1. Symlink (recommended) - No duplication, always in sync
2. Copy - Independent copy for safety
"""

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path


def get_database_stats(db_path: Path) -> dict:
    """Get statistics about the database."""
    if not db_path.exists():
        return {"exists": False}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get table counts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    stats = {"exists": True, "tables": {}}

    for table in tables:
        if table != "sqlite_sequence":
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats["tables"][table] = count

    # Get file size
    stats["size_mb"] = db_path.stat().st_size / (1024 * 1024)

    conn.close()
    return stats


def create_symlink(source: Path, target: Path, force: bool = False):
    """Create symlink from source to target."""
    if target.exists():
        if force:
            target.unlink()
            print(f"Removed existing: {target}")
        else:
            print(f"ERROR: Target already exists: {target}")
            print("Use --force to overwrite")
            return False

    # Ensure target directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    # Create symlink (use absolute path for safety)
    source_abs = source.resolve()
    target.symlink_to(source_abs)
    print(f"Created symlink: {target} -> {source_abs}")
    return True


def copy_database(source: Path, target: Path, force: bool = False):
    """Copy database from source to target."""
    if target.exists():
        if force:
            target.unlink()
            print(f"Removed existing: {target}")
        else:
            print(f"ERROR: Target already exists: {target}")
            print("Use --force to overwrite")
            return False

    # Ensure target directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    # Copy database
    shutil.copy2(source, target)
    print(f"Copied database: {source} -> {target}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Link GEX research database from gex-llm-patterns")

    parser.add_argument(
        "--mode",
        choices=["symlink", "copy"],
        default="symlink",
        help="How to connect the database (default: symlink)",
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=Path("a:/Projects/gex-llm-patterns/.cache/options_historical.db"),
        help="Source database path (gex-llm-patterns)",
    )

    parser.add_argument(
        "--target",
        type=Path,
        default=Path(".cache/gex_research.db"),
        help="Target database path (AutoTrader)",
    )

    parser.add_argument("--force", action="store_true", help="Overwrite existing target")

    parser.add_argument("--stats", action="store_true", help="Show database statistics and exit")

    args = parser.parse_args()

    # Convert target to absolute path relative to project root
    project_root = Path(__file__).parent.parent.parent.parent
    target_abs = project_root / args.target

    print("=== GEX Database Linking Tool ===")
    print()
    print(f"Source: {args.source}")
    print(f"Target: {target_abs}")
    print(f"Mode: {args.mode}")
    print()

    # Check source exists
    if not args.source.exists():
        print(f"ERROR: Source database not found: {args.source}")
        print()
        print("Make sure gex-llm-patterns data collection has completed.")
        sys.exit(1)

    # Show source stats
    source_stats = get_database_stats(args.source)
    print("Source Database Stats:")
    print(f"  Size: {source_stats.get('size_mb', 0):.2f} MB")
    for table, count in source_stats.get("tables", {}).items():
        print(f"  {table}: {count:,} records")
    print()

    # If just showing stats, exit
    if args.stats:
        if target_abs.exists():
            target_stats = get_database_stats(target_abs)
            print("Target Database Stats:")
            print(f"  Size: {target_stats.get('size_mb', 0):.2f} MB")
            for table, count in target_stats.get("tables", {}).items():
                print(f"  {table}: {count:,} records")
        else:
            print("Target database does not exist yet.")
        sys.exit(0)

    # Perform operation
    if args.mode == "symlink":
        success = create_symlink(args.source, target_abs, args.force)
    else:
        success = copy_database(args.source, target_abs, args.force)

    if success:
        print()
        print("SUCCESS! GEX research database is now accessible in AutoTrader")
        print()
        print("Usage in Python:")
        print("  import sqlite3")
        print(f'  conn = sqlite3.connect("{target_abs}")')
        print("  cursor.execute(\"SELECT * FROM options_chains WHERE symbol='SPY'\")")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
