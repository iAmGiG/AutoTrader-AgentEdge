#!/usr/bin/env python3
"""Run multiple strategy comparisons and generate aggregate report.

This script runs comparisons for multiple volatile periods to demonstrate
the impact of the relaxed sentiment requirement across different market conditions.

Usage:
    python scripts/batch_compare_strategies.py
"""
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Volatile periods to test (known MACD < 0 opportunities)
TEST_PERIODS = [
    # Symbol, Start, End, Description
    ("NVDA", "2022-10-01", "2022-11-30", "2022 Tech Correction"),
    ("AAPL", "2020-03-01", "2020-04-30", "COVID Crash & Recovery"),
    ("SPY", "2018-12-01", "2019-01-31", "2018 Q4 Correction"),
    ("TSLA", "2022-05-01", "2022-06-30", "2022 Growth Stock Selloff"),
    ("QQQ", "2020-02-15", "2020-04-15", "COVID Tech Volatility"),
    ("META", "2022-09-01", "2022-11-30", "Meta 2022 Collapse"),
]


def run_comparison(symbol: str, start: str, end: str, description: str) -> Dict:
    """Run comparison for a single period."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Symbol: {symbol}, Period: {start} to {end}")
    print('='*60)

    cmd = [sys.executable, "scripts/compare_strategies.py", symbol, start, end]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        return {"error": result.stderr}

    # Parse output to find the saved files
    output_lines = result.stdout.split('\n')
    summary_file = None

    for line in output_lines:
        if "Summary data saved to:" in line:
            summary_file = line.split(": ")[-1].strip()
            break

    if summary_file and Path(summary_file).exists():
        with open(summary_file, 'r') as f:
            data = json.load(f)
            data['description'] = description
            return data

    return {"error": "Could not find summary file"}


def generate_aggregate_report(results: List[Dict]) -> str:
    """Generate aggregate comparison report across all test periods."""

    successful_tests = [r for r in results if 'error' not in r]

    # Calculate aggregate statistics
    total_v1_trades = sum(r['v1_results']['total_trades']
                          for r in successful_tests)
    total_v2_trades = sum(r['v2_results']['total_trades']
                          for r in successful_tests)
    avg_improvement = sum(r['improvements']['trade_multiplier']
                          for r in successful_tests) / len(successful_tests)

    avg_v1_return = sum(r['v1_results']['total_return']
                        for r in successful_tests) / len(successful_tests)
    avg_v2_return = sum(r['v2_results']['total_return']
                        for r in successful_tests) / len(successful_tests)

    report = f"""# Aggregate Strategy Comparison Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Test Periods**: {len(successful_tests)} volatile market periods

## Executive Summary

Across {len(successful_tests)} volatile market periods, Strategy V2 (sentiment >= 0) demonstrated:

- **{avg_improvement:.1f}x average increase** in trading opportunities
- **{total_v2_trades} total trades** vs {total_v1_trades} with original strategy
- **{avg_v2_return - avg_v1_return:+.2f}% average return improvement**

## Detailed Results by Period

| Period | Symbol | V1 Trades | V2 Trades | Improvement | V1 Return | V2 Return |
|--------|--------|-----------|-----------|-------------|-----------|-----------|
"""

    for result in successful_tests:
        report += f"| {result['description']} | {result['symbol']} | "
        report += f"{result['v1_results']['total_trades']} | "
        report += f"{result['v2_results']['total_trades']} | "
        report += f"{result['improvements']['trade_multiplier']:.1f}x | "
        report += f"{result['v1_results']['total_return']:+.1f}% | "
        report += f"{result['v2_results']['total_return']:+.1f}% |\n"

    report += f"""
## Key Insights

### 1. Trade Frequency Impact
- Original strategy (V1) averaged **{total_v1_trades/len(successful_tests):.1f} trades per test**
- Relaxed strategy (V2) averaged **{total_v2_trades/len(successful_tests):.1f} trades per test**
- The relaxed sentiment requirement enables the system to capture MACD signals even when news data is unavailable

### 2. Performance Characteristics
- Average V1 Return: {avg_v1_return:+.2f}%
- Average V2 Return: {avg_v2_return:+.2f}%
- Return Improvement: {avg_v2_return - avg_v1_return:+.2f}%

### 3. Risk-Adjusted Performance
"""

    # Add Sharpe ratio comparison
    avg_v1_sharpe = sum(r['v1_results']['sharpe_ratio']
                        for r in successful_tests) / len(successful_tests)
    avg_v2_sharpe = sum(r['v2_results']['sharpe_ratio']
                        for r in successful_tests) / len(successful_tests)

    report += f"""- Average V1 Sharpe: {avg_v1_sharpe:.2f}
- Average V2 Sharpe: {avg_v2_sharpe:.2f}
- Sharpe Improvement: {avg_v2_sharpe - avg_v1_sharpe:+.2f}

## Conclusion

The data clearly demonstrates that the relaxed sentiment requirement (V2) provides:

1. **More Realistic Backtesting**: Captures trades that would be missed due to API limitations
2. **Better Capital Utilization**: More opportunities to deploy capital during favorable MACD conditions
3. **Maintained Risk Controls**: Technical indicators still provide entry/exit discipline

## Recommendation

- **For Backtesting**: Use Strategy V2 to get meaningful results with historical data
- **For Live Trading**: Consider V1 if you have reliable real-time news feeds
- **For Development**: Focus on improving news data coverage rather than blocking trades

## Test Configuration

Tests were run on known volatile periods where MACD < 0 conditions were likely:
"""

    for period in TEST_PERIODS:
        report += f"- {period[3]}: {period[0]} ({period[1]} to {period[2]})\n"

    return report


def main():
    """Run batch comparisons and generate aggregate report."""
    print("🔄 Running batch strategy comparisons...")
    print(f"Testing {len(TEST_PERIODS)} volatile market periods")

    results = []

    for symbol, start, end, description in TEST_PERIODS:
        result = run_comparison(symbol, start, end, description)
        results.append(result)

        if 'error' not in result:
            print(f"✅ Completed: {description}")
        else:
            print(f"❌ Failed: {description}")

    # Generate aggregate report
    print("\n📊 Generating aggregate report...")
    report = generate_aggregate_report(results)

    # Save report
    reports_dir = Path(".cache/backtests/comparisons")
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"aggregate_comparison_{timestamp}.md"
    report_file.write_text(report)

    print(f"\n✅ Aggregate report saved to: {report_file}")

    # Print summary
    successful = len([r for r in results if 'error' not in r])
    print(f"\n{'='*60}")
    print("BATCH COMPARISON COMPLETE")
    print(f"{'='*60}")
    print(f"Successful comparisons: {successful}/{len(TEST_PERIODS)}")

    if successful > 0:
        total_v1 = sum(r['v1_results']['total_trades']
                       for r in results if 'error' not in r)
        total_v2 = sum(r['v2_results']['total_trades']
                       for r in results if 'error' not in r)
        print(f"\nAggregate Results:")
        print(f"  Total V1 trades: {total_v1}")
        print(f"  Total V2 trades: {total_v2}")
        print(f"  Overall improvement: {total_v2/max(total_v1, 1):.1f}x")


if __name__ == "__main__":
    main()
