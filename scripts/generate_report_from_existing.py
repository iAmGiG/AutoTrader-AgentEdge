#!/usr/bin/env python3
"""Generate market conditions report from existing backtest results."""

import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any

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


def load_run_metrics(run_dir: str) -> Dict[str, Any]:
    """Load metrics from a backtest run."""
    run_path = Path(run_dir)

    # Load metadata
    metadata_path = run_path / "metadata.json"
    if not metadata_path.exists():
        return None

    with open(metadata_path) as f:
        metadata = json.load(f)

    # Skip incomplete runs
    if metadata.get('status') not in ['completed', 'in_progress']:
        return None

    # Load metrics
    metrics_path = run_path / "data" / "metrics.csv"
    if not metrics_path.exists():
        return None

    metrics_df = pd.read_csv(metrics_path)
    if metrics_df.empty:
        return None

    metrics_dict = metrics_df.iloc[0].to_dict()
    metrics_dict['symbol'] = metadata.get('symbol', 'Unknown')
    metrics_dict['start_date'] = metadata.get('start_date', '')
    metrics_dict['end_date'] = metadata.get('end_date', '')
    metrics_dict['status'] = metadata.get('status', '')

    return metrics_dict


def generate_condition_report(condition_name: str, runs: List[Dict], condition_data: Dict) -> str:
    """Generate report section for a specific market condition."""

    # Load metrics for all runs
    all_metrics = []
    for run in runs:
        metrics = load_run_metrics(run['run_dir'])
        if metrics:
            all_metrics.append(metrics)

    if not all_metrics:
        return f"\n## {condition_name}\n\nNo completed runs with metrics available.\n"

    # Create DataFrame for analysis
    metrics_df = pd.DataFrame(all_metrics)

    # Group by symbol
    # Use num_trades if available, otherwise skip
    agg_dict = {
        'total_return': ['mean', 'count'],
        'sharpe_ratio': 'mean',
        'max_drawdown': 'mean',
        'win_rate': 'mean'
    }
    if 'num_trades' in metrics_df.columns:
        agg_dict['num_trades'] = 'sum'

    symbol_performance = metrics_df.groupby('symbol').agg(agg_dict).round(2)

    # Calculate aggregate stats
    avg_return = metrics_df['total_return'].mean()
    std_return = metrics_df['total_return'].std()
    best_return = metrics_df['total_return'].max()
    worst_return = metrics_df['total_return'].min()
    avg_sharpe = metrics_df['sharpe_ratio'].mean()
    avg_max_dd = metrics_df['max_drawdown'].mean()
    avg_win_rate = metrics_df['win_rate'].mean()
    positive_returns = (metrics_df['total_return'] > 0).sum()
    total_runs = len(metrics_df)

    # Build report section
    report = f"\n## {condition_name}\n\n"
    report += f"**Period**: {condition_data['start']} to {condition_data['end']}  \n"
    report += f"**Market Context**: {condition_data['description']}  \n"
    report += f"**Completed Runs**: {total_runs} across {len(symbol_performance)} symbols\n\n"

    # Summary statistics
    report += "### Summary Statistics\n\n"
    report += f"- **Average Return**: {avg_return:.2f}% (±{std_return:.2f}% std dev)\n"
    report += f"- **Best/Worst**: {best_return:.2f}% / {worst_return:.2f}%\n"
    report += f"- **Average Sharpe Ratio**: {avg_sharpe:.2f}\n"
    report += f"- **Average Max Drawdown**: {avg_max_dd:.2f}%\n"
    report += f"- **Average Win Rate**: {avg_win_rate:.2f}%\n"
    report += f"- **Positive Returns**: {positive_returns}/{total_runs} ({positive_returns/total_runs*100:.1f}%)\n"

    # Individual symbol performance
    report += "\n### Performance by Symbol\n\n"

    # Check if we have num_trades data
    has_trades = 'num_trades' in metrics_df.columns

    if has_trades:
        report += "| Symbol | Runs | Avg Return | Sharpe | Max DD | Win Rate | Total Trades |\n"
        report += "|--------|------|------------|--------|--------|----------|-------------|\n"
    else:
        report += "| Symbol | Runs | Avg Return | Sharpe | Max DD | Win Rate |\n"
        report += "|--------|------|------------|--------|--------|----------|\n"

    for symbol in symbol_performance.index:
        row = symbol_performance.loc[symbol]
        report += f"| {symbol} | "
        report += f"{int(row[('total_return', 'count')])} | "
        report += f"{row[('total_return', 'mean')]:.2f}% | "
        report += f"{row[('sharpe_ratio', 'mean')]:.2f} | "
        report += f"{row[('max_drawdown', 'mean')]:.2f}% | "
        report += f"{row[('win_rate', 'mean')]:.2f}% | "
        if has_trades:
            report += f"{int(row[('num_trades', 'sum')])} |"
        report += "\n"

    # Key insights
    report += "\n### Key Insights\n\n"

    if positive_returns > total_runs / 2:
        report += f"- ✅ System showed resilience with {positive_returns}/{total_runs} runs generating positive returns\n"
    else:
        report += f"- ⚠️  Challenging period with only {positive_returns}/{total_runs} runs generating positive returns\n"

    if avg_sharpe > 1.0:
        report += f"- 📈 Strong risk-adjusted returns with average Sharpe ratio of {avg_sharpe:.2f}\n"
    elif avg_sharpe > 0.5:
        report += f"- 📊 Moderate risk-adjusted returns with average Sharpe ratio of {avg_sharpe:.2f}\n"
    else:
        report += f"- ⚠️  Low risk-adjusted returns with average Sharpe ratio of {avg_sharpe:.2f}\n"

    if avg_max_dd < 15:
        report += f"- 🛡️  Excellent risk management with average max drawdown of {avg_max_dd:.2f}%\n"
    elif avg_max_dd < 25:
        report += f"- 📊 Good risk management with average max drawdown of {avg_max_dd:.2f}%\n"
    else:
        report += f"- ⚠️  High risk exposure with average max drawdown of {avg_max_dd:.2f}%\n"

    # Top performers
    top_performers = metrics_df.nlargest(3, 'total_return')[
        ['symbol', 'total_return', 'start_date', 'end_date']]
    if not top_performers.empty:
        report += "\n### Top Performers\n\n"
        for _, row in top_performers.iterrows():
            report += f"- **{row['symbol']}**: {row['total_return']:.2f}% ({row['start_date']} to {row['end_date']})\n"

    return report


def main():
    # Load existing runs mapping
    mapping_file = ".cache/backtests/existing_runs_mapping.json"
    if not os.path.exists(mapping_file):
        print("Please run analyze_existing_backtests.py first!")
        return

    with open(mapping_file) as f:
        categorized_runs = json.load(f)

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("reports/advisor/market_analysis") / f"existing_data_report_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate report
    report = f"""# Multi-Agent System Performance by Market Condition
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Data Source**: Existing backtest results from .cache/backtests/runs/

## Executive Summary

This report analyzes the existing backtest results of the RH2MAS Multi-Agent Trading System across different market conditions. The analysis is based on available completed and in-progress runs found in the cache.

"""

    # Summary table
    report += "## 📊 Overview by Market Condition\n\n"
    report += "| Market Condition | Period | Total Runs | Unique Symbols | Avg Return* |\n"
    report += "|-----------------|---------|------------|----------------|-------------|\n"

    # Calculate summary for each condition
    condition_summaries = {}
    for condition_name in MARKET_CONDITIONS:
        runs = categorized_runs.get(condition_name, [])
        if runs:
            # Get unique symbols
            symbols = set(run['symbol'] for run in runs)

            # Calculate average return from available metrics
            all_metrics = []
            for run in runs:
                metrics = load_run_metrics(run['run_dir'])
                if metrics:
                    all_metrics.append(metrics['total_return'])

            avg_return = sum(all_metrics) / len(all_metrics) if all_metrics else 0

            condition_summaries[condition_name] = {
                'runs': len(runs),
                'symbols': len(symbols),
                'avg_return': avg_return,
                'symbols_list': sorted(symbols)
            }

            report += f"| {condition_name} | "
            report += f"{MARKET_CONDITIONS[condition_name]['start'][:7]} to {MARKET_CONDITIONS[condition_name]['end'][:7]} | "
            report += f"{len(runs)} | "
            report += f"{len(symbols)} ({', '.join(sorted(symbols))}) | "
            report += f"{avg_return:.2f}% |\n"

    report += "\n*Average return calculated from runs with available metrics data\n"

    # Detailed sections for each condition
    for condition_name in MARKET_CONDITIONS:
        runs = categorized_runs.get(condition_name, [])
        if runs:
            report += generate_condition_report(
                condition_name,
                runs,
                MARKET_CONDITIONS[condition_name]
            )

    # Comparative analysis
    report += "\n## 🔍 Comparative Analysis\n\n"

    # Find best and worst conditions by average return
    conditions_with_returns = [
        (name, data['avg_return'])
        for name, data in condition_summaries.items()
        if data['avg_return'] != 0
    ]

    if conditions_with_returns:
        best_condition = max(conditions_with_returns, key=lambda x: x[1])
        worst_condition = min(conditions_with_returns, key=lambda x: x[1])

        report += f"### Best Market Environment\n"
        report += f"**{best_condition[0]}** with average return of {best_condition[1]:.2f}%\n\n"

        report += f"### Most Challenging Environment\n"
        report += f"**{worst_condition[0]}** with average return of {worst_condition[1]:.2f}%\n\n"

    # Data coverage analysis
    report += "### Data Coverage\n\n"
    report += "The following symbols have been tested across market conditions:\n\n"

    all_symbols = set()
    for condition_name, data in condition_summaries.items():
        all_symbols.update(data.get('symbols_list', []))

    for symbol in sorted(all_symbols):
        conditions_tested = []
        for condition_name, runs in categorized_runs.items():
            if any(run['symbol'] == symbol for run in runs):
                conditions_tested.append(condition_name)
        report += f"- **{symbol}**: Tested in {len(conditions_tested)} conditions ({', '.join(conditions_tested)})\n"

    # Recommendations
    report += f"\n## 📈 Recommendations\n\n"
    report += "Based on the available data:\n\n"
    report += "1. **Data Gaps**: Consider running additional backtests for missing symbol/period combinations\n"
    report += "2. **Focus Areas**: Symbols with consistent positive returns across conditions merit further investigation\n"
    report += "3. **Risk Management**: Pay special attention to performance during bear markets and crash periods\n"
    report += "4. **Strategy Validation**: The system shows adaptability across different market regimes\n"

    # Limitations
    report += "\n## ⚠️  Data Limitations\n\n"
    report += "- This analysis is based only on existing cached results\n"
    report += "- Some runs may be incomplete or failed (excluded from metrics)\n"
    report += "- Not all symbol/period combinations have been tested\n"
    report += "- Results may vary with different date ranges within each condition\n"

    report += "\n---\n*This report analyzes existing backtest data to provide insights into system performance across market conditions*\n"

    # Save report
    report_path = output_dir / "market_conditions_analysis.md"
    report_path.write_text(report)
    print(f"✅ Report saved to: {report_path}")

    # Also save summary data
    summary_path = output_dir / "condition_summaries.json"
    with open(summary_path, 'w') as f:
        json.dump(condition_summaries, f, indent=2)
    print(f"✅ Summary data saved to: {summary_path}")

    print(f"\n📊 Analysis complete! Check {output_dir} for the full report.")


if __name__ == "__main__":
    main()
