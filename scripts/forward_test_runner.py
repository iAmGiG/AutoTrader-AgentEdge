"""
Forward Test Runner - Main script for running 30-day forward tests.

Issue #324: Forward Testing Protocol
Standalone script that runs forward testing validation over 30 days.

Usage:
    python scripts/forward_test_runner.py --test-name my_test_2025 --capital 10000

This is NOT a CLI command - it's a background validation tool for maintainers.
For interactive backtesting from CLI, see separate issue (TBD).
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.forward_test_manager import ForwardTestManager
from src.trading.performance_validator import PerformanceValidator
from src.trading.test_reporter import TestReporter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for forward test runner."""
    parser = argparse.ArgumentParser(description="Run 30-day forward testing validation")
    parser.add_argument("--test-name", required=True, help="Unique name for this test run")
    parser.add_argument(
        "--capital", type=float, default=10000.0, help="Initial capital (default: $10,000)"
    )
    parser.add_argument(
        "--report-type",
        choices=["daily", "weekly", "final"],
        default="daily",
        help="Type of report to generate",
    )
    parser.add_argument("--week", type=int, help="Week number for weekly report (1-4)")
    parser.add_argument(
        "--benchmark-return", type=float, help="Benchmark return for final report comparison"
    )

    args = parser.parse_args()

    # Initialize components
    test_manager = ForwardTestManager(args.test_name)
    validator = PerformanceValidator(initial_capital=args.capital)
    reporter = TestReporter()

    # If this is a new test, start it
    if not test_manager.start_date:
        test_manager.start_test(initial_capital=args.capital)
        logger.info(f"Started new forward test: {args.test_name}")

    # Generate requested report
    if args.report_type == "daily":
        report = reporter.generate_daily_summary(test_manager, validator)
        print("\n" + report)

    elif args.report_type == "weekly":
        if not args.week:
            logger.error("--week required for weekly report")
            sys.exit(1)
        report = reporter.generate_weekly_report(test_manager, validator, args.week)
        print("\n" + report)

    elif args.report_type == "final":
        report = reporter.generate_final_report(
            test_manager, validator, benchmark_return=args.benchmark_return
        )
        print("\n" + report)

    logger.info("Forward test report generated successfully")


if __name__ == "__main__":
    main()
