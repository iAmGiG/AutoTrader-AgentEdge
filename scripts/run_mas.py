"""Run a minimal multi-agent simulation over a date range.

This CLI loops over a calendar range, obtains signals from a
``CoordinatorAgent`` and passes them to a ``StrategyAgent``.  The
decisions are printed as JSON on stdout.
"""

import argparse
import json
from datetime import datetime, timedelta, date

from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.strategy_agent import StrategyAgent
from src.tools.date_utils import get_processed_date_range


def iter_days(start: date, end: date):
    """Yield each day between ``start`` and ``end`` inclusive."""

    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def main() -> None:
    """Entry point for the demo CLI."""

    parser = argparse.ArgumentParser(
        description="Run MAS demo over a date range",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD or relative)",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD or relative)",
    )
    parser.add_argument(
        "--symbol",
        default="AAPL",
        help="Ticker symbol to analyze",
    )
    args = parser.parse_args()

    # Parse the date range using date_utils to support relative strings
    start_str, end_str = get_processed_date_range(args.start, args.end)
    start_dt = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()

    coord = CoordinatorAgent()
    strat = StrategyAgent()

    for day in iter_days(start_dt, end_dt):
        signals = coord.get_signals(day.isoformat(), args.symbol)
        decision = strat.decide_trade(signals)
        print(json.dumps({"date": day.isoformat(), "decision": decision}))


if __name__ == "__main__":
    main()

