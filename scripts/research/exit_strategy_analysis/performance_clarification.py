#!/usr/bin/env python3
"""
Performance Clarification Test
Clarify the actual performance metrics - per-trade vs annual returns.
"""

import warnings
from typing import Dict, List

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


class TechnicalIndicators:
    @staticmethod
    def calculate_macd(prices: pd.Series, fast=13, slow=34, signal=8) -> pd.DataFrame:
        """Calculate MACD with validated parameters."""
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line

        return pd.DataFrame(
            {"macd": macd, "signal": signal_line, "histogram": histogram}, index=prices.index
        )

    @staticmethod
    def calculate_rsi(prices: pd.Series, period=14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)  # Epsilon to prevent div-by-zero in strong uptrends
        rsi = 100 - (100 / (1 + rs))
        return rsi


class DetailedBacktest:
    """Track everything explicitly for clarity."""

    def __init__(
        self, take_profit=0.06, stop_loss=0.08, initial_capital=10000, transaction_cost=0.001
    ):
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost

    def run_detailed_backtest(self, prices: pd.Series) -> Dict:
        """Run backtest with detailed tracking."""
        # Calculate indicators
        macd_df = TechnicalIndicators.calculate_macd(prices)
        rsi = TechnicalIndicators.calculate_rsi(prices)

        # Simple voting logic
        macd_bullish = macd_df["histogram"] > 0
        rsi_bullish = (rsi > 30) & (rsi < 70)
        entry_signals = macd_bullish & rsi_bullish

        # Track everything
        trades = []
        portfolio_value = [self.initial_capital]
        current_capital = self.initial_capital
        position = None

        for i in range(len(prices)):
            current_price = prices.iloc[i]

            if position is None and entry_signals.iloc[i] and i < len(prices) - 1:
                # Enter position (100% of capital)
                capital_after_cost = current_capital * (1 - self.transaction_cost)
                position = {
                    "entry_date": prices.index[i],
                    "entry_price": current_price,
                    "entry_idx": i,
                    "shares": capital_after_cost / current_price,
                    "capital_invested": current_capital,
                }

            elif position is not None:
                # Check exits
                gain = (current_price - position["entry_price"]) / position["entry_price"]

                exit_reason = None
                if gain >= self.take_profit:
                    exit_reason = "take_profit"
                elif gain <= -self.stop_loss:
                    exit_reason = "stop_loss"

                if exit_reason or i == len(prices) - 1:
                    # Exit position
                    exit_value = (position["shares"] * current_price) * (1 - self.transaction_cost)
                    trade_return = (exit_value - position["capital_invested"]) / position[
                        "capital_invested"
                    ]
                    current_capital = exit_value

                    trades.append(
                        {
                            "entry_date": position["entry_date"],
                            "exit_date": prices.index[i],
                            "entry_price": position["entry_price"],
                            "exit_price": current_price,
                            "per_trade_return": trade_return * 100,
                            "exit_reason": exit_reason or "end",
                            "days_held": i - position["entry_idx"],
                            "capital_before": position["capital_invested"],
                            "capital_after": exit_value,
                        }
                    )
                    position = None

            # Track portfolio value
            if position is not None:
                current_value = position["shares"] * current_price
            else:
                current_value = current_capital
            portfolio_value.append(current_value)

        return self._analyze_results(trades, portfolio_value, prices)

    def _analyze_results(
        self, trades: List[Dict], portfolio_value: List[float], prices: pd.Series
    ) -> Dict:
        """Analyze and clarify the results."""
        if not trades:
            return {"error": "No trades executed"}

        # Per-trade statistics
        returns = [t["per_trade_return"] for t in trades]
        winning_trades = [r for r in returns if r > 0]
        losing_trades = [r for r in returns if r < 0]

        # Portfolio statistics
        final_value = portfolio_value[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100

        # Time calculations
        total_days = len(prices)
        years = total_days / 252
        annualized_return = (
            ((final_value / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
        )

        # Sharpe ratio (using daily returns)
        daily_returns = pd.Series(portfolio_value[1:]) / pd.Series(portfolio_value[:-1]) - 1
        sharpe_ratio = (
            np.sqrt(252) * daily_returns.mean() / daily_returns.std()
            if len(daily_returns) > 1 and daily_returns.std() > 0
            else 0
        )

        # Expected value per trade
        win_rate = len(winning_trades) / len(trades)
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        expected_value = win_rate * avg_win + (1 - win_rate) * avg_loss

        return {
            "total_trades": len(trades),
            "win_rate": win_rate * 100,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "avg_win_per_trade": avg_win,
            "avg_loss_per_trade": avg_loss,
            "expected_value_per_trade": expected_value,
            "total_portfolio_return": total_return,
            "annualized_return": annualized_return,
            "sharpe_ratio": sharpe_ratio,
            "avg_days_held": np.mean([t["days_held"] for t in trades]),
            "initial_capital": self.initial_capital,
            "final_capital": final_value,
            "trades": trades,
        }


def generate_realistic_data(days=252) -> pd.Series:
    """Generate realistic stock price data."""
    dates = pd.date_range("2024-01-01", periods=days)

    # More realistic market with trends and volatility
    np.random.seed(42)
    returns = []

    # Market regimes
    for i in range(days):
        if i < 60:  # Bull market
            daily_return = np.random.normal(0.001, 0.015)
        elif i < 120:  # Correction
            daily_return = np.random.normal(-0.0005, 0.02)
        elif i < 180:  # Recovery
            daily_return = np.random.normal(0.0008, 0.018)
        else:  # Sideways
            daily_return = np.random.normal(0.0002, 0.012)
        returns.append(daily_return)

    prices = [100]
    for ret in returns:
        prices.append(prices[-1] * (1 + ret))

    return pd.Series(prices[:-1], index=dates, name="Close")


def main():
    print("=" * 80)
    print("PERFORMANCE CLARIFICATION: Understanding the Real Numbers")
    print("=" * 80)
    print("Note: Includes 0.1% transaction cost per trade (entry + exit)")

    # Generate test data
    prices = generate_realistic_data(252)  # 1 year of data

    # Test different configurations
    configs = [
        (0.06, 0.08, "Conservative (6% TP / 8% SL)"),
        (0.08, 0.05, "Balanced (8% TP / 5% SL)"),
        (0.10, 0.03, "Aggressive (10% TP / 3% SL)"),
    ]

    for take_profit, stop_loss, name in configs:
        print(f"\n{'=' * 60}")
        print(f"Configuration: {name}")
        print(f"{'=' * 60}")

        backtest = DetailedBacktest(take_profit=take_profit, stop_loss=stop_loss)
        results = backtest.run_detailed_backtest(prices)

        print("\n📊 PER-TRADE METRICS:")
        print(f"   Total trades: {results['total_trades']}")
        print(f"   Win rate: {results['win_rate']:.1f}%")
        print(f"   Average WIN per trade: {results['avg_win_per_trade']:.2f}%")
        print(f"   Average LOSS per trade: {results['avg_loss_per_trade']:.2f}%")
        print(f"   Expected value per trade: {results['expected_value_per_trade']:.2f}%")
        print(f"   Average holding period: {results['avg_days_held']:.1f} days")

        print("\n💰 PORTFOLIO METRICS:")
        print(f"   Initial capital: ${results['initial_capital']:,.0f}")
        print(f"   Final capital: ${results['final_capital']:,.2f}")
        print(f"   Total portfolio return: {results['total_portfolio_return']:.2f}%")
        print(f"   Annualized return: {results['annualized_return']:.2f}%")
        print(f"   Sharpe ratio: {results['sharpe_ratio']:.3f}")

        print("\n🔍 MATHEMATICAL VERIFICATION:")
        win_rate = results["win_rate"] / 100
        expected = (
            win_rate * results["avg_win_per_trade"] + (1 - win_rate) * results["avg_loss_per_trade"]
        )
        print(
            f"   Win rate × Avg win: {win_rate:.3f} × {results['avg_win_per_trade']:.2f}% = {win_rate * results['avg_win_per_trade']:.2f}%"
        )
        print(
            f"   Loss rate × Avg loss: {1 - win_rate:.3f} × {results['avg_loss_per_trade']:.2f}% = {(1 - win_rate) * results['avg_loss_per_trade']:.2f}%"
        )
        print(f"   Expected value: {expected:.2f}% per trade")

        # Show sample trades
        if results["total_trades"] > 0:
            print("\n📈 SAMPLE TRADES (first 3):")
            for i, trade in enumerate(results["trades"][:3]):
                print(
                    f"   Trade {i + 1}: ${trade['capital_before']:.2f} → ${trade['capital_after']:.2f}"
                )
                print(
                    f"            Return: {trade['per_trade_return']:+.2f}% in {trade['days_held']} days ({trade['exit_reason']})"
                )

    # Buy and hold comparison
    buy_hold_return = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
    print("\n📊 BUY & HOLD BENCHMARK:")
    print(f"   Return: {buy_hold_return:.2f}%")
    print("   No trades, no stops, just hold")

    print("\n" + "=" * 80)
    print("KEY INSIGHTS:")
    print("=" * 80)
    print("1. The 6%/8% are PER-TRADE take profit/stop loss levels")
    print("2. Portfolio returns compound based on win/loss sequence")
    print("3. Position sizing: 100% of available capital per trade")
    print("4. Actual annual returns depend on trade frequency and sequence")
    print("5. Sharpe ratio reflects risk-adjusted portfolio performance")
    print("6. Transaction costs (0.1%) significantly impact high-frequency strategies")
    print("=" * 80)


if __name__ == "__main__":
    main()
