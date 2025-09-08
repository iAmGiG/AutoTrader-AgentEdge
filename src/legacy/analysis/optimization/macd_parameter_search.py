#!/usr/bin/env python3
"""
MACD Parameter Optimization Framework

Tests different MACD parameter combinations to find optimal settings
for various market conditions and trading strategies.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# Import indicator library
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from ...core.indicators.indicator_library import macd


class MACDParameterOptimizer:
    """Optimize MACD parameters through grid search and analysis."""
    
    def __init__(self, 
                 data_dir: str = ".cache/market_data",
                 results_dir: str = "reports/optimization"):
        """
        Initialize MACD parameter optimizer.
        
        Parameters:
        -----------
        data_dir : str
            Directory containing cached market data
        results_dir : str
            Directory to save optimization results
        """
        self.data_dir = Path(data_dir)
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Default parameter ranges
        self.default_param_ranges = {
            'fast': [5, 8, 12, 15],           # Fast EMA periods
            'slow': [20, 26, 35, 40],         # Slow EMA periods  
            'signal': [5, 7, 9, 12]           # Signal line periods
        }
        
        # Common parameter sets used in practice
        self.common_param_sets = [
            (12, 26, 9),   # Standard MACD
            (8, 21, 5),    # Faster signals
            (5, 35, 5),    # Very fast/slow contrast
            (13, 34, 9),   # Fibonacci-based
            (10, 20, 5),   # Shorter-term trading
            (15, 30, 10),  # Slightly slower standard
        ]
        
    def load_market_data(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        Load market data from cache.
        
        Parameters:
        -----------
        symbol : str
            Stock symbol (e.g., 'AAPL')
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format
            
        Returns:
        --------
        pd.DataFrame or None
            Market data with OHLCV columns
        """
        # Look for consolidated cache files
        pattern = f"{symbol}_{start_date}_{end_date}_*_consolidated.json"
        cache_files = list(self.data_dir.glob(pattern))
        
        if not cache_files:
            print(f"No cached data found for {symbol} from {start_date} to {end_date}")
            return None
            
        # Load the first matching file
        cache_file = cache_files[0]
        print(f"Loading data from: {cache_file.name}")
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
            
        # Convert to DataFrame
        df = pd.DataFrame(data['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Ensure we have required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            print(f"Missing required columns in data")
            return None
            
        return df
    
    def calculate_macd_signals(self, 
                              prices: pd.Series, 
                              fast: int, 
                              slow: int, 
                              signal: int) -> pd.DataFrame:
        """
        Calculate MACD indicators and generate trading signals.
        
        Parameters:
        -----------
        prices : pd.Series
            Close prices
        fast : int
            Fast EMA period
        slow : int
            Slow EMA period
        signal : int
            Signal line EMA period
            
        Returns:
        --------
        pd.DataFrame
            MACD values and trading signals
        """
        # Calculate MACD using indicator library
        macd_df = macd(prices, fast=fast, slow=slow, signal=signal)
        
        # Generate crossover signals
        macd_df['bullish_signal'] = (
            (macd_df['MACD_line'] > macd_df['MACD_signal']) & 
            (macd_df['MACD_line'].shift(1) <= macd_df['MACD_signal'].shift(1))
        )
        
        macd_df['bearish_signal'] = (
            (macd_df['MACD_line'] < macd_df['MACD_signal']) & 
            (macd_df['MACD_line'].shift(1) >= macd_df['MACD_signal'].shift(1))
        )
        
        return macd_df
    
    def backtest_macd_parameters(self,
                                 df: pd.DataFrame,
                                 fast: int,
                                 slow: int,
                                 signal: int,
                                 initial_cash: float = 100000) -> Dict:
        """
        Backtest a specific MACD parameter combination.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Market data
        fast, slow, signal : int
            MACD parameters
        initial_cash : float
            Starting capital
            
        Returns:
        --------
        Dict
            Backtest results and metrics
        """
        # Calculate MACD signals
        macd_df = self.calculate_macd_signals(df['close'], fast, slow, signal)
        
        # Initialize backtest variables
        cash = initial_cash
        position = 0
        trades = []
        portfolio_values = []
        
        for date, row in df.iterrows():
            # Check for signals
            if macd_df.loc[date, 'bullish_signal'] and cash > 0:
                # Buy signal
                shares = int(cash * 0.95 / row['close'])  # Use 95% of cash
                if shares > 0:
                    cost = shares * row['close']
                    cash -= cost
                    position += shares
                    trades.append({
                        'date': date,
                        'action': 'BUY',
                        'shares': shares,
                        'price': row['close'],
                        'cost': cost
                    })
                    
            elif macd_df.loc[date, 'bearish_signal'] and position > 0:
                # Sell signal
                proceeds = position * row['close']
                cash += proceeds
                trades.append({
                    'date': date,
                    'action': 'SELL',
                    'shares': position,
                    'price': row['close'],
                    'proceeds': proceeds
                })
                position = 0
                
            # Track portfolio value
            portfolio_value = cash + (position * row['close'])
            portfolio_values.append(portfolio_value)
        
        # Calculate metrics
        final_value = portfolio_values[-1] if portfolio_values else initial_cash
        total_return = (final_value - initial_cash) / initial_cash * 100
        
        # Calculate max drawdown
        peak = initial_cash
        max_drawdown = 0
        for value in portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # Calculate Sharpe ratio (simplified)
        returns = pd.Series(portfolio_values).pct_change().dropna()
        if len(returns) > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
            
        # Win rate calculation
        winning_trades = 0
        losing_trades = 0
        
        for i, trade in enumerate(trades):
            if trade['action'] == 'SELL' and i > 0:
                # Find the previous buy
                for j in range(i-1, -1, -1):
                    if trades[j]['action'] == 'BUY':
                        buy_price = trades[j]['price']
                        sell_price = trade['price']
                        if sell_price > buy_price:
                            winning_trades += 1
                        else:
                            losing_trades += 1
                        break
        
        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'parameters': {'fast': fast, 'slow': slow, 'signal': signal},
            'total_return': total_return,
            'final_value': final_value,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'num_trades': len([t for t in trades if t['action'] == 'BUY']),
            'win_rate': win_rate,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades
        }
    
    def grid_search(self,
                   symbol: str,
                   start_date: str,
                   end_date: str,
                   param_ranges: Optional[Dict] = None,
                   use_parallel: bool = True) -> List[Dict]:
        """
        Perform grid search over MACD parameter combinations.
        
        Parameters:
        -----------
        symbol : str
            Stock symbol
        start_date : str
            Start date for backtest
        end_date : str
            End date for backtest
        param_ranges : Dict, optional
            Custom parameter ranges
        use_parallel : bool
            Use parallel processing
            
        Returns:
        --------
        List[Dict]
            Results for all parameter combinations
        """
        # Load market data
        df = self.load_market_data(symbol, start_date, end_date)
        if df is None:
            return []
        
        # Use default or custom parameter ranges
        if param_ranges is None:
            param_ranges = self.default_param_ranges
            
        # Generate all parameter combinations
        param_combinations = []
        for fast, slow, signal in itertools.product(
            param_ranges['fast'],
            param_ranges['slow'],
            param_ranges['signal']
        ):
            # Ensure fast < slow (MACD requirement)
            if fast < slow:
                param_combinations.append((fast, slow, signal))
        
        print(f"Testing {len(param_combinations)} parameter combinations...")
        
        results = []
        
        if use_parallel:
            # Parallel processing
            with ProcessPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(
                        self.backtest_macd_parameters, df, fast, slow, signal
                    ): (fast, slow, signal)
                    for fast, slow, signal in param_combinations
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        print(f"Completed: {result['parameters']}")
                    except Exception as e:
                        params = futures[future]
                        print(f"Error with parameters {params}: {e}")
        else:
            # Sequential processing
            for fast, slow, signal in param_combinations:
                try:
                    result = self.backtest_macd_parameters(df, fast, slow, signal)
                    results.append(result)
                    print(f"Completed: ({fast}, {slow}, {signal})")
                except Exception as e:
                    print(f"Error with ({fast}, {slow}, {signal}): {e}")
        
        # Sort results by total return
        results.sort(key=lambda x: x['total_return'], reverse=True)
        
        return results
    
    def test_common_parameters(self,
                              symbol: str,
                              start_date: str,
                              end_date: str) -> List[Dict]:
        """
        Test commonly used MACD parameter sets.
        
        Parameters:
        -----------
        symbol : str
            Stock symbol
        start_date : str
            Start date
        end_date : str
            End date
            
        Returns:
        --------
        List[Dict]
            Results for common parameter sets
        """
        # Load market data
        df = self.load_market_data(symbol, start_date, end_date)
        if df is None:
            return []
        
        results = []
        
        print(f"Testing {len(self.common_param_sets)} common parameter sets...")
        
        for fast, slow, signal in self.common_param_sets:
            try:
                result = self.backtest_macd_parameters(df, fast, slow, signal)
                results.append(result)
                print(f"Completed: ({fast}, {slow}, {signal}) - Return: {result['total_return']:.2f}%")
            except Exception as e:
                print(f"Error with ({fast}, {slow}, {signal}): {e}")
        
        # Sort by total return
        results.sort(key=lambda x: x['total_return'], reverse=True)
        
        return results
    
    def save_results(self, results: List[Dict], filename: str):
        """
        Save optimization results to file.
        
        Parameters:
        -----------
        results : List[Dict]
            Optimization results
        filename : str
            Output filename
        """
        output_path = self.results_dir / filename
        
        # Add metadata
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'num_combinations_tested': len(results),
            'results': results,
            'best_parameters': results[0] if results else None,
            'top_5': results[:5] if len(results) >= 5 else results
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"Results saved to: {output_path}")
    
    def generate_report(self, results: List[Dict]) -> str:
        """
        Generate a summary report of optimization results.
        
        Parameters:
        -----------
        results : List[Dict]
            Optimization results
            
        Returns:
        --------
        str
            Formatted report
        """
        if not results:
            return "No results to report"
        
        report = []
        report.append("MACD Parameter Optimization Report")
        report.append("=" * 50)
        report.append(f"Total combinations tested: {len(results)}")
        report.append("")
        
        # Best parameters
        best = results[0]
        report.append("Best Parameters:")
        report.append(f"  Fast: {best['parameters']['fast']}")
        report.append(f"  Slow: {best['parameters']['slow']}")
        report.append(f"  Signal: {best['parameters']['signal']}")
        report.append(f"  Total Return: {best['total_return']:.2f}%")
        report.append(f"  Max Drawdown: {best['max_drawdown']:.2f}%")
        report.append(f"  Sharpe Ratio: {best['sharpe_ratio']:.3f}")
        report.append(f"  Win Rate: {best['win_rate']:.1f}%")
        report.append("")
        
        # Top 5 results
        report.append("Top 5 Parameter Sets:")
        report.append("-" * 50)
        report.append(f"{'Rank':<5} {'Fast':<5} {'Slow':<5} {'Signal':<7} {'Return %':<10} {'Sharpe':<8} {'Win %':<7}")
        
        for i, result in enumerate(results[:5], 1):
            params = result['parameters']
            report.append(
                f"{i:<5} {params['fast']:<5} {params['slow']:<5} {params['signal']:<7} "
                f"{result['total_return']:<10.2f} {result['sharpe_ratio']:<8.3f} "
                f"{result['win_rate']:<7.1f}"
            )
        
        return "\n".join(report)


def main():
    """Main function for testing MACD parameter optimization."""
    import argparse
    
    parser = argparse.ArgumentParser(description='MACD Parameter Optimization')
    parser.add_argument('--symbol', default='AAPL', help='Stock symbol')
    parser.add_argument('--start', default='2024-01-01', help='Start date')
    parser.add_argument('--end', default='2024-12-31', help='End date')
    parser.add_argument('--mode', choices=['grid', 'common'], default='common',
                       help='Optimization mode: grid search or common parameters')
    parser.add_argument('--output', help='Output filename for results')
    
    args = parser.parse_args()
    
    # Create optimizer
    optimizer = MACDParameterOptimizer()
    
    # Run optimization
    if args.mode == 'grid':
        print(f"Running grid search for {args.symbol}...")
        results = optimizer.grid_search(args.symbol, args.start, args.end)
    else:
        print(f"Testing common parameters for {args.symbol}...")
        results = optimizer.test_common_parameters(args.symbol, args.start, args.end)
    
    if results:
        # Generate and print report
        report = optimizer.generate_report(results)
        print("\n" + report)
        
        # Save results
        if args.output:
            optimizer.save_results(results, args.output)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"macd_optimization_{args.symbol}_{timestamp}.json"
            optimizer.save_results(results, filename)
    else:
        print("No results generated")


if __name__ == "__main__":
    main()