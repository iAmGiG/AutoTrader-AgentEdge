#!/usr/bin/env python3
"""Generate visual comparison charts for V1 vs V2 strategies.

This script creates visualizations showing the impact of the relaxed
sentiment requirement on trading activity and performance.

Usage:
    python scripts/visualize_strategy_comparison.py [comparison_json]
"""
import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import numpy as np


def load_comparison_data(json_file: str = None) -> dict:
    """Load comparison data from JSON file."""
    if json_file is None:
        # Find the most recent comparison
        comparisons_dir = Path(".cache/backtests/comparisons")
        json_files = list(comparisons_dir.glob("*_comparison_*.json"))
        if not json_files:
            print("No comparison files found. Run compare_strategies.py first.")
            sys.exit(1)
        json_file = max(json_files, key=lambda p: p.stat().st_mtime)

    with open(json_file, 'r') as f:
        return json.load(f)


def create_comparison_charts(data: dict, output_dir: Path) -> None:
    """Create comparison visualizations."""

    # Create figure with subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(f"Strategy Comparison: {data['symbol']} ({data['start']} to {data['end']})",
                 fontsize=16)

    # 1. Trade Count Comparison
    strategies = ['V1\n(Sentiment > 0)', 'V2\n(Sentiment >= 0)']
    trade_counts = [data['v1_results']['total_trades'],
                    data['v2_results']['total_trades']]

    bars = ax1.bar(strategies, trade_counts, color=['#e74c3c', '#27ae60'])
    ax1.set_ylabel('Number of Trades')
    ax1.set_title('Trade Activity Comparison')

    # Add value labels on bars
    for bar, count in zip(bars, trade_counts):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                 f'{int(count)}', ha='center', va='bottom')

    # Add improvement annotation
    if data['v1_results']['total_trades'] > 0:
        improvement = data['improvements']['trade_multiplier']
        ax1.text(0.5, max(trade_counts) * 0.8,
                 f'{improvement:.1f}x improvement',
                 ha='center', transform=ax1.transData,
                 bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

    # 2. Return Comparison
    returns = [data['v1_results']['total_return'],
               data['v2_results']['total_return']]

    bars = ax2.bar(strategies, returns,
                   color=['#e74c3c' if r < 0 else '#27ae60' for r in returns])
    ax2.set_ylabel('Total Return (%)')
    ax2.set_title('Performance Comparison')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # Add value labels
    for bar, ret in zip(bars, returns):
        height = bar.get_height()
        label_y = height + 0.5 if height > 0 else height - 1.5
        ax2.text(bar.get_x() + bar.get_width()/2., label_y,
                 f'{ret:.1f}%', ha='center', va='bottom' if height > 0 else 'top')

    # 3. Risk-Adjusted Performance
    metrics_data = {
        'Sharpe Ratio': [data['v1_results']['sharpe_ratio'],
                         data['v2_results']['sharpe_ratio']],
        'Max Drawdown': [-data['v1_results']['max_drawdown'],
                         -data['v2_results']['max_drawdown']],
        'Win Rate': [data['v1_results']['win_rate'],
                     data['v2_results']['win_rate']]
    }

    x = np.arange(len(metrics_data))
    width = 0.35

    for i, (metric, values) in enumerate(metrics_data.items()):
        offset = (i - 1) * width
        bars = ax3.bar(x + offset, values, width, label=metric)

        # Add value labels
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                     f'{val:.1f}', ha='center', va='bottom', fontsize=8)

    ax3.set_ylabel('Value')
    ax3.set_title('Risk Metrics Comparison')
    ax3.set_xticks(x)
    ax3.set_xticklabels(strategies)
    ax3.legend()
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # 4. Trade Distribution (if trade data available)
    if 'trades_data' in data['v2_results'] and data['v2_results']['trades_data']:
        # Create a simple timeline showing when trades occurred
        v2_trades = pd.DataFrame(data['v2_results']['trades_data'])
        v2_trades['date'] = pd.to_datetime(v2_trades['date'])

        # Plot buy/sell points
        buys = v2_trades[v2_trades['action'] == 'BUY']
        sells = v2_trades[v2_trades['action'] == 'SELL']

        if not buys.empty:
            ax4.scatter(buys['date'], buys['price'], color='green',
                        marker='^', s=100, label='Buy', zorder=5)
        if not sells.empty:
            ax4.scatter(sells['date'], sells['price'], color='red',
                        marker='v', s=100, label='Sell', zorder=5)

        # Add price line if we have enough data
        if len(v2_trades) > 1:
            ax4.plot(v2_trades['date'], v2_trades['price'],
                     color='blue', alpha=0.5, label='Price')

        ax4.set_xlabel('Date')
        ax4.set_ylabel('Price ($)')
        ax4.set_title('V2 Trading Activity')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        # Format x-axis
        fig.autofmt_xdate()
    else:
        # If no trade data, show a text message
        ax4.text(0.5, 0.5, 'No trade data available',
                 ha='center', va='center', transform=ax4.transAxes)
        ax4.set_title('Trading Activity')

    # Adjust layout and save
    plt.tight_layout()

    # Save the figure
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / \
        f"{data['symbol']}_comparison_charts_{timestamp}.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ Charts saved to: {output_file}")

    # Also save as PDF for better quality
    pdf_file = output_dir / \
        f"{data['symbol']}_comparison_charts_{timestamp}.pdf"
    plt.savefig(pdf_file, bbox_inches='tight')
    print(f"✅ PDF saved to: {pdf_file}")

    plt.close()


def create_aggregate_charts(json_files: list, output_dir: Path) -> None:
    """Create aggregate comparison charts across multiple tests."""

    # Load all data
    all_data = []
    for json_file in json_files:
        with open(json_file, 'r') as f:
            all_data.append(json.load(f))

    if not all_data:
        print("No data to aggregate")
        return

    # Create aggregate visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle("Aggregate Strategy Comparison Across All Tests", fontsize=16)

    # Extract data for plotting
    symbols = [d['symbol'] for d in all_data]
    v1_trades = [d['v1_results']['total_trades'] for d in all_data]
    v2_trades = [d['v2_results']['total_trades'] for d in all_data]
    improvements = [d['improvements']['trade_multiplier'] for d in all_data]

    # 1. Trade count comparison by symbol
    x = np.arange(len(symbols))
    width = 0.35

    bars1 = ax1.bar(x - width/2, v1_trades, width,
                    label='V1 (Original)', color='#e74c3c')
    bars2 = ax1.bar(x + width/2, v2_trades, width,
                    label='V2 (Relaxed)', color='#27ae60')

    ax1.set_xlabel('Symbol')
    ax1.set_ylabel('Number of Trades')
    ax1.set_title('Trade Activity by Symbol')
    ax1.set_xticks(x)
    ax1.set_xticklabels(symbols)
    ax1.legend()

    # Add improvement labels
    for i, (v1, v2, imp) in enumerate(zip(v1_trades, v2_trades, improvements)):
        if v1 > 0:
            ax1.text(i, max(v1, v2) + 0.5, f'{imp:.1f}x',
                     ha='center', fontsize=9)

    # 2. Return improvement scatter plot
    v1_returns = [d['v1_results']['total_return'] for d in all_data]
    v2_returns = [d['v2_results']['total_return'] for d in all_data]

    ax2.scatter(v1_returns, v2_returns, s=100, alpha=0.6)

    # Add diagonal line (no improvement)
    min_val = min(min(v1_returns), min(v2_returns))
    max_val = max(max(v1_returns), max(v2_returns))
    ax2.plot([min_val, max_val], [min_val, max_val],
             'k--', alpha=0.5, label='No Change')

    # Add labels for each point
    for i, symbol in enumerate(symbols):
        ax2.annotate(symbol, (v1_returns[i], v2_returns[i]),
                     xytext=(5, 5), textcoords='offset points', fontsize=8)

    ax2.set_xlabel('V1 Returns (%)')
    ax2.set_ylabel('V2 Returns (%)')
    ax2.set_title('Return Comparison')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # Add shaded region for improvement
    ax2.fill_between([min_val, max_val], [min_val, max_val], max_val,
                     where=[True, True], alpha=0.1, color='green',
                     label='V2 Improvement Region')

    plt.tight_layout()

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"aggregate_comparison_charts_{timestamp}.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ Aggregate charts saved to: {output_file}")

    plt.close()


def main():
    """Generate comparison visualizations."""
    # Setup output directory
    output_dir = Path(".cache/backtests/comparisons/charts")
    output_dir.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1:
        # Single file specified
        json_file = sys.argv[1]
        print(f"📊 Creating charts for: {json_file}")
        data = load_comparison_data(json_file)
        create_comparison_charts(data, output_dir)
    else:
        # Find all comparison files
        comparisons_dir = Path(".cache/backtests/comparisons")
        json_files = list(comparisons_dir.glob("*_comparison_*.json"))

        if not json_files:
            print("No comparison files found. Run compare_strategies.py first.")
            sys.exit(1)

        # Create individual charts for the most recent
        print("📊 Creating charts for most recent comparison...")
        latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
        data = load_comparison_data(latest_file)
        create_comparison_charts(data, output_dir)

        # Create aggregate charts if multiple files exist
        if len(json_files) > 1:
            print(
                f"\n📊 Creating aggregate charts from {len(json_files)} comparisons...")
            create_aggregate_charts(json_files, output_dir)


if __name__ == "__main__":
    main()
