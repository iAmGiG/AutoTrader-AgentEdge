#!/usr/bin/env python3
"""
Cache Management CLI Tool

Provides administrative commands for managing the SQLite cache:
- View statistics
- Cleanup expired entries
- Vacuum database
- Export data
- Clear cache

Usage:
    python scripts/cache_manager.py stats
    python scripts/cache_manager.py cleanup
    python scripts/cache_manager.py vacuum
    python scripts/cache_manager.py symbols
    python scripts/cache_manager.py export SPY --start 2025-01-01 --end 2025-12-31
    python scripts/cache_manager.py clear --confirm
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_sources.cache import TradingCacheManager


def cmd_stats(args):
    """Show cache statistics."""
    cache = TradingCacheManager(db_path=args.db_path)
    stats = cache.get_stats()

    print("\n" + "=" * 70)
    print("CACHE STATISTICS")
    print("=" * 70)

    print("\n📊 Database Info:")
    print(f"   Path: {stats['db_path']}")
    print(f"   Size: {stats['db_size_mb']} MB")

    print("\n📈 Data Summary:")
    print(f"   Total entries: {stats['total_entries']:,}")
    print(f"   Unique symbols: {stats['unique_symbols']}")

    if stats["date_range"]:
        print(
            f"   Date range: {stats['date_range']['min_date']} to {stats['date_range']['max_date']}"
        )

    print("\n📦 By Source:")
    for source, count in stats["sources"].items():
        pct = (count / stats["total_entries"] * 100) if stats["total_entries"] > 0 else 0
        print(f"   {source:20} {count:6,} days ({pct:5.1f}%)")

    print("\n🏷️  By Asset Type:")
    for asset_type, count in stats["asset_types"].items():
        pct = (count / stats["total_entries"] * 100) if stats["total_entries"] > 0 else 0
        print(f"   {asset_type:20} {count:6,} days ({pct:5.1f}%)")

    print("\n⏰ Expiration:")
    print(f"   Expired entries: {stats['expired_entries']:,}")

    print()


def cmd_cleanup(args):
    """Clean up expired cache entries."""
    cache = TradingCacheManager(db_path=args.db_path)

    print("\n🧹 Cleaning up expired cache entries...")
    deleted = cache.cleanup_expired()

    if deleted > 0:
        print(f"✅ Deleted {deleted:,} expired entries")
    else:
        print("✅ No expired entries found")

    if args.vacuum:
        print("\n🗜️  Vacuuming database to reclaim space...")
        cache.vacuum()
        print("✅ Database optimized")


def cmd_vacuum(args):
    """Optimize database (reclaim space after deletions)."""
    cache = TradingCacheManager(db_path=args.db_path)

    print("\n🗜️  Vacuuming database...")
    cache.vacuum()

    # Show before/after stats
    stats = cache.get_stats()
    print("✅ Database optimized")
    print(f"   Current size: {stats['db_size_mb']} MB")


def cmd_symbols(args):
    """List all cached symbols."""
    cache = TradingCacheManager(db_path=args.db_path)

    symbols = cache.get_symbols(asset_type=args.asset_type)

    print(f"\n📋 Cached Symbols ({args.asset_type}):")
    print(f"   Total: {len(symbols)}")
    print()

    # Print in columns
    cols = 5
    for i in range(0, len(symbols), cols):
        row = symbols[i : i + cols]
        print("   " + "  ".join(f"{s:8}" for s in row))

    print()


def cmd_export(args):
    """Export cache data to JSON."""
    cache = TradingCacheManager(db_path=args.db_path)

    print(f"\n📤 Exporting {args.symbol} data...")
    df = cache.get(
        args.symbol, args.start, args.end, source=args.source, asset_type=args.asset_type
    )

    if df is None or df.empty:
        print(f"❌ No data found for {args.symbol}")
        return

    output_file = args.output or f"{args.symbol}_{args.start}_{args.end}.json"

    # Convert to JSON-serializable format
    export_data = {
        "symbol": args.symbol,
        "start_date": args.start,
        "end_date": args.end,
        "source": args.source or "any",
        "asset_type": args.asset_type,
        "data": df.reset_index().to_dict("records"),
    }

    with open(output_file, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"✅ Exported {len(df)} days to {output_file}")


def cmd_clear(args):
    """Clear all or specific cache data."""
    cache = TradingCacheManager(db_path=args.db_path)

    if args.symbol:
        # Clear specific symbol
        print(f"\n🗑️  Clearing cache for {args.symbol}...")
        if not args.confirm:
            response = input(f"   Delete all {args.symbol} data? (y/N): ")
            if not response.lower().startswith("y"):
                print("   Cancelled")
                return

        deleted = cache.delete(
            args.symbol, args.start, args.end, source=args.source, asset_type=args.asset_type
        )
        print(f"✅ Deleted {deleted} entries for {args.symbol}")

    else:
        # Clear all cache
        print("\n⚠️  WARNING: This will delete ALL cache data!")
        print(f"   Database: {args.db_path}")

        if not args.confirm:
            response = input("   Continue? (y/N): ")
            if not response.lower().startswith("y"):
                print("   Cancelled")
                return

        stats = cache.get_stats()
        total = stats["total_entries"]

        # Delete all entries
        import sqlite3

        with sqlite3.connect(args.db_path) as conn:
            conn.execute("DELETE FROM market_cache")
            conn.commit()

        print(f"✅ Deleted all {total:,} cache entries")

        if args.vacuum:
            print("\n🗜️  Vacuuming database...")
            cache.vacuum()
            print("✅ Database optimized")


def cmd_query(args):
    """Query cache data (advanced)."""
    cache = TradingCacheManager(db_path=args.db_path)

    print("\n🔍 Querying cache...")
    print(f"   Symbol: {args.symbol}")
    print(f"   Date range: {args.start} to {args.end}")
    print(f"   Source: {args.source or 'any'}")

    df = cache.get(
        args.symbol, args.start, args.end, source=args.source, asset_type=args.asset_type
    )

    if df is None or df.empty:
        print("\n❌ No data found")
        return

    print(f"\n✅ Found {len(df)} days")
    print("\nFirst 5 rows:")
    print(df.head().to_string())

    print("\nLast 5 rows:")
    print(df.tail().to_string())

    print("\nSummary statistics:")
    print(df.describe().to_string())


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SQLite Cache Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View cache statistics
  %(prog)s stats

  # Cleanup expired entries
  %(prog)s cleanup

  # Optimize database
  %(prog)s vacuum

  # List all symbols
  %(prog)s symbols

  # Export SPY data to JSON
  %(prog)s export SPY --start 2025-01-01 --end 2025-12-31

  # Clear specific symbol
  %(prog)s clear --symbol SPY --confirm

  # Query cache data
  %(prog)s query SPY --start 2025-10-01 --end 2025-10-31
        """,
    )

    parser.add_argument(
        "--db-path",
        default=".cache/trading_data.db",
        help="Path to SQLite database (default: .cache/trading_data.db)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # stats command
    subparsers.add_parser("stats", help="Show cache statistics")

    # cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Remove expired cache entries")
    cleanup_parser.add_argument(
        "--vacuum", action="store_true", help="Vacuum database after cleanup"
    )

    # vacuum command
    subparsers.add_parser("vacuum", help="Optimize database (reclaim space)")

    # symbols command
    symbols_parser = subparsers.add_parser("symbols", help="List all cached symbols")
    symbols_parser.add_argument(
        "--asset-type", default="stock", help="Asset type filter (default: stock)"
    )

    # export command
    export_parser = subparsers.add_parser("export", help="Export cache data to JSON")
    export_parser.add_argument("symbol", help="Symbol to export")
    export_parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    export_parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    export_parser.add_argument("--source", help="Source filter (optional)")
    export_parser.add_argument("--asset-type", default="stock", help="Asset type (default: stock)")
    export_parser.add_argument("--output", help="Output file (default: SYMBOL_START_END.json)")

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear cache data")
    clear_parser.add_argument("--symbol", help="Symbol to clear (if not specified, clears all)")
    clear_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    clear_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    clear_parser.add_argument("--source", help="Source filter (optional)")
    clear_parser.add_argument("--asset-type", default="stock", help="Asset type (default: stock)")
    clear_parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")
    clear_parser.add_argument("--vacuum", action="store_true", help="Vacuum database after clear")

    # query command
    query_parser = subparsers.add_parser("query", help="Query cache data")
    query_parser.add_argument("symbol", help="Symbol to query")
    query_parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    query_parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    query_parser.add_argument("--source", help="Source filter (optional)")
    query_parser.add_argument("--asset-type", default="stock", help="Asset type (default: stock)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    commands = {
        "stats": cmd_stats,
        "cleanup": cmd_cleanup,
        "vacuum": cmd_vacuum,
        "symbols": cmd_symbols,
        "export": cmd_export,
        "clear": cmd_clear,
        "query": cmd_query,
    }

    try:
        commands[args.command](args)
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
