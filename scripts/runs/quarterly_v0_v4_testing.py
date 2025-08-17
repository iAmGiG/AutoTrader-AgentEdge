#!/usr/bin/env python3
"""
Quarterly Testing Framework for V0-V4 Sentiment Comparison (Issue #187)

Tests all 5 sentiment agent versions (V0-V4) on consistent quarterly periods 
using AAPL to demonstrate gradual LLM introduction value.

Quarterly Test Periods:
- 2024 Q1: January 1 - March 31, 2024  
- 2024 Q2: April 1 - June 30, 2024
- 2024 Q3: July 1 - September 30, 2024
- 2024 Q4: October 1 - December 31, 2024
- 2025 Q1: January 1 - March 31, 2025

Architecture: Consistent MACD strategy + Variable sentiment approach (V0→V4)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import logging
from pathlib import Path
import asyncio
import time
from scipy import stats

# Import all sentiment agents
from src.agents.sentiment_v0 import V0SentimentAgent
from src.agents.sentiment_v1 import SentimentV1Agent  
from src.agents.sentiment_v2 import SentimentV2Agent
from src.agents.sentiment_v3 import SentimentV3Agent
from src.agents.sentiment_v4 import SentimentV4Agent

# Import market data and technical analysis tools
from src.tools.cache.unified_cache import UnifiedCacheManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MACDStrategy:
    """
    Consistent MACD crossover strategy used across all V0-V4 testing.
    
    Entry: MACD line crosses above signal line + sentiment >= 0
    Exit: MACD line crosses below signal line or sentiment < -0.5
    """
    
    def __init__(self):
        self.fast_period = 12
        self.slow_period = 26  
        self.signal_period = 9
        
    def calculate_macd(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """Calculate MACD indicator from price series."""
        
        # Calculate EMAs
        ema_fast = prices.ewm(span=self.fast_period).mean()
        ema_slow = prices.ewm(span=self.slow_period).mean()
        
        # MACD line and signal line
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def generate_signals(self, macd_data: Dict[str, pd.Series]) -> pd.Series:
        """Generate MACD crossover signals."""
        
        macd = macd_data['macd']
        signal = macd_data['signal']
        
        # Entry signals: MACD crosses above signal
        bullish_cross = (macd > signal) & (macd.shift(1) <= signal.shift(1))
        
        # Exit signals: MACD crosses below signal  
        bearish_cross = (macd < signal) & (macd.shift(1) >= signal.shift(1))
        
        signals = pd.Series(0, index=macd.index)
        signals[bullish_cross] = 1  # Buy signal
        signals[bearish_cross] = -1  # Sell signal
        
        return signals


class QuarterlyTestRunner:
    """
    Quarterly Testing Framework for V0-V4 Sentiment Analysis Comparison.
    
    Implements consistent MACD strategy across all versions with variable
    sentiment approaches to demonstrate gradual LLM introduction value.
    """
    
    def __init__(self, symbol: str = "AAPL"):
        self.symbol = symbol
        self.macd_strategy = MACDStrategy()
        self.cache_manager = UnifiedCacheManager()
        
        # Quarterly test periods
        self.quarters = {
            '2024-Q1': ('2024-01-01', '2024-03-31'),
            '2024-Q2': ('2024-04-01', '2024-06-30'), 
            '2024-Q3': ('2024-07-01', '2024-09-30'),
            '2024-Q4': ('2024-10-01', '2024-12-31'),
            '2025-Q1': ('2025-01-01', '2025-03-31'),
        }
        
        # Initialize sentiment agents
        self.sentiment_agents = {
            'V0': V0SentimentAgent(),  # Fixed baseline (1.0)
            'V1': SentimentV1Agent(),  # VADER NLP + News
            'V2': SentimentV2Agent(),  # VXX/VIX volatility
            'V3': SentimentV3Agent(),  # V1+V2 heuristic combination
            'V4': SentimentV4Agent(enable_obfuscation=True)  # LLM analysis with obfuscation
        }
        
        # Results storage
        self.quarterly_results = {}
        self.performance_metrics = {}
        
        logger.info(f"🎯 Initialized Quarterly Testing Framework for {symbol}")
        logger.info(f"📅 Testing {len(self.quarters)} quarters with {len(self.sentiment_agents)} sentiment versions")

    async def validate_data_availability(self) -> Dict[str, bool]:
        """Validate that required data is available for all quarters."""
        
        logger.info("🔍 VALIDATING DATA AVAILABILITY")
        logger.info("=" * 60)
        
        validation_results = {}
        
        for quarter_name, (start_date, end_date) in self.quarters.items():
            logger.info(f"📊 Checking {quarter_name}: {start_date} to {end_date}")
            
            # Check market data availability
            market_data = self.cache_manager.get_market_data(
                self.symbol, start_date, end_date, "polygon"
            )
            
            if market_data is None or market_data.empty:
                # Try Alpha Vantage fallback
                market_data = self.cache_manager.get_market_data(
                    self.symbol, start_date, end_date, "alpha_vantage"
                )
            
            has_market_data = market_data is not None and not market_data.empty
            data_points = len(market_data) if has_market_data else 0
            
            validation_results[quarter_name] = {
                'has_market_data': has_market_data,
                'data_points': data_points,
                'start_date': start_date,
                'end_date': end_date
            }
            
            if has_market_data:
                logger.info(f"   ✅ Market data: {data_points} trading days")
            else:
                logger.warning(f"   ❌ No market data found for {quarter_name}")
        
        # Summary
        available_quarters = sum(1 for q in validation_results.values() if q['has_market_data'])
        logger.info(f"\n📈 Data Validation Summary:")
        logger.info(f"Available quarters: {available_quarters}/{len(self.quarters)}")
        
        return validation_results

    async def run_single_quarter_test(self, quarter_name: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Run V0-V4 comparison test on a single quarter."""
        
        logger.info(f"\n🚀 TESTING {quarter_name}: {start_date} to {end_date}")
        logger.info("=" * 70)
        
        # Load market data  
        market_data = await self._load_market_data(start_date, end_date)
        if market_data is None or market_data.empty:
            logger.error(f"❌ No market data available for {quarter_name}")
            return {'error': f'No market data for {quarter_name}'}
        
        # Calculate MACD signals (consistent across all versions)
        macd_data = self.macd_strategy.calculate_macd(market_data['close'])
        macd_signals = self.macd_strategy.generate_signals(macd_data)
        
        logger.info(f"📊 Market data: {len(market_data)} trading days")
        logger.info(f"📈 MACD signals: {(macd_signals == 1).sum()} buy, {(macd_signals == -1).sum()} sell")
        
        # Test each sentiment version
        quarter_results = {}
        
        for version, agent in self.sentiment_agents.items():
            logger.info(f"\n🧪 Testing {version}: {agent.__class__.__name__}")
            
            try:
                # Run backtesting for this version
                backtest_results = await self._run_version_backtest(
                    version, agent, market_data, macd_signals, start_date, end_date
                )
                
                quarter_results[version] = backtest_results
                
                if 'error' not in backtest_results:
                    total_return = backtest_results['metrics']['total_return']
                    num_trades = backtest_results['metrics']['num_trades']
                    logger.info(f"   ✅ {version}: {total_return:+.2f}% return, {num_trades} trades")
                else:
                    logger.warning(f"   ⚠️ {version}: {backtest_results['error']}")
                    
            except Exception as e:
                logger.error(f"   ❌ {version}: Error - {str(e)}")
                quarter_results[version] = {'error': str(e)}
        
        return {
            'quarter': quarter_name,
            'period': f"{start_date} to {end_date}",
            'market_data_points': len(market_data),
            'macd_signals': {
                'buy_signals': int((macd_signals == 1).sum()),
                'sell_signals': int((macd_signals == -1).sum())
            },
            'results': quarter_results,
            'timestamp': datetime.now().isoformat()
        }

    async def _load_market_data(self, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Load market data for the specified period."""
        
        # Try Polygon first, then Alpha Vantage fallback
        market_data = self.cache_manager.get_market_data(
            self.symbol, start_date, end_date, "polygon"
        )
        
        if market_data is None or market_data.empty:
            market_data = self.cache_manager.get_market_data(
                self.symbol, start_date, end_date, "alpha_vantage"  
            )
        
        return market_data

    async def _run_version_backtest(self, version: str, agent, market_data: pd.DataFrame, 
                                   macd_signals: pd.Series, start_date: str, end_date: str) -> Dict[str, Any]:
        """Run backtest for a specific sentiment version."""
        
        try:
            # Initialize trading variables
            trades = []
            daily_portfolio_values = []
            position = 0  # 0 = no position, 1 = long position
            cash = 10000  # Starting cash
            entry_price = 0
            entry_date = None
            
            # Track sentiment scores for analysis
            sentiment_scores = []
            
            # Daily trading loop
            for date, row in market_data.iterrows():
                current_price = row['close']
                date_str = date.strftime('%Y-%m-%d')
                
                # Get MACD signal for this date
                macd_signal = macd_signals.get(date, 0)
                
                # Get sentiment score from agent
                try:
                    sentiment_response = agent.generate_reply(f"{self.symbol} on {date_str}")
                    
                    # Handle async responses (V1, V3, V4 agents)
                    import asyncio
                    if asyncio.iscoroutine(sentiment_response):
                        sentiment_response = await sentiment_response
                    
                    # Parse JSON response
                    if isinstance(sentiment_response, str):
                        sentiment_data = json.loads(sentiment_response)
                    else:
                        sentiment_data = sentiment_response
                        
                    sentiment_score = sentiment_data.get('sentiment', 0.0) or sentiment_data.get('score', 0.0)
                    
                    # Handle potential string/format issues
                    if isinstance(sentiment_score, str):
                        sentiment_score = float(sentiment_score)
                        
                    sentiment_scores.append(sentiment_score)
                    
                except Exception as e:
                    logger.warning(f"Error getting sentiment for {version} on {date_str}: {e}")
                    sentiment_score = 0.0  # Neutral fallback
                    sentiment_scores.append(sentiment_score)
                
                # Trading logic: MACD + Sentiment
                if position == 0 and macd_signal == 1 and sentiment_score >= 0:
                    # Enter long position
                    shares = int(cash / current_price)  # Buy max shares with available cash
                    if shares > 0:
                        position = shares
                        cash -= shares * current_price
                        entry_price = current_price
                        entry_date = date
                        
                        trades.append({
                            'date': date_str,
                            'action': 'BUY',
                            'price': current_price,
                            'shares': shares,
                            'sentiment': sentiment_score,
                            'macd_signal': macd_signal
                        })
                
                elif position > 0 and (macd_signal == -1 or sentiment_score < -0.5):
                    # Exit position
                    cash += position * current_price
                    exit_return = (current_price - entry_price) / entry_price * 100
                    
                    trades.append({
                        'date': date_str,
                        'action': 'SELL', 
                        'price': current_price,
                        'shares': position,
                        'sentiment': sentiment_score,
                        'macd_signal': macd_signal,
                        'return_pct': exit_return,
                        'entry_date': entry_date.strftime('%Y-%m-%d') if entry_date else None
                    })
                    
                    position = 0
                    entry_price = 0
                    entry_date = None
                
                # Calculate daily portfolio value
                portfolio_value = cash + (position * current_price)
                daily_portfolio_values.append({
                    'date': date_str,
                    'portfolio_value': portfolio_value,
                    'cash': cash,
                    'position': position,
                    'stock_price': current_price,
                    'sentiment': sentiment_score
                })
            
            # Calculate performance metrics
            metrics = self._calculate_performance_metrics(
                daily_portfolio_values, trades, market_data, version
            )
            
            return {
                'version': version,
                'period': f"{start_date} to {end_date}",
                'trades': trades,
                'daily_values': daily_portfolio_values,
                'sentiment_scores': sentiment_scores,
                'metrics': metrics
            }
            
        except Exception as e:
            return {'error': f"Backtest error for {version}: {str(e)}"}

    def _calculate_performance_metrics(self, daily_values: List[Dict], trades: List[Dict], 
                                     market_data: pd.DataFrame, version: str) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""
        
        if not daily_values:
            return {'error': 'No daily values to analyze'}
        
        # Convert to DataFrame for analysis
        portfolio_df = pd.DataFrame(daily_values)
        portfolio_df['date'] = pd.to_datetime(portfolio_df['date'])
        portfolio_df.set_index('date', inplace=True)
        
        # Basic metrics
        initial_value = daily_values[0]['portfolio_value']
        final_value = daily_values[-1]['portfolio_value']
        total_return = ((final_value - initial_value) / initial_value) * 100
        
        # Buy and hold comparison
        initial_price = market_data.iloc[0]['close']
        final_price = market_data.iloc[-1]['close']
        buy_hold_return = ((final_price - initial_price) / initial_price) * 100
        
        # Risk metrics
        portfolio_returns = portfolio_df['portfolio_value'].pct_change().dropna()
        
        if len(portfolio_returns) > 0:
            volatility = portfolio_returns.std() * np.sqrt(252) * 100  # Annualized
            sharpe_ratio = (portfolio_returns.mean() * 252) / (portfolio_returns.std() * np.sqrt(252)) if portfolio_returns.std() > 0 else 0
            
            # Max drawdown
            cumulative = (1 + portfolio_returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min() * 100
        else:
            volatility = 0
            sharpe_ratio = 0
            max_drawdown = 0
        
        # Trade analysis
        profitable_trades = [t for t in trades if t.get('return_pct', 0) > 0]
        losing_trades = [t for t in trades if t.get('return_pct', 0) < 0]
        
        trade_returns = [t.get('return_pct', 0) for t in trades if 'return_pct' in t]
        avg_trade_return = np.mean(trade_returns) if trade_returns else 0
        
        # Sentiment analysis
        sentiments = [dv['sentiment'] for dv in daily_values]
        sentiment_stats = {
            'mean': np.mean(sentiments),
            'std': np.std(sentiments),
            'min': np.min(sentiments),
            'max': np.max(sentiments)
        }
        
        return {
            'total_return': round(total_return, 2),
            'buy_hold_return': round(buy_hold_return, 2),
            'outperformance': round(total_return - buy_hold_return, 2),
            'volatility': round(volatility, 2),
            'sharpe_ratio': round(sharpe_ratio, 3),
            'max_drawdown': round(max_drawdown, 2),
            'num_trades': len(trades),
            'profitable_trades': len(profitable_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(len(profitable_trades) / len(trades) * 100, 1) if trades else 0,
            'avg_trade_return': round(avg_trade_return, 2),
            'final_portfolio_value': round(final_value, 2),
            'sentiment_stats': sentiment_stats
        }

    async def run_full_quarterly_comparison(self) -> Dict[str, Any]:
        """Run complete V0-V4 quarterly comparison across all test periods."""
        
        logger.info("🎯 STARTING FULL QUARTERLY V0-V4 COMPARISON")
        logger.info("=" * 80)
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Quarters: {len(self.quarters)}")
        logger.info(f"Versions: {list(self.sentiment_agents.keys())}")
        logger.info("")
        
        # Validate data availability first
        validation_results = await self.validate_data_availability()
        available_quarters = [q for q, v in validation_results.items() if v['has_market_data']]
        
        if not available_quarters:
            logger.error("❌ No data available for any quarters")
            return {'error': 'No data available for testing'}
        
        logger.info(f"✅ Proceeding with {len(available_quarters)} available quarters")
        
        # Run tests for each available quarter
        all_results = {}
        
        for quarter_name in available_quarters:
            start_date, end_date = self.quarters[quarter_name]
            
            try:
                quarter_results = await self.run_single_quarter_test(
                    quarter_name, start_date, end_date
                )
                all_results[quarter_name] = quarter_results
                
            except Exception as e:
                logger.error(f"❌ Error testing {quarter_name}: {e}")
                all_results[quarter_name] = {'error': str(e)}
        
        # Generate comparative analysis
        comparative_analysis = self._generate_comparative_analysis(all_results)
        
        # Save results
        results_summary = {
            'metadata': {
                'symbol': self.symbol,
                'test_timestamp': datetime.now().isoformat(),
                'quarters_tested': list(available_quarters),
                'sentiment_versions': list(self.sentiment_agents.keys()),
                'framework_version': '1.0'
            },
            'quarterly_results': all_results,
            'comparative_analysis': comparative_analysis,
            'statistical_analysis': self._perform_statistical_analysis(all_results)
        }
        
        # Save to file
        self._save_results(results_summary)
        
        return results_summary

    def _generate_comparative_analysis(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comparative analysis across quarters and versions."""
        
        logger.info("📊 GENERATING COMPARATIVE ANALYSIS")
        
        # Aggregate performance by version
        version_performance = {}
        
        for version in self.sentiment_agents.keys():
            version_metrics = []
            
            for quarter_name, quarter_data in all_results.items():
                if 'error' not in quarter_data and 'results' in quarter_data:
                    version_result = quarter_data['results'].get(version, {})
                    if 'error' not in version_result and 'metrics' in version_result:
                        version_metrics.append(version_result['metrics'])
            
            if version_metrics:
                # Calculate aggregate metrics
                returns = [m['total_return'] for m in version_metrics]
                sharpes = [m['sharpe_ratio'] for m in version_metrics]
                drawdowns = [m['max_drawdown'] for m in version_metrics]
                win_rates = [m['win_rate'] for m in version_metrics]
                
                version_performance[version] = {
                    'quarters_tested': len(version_metrics),
                    'avg_return': round(np.mean(returns), 2),
                    'total_return': round(np.sum(returns), 2),
                    'avg_sharpe': round(np.mean(sharpes), 3),
                    'avg_max_drawdown': round(np.mean(drawdowns), 2),
                    'avg_win_rate': round(np.mean(win_rates), 1),
                    'consistency': round(np.std(returns), 2)  # Lower is more consistent
                }
        
        # Rank versions by performance
        ranked_versions = sorted(
            version_performance.items(),
            key=lambda x: x[1]['avg_return'],
            reverse=True
        )
        
        return {
            'version_performance': version_performance,
            'performance_ranking': [{'version': v, **metrics} for v, metrics in ranked_versions],
            'key_insights': self._extract_key_insights(version_performance)
        }

    def _extract_key_insights(self, version_performance: Dict[str, Any]) -> List[str]:
        """Extract key insights from version performance comparison."""
        
        insights = []
        
        # Best performing version
        best_version = max(version_performance.items(), key=lambda x: x[1]['avg_return'])
        insights.append(f"Best average return: {best_version[0]} with {best_version[1]['avg_return']}%")
        
        # Most consistent version  
        most_consistent = min(version_performance.items(), key=lambda x: x[1]['consistency'])
        insights.append(f"Most consistent: {most_consistent[0]} (std dev: {most_consistent[1]['consistency']}%)")
        
        # Best risk-adjusted
        best_sharpe = max(version_performance.items(), key=lambda x: x[1]['avg_sharpe'])
        insights.append(f"Best risk-adjusted: {best_sharpe[0]} (Sharpe: {best_sharpe[1]['avg_sharpe']})")
        
        # V4 vs V0 comparison (LLM vs baseline)
        if 'V4' in version_performance and 'V0' in version_performance:
            v4_return = version_performance['V4']['avg_return']
            v0_return = version_performance['V0']['avg_return']
            improvement = v4_return - v0_return
            insights.append(f"V4 LLM vs V0 baseline: {improvement:+.2f}% improvement")
        
        return insights

    def _perform_statistical_analysis(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Perform statistical significance testing between versions."""
        
        logger.info("📈 PERFORMING STATISTICAL ANALYSIS")
        
        # Collect returns by version
        version_returns = {}
        
        for version in self.sentiment_agents.keys():
            returns = []
            
            for quarter_data in all_results.values():
                if 'error' not in quarter_data and 'results' in quarter_data:
                    version_result = quarter_data['results'].get(version, {})
                    if 'error' not in version_result and 'metrics' in version_result:
                        returns.append(version_result['metrics']['total_return'])
            
            version_returns[version] = returns
        
        # Pairwise t-tests
        statistical_tests = {}
        
        version_list = list(version_returns.keys())
        for i, v1 in enumerate(version_list):
            for v2 in version_list[i+1:]:
                if len(version_returns[v1]) > 1 and len(version_returns[v2]) > 1:
                    try:
                        t_stat, p_value = stats.ttest_rel(version_returns[v1], version_returns[v2])
                        statistical_tests[f"{v1}_vs_{v2}"] = {
                            't_statistic': round(t_stat, 3),
                            'p_value': round(p_value, 4),
                            'significant': p_value < 0.05
                        }
                    except Exception as e:
                        statistical_tests[f"{v1}_vs_{v2}"] = {'error': str(e)}
        
        return {
            'version_returns': version_returns,
            'pairwise_tests': statistical_tests,
            'sample_sizes': {v: len(returns) for v, returns in version_returns.items()}
        }

    def _json_serialize_helper(self, obj):
        """JSON serialization helper for numpy types."""
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)
        
    def _save_results(self, results_summary: Dict[str, Any]):
        """Save results to organized file structure."""
        
        # Create results directory structure as specified in Issue #187
        results_dir = Path("reports/quarterly_comparison")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save complete results
        results_file = results_dir / f"quarterly_results_{self.symbol}_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(results_summary, f, indent=2, default=self._json_serialize_helper)
        
        logger.info(f"💾 Results saved to: {results_file}")
        
        # Save individual version results (as specified in issue)
        for version in self.sentiment_agents.keys():
            version_data = []
            
            for quarter_data in results_summary['quarterly_results'].values():
                if 'results' in quarter_data and version in quarter_data['results']:
                    version_result = quarter_data['results'][version]
                    if 'error' not in version_result:
                        version_data.append(version_result)
            
            version_file = results_dir / f"{version.lower()}_results_{timestamp}.json"
            with open(version_file, 'w') as f:
                json.dump(version_data, f, indent=2, default=self._json_serialize_helper)
        
        # Save summary report
        self._generate_markdown_report(results_summary, results_dir / f"quarterly_results_summary_{timestamp}.md")
        
        logger.info(f"📊 All results saved to: {results_dir}")

    def _generate_markdown_report(self, results_summary: Dict[str, Any], output_path: Path):
        """Generate markdown summary report."""
        
        comparative = results_summary['comparative_analysis']
        
        report_lines = [
            f"# V0-V4 Quarterly Comparison Results - {self.symbol}",
            f"",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Symbol**: {self.symbol}",
            f"**Quarters Tested**: {len(results_summary['metadata']['quarters_tested'])}",
            f"**Framework**: Issue #187 Implementation",
            f"",
            f"## Executive Summary",
            f""
        ]
        
        # Add key insights
        for insight in comparative['key_insights']:
            report_lines.append(f"- {insight}")
        
        report_lines.extend([
            f"",
            f"## Performance Ranking",
            f""
        ])
        
        # Performance table
        for i, version_data in enumerate(comparative['performance_ranking'], 1):
            version = version_data['version']
            avg_return = version_data['avg_return']
            sharpe = version_data['avg_sharpe']
            drawdown = version_data['avg_max_drawdown']
            
            report_lines.append(f"{i}. **{version}**: {avg_return:+.2f}% avg return, {sharpe:.3f} Sharpe, {drawdown:.2f}% max drawdown")
        
        report_lines.extend([
            f"",
            f"## Statistical Analysis",
            f""
        ])
        
        # Statistical tests
        stats_data = results_summary['statistical_analysis']
        for test_name, test_result in stats_data['pairwise_tests'].items():
            if 'error' not in test_result:
                significance = "✅ Significant" if test_result['significant'] else "❌ Not significant"
                report_lines.append(f"- **{test_name}**: p-value = {test_result['p_value']} ({significance})")
        
        # Save report
        with open(output_path, 'w') as f:
            f.write('\n'.join(report_lines))
        
        logger.info(f"📄 Summary report saved to: {output_path}")


async def main():
    """Main execution function."""
    
    print("🎯 QUARTERLY V0-V4 TESTING FRAMEWORK")
    print("=" * 80)
    print("Issue #187: Quarterly Testing Framework for V0-V4 Sentiment Comparison")
    print()
    
    # Initialize test runner
    runner = QuarterlyTestRunner(symbol="AAPL")
    
    try:
        # Run full quarterly comparison
        results = await runner.run_full_quarterly_comparison()
        
        if 'error' in results:
            print(f"❌ Testing failed: {results['error']}")
            return
        
        # Display summary
        print("\n🎉 QUARTERLY TESTING COMPLETE!")
        print("=" * 80)
        
        comparative = results['comparative_analysis']
        
        print("📊 PERFORMANCE RANKING:")
        for i, version_data in enumerate(comparative['performance_ranking'], 1):
            version = version_data['version']
            avg_return = version_data['avg_return']
            print(f"  {i}. {version}: {avg_return:+.2f}% average return")
        
        print("\n🔍 KEY INSIGHTS:")
        for insight in comparative['key_insights']:
            print(f"  • {insight}")
        
        print(f"\n📁 Results saved to: reports/quarterly_comparison/")
        
    except Exception as e:
        print(f"❌ Error in quarterly testing: {e}")
        logger.error(f"Quarterly testing error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())