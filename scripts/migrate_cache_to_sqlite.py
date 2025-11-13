#!/usr/bin/env python3
"""
Migrate existing JSON cache files to SQLite.

Handles multiple cache formats:
- UnifiedCacheManager (.cache/market_data/*.json)
- Polygon (.cache/polygon/prices/*.json)
- MarketDataCache (MD5 hashed names)

Usage:
    python scripts/migrate_cache_to_sqlite.py [--dry-run] [--no-backup]
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_sources.cache.sqlite_cache import TradingCacheManager


def migrate_unified_format(json_file: Path, db_manager: TradingCacheManager, dry_run: bool = False) -> dict:
    """
    Migrate UnifiedCacheManager format.

    Format: {metadata: {symbol, start_date, end_date, source, ...}, data: [{date, open, high, ...}]}
    Filename: SYMBOL_START_END_SOURCE.json
    """
    try:
        with open(json_file, 'r') as f:
            cache_data = json.load(f)

        # Extract metadata (handle both nested and flat formats)
        if 'metadata' in cache_data:
            metadata = cache_data['metadata']
            symbol = metadata['symbol']
            source = metadata['source']
            data_records = cache_data['data']
        else:
            # Legacy flat format - parse from filename
            parts = json_file.stem.split('_')
            if len(parts) < 4:
                return {"status": "skipped", "reason": "invalid filename format"}

            symbol = parts[0]
            source = parts[3]
            data_records = cache_data.get('data', [])

        if not data_records:
            return {"status": "skipped", "reason": "empty data"}

        # Convert to DataFrame
        df = pd.DataFrame(data_records)

        # Ensure date column exists
        if 'date' not in df.columns and 'Date' in df.columns:
            df.rename(columns={'Date': 'date'}, inplace=True)

        if 'date' not in df.columns:
            return {"status": "skipped", "reason": "no date column"}

        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # Store in SQLite
        if not dry_run:
            db_manager.set(symbol, df, source)

        return {
            "status": "success",
            "symbol": symbol,
            "source": source,
            "rows": len(df),
            "date_range": f"{df.index.min().date()} to {df.index.max().date()}"
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}


def migrate_polygon_format(json_file: Path, db_manager: TradingCacheManager, dry_run: bool = False) -> dict:
    """
    Migrate Polygon format.

    Format: [{date, open, high, low, close, volume, vwap, transactions}]
    Filename: SYMBOL_START_to_END_day.json
    """
    try:
        with open(json_file, 'r') as f:
            data_records = json.load(f)

        if not isinstance(data_records, list) or not data_records:
            return {"status": "skipped", "reason": "empty or invalid data"}

        # Parse symbol from filename
        # Format: SYMBOL_START_to_END_day.json
        parts = json_file.stem.split('_')
        if len(parts) < 4:
            return {"status": "skipped", "reason": "invalid filename format"}

        symbol = parts[0]
        source = "polygon"

        # Convert to DataFrame
        df = pd.DataFrame(data_records)

        # Ensure date column exists
        if 'date' not in df.columns:
            return {"status": "skipped", "reason": "no date column"}

        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # Store in SQLite
        if not dry_run:
            db_manager.set(symbol, df, source)

        return {
            "status": "success",
            "symbol": symbol,
            "source": source,
            "rows": len(df),
            "date_range": f"{df.index.min().date()} to {df.index.max().date()}"
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}


def backup_cache_files(cache_dir: Path, backup_dir: Path) -> bool:
    """
    Backup existing cache files before migration.

    Args:
        cache_dir: Source cache directory
        backup_dir: Destination backup directory

    Returns:
        True if backup successful
    """
    try:
        if backup_dir.exists():
            print(f"⚠️  Backup directory already exists: {backup_dir}")
            print("   Skipping backup (previous backup preserved)")
            return True

        print(f"\n📦 Backing up cache files...")
        print(f"   Source: {cache_dir}")
        print(f"   Destination: {backup_dir}")

        # Copy entire cache directory
        shutil.copytree(cache_dir, backup_dir)

        # Calculate backup size
        total_size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
        size_mb = total_size / (1024 * 1024)

        print(f"✅ Backup complete: {size_mb:.2f} MB")
        return True

    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False


def migrate_directory(directory: Path, db_manager: TradingCacheManager,
                     format_func, dry_run: bool = False) -> dict:
    """
    Migrate all JSON files in a directory.

    Args:
        directory: Directory containing JSON files
        db_manager: SQLite cache manager
        format_func: Function to handle specific format (migrate_unified_format or migrate_polygon_format)
        dry_run: If True, don't actually migrate data

    Returns:
        Dictionary with migration statistics
    """
    stats = {
        "total_files": 0,
        "success": 0,
        "skipped": 0,
        "errors": 0,
        "total_rows": 0,
        "symbols": set()
    }

    if not directory.exists():
        return stats

    json_files = list(directory.glob("*.json"))
    stats["total_files"] = len(json_files)

    for json_file in json_files:
        result = format_func(json_file, db_manager, dry_run)

        if result["status"] == "success":
            stats["success"] += 1
            stats["total_rows"] += result["rows"]
            stats["symbols"].add(result["symbol"])
            print(f"✅ {json_file.name}: {result['symbol']} ({result['rows']} days, {result['date_range']})")
        elif result["status"] == "skipped":
            stats["skipped"] += 1
            print(f"⏭️  {json_file.name}: {result['reason']}")
        else:
            stats["errors"] += 1
            print(f"❌ {json_file.name}: {result['reason']}")

    return stats


def main():
    """Run migration."""
    parser = argparse.ArgumentParser(description="Migrate JSON cache files to SQLite")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without actually doing it")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup (not recommended)")
    parser.add_argument("--db-path", default=".cache/trading_data.db", help="SQLite database path")
    args = parser.parse_args()

    print("=" * 70)
    print("SQLite Cache Migration Tool")
    print("=" * 70)

    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No data will be migrated")

    # Initialize database manager
    db_manager = TradingCacheManager(db_path=args.db_path)

    # Backup existing cache files (unless disabled or dry-run)
    cache_dir = Path(".cache")
    backup_dir = Path(".cache_backup_json")

    if not args.no_backup and not args.dry_run:
        if not backup_cache_files(cache_dir, backup_dir):
            print("\n⚠️  Backup failed! Aborting migration to prevent data loss.")
            print("   Use --no-backup to skip backup (not recommended)")
            return 1

    # Migrate market_data directory (UnifiedCacheManager format)
    market_dir = cache_dir / "market_data"
    if market_dir.exists():
        print(f"\n📁 Migrating market_data directory...")
        print(f"   Path: {market_dir}")
        market_stats = migrate_directory(market_dir, db_manager, migrate_unified_format, args.dry_run)
        print(f"\n   Summary:")
        print(f"   - Total files: {market_stats['total_files']}")
        print(f"   - Migrated: {market_stats['success']}")
        print(f"   - Skipped: {market_stats['skipped']}")
        print(f"   - Errors: {market_stats['errors']}")
        print(f"   - Total rows: {market_stats['total_rows']}")
        print(f"   - Unique symbols: {len(market_stats['symbols'])}")
    else:
        print(f"\n⏭️  market_data directory not found, skipping...")
        market_stats = {"success": 0, "total_rows": 0, "symbols": set()}

    # Migrate polygon/prices directory
    polygon_dir = cache_dir / "polygon" / "prices"
    if polygon_dir.exists():
        print(f"\n📁 Migrating polygon/prices directory...")
        print(f"   Path: {polygon_dir}")
        polygon_stats = migrate_directory(polygon_dir, db_manager, migrate_polygon_format, args.dry_run)
        print(f"\n   Summary:")
        print(f"   - Total files: {polygon_stats['total_files']}")
        print(f"   - Migrated: {polygon_stats['success']}")
        print(f"   - Skipped: {polygon_stats['skipped']}")
        print(f"   - Errors: {polygon_stats['errors']}")
        print(f"   - Total rows: {polygon_stats['total_rows']}")
        print(f"   - Unique symbols: {len(polygon_stats['symbols'])}")
    else:
        print(f"\n⏭️  polygon/prices directory not found, skipping...")
        polygon_stats = {"success": 0, "total_rows": 0, "symbols": set()}

    # Overall statistics
    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)

    total_files = market_stats.get("total_files", 0) + polygon_stats.get("total_files", 0)
    total_success = market_stats.get("success", 0) + polygon_stats.get("success", 0)
    total_rows = market_stats.get("total_rows", 0) + polygon_stats.get("total_rows", 0)
    all_symbols = market_stats.get("symbols", set()) | polygon_stats.get("symbols", set())

    print(f"\nOverall Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Successfully migrated: {total_success}")
    print(f"  Total rows migrated: {total_rows:,}")
    print(f"  Unique symbols: {len(all_symbols)}")

    if not args.dry_run:
        # Get database stats
        db_stats = db_manager.get_stats()
        print(f"\nSQLite Database:")
        print(f"  Path: {db_stats['db_path']}")
        print(f"  Size: {db_stats['db_size_mb']} MB")
        print(f"  Total entries: {db_stats['total_entries']:,}")
        print(f"  Date range: {db_stats['date_range']['min_date']} to {db_stats['date_range']['max_date']}")
        print(f"\n  By source:")
        for source, count in db_stats['sources'].items():
            print(f"    - {source}: {count:,} days")

        if backup_dir.exists():
            print(f"\nBackup Location:")
            print(f"  {backup_dir}")
            print(f"  ⚠️  Review the migration before deleting backup files!")

    print("\n✅ Migration complete!")

    if args.dry_run:
        print("\n💡 Run without --dry-run to perform actual migration")

    return 0


if __name__ == "__main__":
    sys.exit(main())
