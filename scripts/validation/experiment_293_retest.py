#!/usr/bin/env python3
"""
Retest Experiment #293: MACD vs MACD+RSI Voting
Confirming that voting strategy provides better risk-adjusted returns.
"""

import numpy as np
import pandas as pd
from datetime import datetime
import yfinance as yf
from typing import Dict, Tuple
import json
import os
from pathlib import Path

class TechnicalIndicators:
    """Calculate technical indicators."""
    
    @staticmethod
    def calculate_macd(prices: pd.Series, fast=12, slow=26, signal=9) -> pd.DataFrame:
        """Calculate MACD indicator."""
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        
        return pd.DataFrame({
            'macd': macd,
            'signal': signal_line,
            'histogram': histogram
        })
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period=14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

class Strategy:
    """Base strategy class."""
    
    def calculate_metrics(self, returns: pd.Series) -> Dict:
        """Calculate performance metrics."""
        if len(returns) < 2:
            return {"sharpe": 0, "total_return": 0, "max_dd": 0, "volatility": 0}
        
        # Clean returns
        returns = returns.dropna()
        
        # Annual metrics (252 trading days)
        annual_return = returns.mean() * 252
        annual_vol = returns.std() * np.sqrt(252)
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0
        
        # Total return
        total_return = (1 + returns).prod() - 1
        
        # Max drawdown
        cumulative = (1 + returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_dd = drawdown.min()
        
        # Win rate
        winning_days = (returns > 0).sum()
        total_days = len(returns[returns != 0])
        win_rate = winning_days / total_days if total_days > 0 else 0
        
        return {
            "sharpe": sharpe,
            "total_return": total_return,
            "max_dd": max_dd,
            "volatility": annual_vol,
            "win_rate": win_rate
        }

class MACDOnlyStrategy(Strategy):
    """Single MACD indicator strategy."""
    
    def generate_signals(self, prices: pd.Series) -> pd.Series:
        """Generate trading signals from MACD."""
        macd_df = TechnicalIndicators.calculate_macd(prices)
        
        # Simple MACD crossover strategy
        signals = pd.Series(index=prices.index, dtype=float)
        signals[macd_df['histogram'] > 0] = 1  # Buy
        signals[macd_df['histogram'] < 0] = -1  # Sell
        signals[signals.isna()] = 0
        
        return signals

class MACDRSIVotingStrategy(Strategy):
    """MACD + RSI voting strategy."""
    
    def generate_signals(self, prices: pd.Series) -> pd.Series:
        """Generate trading signals from MACD and RSI consensus."""
        # Calculate indicators
        macd_df = TechnicalIndicators.calculate_macd(prices)
        rsi = TechnicalIndicators.calculate_rsi(prices)
        
        # MACD signals
        macd_signal = pd.Series(index=prices.index, dtype=float)
        macd_signal[macd_df['histogram'] > 0] = 1
        macd_signal[macd_df['histogram'] < 0] = -1
        macd_signal[macd_signal.isna()] = 0
        
        # RSI signals (30/70 thresholds)
        rsi_signal = pd.Series(index=prices.index, dtype=float)
        rsi_signal[rsi < 30] = 1  # Oversold - Buy
        rsi_signal[rsi > 70] = -1  # Overbought - Sell
        rsi_signal[rsi_signal.isna()] = 0  # Neutral
        
        # Voting: both must agree for trade, otherwise hold
        signals = pd.Series(index=prices.index, dtype=float)
        
        # Buy only when both bullish or MACD bullish + RSI not bearish
        buy_condition = ((macd_signal == 1) & (rsi_signal >= 0))
        
        # Sell only when both bearish or MACD bearish + RSI not bullish  
        sell_condition = ((macd_signal == -1) & (rsi_signal <= 0))
        
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        signals[~(buy_condition | sell_condition)] = 0
        
        return signals

def load_cached_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Load cached market data if available."""
    cache_file = f"{symbol}_{start_date}_{end_date}_polygon_consolidated.json"
    
    if os.path.exists(cache_file):
        print(f"   Using cached data from {cache_file}")
        with open(cache_file, 'r') as f:
            data = json.load(f)
            
        # Convert to DataFrame (new format has 'data' key)
        df = pd.DataFrame(data['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.rename(columns={'close': 'Close', 'open': 'Open', 'high': 'High', 'low': 'Low', 'volume': 'Volume'}, inplace=True)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    return None

def run_backtest(strategy: Strategy, symbol: str, start_date: str, end_date: str) -> Tuple[Dict, pd.Series]:
    """Run backtest for a given strategy."""
    
    # Try cached data first
    data = load_cached_data(symbol, start_date, end_date)
    
    if data is None:
        # Fall back to yfinance
        print(f"   Downloading data from yfinance...")
        data = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if data.empty:
            print(f"   No data available for {symbol}")
            return None, None
    
    prices = data['Close']
    
    # Generate signals
    signals = strategy.generate_signals(prices)
    
    # Calculate returns
    returns = prices.pct_change()
    strategy_returns = returns * signals.shift(1)  # Trade on next day
    strategy_returns = strategy_returns.dropna()
    
    # Count trades
    position_changes = signals.diff().abs()
    num_trades = position_changes[position_changes > 0].count()
    
    # Calculate metrics
    metrics = strategy.calculate_metrics(strategy_returns)
    metrics["num_trades"] = num_trades
    
    return metrics, strategy_returns

def main():
    """Compare MACD-only vs MACD+RSI voting strategies."""
    
    # Test parameters (same as original experiment)
    symbol = "AAPL"
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    
    print("\n" + "="*70)
    print("EXPERIMENT #293 RETEST: MACD vs MACD+RSI Voting Strategy")
    print(f"Symbol: {symbol} | Period: {start_date} to {end_date}")
    print("="*70)
    
    # Run MACD-only strategy
    print("\n1. MACD-Only Strategy:")
    print("-" * 30)
    macd_strategy = MACDOnlyStrategy()
    macd_metrics, macd_returns = run_backtest(macd_strategy, symbol, start_date, end_date)
    
    if macd_metrics:
        print(f"   Sharpe Ratio: {macd_metrics['sharpe']:.3f}")
        print(f"   Total Return: {macd_metrics['total_return']:.2%}")
        print(f"   Max Drawdown: {macd_metrics['max_dd']:.2%}")
        print(f"   Volatility: {macd_metrics['volatility']:.2%}")
        print(f"   Win Rate: {macd_metrics['win_rate']:.1%}")
        print(f"   Trades: {macd_metrics['num_trades']}")
    
    # Run MACD+RSI voting strategy
    print("\n2. MACD+RSI Voting Strategy:")
    print("-" * 30)
    voting_strategy = MACDRSIVotingStrategy()
    voting_metrics, voting_returns = run_backtest(voting_strategy, symbol, start_date, end_date)
    
    if voting_metrics:
        print(f"   Sharpe Ratio: {voting_metrics['sharpe']:.3f}")
        print(f"   Total Return: {voting_metrics['total_return']:.2%}")
        print(f"   Max Drawdown: {voting_metrics['max_dd']:.2%}")
        print(f"   Volatility: {voting_metrics['volatility']:.2%}")
        print(f"   Win Rate: {voting_metrics['win_rate']:.1%}")
        print(f"   Trades: {voting_metrics['num_trades']}")
    
    # Buy and hold benchmark
    print("\n3. Buy & Hold Benchmark:")
    print("-" * 30)
    data = load_cached_data(symbol, start_date, end_date)
    if data is None:
        data = yf.download(symbol, start=start_date, end=end_date, progress=False)
    if not data.empty:
        buy_hold_return = (data['Close'].iloc[-1] / data['Close'].iloc[0] - 1)
        print(f"   Total Return: {buy_hold_return:.2%}")
    
    # Comparison
    if macd_metrics and voting_metrics:
        print("\n" + "="*70)
        print("COMPARISON:")
        print("-" * 30)
        
        sharpe_diff = voting_metrics['sharpe'] - macd_metrics['sharpe']
        print(f"Sharpe Improvement: {sharpe_diff:+.3f}")
        
        if voting_metrics['sharpe'] > macd_metrics['sharpe']:
            print("✅ Voting strategy has BETTER risk-adjusted returns")
        else:
            print("❌ MACD-only has better risk-adjusted returns")
            
        if abs(voting_metrics['max_dd']) < abs(macd_metrics['max_dd']):
            print("✅ Voting strategy has LOWER drawdown")
        else:
            print("❌ MACD-only has lower drawdown")
            
        print(f"\nOriginal Experiment #293 Results:")
        print(f"   Voting Sharpe: 0.856 | MACD Sharpe: 0.841")
        print(f"   Current Voting Sharpe: {voting_metrics['sharpe']:.3f}")
        
        if abs(voting_metrics['sharpe'] - 0.856) < 0.1:
            print("✅ Results CONSISTENT with original experiment")
        else:
            print("⚠️  Results differ from original experiment")
    
    print("\n" + "="*70)
    print("CONCLUSION:")
    if voting_metrics and macd_metrics:
        if voting_metrics['sharpe'] > macd_metrics['sharpe']:
            print("Voting strategy validated - provides better risk-adjusted returns")
            print("Continue with human-in-loop trade management approach")
        else:
            print("Single indicator may be sufficient for this period")
            print("Focus on execution and trade management rather than complex indicators")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()