#!/usr/bin/env python3
"""
Aggregate and analyze backtest results from multiple runs.

This script:
1. Reads all CSV files from the backtests directory
2. Calculates aggregate statistics across all tests
3. Compares strategy performance vs buy-and-hold
4. Identifies best and worst performing periods
5. Outputs a comprehensive summary report
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Tuple
import glob
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BacktestAggregator:
    """Aggregate and analyze backtest results."""

    def __init__(self, cache_dir: str = None):
        """Initialize aggregator with cache directory path."""
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), '..', '.cache', 'backtests')
        self.cache_dir = cache_dir
        self.trades_data = {}
        self.metrics_data = {}
        self.equity_data = {}

    def load_all_results(self) -> None:
        """Load all CSV files from the backtests directory."""
        print(f"Loading results from {self.cache_dir}")

        # Load trades files
        trades_files = glob.glob(os.path.join(self.cache_dir, "*trades*.csv"))
        for file in trades_files:
            symbol, dates = self._parse_filename(file, "trades")
            if symbol:
                df = pd.read_csv(file)
                self.trades_data[(symbol, dates)] = df
                print(f"  Loaded trades: {symbol} ({dates}) - {len(df)} trades")

        # Load metrics files
        metrics_files = glob.glob(os.path.join(self.cache_dir, "*metrics*.csv"))
        for file in metrics_files:
            symbol, dates = self._parse_filename(file, "metrics")
            if symbol:
                df = pd.read_csv(file)
                self.metrics_data[(symbol, dates)] = df

        # Load equity files
        equity_files = glob.glob(os.path.join(self.cache_dir, "*equity*.csv"))
        for file in equity_files:
            symbol, dates = self._parse_filename(file, "equity")
            if symbol:
                df = pd.read_csv(file)
                self.equity_data[(symbol, dates)] = df

        print(f"Loaded {len(self.trades_data)} trades files, {len(self.metrics_data)} metrics files, {len(self.equity_data)} equity files")

    def _parse_filename(self, filepath: str, file_type: str) -> Tuple[str, str]:
        """Parse symbol and dates from filename."""
        basename = os.path.basename(filepath)
        # Remove .csv extension
        basename_no_ext = basename.replace(".csv", "")

        # Find the file type suffix (_trades, _metrics, _equity)
        suffix = f"_{file_type}"
        if suffix in basename_no_ext:
            # Remove the suffix to get symbol_dates
            base_part = basename_no_ext.replace(suffix, "")

            # Split by first underscore to separate symbol from dates
            parts = base_part.split("_", 1)
            if len(parts) == 2:
                symbol = parts[0]
                dates = parts[1]
                return symbol, dates

        return None, None

    def calculate_aggregate_statistics(self) -> Dict:
        """Calculate aggregate statistics across all tests."""
        stats = {
            "total_tests": len(self.metrics_data),
            "total_trades": 0,
            "overall_win_rate": 0,
            "avg_return_per_trade": 0,
            "total_signals_generated": 0,
            "profitable_tests": 0,
            "best_performing_stock": None,
            "worst_performing_stock": None,
            "max_return": -float('inf'),
            "min_return": float('inf'),
            "worst_drawdown": 0,
            "avg_sharpe_ratio": 0,
            "by_symbol": {}
        }

        all_trades = []
        sharpe_ratios = []

        for (symbol, dates), metrics_df in self.metrics_data.items():
            if metrics_df.empty:
                continue

            metrics = metrics_df.iloc[0]

            # Update symbol-specific stats
            if symbol not in stats["by_symbol"]:
                stats["by_symbol"][symbol] = {
                    "total_trades": 0,
                    "total_return": 0,
                    "win_rate": 0,
                    "max_drawdown": 0,
                    "test_count": 0,
                    "profitable_tests": 0
                }

            stats["by_symbol"][symbol]["total_trades"] += metrics.get("num_trades", 0)
            stats["by_symbol"][symbol]["total_return"] += metrics.get("total_return_pct", 0)
            stats["by_symbol"][symbol]["max_drawdown"] = max(
                stats["by_symbol"][symbol]["max_drawdown"],
                metrics.get("max_drawdown_pct", 0)
            )
            stats["by_symbol"][symbol]["test_count"] += 1

            if metrics.get("total_return_pct", 0) > 0:
                stats["by_symbol"][symbol]["profitable_tests"] += 1
                stats["profitable_tests"] += 1

            # Update overall stats
            stats["total_trades"] += metrics.get("num_trades", 0)
            stats["worst_drawdown"] = max(stats["worst_drawdown"],
                                          metrics.get("max_drawdown_pct", 0))

            if metrics.get("sharpe_ratio", 0) != 0:
                sharpe_ratios.append(metrics.get("sharpe_ratio", 0))

            # Track best/worst performing
            return_pct = metrics.get("total_return_pct", 0)
            if return_pct > stats["max_return"]:
                stats["max_return"] = return_pct
                stats["best_performing_stock"] = f"{symbol} ({dates})"
            if return_pct < stats["min_return"]:
                stats["min_return"] = return_pct
                stats["worst_performing_stock"] = f"{symbol} ({dates})"

            # Collect trade-level data if available
            if (symbol, dates) in self.trades_data:
                trades_df = self.trades_data[(symbol, dates)]
                if not trades_df.empty:
                    all_trades.extend(trades_df.to_dict('records'))

        # Calculate aggregate metrics
        if all_trades:
            winning_trades = [t for t in all_trades if t.get("profit", 0) > 0]
            stats["overall_win_rate"] = len(winning_trades) / len(all_trades) * 100
            stats["avg_return_per_trade"] = np.mean([t.get("return", 0) for t in all_trades]) * 100

        if sharpe_ratios:
            stats["avg_sharpe_ratio"] = np.mean(sharpe_ratios)

        # Count total signals (look at equity files for days processed)
        for equity_df in self.equity_data.values():
            stats["total_signals_generated"] += len(equity_df) - 1  # Exclude initial row

        # Add actual trades count from trades files
        actual_trades_count = 0
        for trades_df in self.trades_data.values():
            if not trades_df.empty:
                actual_trades_count += len(trades_df)

        # Update total trades to reflect actual executed trades
        stats["total_trades"] = actual_trades_count

        return stats

    def calculate_buy_and_hold_comparison(self) -> Dict:
        """Calculate buy-and-hold returns for comparison."""
        bnh_results = {}

        for (symbol, dates), equity_df in self.equity_data.items():
            if equity_df.empty or len(equity_df) < 2:
                continue

            # Get first and last prices
            first_price = equity_df.iloc[0]["price"]
            last_price = equity_df.iloc[-1]["price"]

            # Calculate buy-and-hold return
            bnh_return = (last_price - first_price) / first_price * 100

            # Get strategy return from metrics
            strategy_return = 0
            if (symbol, dates) in self.metrics_data:
                metrics_df = self.metrics_data[(symbol, dates)]
                if not metrics_df.empty:
                    strategy_return = metrics_df.iloc[0].get("total_return_pct", 0)

            bnh_results[(symbol, dates)] = {
                "buy_and_hold_return": bnh_return,
                "strategy_return": strategy_return,
                "excess_return": strategy_return - bnh_return,
                "days": len(equity_df) - 1
            }

        return bnh_results

    def generate_summary_report(self, output_path: str = None) -> str:
        """Generate comprehensive summary report."""
        if output_path is None:
            output_path = os.path.join(self.cache_dir, "aggregate_summary.md")

        # Load all results
        self.load_all_results()

        # Calculate statistics
        stats = self.calculate_aggregate_statistics()
        bnh_comparison = self.calculate_buy_and_hold_comparison()

        # Generate report
        report = []
        report.append("# 📊 Multi-Agent System Backtest Results")
        report.append("\n---")
        report.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        report.append(f"**Strategy**: MACD Crossover with Sentiment Filter")
        report.append(f"**Total Tests**: {stats['total_tests']}")

        # Executive Summary
        report.append("\n## 📈 Executive Summary")

        # Create a summary box
        report.append("\n```")
        report.append(f"Tests Run:        {stats['total_tests']}")
        report.append(f"Trades Executed:  {int(stats['total_trades'])}")
        report.append(f"Win Rate:         {stats['overall_win_rate']:.1f}%")
        report.append(f"Avg Sharpe:       {stats['avg_sharpe_ratio']:.2f}")
        report.append(f"Max Drawdown:     {stats['worst_drawdown']:.2f}%")
        report.append(
            f"Success Rate:     {stats['profitable_tests']}/{stats['total_tests']} ({stats['profitable_tests']/stats['total_tests']*100:.1f}%)")
        report.append("```")

        # Overall Performance
        report.append("\n## 📊 Performance Metrics")
        report.append("\n### Key Statistics")
        report.append(f"- **Total Trades Executed**: {int(stats['total_trades'])}")
        report.append(f"- **Overall Win Rate**: {stats['overall_win_rate']:.1f}%")
        report.append(f"- **Average Return per Trade**: {stats['avg_return_per_trade']:.2f}%")
        report.append(f"- **Average Sharpe Ratio**: {stats['avg_sharpe_ratio']:.2f}")
        report.append(f"- **Worst Drawdown**: {stats['worst_drawdown']:.2f}%")
        report.append(f"- **Total Signals Generated**: {stats['total_signals_generated']}")
        report.append(
            f"- **Profitable Tests**: {stats['profitable_tests']}/{stats['total_tests']} ({stats['profitable_tests']/stats['total_tests']*100:.1f}%)")

        # Add trade analysis section
        if int(stats['total_trades']) > 0:
            report.append("\n### 📊 Trade Analysis")
            report.append(f"- **Total Completed Trades**: {int(stats['total_trades'])}")
            report.append(f"- **Win/Loss Ratio**: {stats['overall_win_rate']:.1f}% wins")
            report.append(f"- **Average P&L per Trade**: {stats['avg_return_per_trade']:.2f}%")
        else:
            report.append("\n### ⚠️ Trade Analysis")
            report.append("- **No completed trades in test period**")
            report.append("- Strategy is highly selective - MACD < 0 condition rarely met")

        # Best/Worst Performance with emojis
        report.append("\n## 🏆 Performance Rankings")

        # Determine status emoji based on return
        best_emoji = "🟢" if stats['max_return'] > 0 else "🔴"
        worst_emoji = "🟢" if stats['min_return'] > 0 else "🔴"

        report.append(f"\n### Best Performer")
        report.append(
            f"{best_emoji} **{stats['best_performing_stock']}**: {stats['max_return']:.2f}%")

        report.append(f"\n### Worst Performer")
        report.append(
            f"{worst_emoji} **{stats['worst_performing_stock']}**: {stats['min_return']:.2f}%")

        # Performance by Symbol
        if stats["by_symbol"]:
            report.append("\n---")
            report.append("\n## 📊 Detailed Performance by Symbol")
            report.append("\n<details>")
            report.append("<summary>Click to expand symbol-by-symbol analysis</summary>")
            report.append("\n")
            report.append("| Symbol | Status | Tests | Trades | Avg Return | Max DD | Success Rate |")
            report.append("|:-------|:------:|:-----:|:------:|:----------:|:------:|:------------:|")

            for symbol, symbol_stats in sorted(stats["by_symbol"].items()):
                avg_return = symbol_stats["total_return"] / symbol_stats["test_count"]
                profitable_pct = symbol_stats["profitable_tests"] / symbol_stats["test_count"] * 100

                # Status emoji based on average return
                if avg_return > 0:
                    status = "🟢"
                elif avg_return == 0:
                    status = "🟡"
                else:
                    status = "🔴"

                # Create visual progress bar for success rate
                bar_length = 10
                filled = int(profitable_pct / 10)
                progress_bar = "█" * filled + "░" * (bar_length - filled)

                report.append(f"| **{symbol}** | {status} | {symbol_stats['test_count']} | "
                              f"{int(symbol_stats['total_trades'])} | {avg_return:.2f}% | "
                              f"{symbol_stats['max_drawdown']:.2f}% | "
                              f"{progress_bar} {profitable_pct:.0f}% |")

            report.append("\n</details>")

        # Strategy vs Buy-and-Hold Comparison
        if bnh_comparison:
            report.append("\n---")
            report.append("\n## 🆚 Strategy vs Buy-and-Hold Comparison")

            # Calculate totals first to show summary
            total_strategy = 0
            total_bnh = 0
            count = 0
            outperformed = 0

            for results in bnh_comparison.values():
                total_strategy += results['strategy_return']
                total_bnh += results['buy_and_hold_return']
                count += 1
                if results['excess_return'] > 0:
                    outperformed += 1

            if count > 0:
                avg_strategy = total_strategy / count
                avg_bnh = total_bnh / count
                avg_excess = avg_strategy - avg_bnh

                # Key insight box
                report.append("\n> **Key Insight**: " + (
                    f"Strategy outperformed buy-and-hold in {outperformed}/{count} tests ({outperformed/count*100:.0f}%)"
                    if outperformed > count / 2 else
                    f"Buy-and-hold outperformed strategy in {count-outperformed}/{count} tests ({(count-outperformed)/count*100:.0f}%)"
                ))

                # Summary stats
                report.append(f"\n**Average Performance**:")
                report.append(f"- Strategy: {avg_strategy:.2f}%")
                report.append(f"- Buy & Hold: {avg_bnh:.2f}%")
                report.append(f"- **Excess Return**: {avg_excess:+.2f}% " +
                              ("✅" if avg_excess > 0 else "❌"))

            # Detailed table
            report.append("\n<details>")
            report.append("<summary>Click to see detailed comparison table</summary>")
            report.append("\n")
            report.append("| Test | Days | Strategy | B&H | Excess | Result |")
            report.append("|:-----|:----:|:--------:|:---:|:------:|:------:|")

            for (symbol, dates), results in sorted(bnh_comparison.items()):
                # Result emoji
                if results['excess_return'] > 5:
                    result = "🟢"
                elif results['excess_return'] > 0:
                    result = "🟡"
                else:
                    result = "🔴"

                report.append(f"| {symbol} ({dates}) | {results['days']} | "
                              f"{results['strategy_return']:.2f}% | "
                              f"{results['buy_and_hold_return']:.2f}% | "
                              f"{results['excess_return']:+.2f}% | {result} |")

            report.append("\n</details>")

        # Action Items and Recommendations
        report.append("\n---")
        report.append("\n## 🎯 Action Items & Recommendations")

        # Calculate insights for recommendations
        tests_with_trades = sum(1 for m in self.metrics_data.values()
                                if not m.empty and m.iloc[0].get('num_trades', 0) > 0)
        trade_frequency = tests_with_trades / \
            stats['total_tests'] * 100 if stats['total_tests'] > 0 else 0

        report.append("\n### Strategy Observations")

        if trade_frequency < 25:
            report.append("- 🔴 **Low Trade Frequency**: Only " +
                          f"{trade_frequency:.0f}% of tests generated trades")
            report.append("  - The MACD < 0 entry condition is very restrictive")
            report.append("  - Consider testing during more volatile market periods")

        if stats['avg_sharpe_ratio'] < 0:
            report.append("- 🔴 **Negative Sharpe Ratio**: Risk-adjusted returns are poor")
        elif stats['avg_sharpe_ratio'] < 1:
            report.append("- 🟡 **Low Sharpe Ratio**: Risk-adjusted returns could be improved")
        else:
            report.append("- 🟢 **Good Sharpe Ratio**: Risk-adjusted returns are acceptable")

        report.append("\n### Recommended Next Steps")
        report.append("- [ ] Test more volatile periods (2008 crisis, 2020 COVID crash)")
        report.append("- [ ] Consider adjusting MACD parameters for more signals")
        report.append("- [ ] Add stop-loss and take-profit levels")
        report.append("- [ ] Test with different sentiment thresholds")
        report.append("- [ ] Analyze trade duration and timing patterns")

        # Technical Details
        report.append("\n---")
        report.append("\n## 📋 Technical Details")

        report.append("\n<details>")
        report.append("<summary>Strategy Configuration</summary>")
        report.append("\n```python")
        report.append("# Entry Conditions (ALL must be true):")
        report.append("- position == 0 (no current position)")
        report.append("- macd_yesterday < 0")
        report.append("- macd_today > macd_yesterday")
        report.append("- sentiment_score > 0")
        report.append("")
        report.append("# Exit Conditions (ANY triggers exit):")
        report.append("- (macd_yesterday < 0 AND macd_today < macd_yesterday)")
        report.append("- (macd_yesterday > 0 AND macd_today < 0)")
        report.append("```")
        report.append("</details>")

        report.append("\n<details>")
        report.append("<summary>Test Statistics</summary>")
        report.append("\n")
        if stats["total_trades"] > 0:
            report.append(
                f"- **Average Trades per Test**: {stats['total_trades'] / stats['total_tests']:.1f}")
        else:
            report.append("- **Average Trades per Test**: 0")

        report.append(
            f"- **Tests with Trades**: {tests_with_trades}/{stats['total_tests']} ({trade_frequency:.0f}%)")
        report.append(f"- **Total Market Days Analyzed**: {stats['total_signals_generated']}")
        report.append(
            f"- **Average Test Duration**: {stats['total_signals_generated']/stats['total_tests']:.1f} days")
        report.append("</details>")

        # Footer
        report.append("\n---")
        report.append("\n### 📌 Notes")
        report.append("- All returns are calculated as percentages")
        report.append("- Buy-and-hold returns assume holding for entire test period")
        report.append("- Excess return = Strategy return - Buy-and-hold return")
        report.append("- 🟢 = Good performance, 🟡 = Caution, 🔴 = Poor performance")

        # Write report
        report_text = "\n".join(report)
        with open(output_path, 'w') as f:
            f.write(report_text)

        print(f"\nSummary report saved to: {output_path}")

        # Also save as JSON for programmatic access
        json_path = output_path.replace('.md', '.json')
        with open(json_path, 'w') as f:
            json.dump({
                "stats": stats,
                "buy_and_hold_comparison": {f"{k[0]}_{k[1]}": v for k, v in bnh_comparison.items()},
                "generated": datetime.now().isoformat()
            }, f, indent=2)

        print(f"JSON data saved to: {json_path}")

        return report_text


def main():
    """Main function to run the aggregator."""
    aggregator = BacktestAggregator()
    report = aggregator.generate_summary_report()
    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
