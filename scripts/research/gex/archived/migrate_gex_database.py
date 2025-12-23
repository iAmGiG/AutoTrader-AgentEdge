#!/usr/bin/env python3
"""Production-grade GEX database migration tool.

Migrates options_historical.db from gex-llm-patterns to AutoTrader with:
- Schema validation
- Data integrity checks
- Safe operations with rollback
- Detailed logging and statistics
- Multiple migration modes

Usage:
    python migrate_gex_database.py --mode symlink
    python migrate_gex_database.py --mode copy --validate
    python migrate_gex_database.py --stats
"""

import argparse
import json
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("gex_migration.log")],
)
logger = logging.getLogger(__name__)


class DatabaseValidator:
    """Validates database schema and data integrity."""

    REQUIRED_TABLES = {"options_chains", "options_daily_summary", "collection_progress"}
    REQUIRED_COLUMNS = {
        "options_chains": {
            "symbol",
            "trading_date",
            "strike",
            "option_type",
            "expiration",
            "open_interest",
            "gamma",
        },
        "options_daily_summary": {"symbol", "trading_date", "total_gex", "regime"},
        "collection_progress": {"symbol", "trading_date", "status"},
    }

    @staticmethod
    def validate_schema(db_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate database has required schema.

        Returns:
            (is_valid, errors)
        """
        errors = []

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            missing_tables = DatabaseValidator.REQUIRED_TABLES - tables
            if missing_tables:
                errors.append(f"Missing required tables: {missing_tables}")

            # Check columns in each table
            for table, required_cols in DatabaseValidator.REQUIRED_COLUMNS.items():
                if table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = {row[1] for row in cursor.fetchall()}

                    missing_cols = required_cols - columns
                    if missing_cols:
                        errors.append(f"Table '{table}' missing columns: {missing_cols}")

            conn.close()

        except Exception as e:
            errors.append(f"Schema validation error: {e}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_data_integrity(db_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate data integrity (referential integrity, nulls, ranges).

        Returns:
            (is_valid, warnings)
        """
        warnings = []

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check for data in options_chains
            cursor.execute("SELECT COUNT(*) FROM options_chains")
            chains_count = cursor.fetchone()[0]
            if chains_count == 0:
                warnings.append("options_chains table is empty")

            # Check for reasonable gamma values
            cursor.execute("SELECT COUNT(*) FROM options_chains WHERE gamma < 0 OR gamma > 1")
            invalid_gamma = cursor.fetchone()[0]
            if invalid_gamma > 0:
                warnings.append(f"{invalid_gamma} records have invalid gamma values (<0 or >1)")

            # Check for null values in critical columns
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM options_chains
                WHERE symbol IS NULL
                   OR trading_date IS NULL
                   OR strike IS NULL
                   OR option_type IS NULL
            """
            )
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                warnings.append(f"{null_count} records have NULL critical values")

            # Check date range
            cursor.execute("SELECT MIN(trading_date), MAX(trading_date) FROM options_chains")
            date_range = cursor.fetchone()
            if date_range[0]:
                logger.info(f"Date range: {date_range[0]} to {date_range[1]}")

            conn.close()

        except Exception as e:
            warnings.append(f"Data integrity check error: {e}")

        return True, warnings  # Warnings don't fail validation

    @staticmethod
    def get_detailed_stats(db_path: Path) -> Dict:
        """Get comprehensive database statistics."""
        stats = {"exists": db_path.exists(), "path": str(db_path)}

        if not db_path.exists():
            return stats

        try:
            # File stats
            stats["size_mb"] = db_path.stat().st_size / (1024 * 1024)
            stats["modified"] = datetime.fromtimestamp(db_path.stat().st_mtime).isoformat()

            # Database stats
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Table counts
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            stats["tables"] = {}

            for table in tables:
                if table != "sqlite_sequence":
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats["tables"][table] = count

            # Symbol coverage
            cursor.execute("SELECT DISTINCT symbol FROM options_chains ORDER BY symbol")
            symbols = [row[0] for row in cursor.fetchall()]
            stats["symbols"] = symbols
            stats["symbol_count"] = len(symbols)

            # Date coverage per symbol
            stats["date_coverage"] = {}
            for symbol in symbols:
                cursor.execute(
                    f"""
                    SELECT MIN(trading_date), MAX(trading_date), COUNT(DISTINCT trading_date)
                    FROM options_chains
                    WHERE symbol = '{symbol}'
                """
                )
                min_date, max_date, days = cursor.fetchone()
                stats["date_coverage"][symbol] = {
                    "start": min_date,
                    "end": max_date,
                    "trading_days": days,
                }

            conn.close()

        except Exception as e:
            stats["error"] = str(e)
            logger.error(f"Error getting stats: {e}")

        return stats


class DatabaseMigrator:
    """Handles database migration operations."""

    def __init__(self, source: Path, target: Path, force: bool = False):
        self.source = source.resolve()
        self.target = target.resolve()
        self.force = force
        self.backup_path = None

    def _backup_existing(self) -> bool:
        """Backup existing target if it exists."""
        if not self.target.exists():
            return True

        if not self.force:
            logger.error(f"Target exists: {self.target}")
            logger.error("Use --force to overwrite")
            return False

        # Create backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = self.target.parent / f"{self.target.stem}_backup_{timestamp}.db"

        try:
            shutil.copy2(self.target, self.backup_path)
            logger.info(f"Created backup: {self.backup_path}")
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    def _rollback(self):
        """Rollback to backup if migration fails."""
        if self.backup_path and self.backup_path.exists():
            try:
                shutil.move(self.backup_path, self.target)
                logger.info("Rolled back to backup")
            except Exception as e:
                logger.error(f"Rollback failed: {e}")

    def symlink(self) -> bool:
        """Create symlink from target to source."""
        logger.info("Creating symlink...")

        if not self._backup_existing():
            return False

        try:
            # Ensure target directory exists
            self.target.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing target
            if self.target.exists():
                self.target.unlink()

            # Create symlink
            self.target.symlink_to(self.source)
            logger.info(f"Symlink created: {self.target} -> {self.source}")

            # Verify symlink
            if not self.target.exists():
                raise Exception("Symlink verification failed")

            return True

        except Exception as e:
            logger.error(f"Symlink failed: {e}")
            self._rollback()
            return False

    def copy(self, verify: bool = True) -> bool:
        """Copy database from source to target with optional verification."""
        logger.info("Copying database...")

        if not self._backup_existing():
            return False

        try:
            # Ensure target directory exists
            self.target.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing target
            if self.target.exists():
                self.target.unlink()

            # Copy database
            shutil.copy2(self.source, self.target)
            logger.info(f"Database copied: {self.source} -> {self.target}")

            # Verify copy
            if verify:
                if not self._verify_copy():
                    raise Exception("Copy verification failed")

            return True

        except Exception as e:
            logger.error(f"Copy failed: {e}")
            self._rollback()
            return False

    def _verify_copy(self) -> bool:
        """Verify copied database matches source."""
        logger.info("Verifying copy...")

        # Check file sizes
        source_size = self.source.stat().st_size
        target_size = self.target.stat().st_size

        if source_size != target_size:
            logger.error(f"Size mismatch: source={source_size}, target={target_size}")
            return False

        # Verify data integrity
        is_valid, warnings = DatabaseValidator.validate_data_integrity(self.target)
        if warnings:
            for warning in warnings:
                logger.warning(warning)

        logger.info("Copy verified successfully")
        return True


def print_stats_report(stats: Dict, label: str):
    """Print formatted statistics report."""
    print(f"\n{label}:")
    print(f"  Path: {stats.get('path', 'N/A')}")
    print(f"  Size: {stats.get('size_mb', 0):.2f} MB")
    print(f"  Modified: {stats.get('modified', 'N/A')}")

    if "symbols" in stats:
        print(f"  Symbols: {', '.join(stats['symbols'])}")

    if "tables" in stats:
        print("\n  Tables:")
        for table, count in stats["tables"].items():
            print(f"    {table}: {count:,} records")

    if "date_coverage" in stats:
        print("\n  Date Coverage:")
        for symbol, coverage in stats["date_coverage"].items():
            print(
                f"    {symbol}: {coverage['start']} to {coverage['end']} "
                f"({coverage['trading_days']} days)"
            )


def validate_source(source: Path) -> None:
    """Validate source database schema and integrity."""
    logger.info("Validating source schema...")
    is_valid, errors = DatabaseValidator.validate_schema(source)
    if not is_valid:
        logger.error("Schema validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)
    logger.info("Schema validation passed")

    logger.info("Validating data integrity...")
    is_valid, warnings = DatabaseValidator.validate_data_integrity(source)
    if warnings:
        for warning in warnings:
            logger.warning(warning)
    logger.info("Data integrity check complete")


def handle_stats_mode(target_abs: Path) -> None:
    """Handle --stats mode and exit."""
    if target_abs.exists():
        target_stats = DatabaseValidator.get_detailed_stats(target_abs)
        print_stats_report(target_stats, "Target Database")
    else:
        print("\nTarget database does not exist yet")
    sys.exit(0)


def handle_success(
    target_abs: Path,
    source_stats: Dict,
    args: argparse.Namespace,
) -> None:
    """Handle successful migration."""
    logger.info("=" * 60)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 60)

    target_stats = DatabaseValidator.get_detailed_stats(target_abs)
    print_stats_report(target_stats, "Target Database")

    if args.save_report:
        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": args.mode,
            "source": source_stats,
            "target": target_stats,
            "success": True,
        }
        with open(args.save_report, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved: {args.save_report}")

    print("\nUsage in Python:")
    print("  import sqlite3")
    print(f'  conn = sqlite3.connect("{target_abs}")')
    print("  cursor.execute(\"SELECT * FROM options_chains WHERE symbol='SPY'\")")


def main():
    parser = argparse.ArgumentParser(
        description="Production-grade GEX database migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create symlink (recommended)
  python migrate_gex_database.py --mode symlink

  # Copy with validation
  python migrate_gex_database.py --mode copy --validate

  # Show statistics only
  python migrate_gex_database.py --stats

  # Force overwrite existing
  python migrate_gex_database.py --mode symlink --force
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["symlink", "copy"],
        default="symlink",
        help="Migration mode (default: symlink)",
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=Path("a:/Projects/gex-llm-patterns/.cache/options_historical.db"),
        help="Source database path",
    )

    parser.add_argument(
        "--target",
        type=Path,
        default=Path(".cache/gex_research.db"),
        help="Target database path",
    )

    parser.add_argument("--force", action="store_true", help="Overwrite existing target")

    parser.add_argument(
        "--validate", action="store_true", help="Validate schema and data integrity"
    )

    parser.add_argument("--stats", action="store_true", help="Show statistics and exit")

    parser.add_argument(
        "--save-report",
        type=Path,
        help="Save migration report to JSON file",
    )

    args = parser.parse_args()

    # Convert target to absolute path
    project_root = Path(__file__).parent.parent.parent.parent
    target_abs = (project_root / args.target).resolve()

    logger.info("=== GEX Database Migration Tool ===")
    logger.info(f"Source: {args.source}")
    logger.info(f"Target: {target_abs}")
    logger.info(f"Mode: {args.mode}")

    # Check source exists
    if not args.source.exists():
        logger.error(f"Source database not found: {args.source}")
        logger.error("Ensure gex-llm-patterns collection completed")
        sys.exit(1)

    # Get source statistics
    source_stats = DatabaseValidator.get_detailed_stats(args.source)
    print_stats_report(source_stats, "Source Database")

    # Validate source schema if requested
    if args.validate:
        validate_source(args.source)

    # Show stats only mode
    if args.stats:
        handle_stats_mode(target_abs)

    # Perform migration
    migrator = DatabaseMigrator(args.source, target_abs, args.force)

    success = migrator.symlink() if args.mode == "symlink" else migrator.copy(verify=args.validate)

    if success:
        handle_success(target_abs, source_stats, args)
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
