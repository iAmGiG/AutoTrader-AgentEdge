#!/usr/bin/env python3
"""Automated multi-timeframe portfolio scanner.

This script runs the daily scanner across multiple timeframes,
progressively expanding the date range to analyze strategy behavior
over different market conditions.
"""

import sys
import os
import json
import time
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import argparse

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from scripts.strategies.mechanical.run_daily_scan import run_daily_scan
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay


def get_market_days(start_date: str, end_date: str) -> List[str]:
    """Get list of market days between start and end dates.

    :param start_date: Start date (YYYY-MM-DD)
    :param end_date: End date (YYYY-MM-DD)
    :return: List of market days as strings
    """
    # Use US market calendar
    us_bd = CustomBusinessDay(calendar=USFederalHolidayCalendar())

    # Generate date range
    date_range = pd.date_range(start=start_date, end=end_date, freq=us_bd)

    # Convert to string format
    return [d.strftime('%Y-%m-%d') for d in date_range]


def get_timeframe_ranges(end_date: str, timeframes: List[int]) -> List[Tuple[str, str, str]]:
    """Generate date ranges for different timeframes.

    :param end_date: End date for all ranges (YYYY-MM-DD)
    :param timeframes: List of days to look back (e.g., [7, 14, 30, 60])
    :return: List of tuples (label, start_date, end_date)
    """
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    ranges = []

    for days in timeframes:
        start_dt = end_dt - timedelta(days=days)
        label = f"{days}_days"
        ranges.append((label, start_dt.strftime('%Y-%m-%d'), end_date))

    return ranges


def scan_date_range(start_date: str, end_date: str, portfolio: List[str],
                    delay_seconds: float = 0.5, cache_only: bool = False, heat_threshold: float = None) -> Dict:
    """Scan a date range and collect results.

    :param start_date: Start date (YYYY-MM-DD)
    :param end_date: End date (YYYY-MM-DD)
    :param portfolio: List of symbols to scan
    :param delay_seconds: Delay between scans to avoid API limits
    :param cache_only: If True, only use cached data (no API calls)
    :param heat_threshold: Override market heat threshold
    :return: Dictionary with aggregated results
    """
    # Get market days in range
    market_days = get_market_days(start_date, end_date)

    results = {
        'start_date': start_date,
        'end_date': end_date,
        'days_scanned': 0,
        'total_ta_signals': 0,
        'total_approved_trades': 0,
        'daily_results': [],
        'symbol_stats': {},
        'market_heat_stats': {
            'min': float('inf'),
            'max': float('-inf'),
            'sum': 0,
            'count': 0,
            'above_threshold_days': 0
        },
        'errors': []
    }

    print(f"\n{'='*60}")
    print(f"Scanning {len(market_days)} market days from {start_date} to {end_date}")
    print(f"{'='*60}")

    for i, date in enumerate(market_days):
        print(f"\n[{i+1}/{len(market_days)}] Scanning {date}...")

        try:
            # Run daily scan
            daily_result = run_daily_scan(scan_date=date, portfolio=portfolio,
                                          cache_only=cache_only, heat_threshold=heat_threshold)

            # Track results
            results['days_scanned'] += 1
            results['total_ta_signals'] += len(daily_result['ta_signals'].get('entries', []))
            results['total_approved_trades'] += len(daily_result['approved_trades'])

            # Store daily summary
            market_heat = daily_result['market_heat'].get('heat_level', 0)
            daily_summary = {
                'date': date,
                'market_heat': market_heat,
                'ta_signals': [s['symbol'] for s in daily_result['ta_signals'].get('entries', [])],
                'approved_trades': [t['symbol'] for t in daily_result['approved_trades']]
            }
            results['daily_results'].append(daily_summary)

            # Update market heat stats
            heat_stats = results['market_heat_stats']
            heat_stats['min'] = min(heat_stats['min'], market_heat)
            heat_stats['max'] = max(heat_stats['max'], market_heat)
            heat_stats['sum'] += market_heat
            heat_stats['count'] += 1
            if market_heat > 0.3:
                heat_stats['above_threshold_days'] += 1

            # Track symbol statistics
            for signal in daily_result['ta_signals'].get('entries', []):
                symbol = signal['symbol']
                if symbol not in results['symbol_stats']:
                    results['symbol_stats'][symbol] = {
                        'ta_signals': 0,
                        'approved_trades': 0,
                        'signal_dates': []
                    }
                results['symbol_stats'][symbol]['ta_signals'] += 1
                results['symbol_stats'][symbol]['signal_dates'].append(date)

            for trade in daily_result['approved_trades']:
                symbol = trade['symbol']
                results['symbol_stats'][symbol]['approved_trades'] += 1

            # Delay to avoid API rate limits (skip if cache-only)
            if not cache_only and i < len(market_days) - 1:  # Don't delay after last scan
                time.sleep(delay_seconds)

        except Exception as e:
            print(f"   ERROR scanning {date}: {e}")
            results['errors'].append({'date': date, 'error': str(e)})
            # Continue with next date

    # Calculate averages
    if results['market_heat_stats']['count'] > 0:
        results['market_heat_stats']['avg'] = (
            results['market_heat_stats']['sum'] / results['market_heat_stats']['count']
        )

    return results


def generate_timeframe_report(timeframe_results: Dict[str, Dict], output_dir: str):
    """Generate a comprehensive report across all timeframes.

    :param timeframe_results: Dictionary of results by timeframe
    :param output_dir: Directory to save report
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Create report
    report_lines = []
    report_lines.append("# Multi-Timeframe Scan Report")
    report_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("\n## Summary by Timeframe\n")

    # Summary table
    report_lines.append(
        "| Timeframe | Days | TA Signals | Approved | Approval Rate | Avg Heat | Heat > 0.3 |")
    report_lines.append(
        "|-----------|------|------------|----------|---------------|----------|------------|")

    for label, results in sorted(timeframe_results.items()):
        days = results['days_scanned']
        ta_signals = results['total_ta_signals']
        approved = results['total_approved_trades']
        approval_rate = (approved / ta_signals * 100) if ta_signals > 0 else 0
        avg_heat = results['market_heat_stats'].get('avg', 0)
        heat_above = results['market_heat_stats']['above_threshold_days']
        heat_pct = (heat_above / days * 100) if days > 0 else 0

        report_lines.append(
            f"| {label:9} | {days:4} | {ta_signals:10} | {approved:8} | "
            f"{approval_rate:12.1f}% | {avg_heat:8.3f} | {heat_above:3} ({heat_pct:4.1f}%) |"
        )

    # Symbol performance
    report_lines.append("\n## Symbol Performance Across All Timeframes\n")

    # Aggregate symbol stats
    all_symbols = {}
    for results in timeframe_results.values():
        for symbol, stats in results['symbol_stats'].items():
            if symbol not in all_symbols:
                all_symbols[symbol] = {'ta_signals': 0, 'approved_trades': 0}
            all_symbols[symbol]['ta_signals'] += stats['ta_signals']
            all_symbols[symbol]['approved_trades'] += stats['approved_trades']

    # Sort by TA signals
    sorted_symbols = sorted(all_symbols.items(), key=lambda x: x[1]['ta_signals'], reverse=True)

    report_lines.append("| Symbol | TA Signals | Approved | Approval Rate |")
    report_lines.append("|--------|------------|----------|---------------|")

    for symbol, stats in sorted_symbols:
        if stats['ta_signals'] > 0:
            approval_rate = (stats['approved_trades'] / stats['ta_signals'] * 100)
            report_lines.append(
                f"| {symbol:6} | {stats['ta_signals']:10} | {stats['approved_trades']:8} | "
                f"{approval_rate:12.1f}% |"
            )

    # Market heat analysis
    report_lines.append("\n## Market Heat Analysis\n")

    for label, results in sorted(timeframe_results.items()):
        heat_stats = results['market_heat_stats']
        if heat_stats['count'] > 0:
            report_lines.append(f"\n### {label}")
            report_lines.append(f"- Average: {heat_stats.get('avg', 0):.3f}")
            report_lines.append(f"- Min: {heat_stats['min']:.3f}")
            report_lines.append(f"- Max: {heat_stats['max']:.3f}")
            report_lines.append(
                f"- Days above threshold (0.3): {heat_stats['above_threshold_days']} / {results['days_scanned']}")

    # Save report
    report_file = f"{output_dir}/multi_timeframe_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_file, 'w') as f:
        f.write('\n'.join(report_lines))

    print(f"\n📊 Report saved to: {report_file}")

    # Also save raw data as JSON
    json_file = f"{output_dir}/multi_timeframe_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_file, 'w') as f:
        json.dump(timeframe_results, f, indent=2)

    print(f"📊 Raw data saved to: {json_file}")


def main():
    """Main entry point for multi-timeframe scanner."""
    parser = argparse.ArgumentParser(description='Run portfolio scans across multiple timeframes')
    parser.add_argument('--end-date', '-e', type=str,
                        default='2025-07-10',
                        help='End date for all scans (YYYY-MM-DD). Default: 2025-07-10')
    parser.add_argument('--timeframes', '-t', type=str,
                        default='7,14,30,60',
                        help='Comma-separated list of timeframes in days. Default: 7,14,30,60')
    parser.add_argument('--symbols', '-s', type=str,
                        help='Comma-separated list of symbols. Default: MAG7+SPY')
    parser.add_argument('--delay', '-d', type=float, default=0.5,
                        help='Delay between scans in seconds. Default: 0.5')
    parser.add_argument('--output-dir', '-o', type=str,
                        default='.cache/multi_timeframe_scans',
                        help='Output directory for reports')
    parser.add_argument('--cache-only', '-c', action='store_true',
                        help='Use cached data only (no API calls)')
    parser.add_argument('--heat-threshold', '-ht', type=float,
                        help='Market heat threshold (default: -0.2)')

    args = parser.parse_args()

    # Parse timeframes
    timeframes = [int(t.strip()) for t in args.timeframes.split(',')]

    # Parse symbols if provided
    portfolio = None
    if args.symbols:
        portfolio = [s.strip().upper() for s in args.symbols.split(',')]

    # Generate date ranges
    date_ranges = get_timeframe_ranges(args.end_date, timeframes)

    print(f"\n🚀 Starting multi-timeframe scan")
    print(f"   End date: {args.end_date}")
    print(f"   Timeframes: {timeframes} days")
    print(f"   Portfolio: {portfolio or 'Default (MAG7+SPY)'}")
    print(f"   Cache-only mode: {'YES' if args.cache_only else 'NO'}")
    if not args.cache_only:
        print(f"   Delay between scans: {args.delay}s")

    # Run scans for each timeframe
    all_results = {}

    for label, start_date, end_date in date_ranges:
        print(f"\n\n{'#'*70}")
        print(f"# Timeframe: {label} ({start_date} to {end_date})")
        print(f"{'#'*70}")

        try:
            results = scan_date_range(start_date, end_date, portfolio, args.delay,
                                      args.cache_only, args.heat_threshold)
            all_results[label] = results

            # Print summary
            print(f"\n✅ {label} Summary:")
            print(f"   Days scanned: {results['days_scanned']}")
            print(f"   Total TA signals: {results['total_ta_signals']}")
            print(f"   Approved trades: {results['total_approved_trades']}")
            if results['market_heat_stats']['count'] > 0:
                print(f"   Avg market heat: {results['market_heat_stats'].get('avg', 0):.3f}")
                print(
                    f"   Days above heat threshold: {results['market_heat_stats']['above_threshold_days']}")

        except Exception as e:
            print(f"\n❌ ERROR in {label}: {e}")
            all_results[label] = {'error': str(e)}

    # Generate report
    print(f"\n\n{'='*70}")
    print("Generating consolidated report...")
    print(f"{'='*70}")

    generate_timeframe_report(all_results, args.output_dir)

    print("\n✅ Multi-timeframe scan complete!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
