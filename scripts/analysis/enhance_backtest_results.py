#!/usr/bin/env python3
"""
Enhanced Backtest Results Analysis

Adds position average cost tracking and additional metrics to existing backtest results
without requiring re-running the backtests.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse


class BacktestEnhancer:
    """Enhance existing backtest results with additional metrics."""
    
    def __init__(self, results_file: str):
        """Initialize with existing results file."""
        self.results_file = Path(results_file)
        with open(self.results_file, 'r') as f:
            self.data = json.load(f)
        
        self.trades_df = pd.DataFrame(self.data['trades'])
        self.daily_df = pd.DataFrame(self.data['daily_values'])
        if not self.daily_df.empty:
            self.daily_df['date'] = pd.to_datetime(self.daily_df['date'])
        
    def calculate_position_average(self) -> List[Dict]:
        """Calculate position average cost tracking throughout the backtest."""
        enhanced_daily = []
        
        # Create complete chronological trade history
        all_trades = sorted(self.data['trades'], key=lambda x: x['date'])
        
        # Build position tracking through all trades
        position_history = {}
        current_shares = 0
        current_avg_cost = 0.0
        total_cost_basis = 0.0
        
        # Process each trade to build position history
        for trade in all_trades:
            trade_date = trade['date']
            
            if trade['action'] == 'BUY':
                new_shares = trade['shares'] 
                new_cost = trade['price'] * new_shares
                
                if current_shares > 0:
                    # Adding to existing position - weighted average
                    total_cost_basis += new_cost
                    current_shares += new_shares
                    current_avg_cost = total_cost_basis / current_shares
                else:
                    # Starting new position
                    current_shares = new_shares
                    current_avg_cost = trade['price']
                    total_cost_basis = new_cost
                    
            elif trade['action'] == 'SELL':
                shares_sold = trade['shares']
                if current_shares > 0:
                    # Reduce position proportionally
                    if shares_sold >= current_shares:
                        # Closing entire position
                        current_shares = 0
                        current_avg_cost = 0.0
                        total_cost_basis = 0.0
                    else:
                        # Partial sale - reduce basis proportionally
                        cost_basis_sold = (shares_sold / current_shares) * total_cost_basis
                        total_cost_basis -= cost_basis_sold
                        current_shares -= shares_sold
                        # Average cost stays the same for remaining shares
            
            # Store position state for this date
            position_history[trade_date] = {
                'shares': current_shares,
                'avg_cost': current_avg_cost,
                'cost_basis': total_cost_basis
            }
        
        # Process daily values and apply position tracking
        for _, row in self.daily_df.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            stock_price = row['stock_price']
            position = row['position']
            
            # Find most recent position state for this date or before
            position_state = {'shares': 0, 'avg_cost': 0.0, 'cost_basis': 0.0}
            for trade_date, state in position_history.items():
                if trade_date <= date_str:
                    position_state = state
                else:
                    break
            
            # Get position metrics from the calculated state
            current_avg_cost = position_state['avg_cost']
            cost_basis = position_state['cost_basis']
            
            # Unrealized P&L calculation
            if position > 0 and current_avg_cost > 0:
                unrealized_pnl = (stock_price - current_avg_cost) * position
                unrealized_pnl_pct = ((stock_price - current_avg_cost) / current_avg_cost) * 100
            else:
                unrealized_pnl = 0.0
                unrealized_pnl_pct = 0.0
            
            # Position value and allocation
            position_value = position * stock_price
            cash = row['cash']
            portfolio_value = row['portfolio_value']
            cash_allocation_pct = (cash / portfolio_value) * 100 if portfolio_value > 0 else 0
            position_allocation_pct = (position_value / portfolio_value) * 100 if portfolio_value > 0 else 0
            
            enhanced_row = {
                'date': date_str,
                'portfolio_value': row['portfolio_value'],
                'cash': cash,
                'position': position,
                'stock_price': stock_price,
                'sentiment': row['sentiment'],
                
                # New metrics
                'position_avg_cost': round(current_avg_cost, 2) if position > 0 else 0.0,
                'position_value': round(position_value, 2),
                'cost_basis': round(cost_basis, 2),
                'unrealized_pnl': round(unrealized_pnl, 2),
                'unrealized_pnl_pct': round(unrealized_pnl_pct, 2),
                'cash_allocation_pct': round(cash_allocation_pct, 1),
                'position_allocation_pct': round(position_allocation_pct, 1),
                'is_averaging_up': current_avg_cost > 0 and stock_price > current_avg_cost,
                'is_averaging_down': current_avg_cost > 0 and stock_price < current_avg_cost
            }
            
            enhanced_daily.append(enhanced_row)
        
        return enhanced_daily
    
    def calculate_risk_metrics(self) -> Dict[str, float]:
        """Calculate portfolio risk and performance metrics."""
        if self.daily_df.empty:
            return {}
        
        # Daily returns
        portfolio_values = self.daily_df['portfolio_value'].values
        daily_returns = np.diff(portfolio_values) / portfolio_values[:-1]
        
        # Maximum drawdown
        cumulative_max = np.maximum.accumulate(portfolio_values)
        drawdowns = (portfolio_values - cumulative_max) / cumulative_max
        max_drawdown = np.min(drawdowns) * 100
        
        # Volatility (annualized)
        volatility = np.std(daily_returns) * np.sqrt(252) * 100
        
        # Sharpe ratio (assuming 4% risk-free rate)
        risk_free_rate = 0.04 / 252  # Daily risk-free rate
        excess_returns = daily_returns - risk_free_rate
        sharpe_ratio = np.mean(excess_returns) / np.std(daily_returns) * np.sqrt(252)
        
        # Time in market
        time_in_market = (self.daily_df['position'] > 0).sum() / len(self.daily_df) * 100
        
        # Average holding period
        trades_df = self.trades_df
        if not trades_df.empty:
            buy_trades = trades_df[trades_df['action'] == 'BUY']
            sell_trades = trades_df[trades_df['action'] == 'SELL']
            
            holding_periods = []
            for _, sell_trade in sell_trades.iterrows():
                if 'entry_date' in sell_trade:
                    entry_date = pd.to_datetime(sell_trade['entry_date'])
                    exit_date = pd.to_datetime(sell_trade['date'])
                    holding_days = (exit_date - entry_date).days
                    holding_periods.append(holding_days)
            
            avg_holding_period = np.mean(holding_periods) if holding_periods else 0
        else:
            avg_holding_period = 0
        
        return {
            'max_drawdown_pct': round(max_drawdown, 2),
            'volatility_pct': round(volatility, 2),
            'sharpe_ratio': round(sharpe_ratio, 3),
            'time_in_market_pct': round(time_in_market, 1),
            'avg_holding_period_days': round(avg_holding_period, 1)
        }
    
    def calculate_trade_analysis(self) -> Dict[str, Any]:
        """Analyze trading patterns and performance."""
        trades_df = self.trades_df
        if trades_df.empty:
            return {}
        
        # Trade statistics
        buy_trades = trades_df[trades_df['action'] == 'BUY']
        sell_trades = trades_df[trades_df['action'] == 'SELL']
        
        # Position sizing analysis
        position_sizes = buy_trades['shares'] * buy_trades['price']
        avg_position_size = position_sizes.mean()
        position_size_std = position_sizes.std()
        
        # Round trip analysis
        round_trips = sell_trades[sell_trades['return_pct'].notna()]
        if not round_trips.empty:
            avg_return_per_trade = round_trips['return_pct'].mean()
            best_trade = round_trips['return_pct'].max()
            worst_trade = round_trips['return_pct'].min()
            profitable_trades_pct = (round_trips['return_pct'] > 0).sum() / len(round_trips) * 100
        else:
            avg_return_per_trade = 0
            best_trade = 0
            worst_trade = 0
            profitable_trades_pct = 0
        
        return {
            'total_trades': len(trades_df),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'avg_position_size': round(avg_position_size, 2),
            'position_size_std': round(position_size_std, 2),
            'avg_return_per_trade_pct': round(avg_return_per_trade, 2),
            'best_trade_pct': round(best_trade, 2),
            'worst_trade_pct': round(worst_trade, 2),
            'profitable_trades_pct': round(profitable_trades_pct, 1)
        }
    
    def enhance_results(self) -> Dict[str, Any]:
        """Create enhanced results with all additional metrics."""
        enhanced_daily = self.calculate_position_average()
        risk_metrics = self.calculate_risk_metrics()
        trade_analysis = self.calculate_trade_analysis()
        
        # Create enhanced results
        enhanced_results = self.data.copy()
        enhanced_results['daily_values'] = enhanced_daily
        enhanced_results['risk_metrics'] = risk_metrics
        enhanced_results['trade_analysis'] = trade_analysis
        enhanced_results['enhancement_metadata'] = {
            'enhanced_at': datetime.now().isoformat(),
            'enhancement_version': '1.0',
            'new_metrics': [
                'position_avg_cost', 'position_value', 'cost_basis',
                'unrealized_pnl', 'unrealized_pnl_pct', 
                'cash_allocation_pct', 'position_allocation_pct',
                'is_averaging_up', 'is_averaging_down'
            ]
        }
        
        return enhanced_results
    
    def save_enhanced_results(self, output_file: Optional[str] = None):
        """Save enhanced results to file."""
        enhanced_results = self.enhance_results()
        
        if output_file is None:
            # Create enhanced filename
            output_file = str(self.results_file).replace('.json', '_enhanced.json')
        
        with open(output_file, 'w') as f:
            json.dump(enhanced_results, f, indent=2)
        
        print(f"Enhanced results saved to: {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(description='Enhance backtest results with additional metrics')
    parser.add_argument('results_file', help='Path to existing backtest results JSON file')
    parser.add_argument('--output', '-o', help='Output file path (optional)')
    parser.add_argument('--show-sample', action='store_true', help='Show sample of enhanced data')
    
    args = parser.parse_args()
    
    enhancer = BacktestEnhancer(args.results_file)
    output_file = enhancer.save_enhanced_results(args.output)
    
    if args.show_sample:
        # Show sample of enhanced data
        enhanced_results = enhancer.enhance_results()
        print("\n📊 ENHANCED METRICS SAMPLE")
        print("=" * 50)
        
        # Show first few days
        sample_daily = enhanced_results['daily_values'][:5]
        for day in sample_daily:
            print(f"\n📅 {day['date']}")
            print(f"  Portfolio: ${day['portfolio_value']:,.2f}")
            print(f"  Position: {day['position']} shares @ ${day['position_avg_cost']:.2f} avg")
            print(f"  Unrealized P&L: ${day['unrealized_pnl']:,.2f} ({day['unrealized_pnl_pct']:+.1f}%)")
            print(f"  Allocation: {day['position_allocation_pct']:.1f}% stocks, {day['cash_allocation_pct']:.1f}% cash")
        
        # Show risk metrics
        print(f"\n📈 RISK METRICS")
        risk = enhanced_results['risk_metrics']
        for key, value in risk.items():
            print(f"  {key}: {value}")
        
        # Show trade analysis
        print(f"\n💼 TRADE ANALYSIS")
        trade_analysis = enhanced_results['trade_analysis']
        for key, value in trade_analysis.items():
            print(f"  {key}: {value}")


if __name__ == '__main__':
    main()