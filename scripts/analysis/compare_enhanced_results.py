#!/usr/bin/env python3
"""
Compare Enhanced Backtest Results Across All Versions

Creates a comprehensive comparison table showing V0-V4 performance with enhanced metrics.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List
import numpy as np


def load_enhanced_results(version: str) -> Dict:
    """Load enhanced results for a specific version."""
    enhanced_path = Path(f"reports/continuous_backtests/{version}/AAPL_2024_results_enhanced.json")
    regular_path = Path(f"reports/continuous_backtests/{version}/AAPL_2024_results.json")
    
    # Try enhanced first, fall back to regular
    if enhanced_path.exists():
        with open(enhanced_path, 'r') as f:
            return json.load(f)
    elif regular_path.exists():
        with open(regular_path, 'r') as f:
            return json.load(f)
    else:
        return None


def extract_metrics(results: Dict) -> Dict:
    """Extract key metrics from results."""
    if not results:
        return {}
    
    performance = results.get('performance', {})
    risk_metrics = results.get('risk_metrics', {})
    trade_analysis = results.get('trade_analysis', {})
    
    # Calculate additional metrics from daily values if available
    daily_values = results.get('daily_values', [])
    
    # Get position tracking metrics
    max_unrealized_pnl = 0
    min_unrealized_pnl = 0
    avg_position_allocation = 0
    
    if daily_values:
        unrealized_pnls = [day.get('unrealized_pnl_pct', 0) for day in daily_values if day.get('position', 0) > 0]
        position_allocations = [day.get('position_allocation_pct', 0) for day in daily_values]
        
        if unrealized_pnls:
            max_unrealized_pnl = max(unrealized_pnls)
            min_unrealized_pnl = min(unrealized_pnls)
        
        if position_allocations:
            avg_position_allocation = np.mean([p for p in position_allocations if p > 0])
    
    return {
        # Core Performance
        'Total Return (%)': performance.get('total_return_pct', 0),
        'Buy & Hold Return (%)': performance.get('buy_hold_return', 0),
        'Outperformance (%)': performance.get('outperformance', 0),
        'Final Portfolio': performance.get('final_portfolio_value', 0),
        
        # Trading Activity
        'Total Trades': performance.get('num_trades', trade_analysis.get('total_trades', 0)),
        'Win Rate (%)': performance.get('win_rate', trade_analysis.get('profitable_trades_pct', 0)),
        'Avg Trade Return (%)': performance.get('avg_trade_return', trade_analysis.get('avg_return_per_trade_pct', 0)),
        'Best Trade (%)': trade_analysis.get('best_trade_pct', 0),
        'Worst Trade (%)': trade_analysis.get('worst_trade_pct', 0),
        
        # Risk Metrics
        'Max Drawdown (%)': risk_metrics.get('max_drawdown_pct', 0),
        'Volatility (%)': risk_metrics.get('volatility_pct', 0),
        'Sharpe Ratio': risk_metrics.get('sharpe_ratio', 0),
        'Time in Market (%)': risk_metrics.get('time_in_market_pct', 0),
        'Avg Hold Days': risk_metrics.get('avg_holding_period_days', 0),
        
        # Position Tracking (Enhanced)
        'Avg Position Size': trade_analysis.get('avg_position_size', 0),
        'Position Size Std': trade_analysis.get('position_size_std', 0),
        'Max Unrealized P&L (%)': max_unrealized_pnl,
        'Min Unrealized P&L (%)': min_unrealized_pnl,
        'Avg Position Alloc (%)': avg_position_allocation
    }


def create_comparison_table():
    """Create comprehensive comparison table for all versions."""
    versions = ['V0', 'V1', 'V2', 'V3']
    
    # Collect metrics for each version
    comparison_data = []
    
    for version in versions:
        results = load_enhanced_results(version)
        if results:
            metrics = extract_metrics(results)
            metrics['Version'] = version
            
            # Add version description
            descriptions = {
                'V0': 'Pure MACD (Fixed Sentiment)',
                'V1': 'VADER + Google News',
                'V2': 'VXX Market Fear',
                'V3': 'V1+V2 Heuristic Combo'
            }
            metrics['Strategy'] = descriptions.get(version, '')
            
            comparison_data.append(metrics)
    
    # Create DataFrame
    df = pd.DataFrame(comparison_data)
    
    # Reorder columns for better presentation
    column_order = [
        'Version', 'Strategy',
        'Total Return (%)', 'Buy & Hold Return (%)', 'Outperformance (%)',
        'Total Trades', 'Win Rate (%)', 'Avg Trade Return (%)',
        'Best Trade (%)', 'Worst Trade (%)',
        'Max Drawdown (%)', 'Volatility (%)', 'Sharpe Ratio',
        'Time in Market (%)', 'Avg Hold Days',
        'Max Unrealized P&L (%)', 'Min Unrealized P&L (%)'
    ]
    
    # Only include columns that exist
    column_order = [col for col in column_order if col in df.columns]
    df = df[column_order]
    
    return df


def print_comparison_report():
    """Print formatted comparison report."""
    df = create_comparison_table()
    
    print("\n" + "=" * 100)
    print("📊 ENHANCED V0-V4 PERFORMANCE COMPARISON (AAPL 2024)")
    print("=" * 100)
    
    # Core Performance Section
    print("\n🎯 CORE PERFORMANCE METRICS")
    print("-" * 50)
    core_cols = ['Version', 'Strategy', 'Total Return (%)', 'Outperformance (%)', 'Total Trades', 'Win Rate (%)']
    print(df[core_cols].to_string(index=False))
    
    # Risk-Adjusted Returns
    print("\n📈 RISK-ADJUSTED RETURNS")
    print("-" * 50)
    risk_cols = ['Version', 'Max Drawdown (%)', 'Volatility (%)', 'Sharpe Ratio', 'Time in Market (%)']
    print(df[risk_cols].to_string(index=False))
    
    # Trading Performance
    print("\n💼 TRADING PERFORMANCE")
    print("-" * 50)
    trade_cols = ['Version', 'Avg Trade Return (%)', 'Best Trade (%)', 'Worst Trade (%)', 'Avg Hold Days']
    print(df[trade_cols].to_string(index=False))
    
    # Position Tracking (Enhanced Metrics)
    print("\n🎯 ENHANCED POSITION TRACKING")
    print("-" * 50)
    if 'Max Unrealized P&L (%)' in df.columns:
        position_cols = ['Version', 'Max Unrealized P&L (%)', 'Min Unrealized P&L (%)']
        print(df[position_cols].to_string(index=False))
    
    # Summary Rankings
    print("\n🏆 PERFORMANCE RANKINGS")
    print("-" * 50)
    
    # Rank by different metrics
    rankings = {}
    
    # Total Return Ranking
    df_sorted = df.sort_values('Total Return (%)', ascending=False)
    print("\nBy Total Return:")
    for i, row in df_sorted.iterrows():
        print(f"  {row['Version']}: {row['Total Return (%)']:.2f}%")
    
    # Sharpe Ratio Ranking (risk-adjusted)
    df_valid_sharpe = df[df['Sharpe Ratio'] != float('-inf')]
    if not df_valid_sharpe.empty:
        df_sorted = df_valid_sharpe.sort_values('Sharpe Ratio', ascending=False)
        print("\nBy Sharpe Ratio (Risk-Adjusted):")
        for i, row in df_sorted.iterrows():
            print(f"  {row['Version']}: {row['Sharpe Ratio']:.3f}")
    
    # Win Rate Ranking
    df_sorted = df.sort_values('Win Rate (%)', ascending=False)
    print("\nBy Win Rate:")
    for i, row in df_sorted.iterrows():
        print(f"  {row['Version']}: {row['Win Rate (%)']:.1f}%")
    
    print("\n" + "=" * 100)
    
    # Key Insights
    print("\n🔍 KEY INSIGHTS")
    print("-" * 50)
    
    # Best performer
    best_return = df.loc[df['Total Return (%)'].idxmax()]
    print(f"✅ Best Total Return: {best_return['Version']} ({best_return['Strategy']}) with {best_return['Total Return (%)']:.2f}%")
    
    # Most consistent
    if not df_valid_sharpe.empty:
        best_sharpe = df_valid_sharpe.loc[df_valid_sharpe['Sharpe Ratio'].idxmax()]
        print(f"✅ Best Risk-Adjusted: {best_sharpe['Version']} with Sharpe ratio of {best_sharpe['Sharpe Ratio']:.3f}")
    
    # Most active
    most_trades = df.loc[df['Total Trades'].idxmax()]
    print(f"✅ Most Active: {most_trades['Version']} with {most_trades['Total Trades']:.0f} trades")
    
    # Best win rate
    best_win_rate = df.loc[df['Win Rate (%)'].idxmax()]
    print(f"✅ Best Win Rate: {best_win_rate['Version']} at {best_win_rate['Win Rate (%)']:.1f}%")
    
    print("\n" + "=" * 100)
    
    # Save to CSV for further analysis
    output_file = "reports/enhanced_comparison_AAPL_2024.csv"
    df.to_csv(output_file, index=False)
    print(f"\n📁 Full comparison saved to: {output_file}")


if __name__ == '__main__':
    print_comparison_report()