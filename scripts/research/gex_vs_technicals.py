"""
GEX vs Technicals Walk-Forward Comparison (#394)

Compare GEX-based trading signals against traditional technical indicators.
Uses existing GEX data from .cache/gex_research.db (2020-2025).

Strategies Compared:
1. TECHNICALS-ONLY: MACD + RSI voting (current VoterAgent baseline)
2. GEX-ONLY: Trade based on GEX regime (positive gamma = bullish)
3. HYBRID: Combine GEX regime with technicals

Walk-Forward Design:
- Train: 2020-2023 (regime classification, parameter optimization)
- Test: 2024-2025 (out-of-sample validation)

Usage:
    python scripts/research/gex_vs_technicals.py
    python scripts/research/gex_vs_technicals.py --symbol SPY --output results.json
"""

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Use simple ISO timestamp without date_utils dependency to avoid config requirement
from datetime import datetime as dt


def now_iso() -> str:
    """Get current timestamp as ISO string."""
    return dt.now().isoformat()


def convert_to_native_types(obj: Any) -> Any:
    """Convert numpy types to native Python types for YAML serialization."""
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_to_native_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_native_types(item) for item in obj]
    return obj


DB_PATH = Path(".cache/gex_research.db")
RESULTS_DB_PATH = Path(".cache/backtest_results.db")


@dataclass
class StrategyResult:
    """Results from a strategy backtest."""

    name: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    avg_trade_return: float


def load_gex_data(symbol: str = "SPY") -> pd.DataFrame:
    """Load GEX data from SQLite database."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"GEX database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT trading_date, regime, underlying_price, total_gex,
               net_call_gex, net_put_gex, asset_class
        FROM options_daily_summary
        WHERE symbol = ?
        AND underlying_price IS NOT NULL
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))
    conn.close()

    if df.empty:
        raise ValueError(f"No data found for symbol: {symbol}")

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df = df.set_index("trading_date")

    # Normalize regime names
    regime_map = {
        "POSITIVE_GAMMA": "POSITIVE",
        "NEGATIVE_GAMMA": "NEGATIVE",
        "NEUTRAL": "NEUTRAL",
    }
    df["regime"] = df["regime"].map(regime_map).fillna("UNKNOWN")

    # Calculate returns
    df["returns"] = df["underlying_price"].pct_change()

    return df


def calculate_macd(prices: pd.Series, fast: int = 13, slow: int = 34, signal: int = 8) -> Dict:
    """Calculate MACD indicator with Fibonacci parameters."""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def generate_technical_signals(df: pd.DataFrame) -> pd.Series:
    """
    Generate trading signals from MACD + RSI voting.
    Based on validated VoterAgent logic (0.856 Sharpe on AAPL 2024).
    """
    prices = df["underlying_price"]

    # Calculate indicators
    macd = calculate_macd(prices)
    rsi = calculate_rsi(prices)

    signals = pd.Series(0.0, index=df.index)

    for i in range(34, len(df)):  # Start after slow EMA period
        macd_signal = 0
        rsi_signal = 0

        # MACD signal: histogram direction
        if macd["histogram"].iloc[i] > 0 and macd["histogram"].iloc[i - 1] <= 0:
            macd_signal = 1  # Bullish crossover
        elif macd["histogram"].iloc[i] < 0 and macd["histogram"].iloc[i - 1] >= 0:
            macd_signal = -1  # Bearish crossover

        # RSI signal: overbought/oversold
        rsi_val = rsi.iloc[i]
        if rsi_val < 30:
            rsi_signal = 1  # Oversold = buy
        elif rsi_val > 70:
            rsi_signal = -1  # Overbought = sell

        # Voting: both agree = strong signal, one signals = weak, disagree = hold
        if macd_signal == rsi_signal and macd_signal != 0:
            signals.iloc[i] = macd_signal  # Strong agreement
        elif macd_signal != 0 and rsi_signal == 0:
            signals.iloc[i] = macd_signal * 0.5  # Weak MACD signal
        elif rsi_signal != 0 and macd_signal == 0:
            signals.iloc[i] = rsi_signal * 0.5  # Weak RSI signal

    return signals


def generate_gex_signals(df: pd.DataFrame) -> pd.Series:
    """
    Generate trading signals from GEX regime.

    Logic:
    - POSITIVE gamma: Dealers hedge by buying dips, selling rips = stabilizing = bullish
    - NEGATIVE gamma: Dealers hedge same direction as market = amplifying = bearish
    - NEUTRAL: No strong dealer positioning = hold
    """
    signals = pd.Series(0.0, index=df.index)

    regime_map = {"POSITIVE": 1, "NEGATIVE": -1, "NEUTRAL": 0, "UNKNOWN": 0}

    for i in range(1, len(df)):
        current_regime = df["regime"].iloc[i]
        prev_regime = df["regime"].iloc[i - 1]

        # Signal on regime transitions
        if current_regime != prev_regime:
            if current_regime == "POSITIVE":
                signals.iloc[i] = 1  # Enter long
            elif current_regime == "NEGATIVE":
                signals.iloc[i] = -1  # Exit or short
        else:
            # Maintain position based on current regime
            signals.iloc[i] = regime_map.get(current_regime, 0) * 0.5

    return signals


def generate_hybrid_signals(df: pd.DataFrame) -> pd.Series:
    """
    Combine GEX regime with technical signals.

    Logic:
    - Only trade technicals when GEX regime is favorable
    - POSITIVE gamma + bullish technicals = strong buy
    - NEGATIVE gamma = reduce exposure regardless of technicals
    """
    tech_signals = generate_technical_signals(df)
    # Note: GEX regime is used directly from df["regime"], not from gex_signals

    signals = pd.Series(0.0, index=df.index)

    for i in range(len(df)):
        tech = tech_signals.iloc[i]
        regime = df["regime"].iloc[i]

        if regime == "POSITIVE":
            # Amplify bullish technicals, dampen bearish
            if tech > 0:
                signals.iloc[i] = tech * 1.5  # Boost bullish
            else:
                signals.iloc[i] = tech * 0.5  # Reduce bearish
        elif regime == "NEGATIVE":
            # Dampen all signals during negative gamma
            signals.iloc[i] = tech * 0.3
        else:
            # Neutral regime - use technicals as-is
            signals.iloc[i] = tech

        # Clip to [-1, 1]
        signals.iloc[i] = np.clip(signals.iloc[i], -1, 1)

    return signals


def backtest_strategy(
    df: pd.DataFrame, signals: pd.Series, initial_capital: float = 10000
) -> StrategyResult:
    """Run backtest on strategy signals."""
    # Simple long-only strategy
    position = 0
    cash = initial_capital
    holdings = 0
    trades = []
    portfolio_values = []

    prices = df["underlying_price"]

    for i in range(len(df)):
        price = prices.iloc[i]
        signal = signals.iloc[i]

        # Track portfolio value
        portfolio_value = cash + holdings * price
        portfolio_values.append(portfolio_value)

        # Trading logic
        if signal > 0.3 and position == 0:
            # Buy
            shares = int(cash * 0.95 / price)  # 95% of cash
            if shares > 0:
                cost = shares * price
                cash -= cost
                holdings += shares
                position = 1
                trades.append({"date": df.index[i], "action": "BUY", "price": price})

        elif signal < -0.3 and position == 1:
            # Sell
            if holdings > 0:
                revenue = holdings * price
                cash += revenue
                trades.append(
                    {
                        "date": df.index[i],
                        "action": "SELL",
                        "price": price,
                        "pnl": revenue - (trades[-1]["price"] * holdings),
                    }
                )
                holdings = 0
                position = 0

    # Close any remaining position
    if holdings > 0:
        cash += holdings * prices.iloc[-1]
        portfolio_values[-1] = cash

    # Calculate metrics
    pv = pd.Series(portfolio_values)
    returns = pv.pct_change().dropna()

    total_return = (pv.iloc[-1] - initial_capital) / initial_capital * 100
    sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0

    # Max drawdown
    cummax = pv.cummax()
    drawdown = (pv - cummax) / cummax
    max_dd = drawdown.min() * 100

    # Win rate
    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    win_rate = len(winning_trades) / len(sell_trades) * 100 if sell_trades else 0

    # Average trade return
    trade_returns = [t.get("pnl", 0) for t in trades if "pnl" in t]
    avg_trade = np.mean(trade_returns) if trade_returns else 0

    return StrategyResult(
        name="",
        total_return=total_return,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        num_trades=len(trades),
        avg_trade_return=avg_trade,
    )


def run_walk_forward_comparison(symbol: str = "SPY") -> Dict[str, Any]:
    """
    Run walk-forward comparison of strategies.

    Train: 2020-2023 (parameter tuning, not used here since we use proven params)
    Test: 2024-2025 (out-of-sample)
    """
    print("=" * 70)
    print(f"GEX vs TECHNICALS WALK-FORWARD COMPARISON: {symbol}")
    print("=" * 70)
    print()

    # Load data
    df = load_gex_data(symbol)
    print(f"Data loaded: {len(df)} days")
    print(f"Date range: {df.index[0].date()} to {df.index[-1].date()}")
    print()

    # Split into train/test
    train_end = "2023-12-31"
    df_train = df[df.index <= train_end]
    df_test = df[df.index > train_end]

    train_start = df_train.index[0].date()
    train_stop = df_train.index[-1].date()
    test_start = df_test.index[0].date()
    test_stop = df_test.index[-1].date()
    print(f"Train period: {train_start} to {train_stop} ({len(df_train)} days)")
    print(f"Test period: {test_start} to {test_stop} ({len(df_test)} days)")
    print()

    if len(df_test) < 20:
        print("Warning: Insufficient test data. Using all data instead.")
        df_test = df

    # Generate signals for test period
    print("Generating signals...")
    tech_signals = generate_technical_signals(df_test)
    gex_signals = generate_gex_signals(df_test)
    hybrid_signals = generate_hybrid_signals(df_test)

    # Run backtests
    print("Running backtests...")
    tech_result = backtest_strategy(df_test, tech_signals)
    tech_result.name = "TECHNICALS (MACD+RSI)"

    gex_result = backtest_strategy(df_test, gex_signals)
    gex_result.name = "GEX-ONLY"

    hybrid_result = backtest_strategy(df_test, hybrid_signals)
    hybrid_result.name = "HYBRID (GEX+Technicals)"

    # Print results
    print()
    print("=" * 70)
    print("RESULTS (Out-of-Sample Test Period)")
    print("=" * 70)
    print()

    results = [tech_result, gex_result, hybrid_result]

    header = f"{'Strategy':<25} {'Return':>10} {'Sharpe':>10} "
    header += f"{'MaxDD':>10} {'WinRate':>10} {'Trades':>8}"
    print(header)
    print("-" * 75)

    for r in results:
        print(
            f"{r.name:<25} {r.total_return:>9.2f}% {r.sharpe_ratio:>10.3f} "
            f"{r.max_drawdown:>9.2f}% {r.win_rate:>9.1f}% {r.num_trades:>8}"
        )

    print("-" * 75)
    print()

    # Determine winner
    best = max(results, key=lambda x: x.sharpe_ratio)
    print(f"WINNER (by Sharpe): {best.name}")
    print()

    # GEX value assessment
    gex_improvement = gex_result.sharpe_ratio - tech_result.sharpe_ratio
    hybrid_improvement = hybrid_result.sharpe_ratio - tech_result.sharpe_ratio

    print("GEX VALUE ASSESSMENT")
    print("-" * 40)
    print(f"GEX-only vs Technicals: {gex_improvement:+.3f} Sharpe")
    print(f"Hybrid vs Technicals: {hybrid_improvement:+.3f} Sharpe")

    if hybrid_improvement > 0.1:
        print("\n-> GEX adds significant value when combined with technicals")
    elif hybrid_improvement > 0:
        print("\n-> GEX provides marginal improvement")
    else:
        print("\n-> GEX does not improve upon technicals in this period")

    return convert_to_native_types(
        {
            "symbol": symbol,
            "train_period": f"{df_train.index[0].date()} to {df_train.index[-1].date()}",
            "test_period": f"{df_test.index[0].date()} to {df_test.index[-1].date()}",
            "results": {
                r.name: {
                    "total_return": r.total_return,
                    "sharpe_ratio": r.sharpe_ratio,
                    "max_drawdown": r.max_drawdown,
                    "win_rate": r.win_rate,
                    "num_trades": r.num_trades,
                }
                for r in results
            },
            "winner": best.name,
            "gex_improvement": hybrid_improvement,
        }
    )


def save_results_to_db(results: Dict[str, Any]) -> None:
    """Save backtest results to SQLite database."""
    conn = sqlite3.connect(RESULTS_DB_PATH)
    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS gex_vs_technicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            train_period TEXT,
            test_period TEXT,
            tech_return REAL,
            tech_sharpe REAL,
            tech_max_dd REAL,
            tech_win_rate REAL,
            tech_trades INTEGER,
            gex_return REAL,
            gex_sharpe REAL,
            gex_max_dd REAL,
            gex_win_rate REAL,
            gex_trades INTEGER,
            hybrid_return REAL,
            hybrid_sharpe REAL,
            hybrid_max_dd REAL,
            hybrid_win_rate REAL,
            hybrid_trades INTEGER,
            winner TEXT,
            gex_improvement REAL
        )
    """
    )

    # Extract strategy results
    tech = results["results"].get("TECHNICALS (MACD+RSI)", {})
    gex = results["results"].get("GEX-ONLY", {})
    hybrid = results["results"].get("HYBRID (GEX+Technicals)", {})

    cursor.execute(
        """
        INSERT INTO gex_vs_technicals (
            run_timestamp, symbol, train_period, test_period,
            tech_return, tech_sharpe, tech_max_dd, tech_win_rate, tech_trades,
            gex_return, gex_sharpe, gex_max_dd, gex_win_rate, gex_trades,
            hybrid_return, hybrid_sharpe, hybrid_max_dd, hybrid_win_rate, hybrid_trades,
            winner, gex_improvement
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_iso(),
            results["symbol"],
            results.get("train_period"),
            results.get("test_period"),
            tech.get("total_return"),
            tech.get("sharpe_ratio"),
            tech.get("max_drawdown"),
            tech.get("win_rate"),
            tech.get("num_trades"),
            gex.get("total_return"),
            gex.get("sharpe_ratio"),
            gex.get("max_drawdown"),
            gex.get("win_rate"),
            gex.get("num_trades"),
            hybrid.get("total_return"),
            hybrid.get("sharpe_ratio"),
            hybrid.get("max_drawdown"),
            hybrid.get("win_rate"),
            hybrid.get("num_trades"),
            results.get("winner"),
            results.get("gex_improvement"),
        ),
    )

    conn.commit()
    conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GEX vs Technicals comparison")
    parser.add_argument("--symbol", default="SPY", help="Symbol to test")
    parser.add_argument("--output", "-o", help="Output YAML file")
    parser.add_argument("--no-db", action="store_true", help="Skip saving to database")

    args = parser.parse_args()

    try:
        results = run_walk_forward_comparison(args.symbol)

        # Save to database by default
        if not args.no_db:
            save_results_to_db(results)
            print(f"\nResults saved to: {RESULTS_DB_PATH}")

        # Save YAML if output specified
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                yaml.dump(results, f, default_flow_style=False, sort_keys=False)
            print(f"Results saved to: {args.output}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Run from project root with .cache/gex_research.db available")
        return 1
    except ValueError as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
