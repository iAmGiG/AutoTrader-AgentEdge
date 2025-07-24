#!/usr/bin/env python3
"""Daily portfolio scanner using Option 1 mechanical strategy.

This script:
1. Scans portfolio for TA signals (MACD histogram entries)
2. Calculates market heat score
3. Applies mechanical filter (TA signal AND market heat > 0.3)
4. Outputs approved trades and saves results to CSV
"""

import sys
import os
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.agents.tech_agent import TechAgent as TechnicalAgent
from src.agents.sentiment_agent import SentimentAgent
from src.agents.strategy_agent import StrategyAgent


def save_scan_results(date: str, ta_signals: dict, market_heat: dict, approved: list, output_dir: str = ".cache/daily_scans"):
    """Save scan results to CSV for tracking.

    :param date: Scan date
    :param ta_signals: TA scan results
    :param market_heat: Market heat analysis
    :param approved: Approved trades after filtering
    :param output_dir: Directory to save results
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Save to daily CSV file
    csv_file = f"{output_dir}/scan_{date}.csv"

    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Symbol', 'TA_Signal', 'Signal_Strength',
                        'Market_Heat', 'Approved', 'Reason'])

        # Write all TA signals with approval status
        for signal in ta_signals.get('entries', []):
            symbol = signal['symbol']
            approved_symbols = [a['symbol'] for a in approved]
            is_approved = symbol in approved_symbols

            writer.writerow([
                date,
                symbol,
                'BUY',  # TA signals are entry signals
                signal.get('signal_strength', 0),
                market_heat.get('heat_level', 0),
                'YES' if is_approved else 'NO',
                f"Market heat {market_heat.get('heat_level', 0):.3f} {'>' if is_approved else '<='} 0.3"
            ])

    # Also save summary JSON
    summary_file = f"{output_dir}/scan_{date}_summary.json"
    summary = {
        'date': date,
        'market_heat': market_heat,
        'ta_signals': ta_signals,
        'approved_trades': approved,
        'statistics': {
            'total_ta_signals': len(ta_signals.get('entries', [])),
            'approved_count': len(approved),
            'approval_rate': len(approved) / len(ta_signals.get('entries', [])) if ta_signals.get('entries') else 0
        }
    }

    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to:")
    print(f"  CSV: {csv_file}")
    print(f"  Summary: {summary_file}")


def run_daily_scan(scan_date: str = None, portfolio: list = None, cache_only: bool = False, heat_threshold: float = None):
    """Run daily portfolio scan with mechanical strategy.

    :param scan_date: Date to scan (YYYY-MM-DD format). If None, uses most recent market day.
    :param portfolio: List of symbols to scan. If None, uses default portfolio.
    :param cache_only: If True, only use cached data (no API calls)
    :param heat_threshold: Override market heat threshold (default: use StrategyAgent default)
    :return: Dictionary with scan results
    """
    # Default portfolio (MAG7 + SPY)
    if portfolio is None:
        portfolio = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "SPY"]

    # Use provided date or most recent market day
    if scan_date is None:
        # For testing, use a date we likely have cached data for
        scan_date = "2025-07-10"  # Recent date that should have cached data
        print(f"Using cached data date: {scan_date}")

    print(f"\n{'='*60}")
    print(f"Daily Portfolio Scan - {scan_date}")
    print(f"{'='*60}")
    print(f"Portfolio: {', '.join(portfolio)}")

    # Initialize agents
    print("\nInitializing agents...")
    if cache_only:
        print("🔒 Running in CACHE-ONLY mode - no API calls will be made")
        # Set environment variable to force cache-only mode
        import os
        os.environ['CACHE_ONLY_MODE'] = 'true'

    ta = TechnicalAgent(name="TechnicalAgent")
    sa = SentimentAgent(name="SentimentAgent")
    strategy = StrategyAgent(name="StrategyAgent")

    # Override heat threshold if provided
    if heat_threshold is not None:
        strategy.market_heat_threshold = heat_threshold
        print(f"📊 Using market heat threshold: {heat_threshold}")

    # 1. Run TA scan for portfolio
    print(f"\n1. Scanning {len(portfolio)} stocks for TA signals...")
    try:
        ta_signals = ta.scan_stocks_sync(portfolio, scan_date)
        print(f"   Found {len(ta_signals.get('entries', []))} stocks with TA entry signals")
        for entry in ta_signals.get('entries', []):
            print(f"   - {entry['symbol']}: Signal strength {entry.get('signal_strength', 0):.3f}")
    except Exception as e:
        print(f"   ERROR in TA scan: {e}")
        ta_signals = {'entries': [], 'errors': [str(e)]}

    # 2. Calculate market heat
    print(f"\n2. Analyzing market heat...")
    try:
        market_heat_result = sa.analyze_market_heat(scan_date)
        market_heat = market_heat_result.get('heat_level', 0)
        print(
            f"   Market Heat: {market_heat:.3f} ({market_heat_result.get('heat_description', 'Unknown')})")
        print(f"   Components:")
        for component, value in market_heat_result.get('components', {}).items():
            if isinstance(value, (int, float)):
                print(f"   - {component}: {value:.3f}")
            else:
                print(f"   - {component}: {value}")
    except Exception as e:
        print(f"   ERROR calculating market heat: {e}")
        market_heat_result = {'heat_level': 0, 'heat_description': 'Error', 'error': str(e)}
        market_heat = 0

    # 3. Apply strategy filter to each TA signal
    print(f"\n3. Applying mechanical filter (TA signal AND market heat > 0.3)...")
    approved_trades = []

    for signal in ta_signals.get('entries', []):
        # Create a TA signal dict for the filter
        ta_signal_dict = {
            'action': 'BUY',  # All entries from scan are BUY signals
            'symbol': signal['symbol'],
            'signal_strength': signal.get('signal_strength', 0)
        }

        # Apply filter
        filtered = strategy.filter_trades(ta_signal_dict, market_heat)

        if filtered['approved']:
            approved_trades.append({
                'symbol': signal['symbol'],
                'action': 'BUY',
                'signal_strength': signal.get('signal_strength', 0),
                'market_heat': market_heat,
                'reason': filtered['reason']
            })
            print(f"   ✓ {signal['symbol']} - APPROVED: {filtered['reason']}")
        else:
            print(f"   ✗ {signal['symbol']} - REJECTED: {filtered['reason']}")

    # 4. Output summary
    print(f"\n{'='*60}")
    print("SCAN SUMMARY")
    print(f"{'='*60}")
    print(f"Date: {scan_date}")
    print(f"Portfolio Size: {len(portfolio)} stocks")
    print(
        f"Market Heat: {market_heat:.3f} {'(Above threshold)' if market_heat > 0.3 else '(Below threshold)'}")
    print(f"TA Signals Found: {len(ta_signals.get('entries', []))}")
    print(f"Approved Trades: {len(approved_trades)}")

    if approved_trades:
        print(f"\nApproved Trades:")
        for trade in approved_trades:
            print(f"  - {trade['symbol']}: BUY (Signal: {trade['signal_strength']:.3f})")
    else:
        print(f"\nNo trades approved for today.")

    # 5. Save results
    save_scan_results(scan_date, ta_signals, market_heat_result, approved_trades)

    # Get strategy decision summary
    if hasattr(strategy, 'print_decision_summary'):
        print("")
        strategy.print_decision_summary()

    return {
        'date': scan_date,
        'portfolio': portfolio,
        'ta_signals': ta_signals,
        'market_heat': market_heat_result,
        'approved_trades': approved_trades
    }


def main():
    """Main entry point for daily scanner."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run daily portfolio scan with mechanical strategy')
    parser.add_argument('--date', '-d', type=str,
                        help='Scan date (YYYY-MM-DD). Default: 2025-07-10 (cached)')
    parser.add_argument('--symbols', '-s', type=str,
                        help='Comma-separated list of symbols. Default: MAG7+SPY')
    parser.add_argument('--cache-only', '-c', action='store_true',
                        help='Use cached data only (no API calls)')
    parser.add_argument('--heat-threshold', '-t', type=float,
                        help='Market heat threshold (default: -0.2)')

    args = parser.parse_args()

    # Parse symbols if provided
    portfolio = None
    if args.symbols:
        portfolio = [s.strip().upper() for s in args.symbols.split(',')]

    # Run scan
    results = run_daily_scan(scan_date=args.date, portfolio=portfolio,
                             cache_only=args.cache_only, heat_threshold=args.heat_threshold)

    return 0 if results['approved_trades'] else 1


if __name__ == "__main__":
    sys.exit(main())
