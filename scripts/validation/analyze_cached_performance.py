#!/usr/bin/env python3
"""
Analyze Cached Performance Data
Extracts insights from existing backtest runs to validate strategy performance.
"""

import sys
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def find_completed_runs() -> List[Path]:
    """Find all completed backtest runs with data."""
    runs_dir = Path(".cache/backtests/runs")
    completed_runs = []

    if not runs_dir.exists():
        return completed_runs

    for run_dir in runs_dir.iterdir():
        if run_dir.is_dir():
            # Check if run has both trades and equity data
            trades_file = run_dir / "data" / "trades.csv"
            equity_file = run_dir / "data" / "equity.csv"

            if trades_file.exists() and equity_file.exists():
                completed_runs.append(run_dir)

    return completed_runs


def analyze_run_performance(run_dir: Path) -> Dict:
    """Analyze performance of a single run."""
    # Parse run details from directory name
    run_name = run_dir.name
    parts = run_name.split('_')

    if len(parts) >= 4:
        symbol = parts[0]
        start_date = parts[1]
        end_date = parts[2]
    else:
        symbol = "UNKNOWN"
        start_date = "UNKNOWN"
        end_date = "UNKNOWN"

    # Load data
    trades_file = run_dir / "data" / "trades.csv"
    equity_file = run_dir / "data" / "equity.csv"

    trades_df = pd.read_csv(trades_file)
    equity_df = pd.read_csv(equity_file)

    # Calculate performance metrics
    initial_equity = equity_df['equity'].iloc[0]
    final_equity = equity_df['equity'].iloc[-1]
    total_return = (final_equity - initial_equity) / initial_equity * 100

    # Calculate buy-and-hold performance
    initial_price = equity_df['price'].iloc[0]
    final_price = equity_df['price'].iloc[-1]
    buy_hold_return = (final_price - initial_price) / initial_price * 100

    # Calculate advantage
    llm_advantage = total_return - buy_hold_return

    # Count trades
    num_trades = len(trades_df)

    return {
        'symbol': symbol,
        'start_date': start_date,
        'end_date': end_date,
        'run_dir': str(run_dir),
        'llm_return': round(total_return, 2),
        'buy_hold_return': round(buy_hold_return, 2),
        'llm_advantage': round(llm_advantage, 2),
        'num_trades': num_trades,
        'trading_days': len(equity_df),
        'initial_equity': initial_equity,
        'final_equity': final_equity
    }


def simulate_mechanical_strategy(equity_df: pd.DataFrame, trades_df: pd.DataFrame) -> Dict:
    """
    Simulate mechanical strategy performance on same data.
    Uses simple MACD-based rules without LLM reasoning.
    """
    initial_equity = 10000
    current_equity = initial_equity
    position = 0
    entry_price = None
    mechanical_trades = []

    for _, row in equity_df.iterrows():
        price = row['price']
        date = row['date']

        # Find corresponding trade data if available
        trade_row = trades_df[trades_df['date'] == date]

        if not trade_row.empty:
            macd_today = trade_row['macd_today'].iloc[0]

            # Simple mechanical rules
            if position == 0 and macd_today > 0:  # Buy signal
                shares = int(current_equity / price)
                if shares > 0:
                    position = shares
                    entry_price = price
                    current_equity = current_equity - (shares * price)
                    mechanical_trades.append({
                        'date': date,
                        'action': 'BUY',
                        'price': price,
                        'shares': shares
                    })

            elif position > 0 and macd_today < -0.1:  # Sell signal
                current_equity = current_equity + (position * price)
                mechanical_trades.append({
                    'date': date,
                    'action': 'SELL',
                    'price': price,
                    'shares': position
                })
                position = 0
                entry_price = None

    # Close position at end if still holding
    if position > 0:
        final_price = equity_df['price'].iloc[-1]
        current_equity = current_equity + (position * final_price)

    mechanical_return = (current_equity - initial_equity) / initial_equity * 100

    return {
        'mechanical_return': round(mechanical_return, 2),
        'mechanical_trades': len(mechanical_trades),
        'final_equity': current_equity
    }


def main():
    """Analyze all cached performance data."""
    print("=== Cached Performance Analysis ===")
    print("Analyzing existing backtest runs for strategy comparison...\n")

    # Find completed runs
    completed_runs = find_completed_runs()

    if not completed_runs:
        print("❌ No completed runs found with trade data")
        return

    print(f"📊 Found {len(completed_runs)} completed runs")

    results = []

    for run_dir in completed_runs:
        try:
            # Analyze LLM performance
            performance = analyze_run_performance(run_dir)

            # Load data for mechanical simulation
            equity_df = pd.read_csv(run_dir / "data" / "equity.csv")
            trades_df = pd.read_csv(run_dir / "data" / "trades.csv")

            # Simulate mechanical strategy
            mechanical_results = simulate_mechanical_strategy(equity_df, trades_df)

            # Combine results
            performance.update(mechanical_results)

            # Calculate mechanical advantage
            buy_hold_return = performance['buy_hold_return']
            mechanical_return = performance['mechanical_return']
            mechanical_advantage = mechanical_return - buy_hold_return
            performance['mechanical_advantage'] = round(mechanical_advantage, 2)

            # Calculate LLM vs Mechanical
            llm_vs_mechanical = performance['llm_return'] - mechanical_return
            performance['llm_vs_mechanical'] = round(llm_vs_mechanical, 2)

            results.append(performance)

            print(
                f"✅ {performance['symbol']} ({performance['start_date']} to {performance['end_date']})")
            print(
                f"   LLM: {performance['llm_return']:+.2f}% | Mechanical: {mechanical_return:+.2f}% | B&H: {buy_hold_return:+.2f}%")

        except Exception as e:
            print(f"❌ Error analyzing {run_dir.name}: {e}")

    if not results:
        print("❌ No successful analyses completed")
        return

    # Generate summary
    print(f"\n=== SUMMARY ({len(results)} runs) ===")

    # Calculate averages
    avg_llm_advantage = sum(r['llm_advantage'] for r in results) / len(results)
    avg_mechanical_advantage = sum(r['mechanical_advantage'] for r in results) / len(results)
    avg_llm_vs_mechanical = sum(r['llm_vs_mechanical'] for r in results) / len(results)

    print(f"Average LLM vs Buy & Hold: {avg_llm_advantage:+.2f}%")
    print(f"Average Mechanical vs Buy & Hold: {avg_mechanical_advantage:+.2f}%")
    print(f"Average LLM vs Mechanical: {avg_llm_vs_mechanical:+.2f}%")

    # Count wins
    llm_wins = sum(1 for r in results if r['llm_advantage'] > 0)
    mechanical_wins = sum(1 for r in results if r['mechanical_advantage'] > 0)
    llm_beats_mechanical = sum(1 for r in results if r['llm_vs_mechanical'] > 0)

    print(f"\nWin Rates:")
    print(f"LLM beats Buy & Hold: {llm_wins}/{len(results)} ({llm_wins/len(results)*100:.1f}%)")
    print(
        f"Mechanical beats Buy & Hold: {mechanical_wins}/{len(results)} ({mechanical_wins/len(results)*100:.1f}%)")
    print(
        f"LLM beats Mechanical: {llm_beats_mechanical}/{len(results)} ({llm_beats_mechanical/len(results)*100:.1f}%)")

    # Find best performances
    best_llm = max(results, key=lambda x: x['llm_advantage'])
    best_mechanical = max(results, key=lambda x: x['mechanical_advantage'])

    print(f"\nBest LLM Performance:")
    print(f"  {best_llm['symbol']} ({best_llm['start_date']} to {best_llm['end_date']}): {best_llm['llm_advantage']:+.2f}% advantage")

    print(f"Best Mechanical Performance:")
    print(f"  {best_mechanical['symbol']} ({best_mechanical['start_date']} to {best_mechanical['end_date']}): {best_mechanical['mechanical_advantage']:+.2f}% advantage")

    # Save detailed results
    output_file = ".cache/backtests/cached_performance_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n📁 Detailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
