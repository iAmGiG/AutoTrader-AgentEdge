"""
Generate Results Summary (#270)

Consolidated reporting tool for backtest results.
Generates text/markdown reports from JSON backtest results.

Usage:
    python scripts/analysis/generate_results_summary.py --file docs/08_research/99_archived/experiment_293_validation/experiment_293_results.json
    python scripts/analysis/generate_results_summary.py --dir docs/08_research/99_archived/experiment_293_validation/ --advanced
    python scripts/analysis/generate_results_summary.py --symbol AAPL --period 2024

Features:
- Basic summary: total return, Sharpe, max drawdown
- Advanced (--advanced): Calmar, Sortino, profit factor, streaks
- Multi-strategy comparison tables
- Monthly/quarterly breakdowns
- Execution cost impact analysis
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from src.backtesting.enhanced_metrics import (
    calculate_enhanced_metrics,
    generate_comparison_table,
)

# Use centralized date utilities
from src.utils.date_utils import get_datetime_now


def load_json_results(file_path: str) -> Dict[str, Any]:
    """Load backtest results from JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_results(directory: str) -> List[Dict[str, Any]]:
    """Load all JSON result files from a directory."""
    results = []
    path = Path(directory)

    for json_file in path.glob("*.json"):
        try:
            data = load_json_results(str(json_file))
            data["_source_file"] = json_file.name
            results.append(data)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse {json_file.name}")

    return results


def generate_basic_summary(data: Dict[str, Any]) -> str:
    """Generate basic text summary from results."""
    lines = []
    lines.append("=" * 70)
    lines.append("BACKTEST RESULTS SUMMARY")
    lines.append("=" * 70)

    # Experiment info
    if "experiment" in data:
        lines.append(f"Experiment: {data['experiment']}")
    if "date" in data:
        lines.append(f"Run Date: {data['date']}")
    lines.append("")

    # Strategy comparison
    strategies = []
    for key in data:
        if isinstance(data[key], dict) and "sharpe_ratio" in data[key]:
            strategies.append((key, data[key]))

    if strategies:
        lines.append("STRATEGY COMPARISON")
        lines.append("-" * 40)
        lines.append(f"{'Strategy':<25} {'Return':>10} {'Sharpe':>10} {'MaxDD':>10}")
        lines.append("-" * 40)

        for name, metrics in strategies:
            ret = metrics.get("total_return", 0)
            sharpe = metrics.get("sharpe_ratio", 0)
            mdd = metrics.get("max_drawdown", 0)
            lines.append(f"{name:<25} {ret:>9.2f}% {sharpe:>10.3f} {mdd:>9.2f}%")

        lines.append("-" * 40)

    # Verdict
    if "verdict" in data:
        lines.append("")
        lines.append(f"VERDICT: {data['verdict']}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def generate_advanced_summary(
    data: Dict[str, Any],
    returns_data: Optional[pd.Series] = None,
    trades_data: Optional[List[Dict]] = None,
) -> str:
    """Generate advanced summary with enhanced metrics."""
    lines = []
    lines.append("=" * 70)
    lines.append("ADVANCED BACKTEST ANALYSIS")
    lines.append("=" * 70)
    lines.append("")

    # If we have raw returns/trades, calculate enhanced metrics
    if returns_data is not None and trades_data is not None:
        max_dd = data.get("max_drawdown", 0) / 100  # Convert to decimal
        enhanced = calculate_enhanced_metrics(
            returns_data, trades_data, max_dd, initial_capital=10000
        )

        lines.append("RISK-ADJUSTED METRICS")
        lines.append("-" * 40)
        lines.append(f"Sharpe Ratio:    {data.get('sharpe_ratio', 0):>10.3f}")
        lines.append(f"Calmar Ratio:    {enhanced.calmar_ratio:>10.3f}")
        lines.append(f"Sortino Ratio:   {enhanced.sortino_ratio:>10.3f}")
        lines.append("")

        lines.append("TRADE QUALITY")
        lines.append("-" * 40)
        lines.append(f"Win Rate:        {data.get('win_rate', 0):>10.1f}%")
        lines.append(f"Profit Factor:   {enhanced.profit_factor:>10.2f}")
        lines.append(f"Win/Loss Ratio:  {enhanced.win_loss_ratio:>10.2f}")
        lines.append(f"Expectancy:      ${enhanced.expectancy:>9.2f}")
        lines.append("")

        lines.append("STREAK ANALYSIS")
        lines.append("-" * 40)
        lines.append(f"Max Win Streak:  {enhanced.max_win_streak:>10} days")
        lines.append(f"Max Loss Streak: {enhanced.max_loss_streak:>10} days")
        lines.append("")

        lines.append("EXECUTION COSTS")
        lines.append("-" * 40)
        lines.append(f"Gross Return:    {enhanced.gross_return:>10.2f}%")
        lines.append(f"Net Return:      {enhanced.net_return:>10.2f}%")
        lines.append(f"Cost Drag:       {enhanced.cost_drag:>10.2f}%")
        lines.append(f"Total Comm:      ${enhanced.total_commissions:>9.2f}")
        lines.append("")

        # Monthly returns
        if enhanced.monthly_returns:
            lines.append("MONTHLY PERFORMANCE")
            lines.append("-" * 40)
            for month, ret in sorted(enhanced.monthly_returns.items()):
                bar = "+" * int(ret) if ret > 0 else "-" * int(abs(ret))
                lines.append(f"{month}: {ret:>+7.2f}% {bar}")
            lines.append("")
            lines.append(f"Best Month:  {enhanced.best_month[0]} ({enhanced.best_month[1]:+.2f}%)")
            lines.append(
                f"Worst Month: {enhanced.worst_month[0]} ({enhanced.worst_month[1]:+.2f}%)"
            )
            lines.append("")

    else:
        # No raw data, just show what we have
        lines.append("(Advanced metrics require returns_series and trades data)")
        lines.append("")
        lines.append("AVAILABLE METRICS")
        lines.append("-" * 40)
        for key, value in data.items():
            if isinstance(value, (int, float)):
                lines.append(f"{key}: {value}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def _extract_strategies(data: Dict[str, Any]) -> List[Dict]:
    """Extract strategy results from data."""
    strategies = []
    for key in data:
        if isinstance(data[key], dict) and "sharpe_ratio" in data[key]:
            strategies.append({"symbol": key, **data[key]})
    return strategies


def _format_benchmark_comparison(data: Dict[str, Any]) -> List[str]:
    """Format buy-and-hold benchmark comparison."""
    lines = ["## Benchmark Comparison", ""]
    bh_ret = data["buy_hold"].get("total_return", 0)
    lines.append(f"- **Buy & Hold Return**: {bh_ret:.2f}%")

    for key in data:
        if isinstance(data[key], dict) and "total_return" in data[key] and key != "buy_hold":
            strat_ret = data[key]["total_return"]
            diff = strat_ret - bh_ret
            vs = "outperforms" if diff > 0 else "underperforms"
            lines.append(f"- **{key}**: {strat_ret:.2f}% ({vs} by {abs(diff):.2f}%)")

    lines.append("")
    return lines


def generate_markdown_report(
    data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """Generate markdown report from results."""
    lines = [
        "# Backtest Results Report",
        "",
        f"**Generated**: {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]

    if "experiment" in data:
        lines.append(f"**Experiment**: {data['experiment']}")
    if "date" in data:
        lines.append(f"**Run Date**: {data['date']}")
    lines.append("")

    strategies = _extract_strategies(data)
    if strategies:
        lines.extend(["## Strategy Comparison", "", generate_comparison_table(strategies), ""])

    if "verdict" in data:
        emoji = "✅" if "WINS" in data["verdict"] else "📊"
        lines.extend([f"## Verdict: {emoji} {data['verdict']}", ""])

    if "buy_hold" in data:
        lines.extend(_format_benchmark_comparison(data))

    lines.extend(["---", "Generated by generate_results_summary.py"])

    report = "\n".join(lines)
    if output_path:
        Path(output_path).write_text(report)
        print(f"Report saved to: {output_path}")

    return report


def _create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate backtest results summary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/analysis/generate_results_summary.py --file docs/08_research/99_archived/experiment_293_validation/experiment_293_results.json
  python scripts/analysis/generate_results_summary.py --dir docs/08_research/99_archived/experiment_293_validation/ --advanced
  python scripts/analysis/generate_results_summary.py --file results.json --format markdown --output report.md
        """,
    )
    parser.add_argument("--file", "-f", help="Single JSON results file to analyze")
    parser.add_argument("--dir", "-d", help="Directory of JSON results to compare")
    parser.add_argument("--advanced", "-a", action="store_true", help="Include advanced metrics")
    parser.add_argument("--format", choices=["text", "markdown"], default="text")
    parser.add_argument("--output", "-o", help="Output file path")
    return parser


def _process_single_file(args) -> int:
    """Process a single results file."""
    if not Path(args.file).exists():
        print(f"Error: File not found: {args.file}")
        return 1

    data = load_json_results(args.file)

    if args.format == "markdown":
        report = generate_markdown_report(data, args.output)
    elif args.advanced:
        report = generate_advanced_summary(data)
    else:
        report = generate_basic_summary(data)

    if not args.output:
        print(report)
    return 0


def _process_directory(args) -> int:
    """Process a directory of results files."""
    if not Path(args.dir).exists():
        print(f"Error: Directory not found: {args.dir}")
        return 1

    results = load_all_results(args.dir)
    if not results:
        print(f"No JSON files found in {args.dir}")
        return 1

    print(f"Found {len(results)} result files\n")
    for data in results:
        source = data.get("_source_file", "unknown")
        print(f"--- {source} ---")
        print(generate_basic_summary(data))
        print("")
    return 0


def main():
    """Main entry point."""
    parser = _create_parser()
    args = parser.parse_args()

    if not args.file and not args.dir:
        default_path = Path(
            "docs/08_research/99_archived/experiment_293_validation/experiment_293_results.json"
        )
        if default_path.exists():
            args.file = str(default_path)
        else:
            parser.print_help()
            print("\nNo input specified and default file not found.")
            return 1

    if args.file:
        return _process_single_file(args)
    return _process_directory(args)


if __name__ == "__main__":
    sys.exit(main())
