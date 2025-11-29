#!/usr/bin/env python3
"""
Safe cleanup of legacy JSON cache files.

After successful migration to SQLite, this script removes old JSON cache files
while preserving the SQLite database and migration backups.

Usage:
    python scripts/cleanup_legacy_cache.py --dry-run  # Preview only
    python scripts/cleanup_legacy_cache.py            # Actually delete files
    python scripts/cleanup_legacy_cache.py --keep-backup  # Keep original backup
"""

import argparse
import shutil
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_sources.cache import TradingCacheManager


def verify_sqlite_cache():
    """
    Verify SQLite cache exists and has data.

    Returns:
        Tuple of (bool, dict) - (is_valid, stats)
    """
    try:
        cache = TradingCacheManager()
        stats = cache.get_stats()

        if stats["total_entries"] == 0:
            return False, stats

        return True, stats
    except Exception as e:
        print(f"❌ Error accessing SQLite cache: {e}")
        return False, {}


def find_legacy_files(cache_dir=".cache"):
    """
    Find all legacy JSON cache files.

    Returns:
        Dict with categorized files
    """
    cache_path = Path(cache_dir)

    if not cache_path.exists():
        return {"unified_format": [], "md5_format": [], "other_json": [], "total_size_mb": 0}

    files = {
        "unified_format": [],  # market_data_SYMBOL_DATE_DATE_SOURCE.json
        "md5_format": [],  # md5 hashed .json files in market_data/
        "other_json": [],  # Other .json files (might be config, review manually)
        "total_size_mb": 0,
    }

    total_size = 0

    # Find unified format cache files
    for json_file in cache_path.glob("market_data_*.json"):
        size = json_file.stat().st_size
        files["unified_format"].append({"path": json_file, "size": size, "name": json_file.name})
        total_size += size

    # Find MD5 format cache files
    md5_dir = cache_path / "market_data"
    if md5_dir.exists():
        for json_file in md5_dir.glob("*.json"):
            size = json_file.stat().st_size
            files["md5_format"].append({"path": json_file, "size": size, "name": json_file.name})
            total_size += size

    # Find other JSON files (excluding important ones)
    exclude_names = ["trading_data.db", "trading_data.db-journal"]
    for json_file in cache_path.glob("*.json"):
        if json_file.name not in exclude_names:
            # Check if it's not already in unified_format
            if json_file not in [f["path"] for f in files["unified_format"]]:
                size = json_file.stat().st_size
                files["other_json"].append(
                    {"path": json_file, "size": size, "name": json_file.name}
                )
                total_size += size

    files["total_size_mb"] = total_size / (1024 * 1024)

    return files


def print_file_summary(files):
    """Print summary of files to be cleaned."""
    print("\n" + "=" * 70)
    print("LEGACY CACHE FILES FOUND")
    print("=" * 70)

    if files["unified_format"]:
        print(f"\n📁 Unified Format Cache ({len(files['unified_format'])} files):")
        print("   Format: market_data_SYMBOL_START_END_SOURCE.json")
        for f in files["unified_format"][:5]:  # Show first 5
            print(f"   - {f['name']} ({f['size'] / 1024:.1f} KB)")
        if len(files["unified_format"]) > 5:
            print(f"   ... and {len(files['unified_format']) - 5} more")

    if files["md5_format"]:
        print(f"\n📁 MD5 Format Cache ({len(files['md5_format'])} files):")
        print("   Location: .cache/market_data/*.json")
        for f in files["md5_format"][:5]:
            print(f"   - {f['name']} ({f['size'] / 1024:.1f} KB)")
        if len(files["md5_format"]) > 5:
            print(f"   ... and {len(files['md5_format']) - 5} more")

    if files["other_json"]:
        print(f"\n⚠️  Other JSON Files ({len(files['other_json'])} files):")
        print("   These will NOT be deleted automatically (review manually):")
        for f in files["other_json"]:
            print(f"   - {f['name']} ({f['size'] / 1024:.1f} KB)")

    print(f"\n💾 Total size to clean: {files['total_size_mb']:.2f} MB")

    # Calculate deletable count
    deletable = len(files["unified_format"]) + len(files["md5_format"])
    print(f"📦 Files to delete: {deletable}")

    print()


def delete_legacy_files(files, dry_run=False, create_backup=True):
    """
    Delete legacy cache files.

    Args:
        files: Dict of file categories
        dry_run: If True, don't actually delete
        create_backup: If True, create backup before deletion
    """
    if dry_run:
        print("\n🔍 DRY RUN MODE - No files will be deleted")
        return

    # Create backup if requested
    if create_backup:
        backup_dir = Path(".cache") / f"cleanup_backup_{Path.cwd().name}"
        if backup_dir.exists():
            print(f"\n⚠️  Backup directory already exists: {backup_dir}")
            response = input("   Overwrite? (y/N): ")
            if not response.lower().startswith("y"):
                print("   Aborted")
                return

        backup_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n💾 Creating backup in {backup_dir}")

        # Copy files to backup
        for category in ["unified_format", "md5_format"]:
            for file_info in files[category]:
                src = file_info["path"]
                dst = backup_dir / src.name
                shutil.copy2(src, dst)

        print(f"✅ Backup created: {backup_dir}")

    # Delete unified format files
    deleted_count = 0
    deleted_size = 0

    print("\n🗑️  Deleting unified format cache files...")
    for file_info in files["unified_format"]:
        try:
            file_path = file_info["path"]
            file_path.unlink()
            deleted_count += 1
            deleted_size += file_info["size"]
            if deleted_count <= 5:  # Show first 5
                print(f"   ✓ Deleted: {file_info['name']}")
        except Exception as e:
            print(f"   ✗ Failed to delete {file_info['name']}: {e}")

    if len(files["unified_format"]) > 5:
        print(f"   ... deleted {len(files['unified_format']) - 5} more files")

    # Delete MD5 format files and directory
    print("\n🗑️  Deleting MD5 format cache files...")
    for file_info in files["md5_format"]:
        try:
            file_path = file_info["path"]
            file_path.unlink()
            deleted_count += 1
            deleted_size += file_info["size"]
            if deleted_count - len(files["unified_format"]) <= 5:
                print(f"   ✓ Deleted: {file_info['name']}")
        except Exception as e:
            print(f"   ✗ Failed to delete {file_info['name']}: {e}")

    # Remove market_data directory if empty
    md5_dir = Path(".cache") / "market_data"
    if md5_dir.exists() and not any(md5_dir.iterdir()):
        md5_dir.rmdir()
        print(f"   ✓ Removed empty directory: {md5_dir}")

    print("\n✅ Cleanup complete!")
    print(f"   Deleted: {deleted_count} files")
    print(f"   Reclaimed: {deleted_size / (1024 * 1024):.2f} MB")


def main():
    """Main cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean up legacy JSON cache files after SQLite migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what will be deleted
  %(prog)s --dry-run

  # Delete files (creates backup by default)
  %(prog)s

  # Delete files without creating backup
  %(prog)s --no-backup
        """,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Preview files to delete without actually deleting"
    )

    parser.add_argument(
        "--no-backup", action="store_true", help="Skip creating backup before deletion"
    )

    parser.add_argument("--cache-dir", default=".cache", help="Cache directory (default: .cache)")

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("LEGACY CACHE CLEANUP")
    print("=" * 70)

    # Step 1: Verify SQLite cache exists and has data
    print("\n🔍 Verifying SQLite cache...")
    valid, stats = verify_sqlite_cache()

    if not valid:
        print("\n❌ ERROR: SQLite cache is empty or inaccessible!")
        print("   Cannot safely delete legacy files without verified SQLite cache.")
        print("   Run the migration script first:")
        print("   python scripts/migrate_cache_to_sqlite.py")
        return 1

    print("✅ SQLite cache verified:")
    print(f"   Database: .cache/trading_data.db ({stats['db_size_mb']} MB)")
    print(f"   Entries: {stats['total_entries']:,}")
    print(f"   Symbols: {stats['unique_symbols']}")

    # Step 2: Find legacy files
    print("\n🔍 Scanning for legacy cache files...")
    files = find_legacy_files(args.cache_dir)

    if not files["unified_format"] and not files["md5_format"]:
        print("\n✅ No legacy cache files found - cleanup not needed!")
        return 0

    # Step 3: Show summary
    print_file_summary(files)

    # Step 4: Confirm deletion (unless dry-run)
    if not args.dry_run:
        print("\n⚠️  WARNING: This will delete legacy cache files!")
        print("   Your data is safe in SQLite (.cache/trading_data.db)")

        if not args.no_backup:
            print("   A backup will be created before deletion")

        response = input("\n   Continue? (y/N): ")
        if not response.lower().startswith("y"):
            print("\n   Aborted - no files deleted")
            return 0

    # Step 5: Delete files
    delete_legacy_files(files, dry_run=args.dry_run, create_backup=not args.no_backup)

    if args.dry_run:
        print("\n💡 To actually delete files, run without --dry-run:")
        print("   python scripts/cleanup_legacy_cache.py")

    # Step 6: Show what remains
    print("\n" + "=" * 70)
    print("AFTER CLEANUP")
    print("=" * 70)
    print("\n✅ Preserved files:")
    print("   - .cache/trading_data.db (SQLite cache)")
    print("   - .cache/backup_*/ (migration backups)")
    if not args.no_backup and not args.dry_run:
        print("   - .cache/cleanup_backup_*/ (cleanup backup)")

    if files["other_json"]:
        print("\n⚠️  Manual review needed:")
        print(f"   {len(files['other_json'])} other JSON files were not deleted")
        print("   Review these manually to determine if they can be removed")

    print("\n🎉 Legacy cache cleanup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
