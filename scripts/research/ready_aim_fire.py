"""
Ready-Aim-Fire Multi-Stochastic Research (#460)

Quick validation of RAF (triple stochastic + TEMA) vs VoterAgent baseline.
Tests: Stoch(5/8/17) with state machine signals.

Usage:
    python scripts/research/ready_aim_fire.py
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

    # Estimate high/low from close (simplified for quick research)
    df["high"] = df["close"] * 1.01
    df["low"] = df["close"] * 0.99

    return df


def calculate_stochastic(df: pd.DataFrame, period: int, smooth: int = 3) -> pd.Series:
    """Calculate stochastic oscillator."""
    low_min = df["low"].rolling(period).min()
    high_max = df["high"].rolling(period).max()
    raw_k = 100 * (df["close"] - low_min) / (high_max - low_min)
    return raw_k.rolling(smooth).mean()


def calculate_tema(prices: pd.Series, period: int = 28) -> pd.Series:
    """Calculate Triple EMA."""
    ema1 = prices.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    return 3 * ema1 - 3 * ema2 + ema3


def generate_raf_signals(df: pd.DataFrame) -> pd.Series:
    """
    Ready-Aim-Fire Multi-Stochastic Signals.

    State machine:
    - READY: k1 crosses above/below 50
    - AIM: k1 and k2 agree
    - FIRE: All three stochastics agree + Fisher extreme
    """
    # Triple stochastic
    k1 = calculate_stochastic(df, period=5, smooth=3)  # Fast
    k2 = calculate_stochastic(df, period=8, smooth=5)  # Medium
    k3 = calculate_stochastic(df, period=17, smooth=5)  # Slow

    # TEMA trend filter
    tema = calculate_tema(df["close"], period=28)

    signals = pd.Series(0.0, index=df.index)

    for i in range(30, len(df)):
        # Get current values
        k1_val = k1.iloc[i]
        k2_val = k2.iloc[i]
        k3_val = k3.iloc[i]
        price = df["close"].iloc[i]
        tema_val = tema.iloc[i]

        # Skip NaN
        if pd.isna(k1_val) or pd.isna(tema_val):
            continue

        # Trend filter
        uptrend = price > tema_val

        # State detection
        k1_bull = k1_val > 50
        k2_bull = k2_val > 50
        k3_bull = k3_val > 50

        k1_bear = k1_val < 50
        k2_bear = k2_val < 50
        k3_bear = k3_val < 50

        # FIRE signal (strongest): all agree + trend
        if k1_bull and k2_bull and k3_bull and uptrend:
            signals.iloc[i] = 1.0
        elif k1_bear and k2_bear and k3_bear and not uptrend:
            signals.iloc[i] = -1.0
        # AIM signal (medium): k1 and k2 agree
        elif k1_bull and k2_bull and uptrend:
            signals.iloc[i] = 0.6
        elif k1_bear and k2_bear and not uptrend:
            signals.iloc[i] = -0.6
        # READY signal (weak): just k1
        elif k1_bull and uptrend:
            signals.iloc[i] = 0.3
        elif k1_bear and not uptrend:
            signals.iloc[i] = -0.3

    return signals


def generate_voter_signals(df: pd.DataFrame) -> pd.Series:
    """VoterAgent baseline: RSI(14) + MACD(13/34/8)."""

    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(prices: pd.Series) -> Dict:
        ema_fast = prices.ewm(span=13, adjust=False).mean()
        ema_slow = prices.ewm(span=34, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=8, adjust=False).mean()
        return {"histogram": macd_line - signal_line}

    prices = df["close"]
    rsi = calculate_rsi(prices, period=14)
    macd = calculate_macd(prices)

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

    if holdings > 0:
        cash += holdings * prices.iloc[-1]
        portfolio_values[-1] = cash

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
    """Run RAF vs VoterAgent comparison."""
    print("=" * 60)
    print("READY-AIM-FIRE MULTI-STOCHASTIC RESEARCH (#460)")
    print("=" * 60)

    results = {
        "run_timestamp": now_iso(),
        "issue": "#460",
        "description": "RAF (Stoch 5/8/17 + TEMA) vs VoterAgent (RSI14 + MACD 13/34/8)",
        "symbol_results": {},
    }

    raf_sharpes = []
    voter_sharpes = []

    for symbol in DEFAULT_SYMBOLS:
        print(f"\n{symbol}:")
        try:
            df = fetch_daily_data(symbol)
            print(f"  Data: {len(df)} days")

            # RAF
            raf_signals = generate_raf_signals(df)
            raf_result = backtest(df, raf_signals)

            # VoterAgent
            va_signals = generate_voter_signals(df)
            va_result = backtest(df, va_signals)

            print(
                f"  RAF: Sharpe={raf_result['sharpe']:.3f}, "
                f"Return={raf_result['total_return']:.1f}%"
            )
            print(
                f"  VoterAgent: Sharpe={va_result['sharpe']:.3f}, "
                f"Return={va_result['total_return']:.1f}%"
            )

            diff = raf_result["sharpe"] - va_result["sharpe"]
            print(f"  Difference: {diff:+.3f}")

            results["symbol_results"][symbol] = {
                "raf": raf_result,
                "voter_agent": va_result,
                "raf_wins": diff > 0,
            }

            raf_sharpes.append(raf_result["sharpe"])
            voter_sharpes.append(va_result["sharpe"])

        except Exception as e:
            print(f"  ERROR: {e}")

    # Summary
    if raf_sharpes:
        raf_wins = sum(1 for r, v in zip(raf_sharpes, voter_sharpes) if r > v)
        results["summary"] = {
            "avg_raf_sharpe": np.mean(raf_sharpes),
            "avg_voter_sharpe": np.mean(voter_sharpes),
            "raf_win_rate": raf_wins / len(raf_sharpes) * 100,
        }

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Avg RAF Sharpe: {results['summary']['avg_raf_sharpe']:.3f}")
        print(f"Avg VoterAgent Sharpe: {results['summary']['avg_voter_sharpe']:.3f}")
        print(f"RAF Win Rate: {results['summary']['raf_win_rate']:.0f}%")

    # Conclusion
    avg_raf = results["summary"]["avg_raf_sharpe"]
    avg_voter = results["summary"]["avg_voter_sharpe"]
    results["conclusion"] = {
        "raf_beats_voter": avg_raf > avg_voter,
        "raf_meets_threshold": avg_raf > 0.6,
        "recommendation": (
            "Consider RAF as 4th voter"
            if avg_raf > avg_voter and avg_raf > 0.6
            else "Archive - VoterAgent sufficient"
        ),
    }

    return convert_to_native(results)


def main():
    results = run_comparison()

    # Save results
    output = Path("docs/08_research/03_strategy_research/raf_results.yaml")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(results, f, default_flow_style=False, sort_keys=False)
    print(f"\nResults saved to: {output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
