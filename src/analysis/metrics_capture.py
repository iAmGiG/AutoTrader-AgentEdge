#!/usr/bin/env python3
"""
MetricsCapture - Real-time metrics collection during backtesting.

Captures advanced metrics in real-time during backtesting execution including:
- Enhanced trade tracking (entry/exit analysis, holding periods)
- Real-time risk metrics (drawdown tracking, volatility)
- Market regime detection (bull/bear identification)
- Sentiment effectiveness tracking
- MACD trend strength analysis
"""

import numpy as np
from datetime import datetime
from typing import Dict, Optional
from collections import deque
import warnings
warnings.filterwarnings('ignore')


class MetricsCapture:
    """Real-time metrics collection during backtesting execution."""

    def __init__(self, symbol: str, initial_cash: float, lookback_window: int = 200):
        self.symbol = symbol
        self.initial_cash = initial_cash
        self.lookback_window = lookback_window

        # Core tracking
        self.daily_data = []
        self.trade_data = []
        self.sentiment_history = deque(maxlen=lookback_window)
        self.price_history = deque(maxlen=lookback_window)
        self.portfolio_history = deque(maxlen=lookback_window)
        self.volume_history = deque(maxlen=lookback_window)

        # Real-time metrics
        self.current_position = 0
        self.position_entry_price = 0
        self.position_entry_date = None
        self.position_entry_sentiment = 0
        self.high_water_mark = initial_cash
        self.current_drawdown = 0
        self.days_since_high = 0

        # Rolling calculations
        self.rolling_returns_30d = deque(maxlen=30)
        self.rolling_returns_90d = deque(maxlen=90)
        self.rolling_sharpe_30d = deque(maxlen=30)

        # Market regime tracking
        self.ma_50_history = deque(maxlen=50)
        self.ma_200_history = deque(maxlen=200)
        self.current_regime = 'neutral'

        # Trade effectiveness tracking
        self.sentiment_buckets = {
            'very_bearish': {'trades': [], 'total_return': 0},
            'bearish': {'trades': [], 'total_return': 0},
            'neutral': {'trades': [], 'total_return': 0},
            'bullish': {'trades': [], 'total_return': 0}
        }

        # Enhanced tracking for future features
        self.macd_histogram_history = deque(maxlen=lookback_window)
        self.vwap_distance_history = deque(maxlen=lookback_window)
        self.volatility_5d_history = deque(maxlen=lookback_window)
        self.volatility_20d_history = deque(maxlen=lookback_window)

    def update_daily_data(self, date: str, portfolio_value: float, cash: float,
                          position: int, stock_price: float, sentiment: float,
                          volume: Optional[float] = None, macd_histogram: Optional[float] = None):
        """Update daily tracking data and calculate real-time metrics."""

        # Update core tracking
        self.price_history.append(stock_price)
        self.portfolio_history.append(portfolio_value)
        self.sentiment_history.append(sentiment)
        if volume:
            self.volume_history.append(volume)
        if macd_histogram:
            self.macd_histogram_history.append(macd_histogram)

        # Calculate daily return
        daily_return = 0
        if len(self.portfolio_history) >= 2:
            prev_value = self.portfolio_history[-2]
            daily_return = (portfolio_value - prev_value) / prev_value if prev_value > 0 else 0
            self.rolling_returns_30d.append(daily_return)
            self.rolling_returns_90d.append(daily_return)

        # Update high water mark and drawdown
        if portfolio_value > self.high_water_mark:
            self.high_water_mark = portfolio_value
            self.days_since_high = 0
        else:
            self.days_since_high += 1

        self.current_drawdown = (self.high_water_mark - portfolio_value) / self.high_water_mark

        # Calculate rolling metrics
        rolling_30d_return = self.calculate_rolling_return(30)
        rolling_90d_return = self.calculate_rolling_return(90)
        ytd_return = (portfolio_value - self.initial_cash) / self.initial_cash

        # Market regime detection
        current_regime = self.detect_market_regime(stock_price)

        # Position concentration
        position_value = position * stock_price if position > 0 else 0
        position_concentration = position_value / portfolio_value if portfolio_value > 0 else 0

        # Rolling Sharpe ratio (30-day)
        rolling_sharpe = self.calculate_rolling_sharpe(30)

        # VWAP distance (if volume available)
        vwap_distance = self.calculate_vwap_distance(stock_price)

        # Price volatility metrics
        volatility_5d = self.calculate_volatility(5)
        volatility_20d = self.calculate_volatility(20)

        # Store enhanced daily data
        daily_metrics = {
            'date': date,
            'portfolio_value': portfolio_value,
            'cash': cash,
            'position': position,
            'stock_price': stock_price,
            'sentiment': sentiment,
            'volume': volume,

            # Real-time risk metrics
            'current_drawdown': self.current_drawdown * 100,
            'days_since_high': self.days_since_high,
            'high_water_mark': self.high_water_mark,
            'daily_return': daily_return * 100,

            # Rolling returns
            'rolling_30d_return': rolling_30d_return * 100,
            'rolling_90d_return': rolling_90d_return * 100,
            'ytd_return': ytd_return * 100,

            # Market regime
            'market_regime': current_regime,
            'position_concentration': position_concentration * 100,
            'rolling_30d_sharpe': rolling_sharpe,

            # Enhanced metrics
            'macd_histogram': macd_histogram,
            'vwap_distance': vwap_distance,
            'volatility_5d': volatility_5d * 100 if volatility_5d else None,
            'volatility_20d': volatility_20d * 100 if volatility_20d else None
        }

        self.daily_data.append(daily_metrics)
        self.current_position = position

    def record_trade(self, date: str, action: str, price: float, shares: int,
                     sentiment: float, macd_signal: str, portfolio_value: float):
        """Record trade execution with enhanced metrics."""

        trade_record = {
            'date': date,
            'action': action,
            'price': price,
            'shares': shares,
            'sentiment': sentiment,
            'macd_signal': macd_signal,
            'portfolio_value_at_trade': portfolio_value
        }

        if action == 'BUY':
            # Record entry metrics
            self.position_entry_price = price
            self.position_entry_date = date
            self.position_entry_sentiment = sentiment

            # Enhanced entry metrics
            trade_record.update({
                'position_avg_cost': price,
                'vwap_distance_at_entry': self.calculate_vwap_distance(price),
                'volatility_5d_at_entry': self.calculate_volatility(5),
                'volatility_20d_at_entry': self.calculate_volatility(20),
                'macd_histogram_at_entry': self.macd_histogram_history[-1] if self.macd_histogram_history else None,
                'market_regime_at_entry': self.current_regime
            })

        elif action == 'SELL' and self.position_entry_date:
            # Calculate trade performance
            entry_date = datetime.strptime(self.position_entry_date, '%Y-%m-%d')
            exit_date = datetime.strptime(date, '%Y-%m-%d')
            holding_period = (exit_date - entry_date).days

            return_pct = (price - self.position_entry_price) / self.position_entry_price * 100

            trade_record.update({
                'entry_date': self.position_entry_date,
                'entry_price': self.position_entry_price,
                'entry_sentiment': self.position_entry_sentiment,
                'exit_sentiment': sentiment,
                'holding_period_days': holding_period,
                'return_pct': return_pct,
                'avg_cost_return_pct': return_pct  # For compatibility
            })

            # Update sentiment effectiveness tracking
            self.update_sentiment_effectiveness(
                self.position_entry_sentiment, return_pct, trade_record)

            # Reset position tracking
            self.position_entry_date = None
            self.position_entry_price = 0
            self.position_entry_sentiment = 0

        self.trade_data.append(trade_record)

    def update_sentiment_effectiveness(self, entry_sentiment: float, return_pct: float, trade_record: Dict):
        """Update sentiment effectiveness buckets."""
        bucket_name = self.get_sentiment_bucket(entry_sentiment)
        self.sentiment_buckets[bucket_name]['trades'].append(trade_record)
        self.sentiment_buckets[bucket_name]['total_return'] += return_pct

    def get_sentiment_bucket(self, sentiment: float) -> str:
        """Determine sentiment bucket for effectiveness analysis."""
        if sentiment < 0.3:
            return 'very_bearish'
        elif sentiment < 0.5:
            return 'bearish'
        elif sentiment < 0.7:
            return 'neutral'
        else:
            return 'bullish'

    def calculate_rolling_return(self, days: int) -> float:
        """Calculate rolling return for specified number of days."""
        if days == 30 and len(self.rolling_returns_30d) >= days:
            returns = list(self.rolling_returns_30d)[-days:]
            return np.prod([1 + r for r in returns]) - 1
        elif days == 90 and len(self.rolling_returns_90d) >= days:
            returns = list(self.rolling_returns_90d)[-days:]
            return np.prod([1 + r for r in returns]) - 1
        return 0

    def calculate_rolling_sharpe(self, days: int) -> float:
        """Calculate rolling Sharpe ratio."""
        if len(self.rolling_returns_30d) < days:
            return 0

        returns = list(self.rolling_returns_30d)[-days:]
        risk_free_rate = 0.02 / 252  # Daily risk-free rate
        excess_returns = [r - risk_free_rate for r in returns]

        if len(excess_returns) == 0 or np.std(excess_returns) == 0:
            return 0

        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

    def detect_market_regime(self, current_price: float) -> str:
        """Detect current market regime using moving averages."""
        if len(self.price_history) < 200:
            return 'neutral'

        prices = list(self.price_history)
        ma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else current_price
        ma_200 = np.mean(prices[-200:])

        self.ma_50_history.append(ma_50)
        self.ma_200_history.append(ma_200)

        regime = 'bull' if ma_50 > ma_200 else 'bear'
        self.current_regime = regime
        return regime

    def calculate_vwap_distance(self, current_price: float) -> Optional[float]:
        """Calculate distance from Volume-Weighted Average Price."""
        if not self.volume_history or not self.price_history:
            return None

        # Use last 20 periods for VWAP calculation
        window = min(20, len(self.price_history), len(self.volume_history))
        if window < 2:
            return None

        prices = list(self.price_history)[-window:]
        volumes = list(self.volume_history)[-window:]

        if sum(volumes) == 0:
            return None

        vwap = sum(p * v for p, v in zip(prices, volumes)) / sum(volumes)
        return ((current_price - vwap) / vwap) * 100

    def calculate_volatility(self, days: int) -> Optional[float]:
        """Calculate price volatility over specified days."""
        if len(self.price_history) < days + 1:
            return None

        prices = list(self.price_history)[-days - 1:]
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]

        if not returns:
            return None

        return np.std(returns) * np.sqrt(252)  # Annualized volatility

    def get_current_metrics_snapshot(self) -> Dict:
        """Get current real-time metrics snapshot."""
        return {
            'timestamp': datetime.now().isoformat(),
            'symbol': self.symbol,
            'portfolio_value': self.portfolio_history[-1] if self.portfolio_history else self.initial_cash,
            'current_drawdown': self.current_drawdown * 100,
            'days_since_high': self.days_since_high,
            'high_water_mark': self.high_water_mark,
            'current_regime': self.current_regime,
            'position_size': self.current_position,
            'rolling_30d_sharpe': self.calculate_rolling_sharpe(30),
            'sentiment_effectiveness': self.get_sentiment_effectiveness_summary()
        }

    def get_sentiment_effectiveness_summary(self) -> Dict:
        """Get current sentiment effectiveness summary."""
        summary = {}
        for bucket_name, bucket_data in self.sentiment_buckets.items():
            trades = bucket_data['trades']
            if trades:
                returns = [t.get('return_pct', 0) for t in trades if 'return_pct' in t]
                summary[bucket_name] = {
                    'total_trades': len(trades),
                    'win_rate': sum(1 for r in returns if r > 0) / len(returns) * 100 if returns else 0,
                    'avg_return': np.mean(returns) if returns else 0,
                    'total_return': sum(returns) if returns else 0
                }
            else:
                summary[bucket_name] = {
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_return': 0,
                    'total_return': 0
                }
        return summary

    def export_enhanced_results(self) -> Dict:
        """Export all collected metrics in enhanced format."""
        # Calculate final performance metrics
        final_portfolio_value = self.portfolio_history[-1] if self.portfolio_history else self.initial_cash
        total_return = (final_portfolio_value - self.initial_cash) / self.initial_cash * 100

        # Calculate maximum drawdown from history
        portfolio_values = list(self.portfolio_history)
        peak = max(portfolio_values) if portfolio_values else self.initial_cash
        trough = min(portfolio_values) if portfolio_values else self.initial_cash
        max_drawdown = (peak - trough) / peak * 100 if peak > 0 else 0

        # Trade statistics
        completed_trades = [t for t in self.trade_data if t['action']
                            == 'SELL' and 'return_pct' in t]
        win_rate = sum(1 for t in completed_trades if t['return_pct']
                       > 0) / len(completed_trades) * 100 if completed_trades else 0
        avg_holding_period = np.mean(
            [t['holding_period_days'] for t in completed_trades if 'holding_period_days' in t]) if completed_trades else 0

        return {
            'metadata': {
                'symbol': self.symbol,
                'initial_cash': self.initial_cash,
                'capture_framework': 'MetricsCapture_v1.0',
                'enhanced_metrics': True
            },
            'performance': {
                'total_return_pct': total_return,
                'final_portfolio_value': final_portfolio_value,
                'max_drawdown_pct': max_drawdown,
                'current_drawdown_pct': self.current_drawdown * 100,
                'high_water_mark': self.high_water_mark,
                'num_trades': len([t for t in self.trade_data if t['action'] == 'SELL']),
                'win_rate': win_rate,
                'avg_holding_period_days': avg_holding_period,
                'final_sharpe_30d': self.calculate_rolling_sharpe(30)
            },
            'enhanced_daily_data': self.daily_data,
            'enhanced_trade_data': self.trade_data,
            'sentiment_effectiveness': self.sentiment_buckets,
            'market_regime_summary': self.get_regime_summary(),
            'real_time_metrics': self.get_current_metrics_snapshot()
        }

    def get_regime_summary(self) -> Dict:
        """Get summary of performance across market regimes."""
        regime_summary = {'bull': [], 'bear': [], 'neutral': []}

        for daily_data in self.daily_data:
            regime = daily_data.get('market_regime', 'neutral')
            if regime in regime_summary:
                regime_summary[regime].append(daily_data)

        summary = {}
        for regime, data_list in regime_summary.items():
            if data_list:
                portfolio_values = [d['portfolio_value'] for d in data_list]
                returns = []
                for i in range(1, len(portfolio_values)):
                    ret = (portfolio_values[i] - portfolio_values[i - 1]) / portfolio_values[i - 1]
                    returns.append(ret)

                summary[regime] = {
                    'days': len(data_list),
                    'avg_daily_return': np.mean(returns) * 100 if returns else 0,
                    'total_return': ((portfolio_values[-1] - portfolio_values[0]) / portfolio_values[0] * 100) if portfolio_values else 0,
                    'volatility': np.std(returns) * np.sqrt(252) * 100 if returns else 0
                }
            else:
                summary[regime] = {'days': 0, 'avg_daily_return': 0,
                                   'total_return': 0, 'volatility': 0}

        return summary

