#!/usr/bin/env python3
"""Backtest service that runs continuously with rate limit awareness.

This service:
1. Monitors API rate limits and pauses when needed
2. Automatically resumes failed runs
3. Runs backtests in sequence with delays
4. Sends notifications on completion
5. Can run as a systemd service or in screen/tmux
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
import json
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.cache/backtests/service.log'),
        logging.StreamHandler()
    ]
)


class BacktestService:
    """Service to run backtests continuously with rate limit management."""

    def __init__(self):
        self.running = True
        self.current_task = None
        self.progress_file = ".cache/backtests/service_progress.json"
        self.rate_limit_tracker = {
            'alpha_vantage': {'calls': 0, 'reset_time': None, 'limit': 25},
            'fmp': {'calls': 0, 'reset_time': None, 'limit': 250},
            'newsapi': {'calls': 0, 'reset_time': None, 'limit': 100},
            'openai': {'calls': 0, 'reset_time': None, 'limit': 500, 'cost': 0.0}  # Track cost too
        }

        # Market conditions and tickers from main script
        self.market_conditions = {
            "Bear Market (2022)": {
                "start": "2022-01-01",
                "end": "2022-12-31",
                "description": "Fed rate hikes, inflation concerns, tech selloff"
            },
            "Bull Recovery (2023)": {
                "start": "2023-01-01",
                "end": "2023-12-31",
                "description": "AI boom, tech recovery, soft landing optimism"
            },
            "Current Market (2024-2025)": {
                "start": "2024-01-01",
                "end": "2025-07-11",
                "description": "Recent market conditions, mixed signals"
            },
            "COVID Crash (2020)": {
                "start": "2020-02-15",
                "end": "2020-05-15",
                "description": "Pandemic volatility, extreme market stress"
            },
            "2018 Correction": {
                "start": "2018-10-01",
                "end": "2018-12-31",
                "description": "Trade war fears, Fed tightening concerns"
            }
        }

        self.tickers = ["SPY", "NVDA", "TSLA", "AAPL", "MSFT", "META", "GOOGL", "AMZN"]

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logging.info("Received shutdown signal, finishing current task...")
        self.running = False

    def load_progress(self) -> Dict:
        """Load service progress from file."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'completed': [],
            'failed': [],
            'pending': [],
            'last_run': None,
            'total_runs': 0,
            'api_errors': 0,
            'openai_total_calls': 0,
            'openai_total_cost': 0.0
        }

    def save_progress(self, progress: Dict):
        """Save service progress to file."""
        os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)

    def check_rate_limits(self) -> Tuple[bool, int]:
        """Check if we can make API calls, return (can_proceed, wait_time)."""
        now = datetime.now()
        wait_times = []

        for api, tracker in self.rate_limit_tracker.items():
            if tracker['reset_time'] and now < tracker['reset_time']:
                # Still in cooldown period
                remaining = (tracker['reset_time'] - now).total_seconds()
                wait_times.append(remaining)
                logging.info(f"{api}: {tracker['calls']}/{tracker['limit']} calls, "
                             f"reset in {remaining:.0f}s")
            elif tracker['calls'] >= tracker['limit']:
                # Hit limit, set reset time
                if api == 'alpha_vantage':
                    # 25 calls per day
                    reset_time = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
                else:
                    # Most APIs reset after 1 hour
                    reset_time = now + timedelta(hours=1)

                tracker['reset_time'] = reset_time
                remaining = (reset_time - now).total_seconds()
                wait_times.append(remaining)
                logging.warning(f"{api}: Rate limit hit! Reset at {reset_time}")
            else:
                # Check if reset time has passed
                if tracker['reset_time'] and now >= tracker['reset_time']:
                    tracker['calls'] = 0
                    tracker['reset_time'] = None
                    logging.info(f"{api}: Rate limit reset, calls available")

        if wait_times:
            return False, max(wait_times)
        return True, 0

    def run_single_backtest(self, symbol: str, start: str, end: str,
                            condition: str) -> bool:
        """Run a single backtest and return success status."""
        self.current_task = f"{symbol} {condition} ({start} to {end})"
        logging.info(f"Starting backtest: {self.current_task}")

        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), '..', 'backtest_mas.py'),
            symbol,
            start,
            end
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=1800)  # 30 min timeout

            # Check for API errors in output
            if "429" in result.stderr or "Too Many Requests" in result.stderr:
                self.rate_limit_tracker['fmp']['calls'] = self.rate_limit_tracker['fmp']['limit']
                logging.warning("FMP rate limit detected")
                return False

            if "403" in result.stderr or "Forbidden" in result.stderr:
                self.rate_limit_tracker['newsapi']['calls'] = self.rate_limit_tracker['newsapi']['limit']
                logging.warning("News API limit detected")
                return False

            if result.returncode == 0:
                # Check if backtest actually completed by looking for output directory
                if "Output directory:" in result.stdout:
                    output_dir = None
                    for line in result.stdout.split('\n'):
                        if "Output directory:" in line:
                            output_dir = line.split("Output directory:")[1].strip()
                            break

                    # Verify the run actually completed
                    if output_dir and os.path.exists(output_dir):
                        metadata_file = os.path.join(output_dir, "metadata.json")
                        if os.path.exists(metadata_file):
                            with open(metadata_file) as f:
                                metadata = json.load(f)
                            if metadata.get('status') == 'completed':
                                logging.info(f"✅ Completed: {self.current_task}")
                                # Increment API call counters (rough estimate)
                                self.rate_limit_tracker['alpha_vantage']['calls'] += 1
                                self.rate_limit_tracker['fmp']['calls'] += 2
                                # Estimate OpenAI calls (4 agents x ~250 trading days)
                                days_processed = metadata.get('days_processed', 250)
                                openai_calls = days_processed * 4  # 4 agents per day
                                self.rate_limit_tracker['openai']['calls'] += openai_calls
                                # GPT-4o-mini cost: $0.15/1M input, $0.60/1M output tokens
                                # Rough estimate: ~2K tokens per call (1.5K in, 0.5K out)
                                # Cost = (1.5K * 0.15 + 0.5K * 0.60) / 1M = $0.000525 per call
                                estimated_cost = openai_calls * 0.000525
                                self.rate_limit_tracker['openai']['cost'] += estimated_cost
                                logging.info(
                                    f"OpenAI usage: {openai_calls} calls, ~${estimated_cost:.2f} (GPT-4o-mini)")
                                return True

                logging.warning(
                    f"⚠️  Backtest ran but didn't complete properly: {self.current_task}")
                return False
            else:
                logging.error(f"❌ Failed: {self.current_task}")
                logging.error(f"Error: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logging.error(f"⏱️  Timeout: {self.current_task}")
            return False
        except Exception as e:
            logging.error(f"❌ Exception: {self.current_task} - {str(e)}")
            return False

    def get_pending_tasks(self, progress: Dict) -> List[Tuple[str, str, str, str]]:
        """Get list of pending backtest tasks."""
        tasks = []
        completed = set(progress['completed'])

        for condition_name, condition_data in self.market_conditions.items():
            for ticker in self.tickers:
                task_id = f"{ticker}_{condition_name}_{condition_data['start']}_{condition_data['end']}"
                if task_id not in completed:
                    tasks.append((ticker, condition_data['start'],
                                  condition_data['end'], condition_name))

        return tasks

    def run_service(self):
        """Main service loop."""
        logging.info("🚀 Backtest Service Started")
        logging.info(f"Total tasks: {len(self.market_conditions) * len(self.tickers)}")

        progress = self.load_progress()

        while self.running:
            # Check rate limits
            can_proceed, wait_time = self.check_rate_limits()

            if not can_proceed:
                logging.info(f"⏸️  Rate limited, waiting {wait_time/60:.1f} minutes...")
                # Check every minute if we should stop
                for _ in range(int(wait_time / 60)):
                    if not self.running:
                        break
                    time.sleep(60)
                continue

            # Get pending tasks
            pending = self.get_pending_tasks(progress)

            if not pending:
                logging.info("✅ All tasks completed!")
                self.generate_final_report()
                break

            # Run next task
            ticker, start, end, condition = pending[0]
            task_id = f"{ticker}_{condition}_{start}_{end}"

            success = self.run_single_backtest(ticker, start, end, condition)

            if success:
                progress['completed'].append(task_id)
                progress['total_runs'] += 1
                # Update OpenAI totals
                progress['openai_total_calls'] = progress.get(
                    'openai_total_calls', 0) + self.rate_limit_tracker['openai']['calls']
                progress['openai_total_cost'] = progress.get(
                    'openai_total_cost', 0.0) + self.rate_limit_tracker['openai']['cost']
            else:
                if task_id not in progress['failed']:
                    progress['failed'].append(task_id)
                progress['api_errors'] += 1

            progress['last_run'] = datetime.now().isoformat()
            self.save_progress(progress)

            # Status update
            completed_count = len(progress['completed'])
            total_count = len(self.market_conditions) * len(self.tickers)
            percent = (completed_count / total_count) * 100
            openai_cost = progress.get('openai_total_cost', 0.0)
            logging.info(
                f"📊 Progress: {completed_count}/{total_count} ({percent:.1f}%) | OpenAI cost: ${openai_cost:.2f}")

            # Delay between runs to avoid hitting limits too fast
            if self.running:
                delay = 30  # 30 seconds between runs
                logging.info(f"⏳ Waiting {delay}s before next run...")
                time.sleep(delay)

        logging.info("🛑 Backtest Service Stopped")

    def generate_final_report(self):
        """Generate the final market conditions report."""
        logging.info("📊 Generating final report...")

        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), '..', 'generate_market_conditions_report.py'),
            "--skip-backtests"
        ]

        try:
            subprocess.run(cmd, check=True)
            logging.info("✅ Final report generated successfully!")
        except Exception as e:
            logging.error(f"❌ Failed to generate report: {e}")


def main():
    """Run the backtest service."""
    service = BacktestService()

    print("""
╔══════════════════════════════════════════════════════════╗
║           RH2MAS Backtest Service                        ║
║                                                          ║
║  This service will:                                      ║
║  • Run all backtest combinations                         ║
║  • Handle API rate limits automatically                  ║
║  • Resume from failures                                  ║
║  • Generate final report when complete                   ║
║                                                          ║
║  Press Ctrl+C to stop gracefully                         ║
╚══════════════════════════════════════════════════════════╝
    """)

    service.run_service()


if __name__ == "__main__":
    main()
