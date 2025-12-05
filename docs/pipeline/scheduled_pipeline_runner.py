#!/usr/bin/env python3
"""
Scheduled Pipeline Runner - Automated Daily Trading

Runs the TradingPipeline on a configurable schedule.
Designed for "set it and forget it" automation.

Schedule Options:
- morning: Run at 9:45 AM ET (15 min after market open)
- afternoon: Run at 3:00 PM ET (1 hour before market close)
- both: Run both morning and afternoon

Usage:
    # Run morning only
    python -m docs.pipeline.scheduled_pipeline_runner --schedule morning

    # Run both morning and afternoon
    python -m docs.pipeline.scheduled_pipeline_runner --schedule both

    # Custom times (ET timezone)
    python -m docs.pipeline.scheduled_pipeline_runner --times "09:45,15:00"

    # Dry-run mode (no actual trades)
    python -m docs.pipeline.scheduled_pipeline_runner --dry-run

Or from project root:
    python docs/pipeline/scheduled_pipeline_runner.py --schedule morning
"""

import argparse
import asyncio
import logging
import sys
from datetime import time
from pathlib import Path

import pytz

# Add project root to path (platform-agnostic)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.autogen_agents.executor_agent import ExecutorAgent
from src.autogen_agents.voter_agent import VoterAgent
from src.trading.scheduling.trading_pipeline import TradingPipeline
from src.utils.date_utils import get_datetime_now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/scheduled_pipeline.log"),
    ],
)

logger = logging.getLogger(__name__)

ET_TZ = pytz.timezone("America/New_York")


class ScheduledPipelineRunner:
    """Manages scheduled pipeline executions."""

    def __init__(
        self,
        scheduled_times: list[time],
        watchlist: list[str] = None,
        paper_trading: bool = True,
        dry_run: bool = False,
    ):
        """
        Initialize scheduled runner.

        Args:
            scheduled_times: List of time objects for daily execution (in ET)
            watchlist: Ticker watchlist
            paper_trading: Use paper trading
            dry_run: Skip actual execution
        """
        self.scheduled_times = scheduled_times
        self.watchlist = watchlist
        self.paper_trading = paper_trading
        self.dry_run = dry_run

        # Track last execution dates to avoid duplicate runs
        self.last_execution = {t: None for t in scheduled_times}

        logger.info("ScheduledPipelineRunner initialized")
        logger.info(f"Schedule times (ET): {[t.strftime('%H:%M') for t in scheduled_times]}")
        logger.info(f"Paper trading: {paper_trading}")
        logger.info(f"Dry-run: {dry_run}")

    async def run_forever(self):
        """
        Run the scheduler loop indefinitely.

        Checks every minute if it's time to run the pipeline.
        """
        logger.info("=" * 80)
        logger.info("SCHEDULED PIPELINE RUNNER - Starting")
        logger.info("=" * 80)

        while True:
            try:
                now_et = get_datetime_now(ET_TZ)
                current_time = now_et.time()
                current_date = now_et.date()

                # Check if any scheduled time matches
                for scheduled_time in self.scheduled_times:
                    if self._should_run(current_time, scheduled_time, current_date):
                        logger.info(f"\n⏰ Scheduled time reached: {scheduled_time}")

                        # Run the pipeline
                        await self._execute_pipeline()

                        # Mark as executed
                        self.last_execution[scheduled_time] = current_date

                # Sleep until next minute
                await asyncio.sleep(60)

            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Continue after error

    def _should_run(self, current_time: time, scheduled_time: time, current_date) -> bool:
        """
        Check if pipeline should run now.

        Returns True if:
        - Current time matches scheduled time (within 1 minute)
        - Haven't already run today at this time
        """
        # Check if within 1 minute of scheduled time
        current_minutes = current_time.hour * 60 + current_time.minute
        scheduled_minutes = scheduled_time.hour * 60 + scheduled_time.minute

        time_match = abs(current_minutes - scheduled_minutes) < 1

        # Check if already ran today
        already_ran = self.last_execution[scheduled_time] == current_date

        return time_match and not already_ran

    async def _execute_pipeline(self):
        """Execute the trading pipeline."""
        try:
            logger.info("Initializing pipeline components...")

            # Create agents
            voter_agent = VoterAgent(name="voter_agent", use_config_file=True)

            executor_agent = None
            order_manager = None
            position_manager = None

            if not self.dry_run:
                try:
                    from src.trading.broker.alpaca_trading_client import (
                        get_trading_client,
                    )
                    from src.trading.orders.order_manager import OrderManager
                    from src.trading.positions.position_manager import PositionManager

                    client = get_trading_client(paper=self.paper_trading)
                    position_manager = PositionManager(client)
                    order_manager = OrderManager(client, position_manager)
                    executor_agent = ExecutorAgent(
                        name="executor_agent",
                        order_manager=order_manager,
                        position_manager=position_manager,
                        paper_trading=self.paper_trading,
                    )
                    logger.info("✓ Broker connection established")
                except Exception as e:
                    logger.warning(f"Could not connect to broker: {e}")
                    logger.info("Running in DRY-RUN mode")
                    executor_agent = ExecutorAgent(name="executor_agent", paper_trading=True)
            else:
                executor_agent = ExecutorAgent(name="executor_agent", paper_trading=True)

            # Create pipeline
            pipeline = TradingPipeline(
                voter_agent=voter_agent,
                executor_agent=executor_agent,
                position_manager=position_manager,
                order_manager=order_manager,
                watchlist=self.watchlist,
            )

            # Run pipeline
            logger.info("▶️  Starting pipeline execution...")
            metrics = await pipeline.run_full_pipeline()

            # Log results
            logger.info("")
            logger.info("=" * 80)
            logger.info("EXECUTION COMPLETE")
            logger.info("=" * 80)
            logger.info(f"Status: {pipeline.pipeline_status.value.upper()}")
            logger.info(
                f"Duration: {(metrics.completed_at - metrics.started_at).total_seconds():.1f}s"
            )
            logger.info(f"Signals: {metrics.total_signals}")
            logger.info(f"Orders: {metrics.total_orders}")
            logger.info(f"Errors: {metrics.total_errors}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)


def parse_schedule_times(schedule_arg: str) -> list[time]:
    """
    Parse schedule argument into list of time objects.

    Args:
        schedule_arg: "morning", "afternoon", "both", or "HH:MM,HH:MM"

    Returns:
        List of time objects
    """
    if schedule_arg == "morning":
        return [time(9, 45)]  # 9:45 AM ET
    elif schedule_arg == "afternoon":
        return [time(15, 0)]  # 3:00 PM ET
    elif schedule_arg == "both":
        return [time(9, 45), time(15, 0)]
    else:
        # Parse custom times (e.g., "09:45,15:00")
        times = []
        for time_str in schedule_arg.split(","):
            hour, minute = time_str.strip().split(":")
            times.append(time(int(hour), int(minute)))
        return times


def main():
    parser = argparse.ArgumentParser(description="Scheduled Pipeline Runner")

    parser.add_argument(
        "--schedule",
        type=str,
        default="morning",
        help=(
            "Schedule times: 'morning' (9:45 AM), 'afternoon' (3:00 PM), "
            "'both', or custom times like '09:45,15:00' (ET)"
        ),
    )

    parser.add_argument(
        "--watchlist",
        type=str,
        help="Comma-separated list of tickers (e.g., SPY,QQQ,AAPL)",
    )

    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Trading mode (default: paper)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual order execution",
    )

    args = parser.parse_args()

    # Parse schedule times
    try:
        scheduled_times = parse_schedule_times(args.schedule)
    except Exception as e:
        logger.error(f"Invalid schedule format: {e}")
        return

    # Parse watchlist
    watchlist = None
    if args.watchlist:
        watchlist = [ticker.strip().upper() for ticker in args.watchlist.split(",")]

    # Create and run scheduler
    runner = ScheduledPipelineRunner(
        scheduled_times=scheduled_times,
        watchlist=watchlist,
        paper_trading=(args.mode == "paper"),
        dry_run=args.dry_run,
    )

    # Run forever (until Ctrl+C)
    try:
        asyncio.run(runner.run_forever())
    except KeyboardInterrupt:
        logger.info("\nScheduler stopped by user")


if __name__ == "__main__":
    main()
