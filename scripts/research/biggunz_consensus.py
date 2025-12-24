"""
BIGGUNZ Triple-Consensus Research (#461)

Quick validation of BIGGUNZ indicator parameters vs VoterAgent baseline.
Tests: RSI(7) + Stochastic(14/3) + MACD(12/26/9) triple consensus.

Usage:
    python scripts/research/biggunz_consensus.py
"""

import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.date_utils import now_iso

GEX_DB_PATH = Path(".cache/gex_research.db")
DEFAULT_SYMBOLS = ["QQQ", "SPY", "IWM", "TQQQ", "SOXL"]


def convert_to_native(obj: Any) -> Any:
    """Convert numpy types for YAML."""
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer, np.floating)):
        return None if np.isnan(obj) else obj.item()
    if isinstance(obj, dict):
        return {k: convert_to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [convert_to_native(i) for i in obj]
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def fetch_daily_data(symbol: str) -> pd.DataFrame:
    """Fetch daily data from GEX database."""
    conn = sqlite3.connect(GEX_DB_PATH)
    query = """
        SELECT trading_date, underlying_price
        FROM options_daily_summary
        WHERE symbol = ? AND underlying_price IS NOT NULL
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))
    conn.close()

    if df.empty:
        raise ValueError(f"No data for {symbol}")

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df = df.set_index("trading_date")
    df = df.rename(columns={"underlying_price": "close"})
    df["returns"] = df["close"].pct_change()
    return df


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))


def calculate_stochastic(prices: pd.Series, k_period: int = 14, d_period: int = 3) -> Dict:
    """Calculate Stochastic Slow."""
    low_min = prices.rolling(k_period).min()
    high_max = prices.rolling(k_period).max()
    fast_k = 100 * (prices - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(d_period).mean()  # Slow %K
    slow_d = slow_k.rolling(d_period).mean()  # Slow %D
    return {"slow_k": slow_k, "slow_d": slow_d}


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
    """Calculate MACD."""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return {"macd": macd_line, "signal": signal_line, "histogram": macd_line - signal_line}


def generate_biggunz_signals(df: pd.DataFrame) -> pd.Series:
    """
    BIGGUNZ Triple Consensus: RSI(7) + Stoch(14/3) + MACD(12/26/9).
    All three must agree for signal.
    """
    prices = df["close"]

    # BIGGUNZ parameters
    rsi = calculate_rsi(prices, period=7)
    stoch = calculate_stochastic(prices, k_period=14, d_period=3)
    macd = calculate_macd(prices, fast=12, slow=26, signal=9)

    signals = pd.Series(0.0, index=df.index)

    for i in range(30, len(df)):
        rsi_bull = rsi.iloc[i] > 50
        stoch_bull = stoch["slow_k"].iloc[i] > 50
        macd_bull = macd["macd"].iloc[i] > macd["signal"].iloc[i]

        rsi_bear = rsi.iloc[i] < 50
        stoch_bear = stoch["slow_k"].iloc[i] < 50
        macd_bear = macd["macd"].iloc[i] < macd["signal"].iloc[i]

        # Triple consensus
        if rsi_bull and stoch_bull and macd_bull:
            signals.iloc[i] = 1.0
        elif rsi_bear and stoch_bear and macd_bear:
            signals.iloc[i] = -1.0

    return signals


def generate_voter_signals(df: pd.DataFrame) -> pd.Series:
    """VoterAgent baseline: RSI(14) + MACD(13/34/8)."""
    prices = df["close"]

    rsi = calculate_rsi(prices, period=14)
    macd = calculate_macd(prices, fast=13, slow=34, signal=8)

    signals = pd.Series(0.0, index=df.index)

    for i in range(35, len(df)):
        macd_bull = macd["histogram"].iloc[i] > 0
        rsi_bull = 30 < rsi.iloc[i] < 70

        if macd_bull and rsi_bull:
            signals.iloc[i] = 1.0
        elif not macd_bull:
            signals.iloc[i] = -0.5

    return signals


def backtest(df: pd.DataFrame, signals: pd.Series) -> Dict:
    """Simple backtest with proper strategy returns."""
    position = 0
    cash = 10000
    holdings = 0.0
    trades = []
    portfolio_values = []

    prices = df["close"]

    for i in range(len(df)):
        price = prices.iloc[i]
        signal = signals.iloc[i]

        # Track portfolio value
        pv = cash + holdings * price
        portfolio_values.append(pv)

        if signal > 0.5 and position == 0:
            shares = cash * 0.95 / price
            cash -= shares * price
            holdings = shares
            position = 1
            trades.append({"action": "BUY", "price": price})

        elif signal < -0.3 and position == 1:
            cash += holdings * price
            if trades:
                trades[-1]["pnl"] = (price - trades[-1]["price"]) / trades[-1]["price"]
            holdings = 0
            position = 0

    # Close position
    if holdings > 0:
        cash += holdings * prices.iloc[-1]
        portfolio_values[-1] = cash

    # Metrics from strategy returns
    pv_series = pd.Series(portfolio_values)
    strategy_returns = pv_series.pct_change().dropna()

    total_return = (pv_series.iloc[-1] - 10000) / 10000 * 100
    sharpe = (
        np.sqrt(252) * strategy_returns.mean() / strategy_returns.std()
        if strategy_returns.std() > 0
        else 0
    )

    sell_trades = [t for t in trades if "pnl" in t]
    win_rate = (
        sum(1 for t in sell_trades if t["pnl"] > 0) / len(sell_trades) * 100 if sell_trades else 0
    )

    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "trades": len(trades),
        "win_rate": win_rate,
    }


def run_comparison():
    """Run BIGGUNZ vs VoterAgent comparison."""
    print("=" * 60)
    print("BIGGUNZ TRIPLE-CONSENSUS RESEARCH (#461)")
    print("=" * 60)

    results = {
        "run_timestamp": now_iso(),
        "issue": "#461",
        "description": "BIGGUNZ (RSI7+Stoch+MACD 12/26/9) vs VoterAgent (RSI14+MACD 13/34/8)",
        "symbol_results": {},
    }

    biggunz_sharpes = []
    voter_sharpes = []

    for symbol in DEFAULT_SYMBOLS:
        print(f"\n{symbol}:")
        try:
            df = fetch_daily_data(symbol)
            print(f"  Data: {len(df)} days")

            # BIGGUNZ
            bg_signals = generate_biggunz_signals(df)
            bg_result = backtest(df, bg_signals)

            # VoterAgent
            va_signals = generate_voter_signals(df)
            va_result = backtest(df, va_signals)

            print(
                f"  BIGGUNZ: Sharpe={bg_result['sharpe']:.3f}, Return={bg_result['total_return']:.1f}%"
            )
            print(
                f"  VoterAgent: Sharpe={va_result['sharpe']:.3f}, Return={va_result['total_return']:.1f}%"
            )

            diff = bg_result["sharpe"] - va_result["sharpe"]
            print(f"  Difference: {diff:+.3f}")

            results["symbol_results"][symbol] = {
                "biggunz": bg_result,
                "voter_agent": va_result,
                "biggunz_wins": diff > 0,
            }

            biggunz_sharpes.append(bg_result["sharpe"])
            voter_sharpes.append(va_result["sharpe"])

        except Exception as e:
            print(f"  ERROR: {e}")

    # Summary
    if biggunz_sharpes:
        bg_wins = sum(1 for b, v in zip(biggunz_sharpes, voter_sharpes) if b > v)
        results["summary"] = {
            "avg_biggunz_sharpe": np.mean(biggunz_sharpes),
            "avg_voter_sharpe": np.mean(voter_sharpes),
            "biggunz_win_rate": bg_wins / len(biggunz_sharpes) * 100,
        }

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Avg BIGGUNZ Sharpe: {results['summary']['avg_biggunz_sharpe']:.3f}")
        print(f"Avg VoterAgent Sharpe: {results['summary']['avg_voter_sharpe']:.3f}")
        print(f"BIGGUNZ Win Rate: {results['summary']['biggunz_win_rate']:.0f}%")

    # Conclusion
    results["conclusion"] = {
        "macd_12_26_9_better": results["summary"]["avg_biggunz_sharpe"]
        > results["summary"]["avg_voter_sharpe"],
        "stochastic_adds_value": False,  # Will determine based on results
        "recommendation": (
            "Keep VoterAgent 13/34/8"
            if results["summary"]["avg_voter_sharpe"] >= results["summary"]["avg_biggunz_sharpe"]
            else "Consider 12/26/9 params"
        ),
    }

    return convert_to_native(results)


def main():
    results = run_comparison()

    # Save results
    output = Path("docs/08_research/03_strategy_research/biggunz_results.yaml")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(results, f, default_flow_style=False, sort_keys=False)
    print(f"\nResults saved to: {output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
