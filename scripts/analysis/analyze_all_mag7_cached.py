#!/usr/bin/env python3
"""
Comprehensive analysis of all MAG7 cached backtest results.

This script will:
1. Load all available cached data for MAG7 stocks
2. Analyze performance across different market conditions
3. Generate comprehensive performance report
"""

import os
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Tuple

# MAG7 stocks
MAG7_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

# Cache directory
CACHE_DIR = Path(".cache/backtests/runs")


def find_all_mag7_runs() -> Dict[str, List[Path]]:
    """Find all cached runs for MAG7 stocks."""
    mag7_runs = {stock: [] for stock in MAG7_STOCKS}
    
    # Find all run directories
    for run_dir in CACHE_DIR.iterdir():
        if run_dir.is_dir():
            # Check if it's a MAG7 stock
            for stock in MAG7_STOCKS:
                if run_dir.name.startswith(f"{stock}_"):
                    # Check if metrics file exists
                    metrics_file = run_dir / "data" / "metrics.csv"
                    if metrics_file.exists():
                        mag7_runs[stock].append(run_dir)
    
    return mag7_runs


def parse_run_info(run_dir: Path) -> Dict:
    """Extract run information from directory name and metadata."""
    # Directory format: SYMBOL_START_END_TIMESTAMP
    parts = run_dir.name.split('_')
    
    info = {
        'symbol': parts[0],
        'start_date': parts[1],
        'end_date': parts[2],
        'timestamp': parts[3] + '_' + parts[4] if len(parts) > 4 else parts[3],
        'run_dir': run_dir
    }
    
    # Try to load metadata
    metadata_file = run_dir / "metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                info['metadata'] = metadata
        except:
            pass
    
    return info


def load_metrics(run_dir: Path) -> Dict:
    """Load performance metrics from a run."""
    metrics_file = run_dir / "data" / "metrics.csv"
    
    try:
        df = pd.read_csv(metrics_file)
        if len(df) > 0:
            return df.iloc[0].to_dict()
        else:
            return {}
    except Exception as e:
        print(f"Error loading metrics from {run_dir}: {e}")
        return {}


def load_trades(run_dir: Path) -> pd.DataFrame:
    """Load trades data from a run."""
    trades_file = run_dir / "data" / "trades.csv"
    
    if trades_file.exists():
        try:
            return pd.read_csv(trades_file)
        except:
            pass
    
    return pd.DataFrame()


def categorize_market_period(start_date: str, end_date: str) -> str:
    """Categorize the market period based on dates."""
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # COVID crash period
    if start >= pd.to_datetime('2020-02-01') and end <= pd.to_datetime('2020-05-01'):
        return "COVID Crash (2020)"
    
    # 2022 Bear Market
    elif start >= pd.to_datetime('2022-01-01') and end <= pd.to_datetime('2022-12-31'):
        return "Bear Market (2022)"
    
    # 2023 Recovery
    elif start >= pd.to_datetime('2023-01-01') and end <= pd.to_datetime('2023-12-31'):
        return "Recovery (2023)"
    
    # 2024 Period
    elif start >= pd.to_datetime('2024-01-01'):
        return "Recent (2024-2025)"
    
    else:
        return "Other Period"


def analyze_stock_performance(stock: str, runs: List[Path]) -> Dict:
    """Analyze performance for a specific stock across all runs."""
    print(f"\n📊 Analyzing {stock}...")
    
    results = []
    
    for run_dir in runs:
        run_info = parse_run_info(run_dir)
        metrics = load_metrics(run_dir)
        trades_df = load_trades(run_dir)
        
        if metrics:
            # Calculate trading days
            start = pd.to_datetime(run_info['start_date'])
            end = pd.to_datetime(run_info['end_date'])
            trading_days = pd.bdate_range(start, end).shape[0]
            
            result = {
                'period': f"{run_info['start_date']} to {run_info['end_date']}",
                'market_condition': categorize_market_period(run_info['start_date'], run_info['end_date']),
                'trading_days': trading_days,
                'total_return': metrics.get('total_return_pct', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'max_drawdown': metrics.get('max_drawdown_pct', metrics.get('max_drawdown', 0)),
                'win_rate': metrics.get('win_rate', 0),
                'num_trades': metrics.get('num_trades', 0),
                'profit_factor': metrics.get('profit_factor', 0),
                'trades_data': trades_df
            }
            
            results.append(result)
    
    # Sort by period
    results.sort(key=lambda x: x['period'])
    
    return {
        'stock': stock,
        'num_backtests': len(results),
        'results': results,
        'summary': calculate_summary_stats(results)
    }


def calculate_summary_stats(results: List[Dict]) -> Dict:
    """Calculate summary statistics across all runs."""
    if not results:
        return {}
    
    # Filter out runs with no trades
    active_results = [r for r in results if r['num_trades'] > 0]
    
    if not active_results:
        return {'status': 'No active trading in any period'}
    
    returns = [r['total_return'] for r in active_results]
    sharpes = [r['sharpe_ratio'] for r in active_results if r['sharpe_ratio'] != 0]
    win_rates = [r['win_rate'] for r in active_results if r['win_rate'] > 0]
    
    return {
        'avg_return': sum(returns) / len(returns) if returns else 0,
        'best_return': max(returns) if returns else 0,
        'worst_return': min(returns) if returns else 0,
        'avg_sharpe': sum(sharpes) / len(sharpes) if sharpes else 0,
        'avg_win_rate': sum(win_rates) / len(win_rates) if win_rates else 0,
        'total_trades': sum(r['num_trades'] for r in active_results),
        'periods_tested': len(active_results)
    }


def generate_comprehensive_report(all_results: Dict[str, Dict]):
    """Generate comprehensive MAG7 performance report."""
    
    print("\n" + "=" * 80)
    print("MAG7 COMPREHENSIVE BACKTEST ANALYSIS")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Stocks Analyzed: {', '.join(MAG7_STOCKS)}")
    
    # Summary by Stock
    print("\n" + "=" * 80)
    print("SUMMARY BY STOCK")
    print("=" * 80)
    
    summary_data = []
    
    for stock in MAG7_STOCKS:
        if stock in all_results and all_results[stock]['summary']:
            summary = all_results[stock]['summary']
            if 'avg_return' in summary:  # Has valid data
                summary_data.append({
                    'Stock': stock,
                    'Periods': all_results[stock]['num_backtests'],
                    'Avg Return': f"{summary['avg_return']:.2f}%",
                    'Best Return': f"{summary['best_return']:.2f}%",
                    'Worst Return': f"{summary['worst_return']:.2f}%",
                    'Avg Win Rate': f"{summary['avg_win_rate']*100:.1f}%",
                    'Total Trades': summary['total_trades']
                })
    
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        print(df_summary.to_string(index=False))
    
    # Detailed Results by Market Condition
    print("\n" + "=" * 80)
    print("PERFORMANCE BY MARKET CONDITION")
    print("=" * 80)
    
    market_conditions = {}
    
    for stock, data in all_results.items():
        for result in data.get('results', []):
            condition = result['market_condition']
            if condition not in market_conditions:
                market_conditions[condition] = []
            
            market_conditions[condition].append({
                'stock': stock,
                'period': result['period'],
                'return': result['total_return'],
                'trades': result['num_trades']
            })
    
    for condition, results in sorted(market_conditions.items()):
        print(f"\n{condition}:")
        print("-" * 40)
        
        # Calculate average return for this condition
        returns = [r['return'] for r in results if r['trades'] > 0]
        if returns:
            avg_return = sum(returns) / len(returns)
            print(f"Average Return: {avg_return:+.2f}%")
            print(f"Number of Tests: {len(results)}")
            
            # Show top performers
            top_performers = sorted(results, key=lambda x: x['return'], reverse=True)[:3]
            print("\nTop Performers:")
            for perf in top_performers:
                if perf['trades'] > 0:
                    print(f"  {perf['stock']} ({perf['period']}): {perf['return']:+.2f}%")
    
    # Detailed Stock Analysis
    print("\n" + "=" * 80)
    print("DETAILED STOCK ANALYSIS")
    print("=" * 80)
    
    for stock in MAG7_STOCKS:
        if stock in all_results and all_results[stock]['results']:
            print(f"\n{stock} - {all_results[stock]['num_backtests']} Backtests")
            print("-" * 60)
            
            for result in all_results[stock]['results']:
                if result['num_trades'] > 0:
                    print(f"\nPeriod: {result['period']} ({result['market_condition']})")
                    print(f"  Return: {result['total_return']:+.2f}%")
                    print(f"  Sharpe Ratio: {result['sharpe_ratio']:.2f}")
                    print(f"  Max Drawdown: {result['max_drawdown']:.2f}%")
                    print(f"  Win Rate: {result['win_rate']*100:.1f}%")
                    print(f"  Number of Trades: {result['num_trades']}")
                    
                    # Show sample trades if available
                    if not result['trades_data'].empty and len(result['trades_data']) > 0:
                        print("  Sample Trade:")
                        first_trade = result['trades_data'].iloc[0]
                        print(f"    {first_trade['date']} {first_trade['action']} @ ${first_trade['price']:.2f}")
    
    # Overall Statistics
    print("\n" + "=" * 80)
    print("OVERALL STATISTICS")
    print("=" * 80)
    
    all_returns = []
    all_trades = 0
    total_periods = 0
    
    for stock, data in all_results.items():
        if 'summary' in data and 'avg_return' in data['summary']:
            for result in data['results']:
                if result['num_trades'] > 0:
                    all_returns.append(result['total_return'])
                    all_trades += result['num_trades']
                    total_periods += 1
    
    if all_returns:
        print(f"\nTotal Periods Tested: {total_periods}")
        print(f"Total Trades Executed: {all_trades}")
        print(f"Overall Average Return: {sum(all_returns)/len(all_returns):+.2f}%")
        print(f"Overall Best Return: {max(all_returns):+.2f}%")
        print(f"Overall Worst Return: {min(all_returns):+.2f}%")
        
        # Win/Loss ratio
        profitable = sum(1 for r in all_returns if r > 0)
        print(f"Profitable Periods: {profitable}/{len(all_returns)} ({profitable/len(all_returns)*100:.1f}%)")
    
    return all_results


def save_analysis_report(all_results: Dict[str, Dict]):
    """Save analysis to files."""
    output_dir = Path(".cache/backtests/mag7_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save JSON data
    json_file = output_dir / f"mag7_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_file, 'w') as f:
        # Convert to serializable format
        serializable_results = {}
        for stock, data in all_results.items():
            serializable_results[stock] = {
                'num_backtests': data['num_backtests'],
                'summary': data['summary'],
                'results': [
                    {k: v for k, v in r.items() if k != 'trades_data'}
                    for r in data['results']
                ]
            }
        json.dump(serializable_results, f, indent=2)
    
    print(f"\n💾 Analysis saved to: {json_file}")
    
    # Save summary CSV
    summary_rows = []
    for stock, data in all_results.items():
        for result in data.get('results', []):
            if result['num_trades'] > 0:
                summary_rows.append({
                    'Stock': stock,
                    'Period': result['period'],
                    'Market_Condition': result['market_condition'],
                    'Trading_Days': result['trading_days'],
                    'Total_Return': result['total_return'],
                    'Sharpe_Ratio': result['sharpe_ratio'],
                    'Max_Drawdown': result['max_drawdown'],
                    'Win_Rate': result['win_rate'],
                    'Num_Trades': result['num_trades']
                })
    
    if summary_rows:
        csv_file = output_dir / f"mag7_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        pd.DataFrame(summary_rows).to_csv(csv_file, index=False)
        print(f"📊 Summary CSV saved to: {csv_file}")


def main():
    """Run comprehensive MAG7 analysis."""
    print("🔍 Finding all MAG7 cached backtest runs...")
    
    # Find all runs
    mag7_runs = find_all_mag7_runs()
    
    # Show what we found
    print("\n📁 Cached Backtest Runs Found:")
    for stock, runs in mag7_runs.items():
        print(f"  {stock}: {len(runs)} runs")
    
    # Analyze each stock
    all_results = {}
    
    for stock in MAG7_STOCKS:
        if mag7_runs[stock]:
            all_results[stock] = analyze_stock_performance(stock, mag7_runs[stock])
    
    # Generate comprehensive report
    generate_comprehensive_report(all_results)
    
    # Save results
    save_analysis_report(all_results)
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()