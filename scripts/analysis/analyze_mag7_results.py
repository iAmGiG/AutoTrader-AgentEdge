#!/usr/bin/env python3
"""Analyze existing MAG7 comparison results and generate insights."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import json
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List

# Configuration
RESULTS_DIR = Path(".cache/backtests/mag7_comparison")


def load_results() -> Dict:
    """Load results from JSON file."""
    results_file = RESULTS_DIR / "all_results.json"

    if not results_file.exists():
        print(f"❌ Results file not found: {results_file}")
        print("Please run the MAG7 comparison first.")
        return {}

    with open(results_file, "r") as f:
        return json.load(f)


def analyze_results(results: List[Dict]):
    """Analyze and visualize MAG7 comparison results."""

    # Filter successful results
    successful = [r for r in results if r.get("status") == "completed"]

    if not successful:
        print("❌ No successful results to analyze")
        return

    print(f"\n✅ Found {len(successful)} successful comparisons")

    # Extract performance data
    data = []
    for result in successful:
        perf = result["performance"]
        comp = perf["comparisons"]

        data.append({
            "Symbol": result["symbol"],
            "Period": result["period"],
            "Buy & Hold Return": perf["buy_hold"]["total_return_pct"],
            "Mechanical Return": perf["mechanical"]["total_return_pct"],
            "LLM Return": perf["llm"]["total_return_pct"],
            "Mech vs B&H": comp["mechanical_vs_bh"]["outperformance"],
            "LLM vs B&H": comp["llm_vs_bh"]["outperformance"],
            "LLM vs Mech": comp["llm_vs_mechanical"]["outperformance"],
            "Buy & Hold Sharpe": perf["buy_hold"]["sharpe_ratio"],
            "Mechanical Sharpe": perf["mechanical"]["sharpe_ratio"],
            "LLM Sharpe": perf["llm"]["sharpe_ratio"],
        })

    df = pd.DataFrame(data)

    # Print summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    print("\nAverage Outperformance:")
    print(
        f"  Mechanical vs Buy & Hold: {df['Mech vs B&H'].mean():+.2f}% ± {df['Mech vs B&H'].std():.2f}%")
    print(f"  LLM vs Buy & Hold: {df['LLM vs B&H'].mean():+.2f}% ± {df['LLM vs B&H'].std():.2f}%")
    print(f"  LLM vs Mechanical: {df['LLM vs Mech'].mean():+.2f}% ± {df['LLM vs Mech'].std():.2f}%")

    print("\nWin Rates:")
    print(f"  Mechanical beats Buy & Hold: {(df['Mech vs B&H'] > 0).sum() / len(df) * 100:.1f}%")
    print(f"  LLM beats Buy & Hold: {(df['LLM vs B&H'] > 0).sum() / len(df) * 100:.1f}%")
    print(f"  LLM beats Mechanical: {(df['LLM vs Mech'] > 0).sum() / len(df) * 100:.1f}%")

    # Best performers
    print("\n" + "=" * 60)
    print("BEST PERFORMERS")
    print("=" * 60)

    print("\nTop 3 LLM Outperformance vs Buy & Hold:")
    top_llm = df.nlargest(3, 'LLM vs B&H')
    for _, row in top_llm.iterrows():
        print(f"  {row['Symbol']} ({row['Period']}): {row['LLM vs B&H']:+.2f}%")

    print("\nTop 3 LLM Outperformance vs Mechanical:")
    top_llm_mech = df.nlargest(3, 'LLM vs Mech')
    for _, row in top_llm_mech.iterrows():
        print(f"  {row['Symbol']} ({row['Period']}): {row['LLM vs Mech']:+.2f}%")

    # Period analysis
    print("\n" + "=" * 60)
    print("PERFORMANCE BY PERIOD")
    print("=" * 60)

    period_stats = df.groupby('Period')[['Mech vs B&H', 'LLM vs B&H', 'LLM vs Mech']].mean()
    print(period_stats.round(2))

    # Stock analysis
    print("\n" + "=" * 60)
    print("PERFORMANCE BY STOCK")
    print("=" * 60)

    stock_stats = df.groupby('Symbol')[['Mech vs B&H', 'LLM vs B&H', 'LLM vs Mech']].mean()
    print(stock_stats.round(2))

    # Generate visualizations
    generate_plots(df)

    # Statistical significance
    print("\n" + "=" * 60)
    print("STATISTICAL ANALYSIS")
    print("=" * 60)

    from scipy import stats

    # Test if LLM significantly outperforms Buy & Hold
    t_stat, p_value = stats.ttest_1samp(df['LLM vs B&H'], 0)
    print(f"\nLLM vs Buy & Hold (one-sample t-test):")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value: {p_value:.4f}")
    print(f"  Significant at 0.05 level: {'Yes' if p_value < 0.05 else 'No'}")

    # Test if LLM significantly outperforms Mechanical
    t_stat_mech, p_value_mech = stats.ttest_1samp(df['LLM vs Mech'], 0)
    print(f"\nLLM vs Mechanical (one-sample t-test):")
    print(f"  t-statistic: {t_stat_mech:.3f}")
    print(f"  p-value: {p_value_mech:.4f}")
    print(f"  Significant at 0.05 level: {'Yes' if p_value_mech < 0.05 else 'No'}")


def generate_plots(df: pd.DataFrame):
    """Generate visualization plots."""

    output_dir = RESULTS_DIR / "plots"
    output_dir.mkdir(exist_ok=True)

    # Set style
    plt.style.use('seaborn-v0_8-darkgrid')

    # 1. Outperformance distribution
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # Mechanical vs B&H
    axes[0].hist(df['Mech vs B&H'], bins=10, alpha=0.7, color='blue', edgecolor='black')
    axes[0].axvline(0, color='red', linestyle='--', alpha=0.5)
    axes[0].set_title('Mechanical vs Buy & Hold')
    axes[0].set_xlabel('Outperformance (%)')
    axes[0].set_ylabel('Frequency')

    # LLM vs B&H
    axes[1].hist(df['LLM vs B&H'], bins=10, alpha=0.7, color='green', edgecolor='black')
    axes[1].axvline(0, color='red', linestyle='--', alpha=0.5)
    axes[1].set_title('LLM vs Buy & Hold')
    axes[1].set_xlabel('Outperformance (%)')

    # LLM vs Mechanical
    axes[2].hist(df['LLM vs Mech'], bins=10, alpha=0.7, color='orange', edgecolor='black')
    axes[2].axvline(0, color='red', linestyle='--', alpha=0.5)
    axes[2].set_title('LLM vs Mechanical')
    axes[2].set_xlabel('Outperformance (%)')

    plt.tight_layout()
    plt.savefig(output_dir / 'outperformance_distributions.png', dpi=300)
    plt.close()

    # 2. Performance by stock
    fig, ax = plt.subplots(figsize=(10, 6))

    stock_perf = df.groupby('Symbol')[['Mech vs B&H', 'LLM vs B&H', 'LLM vs Mech']].mean()
    stock_perf.plot(kind='bar', ax=ax)
    ax.set_title('Average Outperformance by Stock')
    ax.set_ylabel('Outperformance (%)')
    ax.axhline(0, color='black', linestyle='-', alpha=0.3)
    ax.legend(['Mech vs B&H', 'LLM vs B&H', 'LLM vs Mech'])
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(output_dir / 'performance_by_stock.png', dpi=300)
    plt.close()

    # 3. Performance by period
    fig, ax = plt.subplots(figsize=(10, 6))

    period_perf = df.groupby('Period')[['Mech vs B&H', 'LLM vs B&H', 'LLM vs Mech']].mean()
    period_perf.plot(kind='bar', ax=ax)
    ax.set_title('Average Outperformance by Period')
    ax.set_ylabel('Outperformance (%)')
    ax.axhline(0, color='black', linestyle='-', alpha=0.3)
    ax.legend(['Mech vs B&H', 'LLM vs B&H', 'LLM vs Mech'])
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(output_dir / 'performance_by_period.png', dpi=300)
    plt.close()

    # 4. Scatter plot: LLM vs Mechanical returns
    fig, ax = plt.subplots(figsize=(8, 8))

    ax.scatter(df['Mechanical Return'], df['LLM Return'], alpha=0.6)

    # Add diagonal line
    min_val = min(df['Mechanical Return'].min(), df['LLM Return'].min())
    max_val = max(df['Mechanical Return'].max(), df['LLM Return'].max())
    ax.plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.5)

    ax.set_xlabel('Mechanical Return (%)')
    ax.set_ylabel('LLM Return (%)')
    ax.set_title('LLM vs Mechanical Returns')

    # Add labels for outliers
    for _, row in df.iterrows():
        if abs(row['LLM Return'] - row['Mechanical Return']) > 10:
            ax.annotate(f"{row['Symbol']}\n{row['Period'][:4]}",
                        (row['Mechanical Return'], row['LLM Return']),
                        fontsize=8, alpha=0.7)

    plt.tight_layout()
    plt.savefig(output_dir / 'llm_vs_mechanical_scatter.png', dpi=300)
    plt.close()

    print(f"\n📊 Plots saved to: {output_dir}")


def main():
    """Main analysis function."""

    print("\n" + "=" * 60)
    print("MAG7 COMPARISON RESULTS ANALYSIS")
    print("=" * 60)

    # Load results
    results = load_results()

    if results:
        analyze_results(results)

    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
