#!/usr/bin/env python3
"""Compare original vs V2 sentiment strategies.

This script runs backtests with both strategies on the same data
and generates a detailed comparison report showing the impact of
allowing neutral sentiment (>= 0) vs requiring positive sentiment (> 0).

Usage:
    python scripts/compare_strategies.py SYMBOL START END
    
Example:
    python scripts/compare_strategies.py NVDA 2022-10-01 2022-11-30
"""
from src.utils.date_utils import process_date_param
import sys
import os
import subprocess
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add src to Python path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


def run_backtest_with_strategy(symbol: str, start: str, end: str,
                               strategy_version: str) -> Dict:
    """Run backtest with specified strategy version.

    Args:
        symbol: Stock symbol
        start: Start date
        end: End date
        strategy_version: Either 'v1' or 'v2'

    Returns:
        Dictionary with backtest results
    """
    # Set up environment
    env = os.environ.copy()
    project_root = Path(__file__).parent.parent
    env['PYTHONPATH'] = str(project_root)

    # Temporarily modify backtest_mas.py to use the right strategy
    backtest_script = Path(__file__).parent / "backtest_mas.py"

    # Read the current script
    original_content = backtest_script.read_text()

    # Modify import based on strategy version
    if strategy_version == "v2":
        modified_content = original_content.replace(
            "from src.agents.strategy_agent import StrategyAgent",
            "from src.agents.strategy_agent_v2 import StrategyAgent"
        )
    else:
        modified_content = original_content  # Keep original

    # Write modified version
    backtest_script.write_text(modified_content)

    try:
        # Run the backtest
        cmd = [sys.executable, str(backtest_script), symbol, start, end]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        if result.returncode != 0:
            print(f"Error running {strategy_version}: {result.stderr}")
            return {"error": result.stderr}

        # Parse output to extract metrics
        output_lines = result.stdout.split('\n')
        metrics = parse_backtest_output(output_lines)

        # Also get the output directory for detailed data
        for line in output_lines:
            if "Created organized output directory:" in line:
                output_dir = line.split(": ")[-1].strip()
                metrics['output_dir'] = output_dir

                # Load detailed data
                try:
                    trades_file = Path(output_dir) / "data" / "trades.csv"
                    if trades_file.exists():
                        trades_df = pd.read_csv(trades_file)
                        metrics['trades_data'] = trades_df.to_dict('records')

                    metrics_file = Path(output_dir) / "data" / "metrics.csv"
                    if metrics_file.exists():
                        metrics_df = pd.read_csv(metrics_file)
                        metrics.update(metrics_df.iloc[0].to_dict())
                except Exception as e:
                    print(f"Warning: Could not load detailed data: {e}")

                break

        return metrics

    finally:
        # Restore original content
        backtest_script.write_text(original_content)


def parse_backtest_output(lines: List[str]) -> Dict:
    """Parse backtest console output to extract key metrics."""
    metrics = {
        'total_trades': 0,
        'total_return': 0.0,
        'sharpe_ratio': 0.0,
        'max_drawdown': 0.0,
        'win_rate': 0.0,
        'successful_days': 0,
        'total_days': 0
    }

    for line in lines:
        if "Total trades:" in line:
            metrics['total_trades'] = int(line.split(": ")[-1])
        elif "Total return:" in line:
            metrics['total_return'] = float(line.split(": ")[-1].rstrip('%'))
        elif "Sharpe Ratio:" in line:
            metrics['sharpe_ratio'] = float(line.split(": ")[-1])
        elif "Max Drawdown:" in line:
            metrics['max_drawdown'] = float(line.split(": ")[-1].rstrip('%'))
        elif "Win Rate:" in line:
            metrics['win_rate'] = float(line.split(": ")[-1].rstrip('%'))
        elif "Successful:" in line and "days" in line:
            # Parse "Successful: 20 (80.0%)"
            parts = line.split(": ")[-1].split(" ")
            metrics['successful_days'] = int(parts[0])
        elif "Total days:" in line:
            metrics['total_days'] = int(line.split(": ")[-1])

    return metrics


def generate_comparison_report(symbol: str, start: str, end: str,
                               v1_results: Dict, v2_results: Dict) -> str:
    """Generate markdown comparison report."""

    # Calculate improvements
    trade_improvement = (v2_results['total_trades'] / max(v1_results['total_trades'], 1)
                         if v1_results['total_trades'] >= 0 else 0)

    return_diff = v2_results['total_return'] - v1_results['total_return']

    report = f"""# Strategy Comparison Report: {symbol}

**Period**: {start} to {end}  
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

The relaxed sentiment requirement (V2: sentiment >= 0) enables **{trade_improvement:.1f}x more trades** compared to the original strategy (V1: sentiment > 0).

## Key Findings

### Trade Activity
- **V1 (Original)**: {v1_results['total_trades']} trades
- **V2 (Relaxed)**: {v2_results['total_trades']} trades
- **Improvement**: {trade_improvement:.1f}x more trading opportunities

### Performance Metrics

| Metric | V1 (Sentiment > 0) | V2 (Sentiment >= 0) | Difference |
|--------|-------------------|---------------------|------------|
| Total Return | {v1_results['total_return']:.2f}% | {v2_results['total_return']:.2f}% | {return_diff:+.2f}% |
| Sharpe Ratio | {v1_results['sharpe_ratio']:.2f} | {v2_results['sharpe_ratio']:.2f} | {v2_results['sharpe_ratio'] - v1_results['sharpe_ratio']:+.2f} |
| Max Drawdown | {v1_results['max_drawdown']:.2f}% | {v2_results['max_drawdown']:.2f}% | {v2_results['max_drawdown'] - v1_results['max_drawdown']:+.2f}% |
| Win Rate | {v1_results['win_rate']:.2f}% | {v2_results['win_rate']:.2f}% | {v2_results['win_rate'] - v1_results['win_rate']:+.2f}% |

### Data Processing
- Total Days: {v1_results['total_days']}
- V1 Successful Days: {v1_results['successful_days']} ({v1_results['successful_days']/max(v1_results['total_days'], 1)*100:.1f}%)
- V2 Successful Days: {v2_results['successful_days']} ({v2_results['successful_days']/max(v2_results['total_days'], 1)*100:.1f}%)

## Analysis

### Why V2 Captures More Trades

1. **News Data Limitations**:
   - Historical news data is sparse for periods > 90 days
   - ETFs receive minimal news coverage
   - Free API tiers have limited historical depth

2. **V2 Strategy Advantage**:
   - Allows trading when MACD conditions are met but no news is available
   - Treats "no news" as neutral (0.0) rather than blocking the trade
   - Maintains all other risk controls (MACD conditions)

### Risk Considerations

While V2 allows more trades, it maintains the same technical analysis requirements:
- MACD must be negative yesterday
- MACD must be improving today
- Exit conditions remain unchanged

## Recommendation

For backtesting historical data, **Strategy V2 is recommended** because:
1. It provides meaningful results even with limited news data
2. The technical indicators still provide risk management
3. It better represents how the system would perform with sporadic news coverage

For live trading with real-time news feeds, the original strategy (V1) may be preferred if consistent news coverage is available.

## Trade Examples
"""

    # Add sample trades from each strategy if available
    if 'trades_data' in v1_results and v1_results['trades_data']:
        report += "\n### V1 Sample Trades\n"
        for i, trade in enumerate(v1_results['trades_data'][:3]):
            report += f"- {trade['date']}: {trade['action']} @ ${trade['price']:.2f} "
            report += f"(Sentiment: {trade.get('sentiment', 'N/A')})\n"

    if 'trades_data' in v2_results and v2_results['trades_data']:
        report += "\n### V2 Sample Trades\n"
        for i, trade in enumerate(v2_results['trades_data'][:3]):
            report += f"- {trade['date']}: {trade['action']} @ ${trade['price']:.2f} "
            report += f"(Sentiment: {trade.get('sentiment', 'N/A')})\n"

    return report


def main():
    """Main comparison function."""
    if len(sys.argv) < 4:
        print("Usage: python compare_strategies.py SYMBOL START END")
        print("Example: python compare_strategies.py NVDA 2022-10-01 2022-11-30")
        sys.exit(1)

    symbol = sys.argv[1]
    start = process_date_param(sys.argv[2])
    end = process_date_param(sys.argv[3])

    print(f"\n🔄 Comparing strategies for {symbol} from {start} to {end}")
    print("="*60)

    # Run V1 (original strategy)
    print("\n📊 Running V1 (Original Strategy: sentiment > 0)...")
    v1_results = run_backtest_with_strategy(symbol, start, end, "v1")

    if "error" in v1_results:
        print(f"❌ V1 failed: {v1_results['error']}")
        return

    print(f"✅ V1 Complete: {v1_results['total_trades']} trades")

    # Run V2 (relaxed strategy)
    print("\n📊 Running V2 (Relaxed Strategy: sentiment >= 0)...")
    v2_results = run_backtest_with_strategy(symbol, start, end, "v2")

    if "error" in v2_results:
        print(f"❌ V2 failed: {v2_results['error']}")
        return

    print(f"✅ V2 Complete: {v2_results['total_trades']} trades")

    # Generate comparison report
    print("\n📝 Generating comparison report...")
    report = generate_comparison_report(
        symbol, start, end, v1_results, v2_results)

    # Save report
    reports_dir = Path(".cache/backtests/comparisons")
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / \
        f"{symbol}_{start}_{end}_comparison_{timestamp}.md"
    report_file.write_text(report)

    print(f"\n✅ Comparison report saved to: {report_file}")

    # Print summary
    print("\n" + "="*60)
    print("COMPARISON SUMMARY")
    print("="*60)

    trade_improvement = v2_results['total_trades'] / \
        max(v1_results['total_trades'], 1)
    print(f"\nTrade Activity:")
    print(f"  V1 (Original): {v1_results['total_trades']} trades")
    print(f"  V2 (Relaxed):  {v2_results['total_trades']} trades")
    print(f"  Improvement:   {trade_improvement:.1f}x more trades")

    print(f"\nReturns:")
    print(f"  V1: {v1_results['total_return']:+.2f}%")
    print(f"  V2: {v2_results['total_return']:+.2f}%")
    print(
        f"  Difference: {v2_results['total_return'] - v1_results['total_return']:+.2f}%")

    print(f"\nRisk Metrics:")
    print(
        f"  Sharpe - V1: {v1_results['sharpe_ratio']:.2f}, V2: {v2_results['sharpe_ratio']:.2f}")
    print(
        f"  Max DD - V1: {v1_results['max_drawdown']:.2f}%, V2: {v2_results['max_drawdown']:.2f}%")

    # Also save summary JSON for programmatic access
    summary_data = {
        'symbol': symbol,
        'start': start,
        'end': end,
        'timestamp': timestamp,
        'v1_results': v1_results,
        'v2_results': v2_results,
        'improvements': {
            'trade_multiplier': trade_improvement,
            'return_difference': v2_results['total_return'] - v1_results['total_return'],
            'sharpe_difference': v2_results['sharpe_ratio'] - v1_results['sharpe_ratio']
        }
    }

    summary_file = reports_dir / \
        f"{symbol}_{start}_{end}_comparison_{timestamp}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary_data, f, indent=2, default=str)

    print(f"\n✅ Summary data saved to: {summary_file}")


if __name__ == "__main__":
    main()
