#!/usr/bin/env python3
"""
MetricsAnalyzer - Comprehensive analysis of existing backtest JSON results.

Analyzes existing V0-V4 backtest results to provide advanced metrics including:
- Sentiment effectiveness analysis
- Trade quality metrics
- Risk-adjusted performance
- Market regime performance
- Strategy comparison matrices
- Checkpoint extraction for continuation
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')


class MetricsAnalyzer:
    """Analyze existing backtest JSON results with comprehensive metrics."""
    
    def __init__(self, results_dir: str = "reports/continuous_backtests"):
        self.results_dir = Path(results_dir)
        self.analysis_results = {}
        
    def load_result_file(self, file_path: Path) -> Optional[Dict]:
        """Load and validate a single result JSON file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return None
    
    def calculate_sentiment_effectiveness(self, trades: List[Dict]) -> Dict:
        """Analyze effectiveness of different sentiment ranges."""
        sentiment_buckets = {
            'very_bearish': {'range': (0.0, 0.3), 'trades': [], 'returns': []},
            'bearish': {'range': (0.3, 0.5), 'trades': [], 'returns': []},
            'neutral': {'range': (0.5, 0.7), 'trades': [], 'returns': []},
            'bullish': {'range': (0.7, 1.0), 'trades': [], 'returns': []}
        }
        
        # Group SELL trades by entry sentiment
        for trade in trades:
            if trade['action'] == 'SELL' and 'return_pct' in trade:
                sentiment = trade.get('sentiment', 0.5)
                return_pct = trade['return_pct']
                
                for bucket_name, bucket in sentiment_buckets.items():
                    min_val, max_val = bucket['range']
                    if min_val <= sentiment < max_val or (bucket_name == 'bullish' and sentiment == 1.0):
                        bucket['trades'].append(trade)
                        bucket['returns'].append(return_pct)
                        break
        
        # Calculate metrics for each bucket
        analysis = {}
        for bucket_name, bucket in sentiment_buckets.items():
            if bucket['returns']:
                returns = np.array(bucket['returns'])
                analysis[bucket_name] = {
                    'total_trades': len(returns),
                    'win_rate': (returns > 0).mean() * 100,
                    'avg_return': returns.mean(),
                    'total_return': returns.sum(),
                    'best_trade': returns.max(),
                    'worst_trade': returns.min(),
                    'sentiment_range': bucket['range']
                }
            else:
                analysis[bucket_name] = {
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_return': 0,
                    'total_return': 0,
                    'best_trade': 0,
                    'worst_trade': 0,
                    'sentiment_range': bucket['range']
                }
        
        return analysis
    
    def calculate_trade_quality_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate comprehensive trade quality metrics."""
        sell_trades = [t for t in trades if t['action'] == 'SELL' and 'return_pct' in t]
        
        if not sell_trades:
            return {
                'holding_periods': {'avg': 0, 'min': 0, 'max': 0},
                'profit_factor': 0,
                'largest_winner': 0,
                'largest_loser': 0,
                'avg_winner': 0,
                'avg_loser': 0,
                'win_loss_ratio': 0,
                'consecutive_wins': 0,
                'consecutive_losses': 0
            }
        
        returns = [t['return_pct'] for t in sell_trades]
        holding_periods = []
        
        # Calculate holding periods
        for trade in sell_trades:
            if 'entry_date' in trade:
                entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d')
                exit_date = datetime.strptime(trade['date'], '%Y-%m-%d')
                holding_days = (exit_date - entry_date).days
                holding_periods.append(holding_days)
        
        winners = [r for r in returns if r > 0]
        losers = [r for r in returns if r < 0]
        
        # Profit factor calculation
        total_wins = sum(winners) if winners else 0
        total_losses = abs(sum(losers)) if losers else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Win/loss streaks
        consecutive_wins = consecutive_losses = 0
        current_win_streak = current_loss_streak = 0
        max_win_streak = max_loss_streak = 0
        
        for ret in returns:
            if ret > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            else:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
        
        return {
            'holding_periods': {
                'avg': np.mean(holding_periods) if holding_periods else 0,
                'min': min(holding_periods) if holding_periods else 0,
                'max': max(holding_periods) if holding_periods else 0
            },
            'profit_factor': profit_factor,
            'largest_winner': max(returns) if returns else 0,
            'largest_loser': min(returns) if returns else 0,
            'avg_winner': np.mean(winners) if winners else 0,
            'avg_loser': np.mean(losers) if losers else 0,
            'win_loss_ratio': (np.mean(winners) / abs(np.mean(losers))) if losers and winners else 0,
            'consecutive_wins': max_win_streak,
            'consecutive_losses': max_loss_streak,
            'total_winning_trades': len(winners),
            'total_losing_trades': len(losers)
        }
    
    def calculate_risk_metrics(self, daily_values: List[Dict], initial_cash: float) -> Dict:
        """Calculate risk-adjusted performance metrics."""
        if not daily_values:
            return {
                'max_drawdown': 0,
                'drawdown_duration': 0,
                'calmar_ratio': 0,
                'recovery_factor': 0,
                'sharpe_ratio': 0,
                'volatility': 0
            }
        
        portfolio_values = [d['portfolio_value'] for d in daily_values]
        dates = [datetime.strptime(d['date'], '%Y-%m-%d') for d in daily_values]
        
        # Calculate returns
        returns = []
        for i in range(1, len(portfolio_values)):
            daily_return = (portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
            returns.append(daily_return)
        
        # Maximum drawdown calculation
        peak = portfolio_values[0]
        max_drawdown = 0
        drawdown_start = None
        max_drawdown_duration = 0
        current_drawdown_duration = 0
        
        for i, value in enumerate(portfolio_values):
            if value > peak:
                peak = value
                if drawdown_start is not None:
                    # End of drawdown period
                    current_drawdown_duration = i - drawdown_start
                    max_drawdown_duration = max(max_drawdown_duration, current_drawdown_duration)
                    drawdown_start = None
            else:
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                if drawdown_start is None:
                    drawdown_start = i
        
        # Final drawdown duration if still in drawdown
        if drawdown_start is not None:
            current_drawdown_duration = len(portfolio_values) - 1 - drawdown_start
            max_drawdown_duration = max(max_drawdown_duration, current_drawdown_duration)
        
        # Annualized return
        final_value = portfolio_values[-1]
        total_return = (final_value - initial_cash) / initial_cash
        days = (dates[-1] - dates[0]).days
        annualized_return = (1 + total_return) ** (365.25 / days) - 1 if days > 0 else 0
        
        # Risk metrics
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else float('inf')
        recovery_factor = total_return / max_drawdown if max_drawdown > 0 else float('inf')
        
        # Sharpe ratio (assuming risk-free rate of 2%)
        risk_free_rate = 0.02 / 252  # Daily risk-free rate
        if returns:
            excess_returns = [r - risk_free_rate for r in returns]
            sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
            volatility = np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = volatility = 0
        
        return {
            'max_drawdown': max_drawdown * 100,  # Convert to percentage
            'drawdown_duration': max_drawdown_duration,
            'calmar_ratio': calmar_ratio,
            'recovery_factor': recovery_factor,
            'sharpe_ratio': sharpe_ratio,
            'volatility': volatility * 100,  # Convert to percentage
            'annualized_return': annualized_return * 100
        }
    
    def detect_market_regimes(self, daily_values: List[Dict], window_50: int = 50, window_200: int = 200) -> List[Dict]:
        """Detect bull/bear market regimes using moving averages."""
        if len(daily_values) < window_200:
            return []
        
        enriched_data = []
        stock_prices = [d['stock_price'] for d in daily_values]
        
        for i, day_data in enumerate(daily_values):
            regime_data = day_data.copy()
            
            if i >= window_200:
                # Calculate moving averages
                ma_50 = np.mean(stock_prices[i-window_50:i]) if i >= window_50 else stock_prices[i]
                ma_200 = np.mean(stock_prices[i-window_200:i])
                
                # Determine regime
                regime_data['ma_50'] = ma_50
                regime_data['ma_200'] = ma_200
                regime_data['regime'] = 'bull' if ma_50 > ma_200 else 'bear'
            else:
                regime_data['ma_50'] = stock_prices[i]
                regime_data['ma_200'] = stock_prices[i]
                regime_data['regime'] = 'neutral'  # Not enough data
            
            enriched_data.append(regime_data)
        
        return enriched_data
    
    def calculate_regime_performance(self, trades: List[Dict], daily_values_with_regime: List[Dict]) -> Dict:
        """Calculate strategy performance during different market regimes."""
        # Create a date-to-regime mapping
        regime_map = {d['date']: d['regime'] for d in daily_values_with_regime}
        
        bull_trades = []
        bear_trades = []
        neutral_trades = []
        
        for trade in trades:
            if trade['action'] == 'SELL' and 'return_pct' in trade:
                regime = regime_map.get(trade['date'], 'neutral')
                if regime == 'bull':
                    bull_trades.append(trade['return_pct'])
                elif regime == 'bear':
                    bear_trades.append(trade['return_pct'])
                else:
                    neutral_trades.append(trade['return_pct'])
        
        def calc_regime_stats(trades_returns: List[float]) -> Dict:
            if not trades_returns:
                return {'total_trades': 0, 'win_rate': 0, 'avg_return': 0, 'total_return': 0}
            
            returns = np.array(trades_returns)
            return {
                'total_trades': len(returns),
                'win_rate': (returns > 0).mean() * 100,
                'avg_return': returns.mean(),
                'total_return': returns.sum()
            }
        
        return {
            'bull_market': calc_regime_stats(bull_trades),
            'bear_market': calc_regime_stats(bear_trades),
            'neutral_market': calc_regime_stats(neutral_trades)
        }
    
    def extract_checkpoint_data(self, data: Dict) -> Dict:
        """Extract final state data for continuation into 2025."""
        daily_values = data.get('daily_values', [])
        trades = data.get('trades', [])
        metadata = data.get('metadata', {})
        performance = data.get('performance', {})
        
        if not daily_values:
            return {}
        
        final_day = daily_values[-1]
        last_trade = trades[-1] if trades else {}
        
        # Calculate high water mark
        portfolio_values = [d['portfolio_value'] for d in daily_values]
        high_water_mark = max(portfolio_values)
        
        return {
            'date': final_day['date'],
            'portfolio_value': final_day['portfolio_value'],
            'cash': final_day['cash'],
            'position': final_day['position'],
            'position_avg_cost': final_day.get('position_avg_cost', 0),
            'stock_price': final_day['stock_price'],
            'last_sentiment': final_day.get('sentiment', 0.5),
            'last_macd_signal': last_trade.get('macd_signal', '0'),
            'last_trade_date': last_trade.get('date', final_day['date']),
            'cumulative_return': performance.get('total_return_pct', 0),
            'high_water_mark': high_water_mark,
            'initial_cash': metadata.get('initial_cash', 100000),
            'symbol': metadata.get('symbol', ''),
            'version': metadata.get('version', ''),
            'framework_version': metadata.get('framework', 'SimpleContinuousBacktest_v1.0')
        }
    
    def analyze_single_result(self, file_path: Path) -> Optional[Dict]:
        """Analyze a single backtest result file."""
        data = self.load_result_file(file_path)
        if not data:
            return None
        
        metadata = data.get('metadata', {})
        performance = data.get('performance', {})
        trades = data.get('trades', [])
        daily_values = data.get('daily_values', [])
        
        # Core analysis
        sentiment_analysis = self.calculate_sentiment_effectiveness(trades)
        trade_quality = self.calculate_trade_quality_metrics(trades)
        risk_metrics = self.calculate_risk_metrics(daily_values, metadata.get('initial_cash', 100000))
        
        # Market regime analysis
        daily_with_regime = self.detect_market_regimes(daily_values)
        regime_performance = self.calculate_regime_performance(trades, daily_with_regime)
        
        # Checkpoint data
        checkpoint = self.extract_checkpoint_data(data)
        
        return {
            'file_info': {
                'path': str(file_path),
                'symbol': metadata.get('symbol', ''),
                'version': metadata.get('version', ''),
                'year': metadata.get('year', ''),
                'execution_time': metadata.get('execution_time', '')
            },
            'basic_performance': performance,
            'sentiment_effectiveness': sentiment_analysis,
            'trade_quality': trade_quality,
            'risk_metrics': risk_metrics,
            'regime_performance': regime_performance,
            'checkpoint_data': checkpoint,
            'metadata': metadata
        }
    
    def analyze_all_results(self, pattern: str = "*_results.json") -> Dict:
        """Analyze all result files and generate comprehensive report."""
        print(f"🔍 Analyzing backtest results with pattern: {pattern}")
        
        all_results = {}
        comparison_data = []
        
        # Process all result files
        for version_dir in self.results_dir.iterdir():
            if not version_dir.is_dir() or not version_dir.name.startswith('V'):
                continue
            
            version = version_dir.name
            print(f"📊 Processing {version}...")
            
            for result_file in version_dir.glob(pattern):
                print(f"  • Analyzing {result_file.name}")
                
                analysis = self.analyze_single_result(result_file)
                if analysis:
                    symbol = analysis['file_info']['symbol']
                    key = f"{symbol}_{version}"
                    all_results[key] = analysis
                    
                    # Add to comparison data
                    row = {
                        'Symbol': symbol,
                        'Version': version,
                        'Total_Return': analysis['basic_performance'].get('total_return_pct', 0),
                        'Max_Drawdown': analysis['risk_metrics']['max_drawdown'],
                        'Sharpe_Ratio': analysis['risk_metrics']['sharpe_ratio'],
                        'Calmar_Ratio': analysis['risk_metrics']['calmar_ratio'],
                        'Profit_Factor': analysis['trade_quality']['profit_factor'],
                        'Win_Rate': analysis['basic_performance'].get('win_rate', 0),
                        'Num_Trades': analysis['basic_performance'].get('num_trades', 0),
                        'Avg_Holding_Days': analysis['trade_quality']['holding_periods']['avg']
                    }
                    comparison_data.append(row)
        
        # Create comparison DataFrame
        comparison_df = pd.DataFrame(comparison_data)
        
        # Generate strategy rankings
        strategy_rankings = self.generate_strategy_rankings(comparison_df)
        
        # Best strategy per ticker
        best_strategies = self.identify_best_strategies(comparison_df)
        
        comprehensive_analysis = {
            'analysis_timestamp': datetime.now().isoformat(),
            'total_files_analyzed': len(all_results),
            'individual_analyses': all_results,
            'comparative_analysis': comparison_data,
            'strategy_rankings': strategy_rankings,
            'best_strategy_per_ticker': best_strategies,
            'summary_statistics': self.calculate_summary_statistics(comparison_df)
        }
        
        return comprehensive_analysis
    
    def generate_strategy_rankings(self, df: pd.DataFrame) -> Dict:
        """Generate rankings for each strategy across different metrics."""
        if df.empty:
            return {}
        
        rankings = {}
        metrics = ['Total_Return', 'Sharpe_Ratio', 'Calmar_Ratio', 'Profit_Factor']
        
        for metric in metrics:
            if metric in df.columns:
                version_means = df.groupby('Version')[metric].mean().sort_values(ascending=False)
                rankings[metric] = version_means.to_dict()
        
        return rankings
    
    def identify_best_strategies(self, df: pd.DataFrame) -> Dict:
        """Identify the best strategy for each ticker based on Sharpe ratio."""
        if df.empty:
            return {}
        
        best_strategies = {}
        for symbol in df['Symbol'].unique():
            symbol_data = df[df['Symbol'] == symbol]
            if not symbol_data.empty:
                best_idx = symbol_data['Sharpe_Ratio'].idxmax()
                best_version = symbol_data.loc[best_idx, 'Version']
                best_sharpe = symbol_data.loc[best_idx, 'Sharpe_Ratio']
                best_strategies[symbol] = {
                    'best_version': best_version,
                    'sharpe_ratio': best_sharpe
                }
        
        return best_strategies
    
    def calculate_summary_statistics(self, df: pd.DataFrame) -> Dict:
        """Calculate overall summary statistics."""
        if df.empty:
            return {}
        
        return {
            'mean_returns': df.groupby('Version')['Total_Return'].mean().to_dict(),
            'mean_sharpe_ratios': df.groupby('Version')['Sharpe_Ratio'].mean().to_dict(),
            'mean_max_drawdowns': df.groupby('Version')['Max_Drawdown'].mean().to_dict(),
            'version_counts': df['Version'].value_counts().to_dict(),
            'symbol_counts': df['Symbol'].value_counts().to_dict()
        }
    
    def save_analysis_report(self, analysis: Dict, output_path: str = "reports/backtest_analysis_2024.json"):
        """Save comprehensive analysis report."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert numpy types to native Python types for JSON serialization
        def convert_numpy_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            return obj
        
        analysis_clean = convert_numpy_types(analysis)
        
        with open(output_file, 'w') as f:
            json.dump(analysis_clean, f, indent=2)
        
        print(f"💾 Analysis report saved to: {output_file}")
        return output_file
    
    def save_comparison_csv(self, analysis: Dict, output_path: str = "reports/strategy_comparison_2024.csv"):
        """Save strategy comparison as CSV."""
        comparison_data = analysis.get('comparative_analysis', [])
        if not comparison_data:
            print("❌ No comparison data available")
            return
        
        df = pd.DataFrame(comparison_data)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output_file, index=False)
        print(f"💾 Strategy comparison CSV saved to: {output_file}")
        return output_file
    
    def save_checkpoints(self, analysis: Dict, output_dir: str = "reports/continuation_states_2025"):
        """Save continuation state files for 2025 backtesting."""
        checkpoint_dir = Path(output_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        individual_analyses = analysis.get('individual_analyses', {})
        saved_checkpoints = []
        
        for key, result in individual_analyses.items():
            checkpoint_data = result.get('checkpoint_data', {})
            if checkpoint_data:
                symbol = checkpoint_data.get('symbol', '')
                version = checkpoint_data.get('version', '')
                
                if symbol and version:
                    checkpoint_file = checkpoint_dir / f"{symbol}_{version}_2024_01_01_to_2024_12_31_continuation_state.json"
                    with open(checkpoint_file, 'w') as f:
                        json.dump(checkpoint_data, f, indent=2)
                    saved_checkpoints.append(str(checkpoint_file))
        
        print(f"💾 Saved {len(saved_checkpoints)} checkpoint files to: {checkpoint_dir}")
        return saved_checkpoints


def main():
    """Main function to run comprehensive analysis."""
    print("🚀 Starting comprehensive backtest analysis...")
    
    analyzer = MetricsAnalyzer()
    
    # Analyze all results
    analysis = analyzer.analyze_all_results()
    
    # Save comprehensive report
    analyzer.save_analysis_report(analysis)
    
    # Save comparison CSV
    analyzer.save_comparison_csv(analysis)
    
    # Save checkpoints
    analyzer.save_checkpoints(analysis)
    
    # Print summary
    print("\n" + "="*60)
    print("📊 ANALYSIS COMPLETE")
    print("="*60)
    
    total_files = analysis.get('total_files_analyzed', 0)
    print(f"✅ Analyzed {total_files} backtest result files")
    
    best_strategies = analysis.get('best_strategy_per_ticker', {})
    if best_strategies:
        print(f"\n🏆 Best Strategy per Ticker (by Sharpe Ratio):")
        for symbol, info in best_strategies.items():
            version = info['best_version']
            sharpe = info['sharpe_ratio']
            print(f"  • {symbol}: {version} (Sharpe: {sharpe:.3f})")
    
    strategy_rankings = analysis.get('strategy_rankings', {})
    if 'Total_Return' in strategy_rankings:
        print(f"\n📈 Strategy Rankings by Total Return:")
        for i, (version, return_pct) in enumerate(strategy_rankings['Total_Return'].items(), 1):
            print(f"  {i}. {version}: {return_pct:.2f}%")
    
    print(f"\n📄 Reports saved:")
    print(f"  • Comprehensive JSON: reports/backtest_analysis_2024.json")
    print(f"  • Comparison CSV: reports/strategy_comparison_2024.csv")
    print(f"  • Checkpoints: checkpoints/2025_continuation/")


if __name__ == "__main__":
    main()