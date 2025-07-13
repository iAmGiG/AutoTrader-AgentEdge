#!/usr/bin/env python3
"""Analyze existing backtest results and categorize by market condition."""

import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from collections import defaultdict

# Define market condition periods
MARKET_CONDITIONS = {
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
        "end": "2025-12-31",
        "description": "Recent market conditions, mixed signals"
    },
    "COVID Crash (2020)": {
        "start": "2020-01-01",
        "end": "2020-12-31",
        "description": "Pandemic volatility, extreme market stress"
    }
}


def categorize_run(start_date: str, end_date: str) -> str:
    """Categorize a backtest run into a market condition."""
    for condition_name, condition_data in MARKET_CONDITIONS.items():
        if (start_date >= condition_data['start'] and
            start_date <= condition_data['end'] and
            end_date >= condition_data['start'] and
                end_date <= condition_data['end']):
            return condition_name
    return "Other"


def main():
    runs_dir = Path(".cache/backtests/runs")
    if not runs_dir.exists():
        print("No backtest runs found!")
        return

    # Categorize all runs
    categorized_runs = defaultdict(list)

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        metadata_path = run_dir / "metadata.json"
        if not metadata_path.exists():
            continue

        with open(metadata_path) as f:
            metadata = json.load(f)

        start_date = metadata.get('start_date', '')
        end_date = metadata.get('end_date', '')

        if start_date and end_date:
            category = categorize_run(start_date, end_date)
            categorized_runs[category].append({
                'run_dir': str(run_dir),
                'symbol': metadata.get('symbol', 'Unknown'),
                'start_date': start_date,
                'end_date': end_date,
                'status': metadata.get('status', 'unknown')
            })

    # Print summary
    print("\n📊 Existing Backtest Summary by Market Condition\n")
    print("=" * 80)

    for condition_name in MARKET_CONDITIONS:
        runs = categorized_runs.get(condition_name, [])
        if runs:
            print(f"\n{condition_name}:")
            print(f"  Total runs: {len(runs)}")

            # Group by symbol
            by_symbol = defaultdict(list)
            for run in runs:
                by_symbol[run['symbol']].append(run)

            print(f"  Unique symbols: {', '.join(sorted(by_symbol.keys()))}")

            # Show details
            for symbol in sorted(by_symbol.keys()):
                symbol_runs = by_symbol[symbol]
                print(f"\n  {symbol}:")
                for run in symbol_runs:
                    print(f"    - {run['start_date']} to {run['end_date']} ({run['status']})")

    # Other runs
    other_runs = categorized_runs.get("Other", [])
    if other_runs:
        print(f"\nOther periods: {len(other_runs)} runs")
        by_symbol = defaultdict(list)
        for run in other_runs:
            by_symbol[run['symbol']].append(run)
        print(f"  Symbols: {', '.join(sorted(by_symbol.keys()))}")

    print("\n" + "=" * 80)

    # Save mapping for use by report generator
    output_file = ".cache/backtests/existing_runs_mapping.json"
    with open(output_file, 'w') as f:
        json.dump(categorized_runs, f, indent=2)
    print(f"\nMapping saved to: {output_file}")


if __name__ == "__main__":
    main()
