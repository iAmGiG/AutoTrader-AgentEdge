#!/usr/bin/env python3
"""
Experiment #294: Optimal Vote Threshold Analysis
Testing 2/4, 3/4, and 4/4 agreement thresholds with MACD+RSI+Bollinger+Stochastic
"""

import json
import os

# Add project root to path
import sys
from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.core.indicators.indicator_library import bollinger_bands, macd, rsi, stochrsi


@dataclass
class IndicatorSignal:
    """Individual indicator signal."""

    name: str
    signal: int  # -1 (sell), 0 (hold), 1 (buy)
    strength: float  # 0-100
    confidence: float  # 0-1


class FourIndicatorStrategy:
    """Strategy using MACD, RSI, Bollinger Bands, and Stochastic RSI with configurable vote threshold."""

    def __init__(self, vote_threshold: int = 2):
        """
        Args:
            vote_threshold: Number of indicators that must agree (2, 3, or 4)
        """
        self.vote_threshold = vote_threshold
        self.name = f"{vote_threshold}_of_4_voting"

    def calculate_macd_signal(self, prices: pd.Series) -> IndicatorSignal:
        """MACD signal generation."""
        macd_data = macd(prices)
        histogram = macd_data["MACD_hist"]

        # Signal based on histogram
        current_hist = histogram.iloc[-1]
        signal = 1 if current_hist > 0 else -1 if current_hist < 0 else 0
        strength = min(abs(current_hist) * 100, 100)  # Scale histogram to 0-100
        confidence = min(abs(current_hist) / 0.5, 1.0)  # Confidence based on magnitude

        return IndicatorSignal("MACD", signal, strength, confidence)

    def calculate_rsi_signal(self, prices: pd.Series) -> IndicatorSignal:
        """RSI signal generation."""
        rsi_values = rsi(prices, period=14)
        current_rsi = rsi_values.iloc[-1]

        # RSI signals: <30 oversold (buy), >70 overbought (sell)
        if current_rsi < 30:
            signal = 1
            strength = (30 - current_rsi) * 3.33  # Scale to 0-100
        elif current_rsi > 70:
            signal = -1
            strength = (current_rsi - 70) * 3.33  # Scale to 0-100
        else:
            signal = 0
            strength = 0

        confidence = abs(50 - current_rsi) / 50  # Distance from neutral (50)

        return IndicatorSignal("RSI", signal, strength, confidence)

    def calculate_bollinger_signal(self, prices: pd.Series) -> IndicatorSignal:
        """Bollinger Bands signal generation."""
        bb_data = bollinger_bands(prices, window=20, num_std=2.0)

        current_price = prices.iloc[-1]
        upper_band = bb_data["BB_upper"].iloc[-1]
        lower_band = bb_data["BB_lower"].iloc[-1]
        middle_band = bb_data["BB_middle"].iloc[-1]

        # Bollinger signals: below lower (buy), above upper (sell)
        if current_price < lower_band:
            signal = 1
            strength = ((lower_band - current_price) / lower_band) * 100
        elif current_price > upper_band:
            signal = -1
            strength = ((current_price - upper_band) / upper_band) * 100
        else:
            signal = 0
            strength = 0

        # Confidence based on distance from middle band
        band_width = upper_band - lower_band
        distance_from_middle = abs(current_price - middle_band)
        confidence = distance_from_middle / (band_width / 2)

        return IndicatorSignal("Bollinger", signal, min(strength, 100), min(confidence, 1.0))

    def calculate_stochastic_signal(self, prices: pd.Series) -> IndicatorSignal:
        """Stochastic RSI signal generation."""
        stoch_data = stochrsi(prices, rsi_period=14, stoch_period=14)

        current_k = stoch_data["StochRSI_K"].iloc[-1] * 100  # Convert to 0-100 scale
        current_d = stoch_data["StochRSI_D"].iloc[-1] * 100

        # Stochastic signals: <20 oversold (buy), >80 overbought (sell)
        if current_k < 20:
            signal = 1
            strength = (20 - current_k) * 5  # Scale to 0-100
        elif current_k > 80:
            signal = -1
            strength = (current_k - 80) * 5  # Scale to 0-100
        else:
            signal = 0
            strength = 0

        confidence = abs(50 - current_k) / 50  # Distance from neutral

        return IndicatorSignal("Stochastic", signal, min(strength, 100), min(confidence, 1.0))

    def generate_signals(self, prices: pd.Series) -> pd.Series:
        """Generate trading signals based on vote threshold."""
        if len(prices) < 50:  # Need enough data for indicators
            return pd.Series(0, index=prices.index)

        signals = pd.Series(0, index=prices.index, dtype=float)

        # Calculate signals for each day (using rolling window)
        for i in range(50, len(prices)):  # Start after indicators have enough data
            price_window = prices.iloc[: i + 1]

            # Get individual indicator signals
            macd_signal = self.calculate_macd_signal(price_window)
            rsi_signal = self.calculate_rsi_signal(price_window)
            bb_signal = self.calculate_bollinger_signal(price_window)
            stoch_signal = self.calculate_stochastic_signal(price_window)

            # Count votes for each direction
            buy_votes = sum(
                1 for sig in [macd_signal, rsi_signal, bb_signal, stoch_signal] if sig.signal == 1
            )
            sell_votes = sum(
                1 for sig in [macd_signal, rsi_signal, bb_signal, stoch_signal] if sig.signal == -1
            )

            # Decision based on vote threshold
            if buy_votes >= self.vote_threshold:
                signals.iloc[i] = 1  # Buy
            elif sell_votes >= self.vote_threshold:
                signals.iloc[i] = -1  # Sell
            else:
                signals.iloc[i] = 0  # Hold

        return signals


def load_cached_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Load cached market data."""
    cache_file = f"{symbol}_{start_date}_{end_date}_polygon_consolidated.json"

    if os.path.exists(cache_file):
        print(f"   Using cached data from {cache_file}")
        with open(cache_file, "r") as f:
            data = json.load(f)

        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        df.rename(
            columns={
                "close": "Close",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "volume": "Volume",
            },
            inplace=True,
        )
        return df[["Open", "High", "Low", "Close", "Volume"]]

    return None


def calculate_metrics(returns: pd.Series) -> Dict:
    """Calculate performance metrics."""
    if len(returns) < 2:
        return {"sharpe": 0, "total_return": 0, "max_dd": 0, "volatility": 0, "win_rate": 0}

    returns = returns.dropna()

    # Annual metrics
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
        "win_rate": win_rate,
    }


def run_backtest(
    strategy: FourIndicatorStrategy, symbol: str, start_date: str, end_date: str
) -> Dict:
    """Run backtest for voting strategy."""

    # Load data
    data = load_cached_data(symbol, start_date, end_date)
    if data is None or data.empty:
        print(f"   No data available for {symbol}")
        return None

    prices = data["Close"]

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
    metrics = calculate_metrics(strategy_returns)
    metrics["num_trades"] = num_trades
    metrics["strategy_name"] = strategy.name

    return metrics


def main():
    """Test different vote thresholds."""

    symbol = "AAPL"
    start_date = "2024-01-01"
    end_date = "2024-12-31"

    print("\n" + "=" * 80)
    print("EXPERIMENT #294: OPTIMAL VOTE THRESHOLD ANALYSIS")
    print(f"Testing MACD + RSI + Bollinger + Stochastic on {symbol}")
    print(f"Period: {start_date} to {end_date}")
    print("=" * 80)

    # Test different vote thresholds
    thresholds = [2, 3, 4]
    results = {}

    for threshold in thresholds:
        print(f"\n{threshold}/4 Agreement Threshold:")
        print("-" * 40)

        strategy = FourIndicatorStrategy(vote_threshold=threshold)
        metrics = run_backtest(strategy, symbol, start_date, end_date)

        if metrics:
            results[threshold] = metrics
            print(f"   Sharpe Ratio: {metrics['sharpe']:.3f}")
            print(f"   Total Return: {metrics['total_return']:.2%}")
            print(f"   Max Drawdown: {metrics['max_dd']:.2%}")
            print(f"   Volatility: {metrics['volatility']:.2%}")
            print(f"   Win Rate: {metrics['win_rate']:.1%}")
            print(f"   Trades: {metrics['num_trades']}")

    # Comparison and analysis
    if results:
        print("\n" + "=" * 80)
        print("THRESHOLD COMPARISON:")
        print("-" * 40)

        best_sharpe = max(results.items(), key=lambda x: x[1]["sharpe"])
        best_return = max(results.items(), key=lambda x: x[1]["total_return"])
        lowest_dd = max(results.items(), key=lambda x: x[1]["max_dd"])  # Least negative

        print(f"Best Sharpe Ratio: {best_sharpe[0]}/4 ({best_sharpe[1]['sharpe']:.3f})")
        print(f"Best Total Return: {best_return[0]}/4 ({best_return[1]['total_return']:.2%})")
        print(f"Lowest Drawdown: {lowest_dd[0]}/4 ({lowest_dd[1]['max_dd']:.2%})")

        print("\nTrade Frequency Analysis:")
        for threshold in thresholds:
            if threshold in results:
                trades_per_month = results[threshold]["num_trades"] / 12
                print(
                    f"   {threshold}/4: {results[threshold]['num_trades']} trades ({trades_per_month:.1f}/month)"
                )

        print("\nComparison to Issue #293 Baseline:")
        print("   Original MACD+RSI: 0.856 Sharpe, 12.6% return")

        for threshold in thresholds:
            if threshold in results:
                sharpe_diff = results[threshold]["sharpe"] - 0.856
                return_diff = results[threshold]["total_return"] - 0.126
                print(
                    f"   {threshold}/4 vs Baseline: {sharpe_diff:+.3f} Sharpe, {return_diff:+.2%} return"
                )

    print("\n" + "=" * 80)
    print("CONCLUSION:")
    if results:
        best_overall = max(results.items(), key=lambda x: x[1]["sharpe"])
        print(f"Optimal threshold: {best_overall[0]}/4 indicators")
        print("This approach balances signal quality with trade frequency")

        if best_overall[1]["sharpe"] > 0.856:
            print("✅ Multi-indicator voting improves upon 2-indicator baseline")
        else:
            print("⚠️  2-indicator baseline may be optimal - additional complexity not beneficial")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
