#!/usr/bin/env python3
"""
MACD Parameter Optimization Using Existing Backtest Results

Analyzes existing backtest results to test different MACD parameters
without requiring new data collection.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from ...core.indicators.indicator_library import macd


class MACDResultsOptimizer:
    """Optimize MACD parameters using existing backtest results."""
    
    def __init__(self, results_dir: str = "reports/continuous_backtests"):
        """Initialize optimizer with results directory."""
        self.results_dir = Path(results_dir)
        self.optimization_results = []
        
        # Common MACD parameter sets to test
        self.param_sets = [
            (12, 26, 9),   # Standard MACD
            (8, 21, 5),    # Faster signals
            (5, 35, 5),    # Very fast/slow contrast
            (13, 34, 9),   # Fibonacci-based
            (10, 20, 5),   # Shorter-term trading
            (15, 30, 10),  # Slightly slower
            (7, 14, 7),    # Week-based periods
            (20, 50, 10),  # Longer-term trending
        ]
        
    def load_backtest_results(self, symbol: str, version: str = "V0") -> Optional[Dict]:
        """Load existing backtest results for a symbol."""
        results_file = self.results_dir / version / f"{symbol}_2024_results.json"
        
        if not results_file.exists():
            print(f"Results file not found: {results_file}")
            return None
            
        with open(results_file, 'r') as f:
            return json.load(f)
    
    def extract_market_data(self, results: Dict) -> pd.DataFrame:
        """Extract market data from backtest results."""
        daily_values = results.get('daily_values', [])
        
        if not daily_values:
            return pd.DataFrame()
            
        df = pd.DataFrame(daily_values)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Rename columns to match expected format
        df.rename(columns={'stock_price': 'close'}, inplace=True)
        
        return df
    
    def simulate_macd_strategy(self, 
                              df: pd.DataFrame,
                              fast: int,
                              slow: int,
                              signal: int,
                              initial_cash: float = 100000) -> Dict:
        """Simulate MACD strategy with given parameters."""
        
        if 'close' not in df.columns:
            return {}
            
        # Calculate MACD
        macd_df = macd(df['close'], fast=fast, slow=slow, signal=signal)
        
        # Generate signals
        macd_df['buy_signal'] = (
            (macd_df['MACD_line'] > macd_df['MACD_signal']) & 
            (macd_df['MACD_line'].shift(1) <= macd_df['MACD_signal'].shift(1))
        )
        
        macd_df['sell_signal'] = (
            (macd_df['MACD_line'] < macd_df['MACD_signal']) & 
            (macd_df['MACD_line'].shift(1) >= macd_df['MACD_signal'].shift(1))
        )
        
        # Simulate trading
        cash = initial_cash
        position = 0
        trades = []
        portfolio_values = []
        
        for date, row in df.iterrows():
            if date in macd_df.index:
                # Buy signal
                if macd_df.loc[date, 'buy_signal'] and cash > 0 and position == 0:
                    shares = int(cash * 0.95 / row['close'])
                    if shares > 0:
                        cost = shares * row['close']
                        cash -= cost
                        position = shares
                        trades.append({
                            'date': date,
                            'action': 'BUY',
                            'price': row['close'],
                            'shares': shares
                        })
                
                # Sell signal
                elif macd_df.loc[date, 'sell_signal'] and position > 0:
                    proceeds = position * row['close']
                    cash += proceeds
                    trades.append({
                        'date': date,
                        'action': 'SELL',
                        'price': row['close'],
                        'shares': position,
                        'proceeds': proceeds
                    })
                    position = 0
            
            # Track portfolio value
            portfolio_value = cash + (position * row['close'])
            portfolio_values.append(portfolio_value)
        
        # Calculate metrics
        if not portfolio_values:
            return {}
            
        final_value = portfolio_values[-1]
        total_return = (final_value - initial_cash) / initial_cash * 100
        
        # Max drawdown
        peak = initial_cash
        max_drawdown = 0
        for value in portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # Win rate
        winning_trades = 0
        total_sell_trades = 0
        
        for i, trade in enumerate(trades):
            if trade['action'] == 'SELL':
                total_sell_trades += 1
                # Find corresponding buy
                for j in range(i-1, -1, -1):
                    if trades[j]['action'] == 'BUY':
                        if trade['price'] > trades[j]['price']:
                            winning_trades += 1
                        break
        
        win_rate = (winning_trades / total_sell_trades * 100) if total_sell_trades > 0 else 0
        
        return {
            'parameters': f"({fast},{slow},{signal})",
            'fast': fast,
            'slow': slow, 
            'signal': signal,
            'total_return': total_return,
            'final_value': final_value,
            'max_drawdown': max_drawdown,
            'num_trades': len([t for t in trades if t['action'] == 'BUY']),
            'win_rate': win_rate,
            'winning_trades': winning_trades,
            'total_trades': total_sell_trades
        }
    
    def optimize_symbol(self, symbol: str) -> List[Dict]:
        """Optimize MACD parameters for a specific symbol."""
        print(f"\nOptimizing MACD parameters for {symbol}...")
        
        # Load backtest results
        results = self.load_backtest_results(symbol)
        if not results:
            return []
        
        # Extract market data
        df = self.extract_market_data(results)
        if df.empty:
            print(f"No market data found for {symbol}")
            return []
        
        optimization_results = []
        
        # Test each parameter set
        for fast, slow, signal in self.param_sets:
            try:
                result = self.simulate_macd_strategy(df, fast, slow, signal)
                if result:
                    result['symbol'] = symbol
                    optimization_results.append(result)
                    print(f"  ({fast:2},{slow:2},{signal:2}) -> Return: {result['total_return']:6.2f}%, Win Rate: {result['win_rate']:5.1f}%")
            except Exception as e:
                print(f"  Error with ({fast},{slow},{signal}): {e}")
        
        # Sort by total return
        optimization_results.sort(key=lambda x: x['total_return'], reverse=True)
        
        return optimization_results
    
    def optimize_all_symbols(self) -> Dict[str, List[Dict]]:
        """Optimize MACD parameters for all available symbols."""
        all_results = {}
        
        # Find all result files
        v0_dir = self.results_dir / "V0"
        if not v0_dir.exists():
            print(f"V0 results directory not found")
            return all_results
        
        # Get unique symbols
        symbols = set()
        for file in v0_dir.glob("*_results.json"):
            symbol = file.stem.split('_')[0]
            symbols.add(symbol)
        
        print(f"Found {len(symbols)} symbols to optimize: {', '.join(sorted(symbols))}")
        
        # Optimize each symbol
        for symbol in sorted(symbols):
            results = self.optimize_symbol(symbol)
            if results:
                all_results[symbol] = results
        
        return all_results
    
    def generate_report(self, all_results: Dict[str, List[Dict]]) -> str:
        """Generate optimization report."""
        report = []
        report.append("\nMACD PARAMETER OPTIMIZATION REPORT")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        for symbol, results in all_results.items():
            if not results:
                continue
                
            report.append(f"\n{symbol} - Best Parameters")
            report.append("-" * 40)
            
            # Best result
            best = results[0]
            report.append(f"Best: ({best['fast']},{best['slow']},{best['signal']})")
            report.append(f"  Return: {best['total_return']:.2f}%")
            report.append(f"  Max Drawdown: {best['max_drawdown']:.2f}%")
            report.append(f"  Win Rate: {best['win_rate']:.1f}%")
            report.append(f"  Trades: {best['num_trades']}")
            
            # Top 3
            report.append("\nTop 3 Parameter Sets:")
            for i, result in enumerate(results[:3], 1):
                report.append(f"{i}. ({result['fast']:2},{result['slow']:2},{result['signal']:2}) "
                            f"Return: {result['total_return']:6.2f}% "
                            f"DD: {result['max_drawdown']:5.2f}% "
                            f"WR: {result['win_rate']:5.1f}%")
        
        # Overall best across all symbols
        report.append("\n\nOVERALL BEST PARAMETERS")
        report.append("=" * 70)
        
        # Aggregate scores
        param_scores = {}
        for symbol, results in all_results.items():
            for result in results:
                key = (result['fast'], result['slow'], result['signal'])
                if key not in param_scores:
                    param_scores[key] = []
                param_scores[key].append(result['total_return'])
        
        # Calculate average returns
        avg_returns = []
        for params, returns in param_scores.items():
            avg_return = sum(returns) / len(returns)
            avg_returns.append({
                'params': params,
                'avg_return': avg_return,
                'num_symbols': len(returns)
            })
        
        avg_returns.sort(key=lambda x: x['avg_return'], reverse=True)
        
        report.append("Average Return Across All Symbols:")
        for i, item in enumerate(avg_returns[:5], 1):
            params = item['params']
            report.append(f"{i}. ({params[0]:2},{params[1]:2},{params[2]:2}) "
                        f"Avg Return: {item['avg_return']:6.2f}% "
                        f"(tested on {item['num_symbols']} symbols)")
        
        return "\n".join(report)
    
    def save_results(self, all_results: Dict[str, List[Dict]], 
                    output_dir: str = "reports/optimization"):
        """Save optimization results to JSON."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = output_path / f"macd_optimization_{timestamp}.json"
        
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'param_sets_tested': self.param_sets,
            'results_by_symbol': all_results,
            'summary': self.generate_summary_stats(all_results)
        }
        
        with open(filename, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"\nResults saved to: {filename}")
        return filename
    
    def generate_summary_stats(self, all_results: Dict[str, List[Dict]]) -> Dict:
        """Generate summary statistics."""
        summary = {
            'num_symbols': len(all_results),
            'total_tests': sum(len(r) for r in all_results.values()),
            'best_by_symbol': {},
            'standard_macd_performance': {}
        }
        
        for symbol, results in all_results.items():
            if results:
                # Best for this symbol
                summary['best_by_symbol'][symbol] = {
                    'parameters': f"({results[0]['fast']},{results[0]['slow']},{results[0]['signal']})",
                    'return': results[0]['total_return']
                }
                
                # Standard MACD (12,26,9) performance
                for r in results:
                    if r['fast'] == 12 and r['slow'] == 26 and r['signal'] == 9:
                        summary['standard_macd_performance'][symbol] = r['total_return']
                        break
        
        return summary


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='MACD Parameter Optimization from Results')
    parser.add_argument('--symbol', help='Specific symbol to optimize')
    parser.add_argument('--save', action='store_true', help='Save results to file')
    
    args = parser.parse_args()
    
    optimizer = MACDResultsOptimizer()
    
    if args.symbol:
        results = optimizer.optimize_symbol(args.symbol)
        if results:
            print(f"\nTop 3 for {args.symbol}:")
            for i, r in enumerate(results[:3], 1):
                print(f"{i}. {r['parameters']}: {r['total_return']:.2f}%")
    else:
        all_results = optimizer.optimize_all_symbols()
        report = optimizer.generate_report(all_results)
        print(report)
        
        if args.save:
            optimizer.save_results(all_results)


if __name__ == "__main__":
    main()