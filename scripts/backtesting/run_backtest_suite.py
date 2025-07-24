#!/usr/bin/env python3
"""
Unified Backtesting Suite for RH2MAS

This script consolidates all backtesting functionality into a single, 
configurable tool. It supports:
- Configuration-based test definitions
- Multiple test suites (quick, comprehensive, extended)
- Parallel execution
- Progress tracking
- Automatic result aggregation
- Resume capability for interrupted runs

Usage:
    python run_backtest_suite.py [suite_name] [options]

Examples:
    python run_backtest_suite.py quick
    python run_backtest_suite.py comprehensive --parallel
    python run_backtest_suite.py extended --symbols AAPL,MSFT
    python run_backtest_suite.py --config custom_tests.yaml
    python run_backtest_suite.py --resume
"""

import sys
import os
import yaml
import json
import argparse
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import signal
import pickle

# Add src to Python path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../..')))


class BacktestRunner:
    """Manages backtest execution with configuration support."""

    def __init__(self, config_file: str = "backtest_configs.yaml"):
        self.config_file = config_file
        self.config = self._load_config()
        self.results_dir = Path(self.config['defaults']['output_dir'])
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.results_dir / ".backtest_state.pkl"
        self.completed_tests = set()
        self.failed_tests = {}

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        config_path = Path(__file__).parent / self.config_file
        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _save_state(self):
        """Save current execution state for resume capability."""
        state = {
            'completed_tests': self.completed_tests,
            'failed_tests': self.failed_tests,
            'timestamp': datetime.now().isoformat()
        }
        with open(self.state_file, 'wb') as f:
            pickle.dump(state, f)

    def _load_state(self) -> bool:
        """Load previous execution state if available."""
        if not self.state_file.exists():
            return False

        try:
            with open(self.state_file, 'rb') as f:
                state = pickle.load(f)
            self.completed_tests = state.get('completed_tests', set())
            self.failed_tests = state.get('failed_tests', {})
            print(f"Resuming from previous run: {len(self.completed_tests)} completed, "
                  f"{len(self.failed_tests)} failed")
            return True
        except Exception as e:
            print(f"Could not load state: {e}")
            return False

    def _clear_state(self):
        """Clear saved state."""
        if self.state_file.exists():
            self.state_file.unlink()
        self.completed_tests.clear()
        self.failed_tests.clear()

    def get_tests_for_suite(self, suite_name: str) -> List[Dict]:
        """Get all tests for a given suite."""
        if suite_name not in self.config['test_suites']:
            raise ValueError(f"Unknown test suite: {suite_name}")

        suite_config = self.config['test_suites'][suite_name]
        all_tests = []

        for test_group in suite_config['tests']:
            if test_group in self.config:
                all_tests.extend(self.config[test_group])

        return all_tests

    def run_single_backtest(self, test: Dict, timeout: int) -> Tuple[str, bool, float, str]:
        """Run a single backtest and return results."""
        test_id = f"{test['symbol']}_{test['start']}_{test['end']}"

        # Skip if already completed
        if test_id in self.completed_tests:
            return test_id, True, 0.0, "Already completed"

        print(f"\nRunning: {test['name']}")
        print(f"  Symbol: {test['symbol']}")
        print(f"  Period: {test['start']} to {test['end']}")
        print(f"  Description: {test['description']}")

        start_time = time.time()

        # Construct command
        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), '..', 'backtest_mas.py'),
            test['symbol'],
            test['start'],
            test['end']
        ]

        try:
            # Run with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout * 60,  # Convert to seconds
                cwd=Path(__file__).parent
            )

            elapsed = time.time() - start_time

            if result.returncode == 0:
                print(f"  ✅ Completed in {elapsed:.1f}s")
                self.completed_tests.add(test_id)
                return test_id, True, elapsed, "Success"
            else:
                error_msg = result.stderr[-200:] if result.stderr else "Unknown error"
                print(f"  ❌ Failed: {error_msg}")
                self.failed_tests[test_id] = error_msg
                return test_id, False, elapsed, error_msg

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            print(f"  ⏱️ Timeout after {timeout} minutes")
            self.failed_tests[test_id] = "Timeout"
            return test_id, False, elapsed, "Timeout"
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ❌ Error: {str(e)}")
            self.failed_tests[test_id] = str(e)
            return test_id, False, elapsed, str(e)
        finally:
            self._save_state()

    def run_suite(self, suite_name: str, parallel: Optional[bool] = None,
                  max_workers: Optional[int] = None, symbols_filter: Optional[List[str]] = None):
        """Run a complete test suite."""
        suite_config = self.config['test_suites'][suite_name]
        tests = self.get_tests_for_suite(suite_name)

        # Apply symbol filter if provided
        if symbols_filter:
            tests = [t for t in tests if t['symbol'] in symbols_filter]

        # Use config defaults if not specified
        if parallel is None:
            parallel = suite_config.get('parallel', False)
        if max_workers is None:
            max_workers = suite_config.get('max_parallel', 4)

        timeout = suite_config.get('timeout_minutes', 5)

        print(f"\n{'='*60}")
        print(f"Running {suite_name} test suite")
        print(f"{'='*60}")
        print(f"Total tests: {len(tests)}")
        print(f"Parallel execution: {parallel}")
        if parallel:
            print(f"Max workers: {max_workers}")
        print(f"Timeout per test: {timeout} minutes")
        print(f"{'='*60}\n")

        start_time = time.time()
        results = []

        if parallel and len(tests) > 1:
            # Parallel execution
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_to_test = {
                    executor.submit(self.run_single_backtest, test, timeout): test
                    for test in tests
                }

                completed = 0
                for future in as_completed(future_to_test):
                    completed += 1
                    result = future.result()
                    results.append(result)
                    print(
                        f"\nProgress: {completed}/{len(tests)} tests completed")
        else:
            # Sequential execution
            for i, test in enumerate(tests):
                result = self.run_single_backtest(test, timeout)
                results.append(result)
                print(f"\nProgress: {i+1}/{len(tests)} tests completed")

        # Summary
        total_time = time.time() - start_time
        successful = sum(1 for _, success, _, _ in results if success)
        failed = len(results) - successful

        print(f"\n{'='*60}")
        print(f"Test Suite Complete: {suite_name}")
        print(f"{'='*60}")
        print(f"Total tests: {len(results)}")
        print(f"Successful: {successful} ({successful/len(results)*100:.1f}%)")
        print(f"Failed: {failed}")
        print(f"Total time: {total_time/60:.1f} minutes")
        print(f"Average time per test: {total_time/len(results):.1f} seconds")

        # Save summary
        summary = {
            'suite': suite_name,
            'timestamp': datetime.now().isoformat(),
            'total_tests': len(results),
            'successful': successful,
            'failed': failed,
            'total_time_minutes': total_time / 60,
            'results': [
                {
                    'test_id': test_id,
                    'success': success,
                    'time_seconds': elapsed,
                    'message': msg
                }
                for test_id, success, elapsed, msg in results
            ]
        }

        summary_file = self.results_dir / \
            f"suite_summary_{suite_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\nSummary saved to: {summary_file}")

        # Run aggregator if configured
        if suite_config.get('aggregate_on_completion', True) and successful > 0:
            print("\nRunning result aggregation...")
            self.run_aggregator()

    def run_aggregator(self):
        """Run the result aggregation script."""
        try:
            cmd = [sys.executable, "aggregate_results.py"]
            result = subprocess.run(cmd, cwd=Path(
                __file__).parent, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Aggregation complete")
            else:
                print(f"❌ Aggregation failed: {result.stderr}")
        except Exception as e:
            print(f"❌ Could not run aggregator: {e}")

    def list_suites(self):
        """List all available test suites."""
        print("\nAvailable Test Suites:")
        print("=" * 60)
        for suite_name, suite_config in self.config['test_suites'].items():
            total_tests = sum(len(self.config.get(test_group, []))
                              for test_group in suite_config['tests'])
            print(f"\n{suite_name}:")
            print(f"  Description: {suite_config['description']}")
            print(f"  Total tests: {total_tests}")
            print(
                f"  Timeout: {suite_config['timeout_minutes']} minutes per test")
            print(f"  Parallel: {suite_config.get('parallel', False)}")


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    print("\n\nInterrupted! State has been saved. Use --resume to continue.")
    sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Backtesting Suite for RH2MAS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_backtest_suite.py quick                    # Run quick tests
  python run_backtest_suite.py comprehensive --parallel # Run comprehensive tests in parallel
  python run_backtest_suite.py extended --symbols AAPL,MSFT  # Run extended tests for specific symbols
  python run_backtest_suite.py --list                   # List available test suites
  python run_backtest_suite.py --resume                 # Resume interrupted run
        """
    )

    parser.add_argument('suite', nargs='?', default=None,
                        help='Test suite to run (quick, comprehensive, extended, all)')
    parser.add_argument('--config', default='backtest_configs.yaml',
                        help='Configuration file (default: backtest_configs.yaml)')
    parser.add_argument('--parallel', action='store_true',
                        help='Enable parallel execution')
    parser.add_argument('--no-parallel', action='store_true',
                        help='Disable parallel execution')
    parser.add_argument('--workers', type=int, default=None,
                        help='Number of parallel workers')
    parser.add_argument('--symbols', type=str, default=None,
                        help='Comma-separated list of symbols to test')
    parser.add_argument('--list', action='store_true',
                        help='List available test suites')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from previous interrupted run')
    parser.add_argument('--clear-state', action='store_true',
                        help='Clear saved state and start fresh')

    args = parser.parse_args()

    # Set up signal handler for graceful interruption
    signal.signal(signal.SIGINT, signal_handler)

    try:
        runner = BacktestRunner(args.config)

        if args.list:
            runner.list_suites()
            return

        if args.clear_state:
            runner._clear_state()
            print("State cleared.")

        if args.resume:
            if not runner._load_state():
                print("No previous state found to resume from.")
                return

        if not args.suite:
            print(
                "Error: Please specify a test suite or use --list to see available suites.")
            parser.print_help()
            return

        # Parse symbols filter
        symbols_filter = None
        if args.symbols:
            symbols_filter = [s.strip() for s in args.symbols.split(',')]

        # Determine parallel setting
        parallel = None
        if args.parallel:
            parallel = True
        elif args.no_parallel:
            parallel = False

        # Run the suite
        runner.run_suite(
            args.suite,
            parallel=parallel,
            max_workers=args.workers,
            symbols_filter=symbols_filter
        )

        # Clear state on successful completion
        runner._clear_state()

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
