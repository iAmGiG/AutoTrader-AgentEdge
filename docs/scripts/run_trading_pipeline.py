#!/usr/bin/env python3
"""
Example: Run Full Trading Pipeline

Demonstrates the complete daily trading workflow orchestration.

Usage:
    python -m docs.scripts.run_trading_pipeline --watchlist SPY,QQQ,AAPL
    python -m docs.scripts.run_trading_pipeline --mode paper  # Use paper trading
    python -m docs.scripts.run_trading_pipeline --dry-run     # Skip actual execution

Or from project root:
    python docs/scripts/run_trading_pipeline.py --watchlist SPY,QQQ,AAPL
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path (platform-agnostic)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.autogen_agents.executor_agent import ExecutorAgent
from src.autogen_agents.voter_agent import VoterAgent
from src.trading.scheduling.trading_pipeline import TradingPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/pipeline_demo.log"),
    ],
)

logger = logging.getLogger(__name__)


async def run_pipeline(
    watchlist: list[str] = None,
    paper_trading: bool = True,
    dry_run: bool = False,
):
    """
    Run the full trading pipeline.

    Args:
        watchlist: List of tickers to scan
        paper_trading: Whether to use paper trading mode
        dry_run: Skip actual order execution
    """
    logger.info("=" * 80)
    logger.info("TRADING PIPELINE DEMO")
    logger.info("=" * 80)

    # Create agents
    voter_agent = VoterAgent(name="voter_agent", use_config_file=True)

    executor_agent = None
    order_manager = None
    position_manager = None

    if not dry_run:
        try:
            from src.trading.broker.alpaca_trading_client import get_trading_client
            from src.trading.orders.order_manager import OrderManager
            from src.trading.positions.position_manager import PositionManager

            logger.info(f"Initializing {'paper' if paper_trading else 'live'} trading...")
            client = get_trading_client(paper=paper_trading)
            position_manager = PositionManager(client)
            order_manager = OrderManager(client, position_manager)
            executor_agent = ExecutorAgent(
                name="executor_agent",
                order_manager=order_manager,
                position_manager=position_manager,
                paper_trading=paper_trading,
            )
        except Exception as e:
            logger.warning(f"Could not initialize broker connection: {e}")
            logger.info("Running in DRY-RUN mode (no actual trades)")
            executor_agent = ExecutorAgent(name="executor_agent", paper_trading=True)

    # Create pipeline
    pipeline = TradingPipeline(
        voter_agent=voter_agent,
        executor_agent=executor_agent,
        position_manager=position_manager,
        order_manager=order_manager,
        watchlist=watchlist,
    )

    # Run the full workflow
    try:
        metrics = await pipeline.run_full_pipeline()

        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("PIPELINE RESULTS")
        logger.info("=" * 80)
        logger.info(f"Status: {pipeline.pipeline_status.value.upper()}")
        logger.info(f"Duration: {(metrics.completed_at - metrics.started_at).total_seconds():.1f}s")
        logger.info(f"Phases Completed: {metrics.phases_completed}/{metrics.total_phases}")
        logger.info(f"Signals Generated: {metrics.total_signals}")
        logger.info(f"Orders Placed: {metrics.total_orders}")
        logger.info(f"Errors: {metrics.total_errors}")

        # Phase breakdown
        logger.info("")
        logger.info("Phase Breakdown:")
        for phase_result in metrics.phase_results:
            duration = (
                (phase_result.completed_at - phase_result.started_at).total_seconds()
                if phase_result.completed_at
                else 0
            )
            logger.info(
                f"  {phase_result.phase.value}: {phase_result.status.value} ({duration:.1f}s)"
            )
            if phase_result.errors:
                for error in phase_result.errors:
                    logger.error(f"    Error: {error}")

        logger.info("=" * 80)

        return metrics

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise


def main():
    parser = argparse.ArgumentParser(description="Run Trading Pipeline Demo")
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
        help="Skip actual order execution (simulation only)",
    )

    args = parser.parse_args()

    # Parse watchlist
    watchlist = None
    if args.watchlist:
        watchlist = [ticker.strip().upper() for ticker in args.watchlist.split(",")]
        logger.info(f"Using custom watchlist: {watchlist}")

    # Run pipeline
    asyncio.run(
        run_pipeline(
            watchlist=watchlist,
            paper_trading=(args.mode == "paper"),
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
