"""
MACD Parameter Stability Analysis (#518)

Walk-forward analysis to test stability of MACD parameter combinations.
Motivated by 65-93% degradation observed in baseline MACD+RSI strategy.

METHODOLOGY FIXES APPLIED:
1. Symmetric signals: +1.0 long, -1.0 short (not asymmetric +1.0/-0.5)
2. RSI as trend confirmation: RSI > 50 confirms bullish, RSI < 50 confirms bearish
   (NOT range-bound 30-70 which contradicts trend-following)
3. Dynamic warmup: Calculated from actual parameters (slow EMA + signal + buffer)
4. Transaction costs: 5 bps per trade modeled
5. TSMOM baseline: Compare to validated 12-month momentum strategy

Parameter Grid:
- MACD: Standard (12/26/9), Fibonacci (13/34/8), Fast (8/17/9), Slow (19/39/9)
- RSI: None, Trend-confirming (>50 for long, <50 for short)

Stability metric:
    Stability = 1 - abs(IS_Sharpe - OOS_Sharpe) / max(abs(IS_Sharpe), EPSILON)
"""

import sqlite3
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# Constants
EPSILON = 1e-9
MIN_DATA_POINTS = 252
TRAIN_END = "2022-12-31"
TEST_START = "2023-01-01"
COST_BPS = 5  # Transaction cost per trade

DB_PATH = Path(".cache/gex_research.db")
OUTPUT_PATH = Path("docs/08_research/03_strategy_research/macd_stability_results.yaml")

# Parameter grid
MACD_PARAMS = {
    "standard": (12, 26, 9),
    "fibonacci": (13, 34, 8),
    "fast": (8, 17, 9),
    "slow": (19, 39, 9),
}

# RSI filters - trend-confirming, NOT range-bound
RSI_PARAMS = {
    "none": None,
    "trend_confirm": (14, "trend"),  # RSI > 50 confirms long, < 50 confirms short
}


@dataclass
class ParameterResult:
    """Results for a single parameter combination."""

    macd_name: str
    macd_fast: int
    macd_slow: int
    macd_signal: int
    rsi_name: str
    rsi_period: Optional[int]

    is_sharpe_gross: float
    is_sharpe_net: float
    oos_sharpe_gross: float
    oos_sharpe_net: float
    is_return: float
    oos_return: float
    is_trades: int
    oos_trades: int

    degradation_pct: float
    stability_score: float
    passes_validation: bool


def safe_sharpe(returns: pd.Series, annualize: int = 252) -> float:
    """Calculate Sharpe with safeguards."""
    if len(returns) < 2:
        return 0.0

    returns = returns.dropna()
    if len(returns) < 2:
        return 0.0

    std = returns.std()
    if std < EPSILON:
        return 0.0

    sharpe = (returns.mean() / std) * np.sqrt(annualize)
    return float(np.clip(sharpe, -10.0, 10.0))


def calculate_macd(prices: pd.Series, fast: int, slow: int, signal: int) -> pd.DataFrame:
    """Calculate MACD with given parameters."""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
            "bullish": histogram > 0,
        },
        index=prices.index,
    )


def calculate_rsi(prices: pd.Series, period: int) -> pd.Series:
    """Calculate RSI with div-by-zero protection."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / (loss + EPSILON)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_tsmom_signals(prices: pd.Series, lookback: int = 252) -> pd.Series:
    """
    Calculate academic TSMOM signals (12-month return).
    Used as validated baseline for comparison.
    """
    if len(prices) < lookback + 1:
        return pd.Series(0.0, index=prices.index)

    past_return = (prices - prices.shift(lookback)) / (prices.shift(lookback) + EPSILON)
    signals = np.sign(past_return)
    signals.iloc[:lookback] = 0.0
    signals = signals.shift(1).fillna(0)

    return signals


def generate_signals(
    prices: pd.Series, macd_params: Tuple[int, int, int], rsi_params: Optional[Tuple]
) -> pd.Series:
    """
    Generate trading signals for parameter combination.

    Uses symmetric signals (+1.0 long, -1.0 short) and trend-confirming RSI.
    """
    fast, slow, signal_period = macd_params

    # Dynamic warmup: accounts for all lookback periods
    rsi_period = rsi_params[0] if rsi_params else 0
    warmup = max(slow + signal_period, rsi_period) + 5

    if len(prices) < warmup:
        return pd.Series(0.0, index=prices.index)

    # Calculate MACD
    macd_df = calculate_macd(prices, fast, slow, signal_period)

    # SYMMETRIC signals: +1.0 long, -1.0 short
    signals = pd.Series(0.0, index=prices.index)
    signals[macd_df["bullish"]] = 1.0
    signals[~macd_df["bullish"]] = -1.0  # Fixed: was -0.5 (asymmetric bias)

    # Apply RSI filter if specified - TREND CONFIRMING, not range-bound
    if rsi_params is not None:
        period, filter_type = rsi_params
        rsi = calculate_rsi(prices, period)

        if filter_type == "trend":
            # RSI > 50 confirms long momentum, RSI < 50 confirms short momentum
            # Only take signals when RSI confirms direction
            long_confirmed = (signals > 0) & (rsi > 50)
            short_confirmed = (signals < 0) & (rsi < 50)
            signals = signals.where(long_confirmed | short_confirmed, 0.0)

    # Zero out warmup period
    signals.iloc[:warmup] = 0.0

    # Shift for t+1 execution (avoid look-ahead)
    signals = signals.shift(1).fillna(0)

    return signals


def run_backtest(
    prices: pd.Series, signals: pd.Series, cost_bps: int = 0
) -> Tuple[float, float, float, int]:
    """
    Run backtest with optional transaction costs.

    Returns:
        (gross_sharpe, net_sharpe, total_return, trade_count)
    """
    returns = prices.pct_change()
    gross_returns = signals * returns

    # Calculate trades and apply costs
    signal_changes = signals.diff().abs()
    trade_mask = signal_changes > EPSILON
    trade_count = int(trade_mask.sum())

    cost_per_trade = cost_bps / 10000
    net_returns = gross_returns.copy()
    net_returns[trade_mask] -= cost_per_trade

    gross_sharpe = safe_sharpe(gross_returns)
    net_sharpe = safe_sharpe(net_returns)

    # Total return (net)
    cumulative = (1 + net_returns).cumprod()
    total_return = (cumulative.iloc[-1] - 1) * 100 if len(cumulative) > 0 else 0.0

    return gross_sharpe, net_sharpe, total_return, trade_count


def get_price_data(conn: sqlite3.Connection, symbol: str) -> Optional[pd.DataFrame]:
    """Fetch price data from database."""
    query = """
        SELECT trading_date, underlying_price
        FROM options_daily_summary
        WHERE symbol = ? AND underlying_price IS NOT NULL
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))

    if len(df) < MIN_DATA_POINTS:
        return None

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df.set_index("trading_date", inplace=True)
    df.columns = ["close"]

    return df


def analyze_parameters(
    prices: pd.DataFrame,
    macd_name: str,
    macd_params: Tuple[int, int, int],
    rsi_name: str,
    rsi_params: Optional[Tuple],
) -> Optional[ParameterResult]:
    """Analyze a single parameter combination with walk-forward validation."""
    train_end_dt = pd.Timestamp(TRAIN_END)
    test_start_dt = pd.Timestamp(TEST_START)

    train_data = prices[prices.index <= train_end_dt]["close"]
    test_data = prices[prices.index >= test_start_dt]["close"]

    if len(train_data) < 100 or len(test_data) < 50:
        return None

    # Generate signals
    train_signals = generate_signals(train_data, macd_params, rsi_params)
    test_signals = generate_signals(test_data, macd_params, rsi_params)

    # Run backtests with transaction costs
    is_gross, is_net, is_return, is_trades = run_backtest(train_data, train_signals, COST_BPS)
    oos_gross, oos_net, oos_return, oos_trades = run_backtest(test_data, test_signals, COST_BPS)

    # Calculate degradation (using net Sharpe)
    if abs(is_net) > EPSILON:
        degradation = ((is_net - oos_net) / abs(is_net)) * 100
    else:
        degradation = 0.0 if abs(oos_net) < EPSILON else -100.0

    # Stability score
    stability = max(0.0, 1.0 - abs(is_net - oos_net) / (abs(is_net) + EPSILON))

    # Pass validation: OOS net > 0.3 and stability > 0.5
    passes = oos_net > 0.3 and stability > 0.5

    return ParameterResult(
        macd_name=macd_name,
        macd_fast=macd_params[0],
        macd_slow=macd_params[1],
        macd_signal=macd_params[2],
        rsi_name=rsi_name,
        rsi_period=rsi_params[0] if rsi_params else None,
        is_sharpe_gross=round(is_gross, 3),
        is_sharpe_net=round(is_net, 3),
        oos_sharpe_gross=round(oos_gross, 3),
        oos_sharpe_net=round(oos_net, 3),
        is_return=round(is_return, 2),
        oos_return=round(oos_return, 2),
        is_trades=is_trades,
        oos_trades=oos_trades,
        degradation_pct=round(degradation, 1),
        stability_score=round(stability, 3),
        passes_validation=passes,
    )


def analyze_tsmom_baseline(prices: pd.DataFrame) -> Optional[Dict]:
    """Analyze TSMOM baseline for comparison."""
    train_end_dt = pd.Timestamp(TRAIN_END)
    test_start_dt = pd.Timestamp(TEST_START)

    train_data = prices[prices.index <= train_end_dt]["close"]
    test_data = prices[prices.index >= test_start_dt]["close"]

    if len(train_data) < 300 or len(test_data) < 50:
        return None

    train_signals = calculate_tsmom_signals(train_data)
    test_signals = calculate_tsmom_signals(test_data)

    _, is_net, _, is_trades = run_backtest(train_data, train_signals, COST_BPS)
    _, oos_net, _, oos_trades = run_backtest(test_data, test_signals, COST_BPS)

    if abs(is_net) > EPSILON:
        degradation = ((is_net - oos_net) / abs(is_net)) * 100
    else:
        degradation = 0.0

    stability = max(0.0, 1.0 - abs(is_net - oos_net) / (abs(is_net) + EPSILON))

    return {
        "is_sharpe_net": round(is_net, 3),
        "oos_sharpe_net": round(oos_net, 3),
        "degradation_pct": round(degradation, 1),
        "stability": round(stability, 3),
        "is_trades": is_trades,
        "oos_trades": oos_trades,
    }


def main():  # noqa: C901
    """Main entry point."""
    print("=" * 70)
    print("MACD PARAMETER STABILITY ANALYSIS (#518)")
    print("METHODOLOGY: Symmetric signals, trend-confirming RSI, with costs")
    print(f"Train: 2016-{TRAIN_END} | Test: {TEST_START}-2024 | Cost: {COST_BPS} bps")
    print("=" * 70)

    if not DB_PATH.exists():
        print(f"ERROR: Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT symbol, COUNT(*) as days
            FROM options_daily_summary
            WHERE underlying_price IS NOT NULL
            GROUP BY symbol
            HAVING days >= ?
            ORDER BY days DESC
        """,
            (MIN_DATA_POINTS,),
        )

        symbols = [(row[0], row[1]) for row in cursor.fetchall()]
        print(f"\nSymbols with sufficient data: {len(symbols)}")

        param_combos = list(product(MACD_PARAMS.items(), RSI_PARAMS.items()))
        print(f"Parameter combinations: {len(param_combos)}")

        all_results: Dict[str, List[ParameterResult]] = {}
        tsmom_baselines: Dict[str, Dict] = {}

        for symbol, days in symbols[:10]:
            print(f"\nAnalyzing {symbol} ({days} days)...")

            prices = get_price_data(conn, symbol)
            if prices is None:
                continue

            # TSMOM baseline
            tsmom = analyze_tsmom_baseline(prices)
            if tsmom:
                tsmom_baselines[symbol] = tsmom
                print(
                    f"  TSMOM baseline: IS={tsmom['is_sharpe_net']:.2f}, OOS={tsmom['oos_sharpe_net']:.2f}"
                )

            symbol_results = []

            for (macd_name, macd_params), (rsi_name, rsi_params) in param_combos:
                result = analyze_parameters(prices, macd_name, macd_params, rsi_name, rsi_params)

                if result:
                    symbol_results.append(result)
                    status = "[PASS]" if result.passes_validation else "[FAIL]"
                    print(
                        f"  {macd_name}+{rsi_name}: "
                        f"IS={result.is_sharpe_net:.2f}, OOS={result.oos_sharpe_net:.2f}, "
                        f"Stability={result.stability_score:.2f} {status}"
                    )

            all_results[symbol] = symbol_results

        # Aggregate results
        print("\n" + "=" * 70)
        print("AGGREGATED RESULTS BY PARAMETER COMBINATION")
        print("=" * 70)

        param_aggregates: Dict[str, Dict] = {}

        for (macd_name, _), (rsi_name, _) in param_combos:
            key = f"{macd_name}+{rsi_name}"

            combo_results = []
            for symbol_results in all_results.values():
                for r in symbol_results:
                    if r.macd_name == macd_name and r.rsi_name == rsi_name:
                        combo_results.append(r)

            if combo_results:
                avg_is = np.mean([r.is_sharpe_net for r in combo_results])
                avg_oos = np.mean([r.oos_sharpe_net for r in combo_results])
                avg_stability = np.mean([r.stability_score for r in combo_results])
                pass_rate = np.mean([r.passes_validation for r in combo_results]) * 100

                param_aggregates[key] = {
                    "avg_is_sharpe": float(round(avg_is, 3)),
                    "avg_oos_sharpe": float(round(avg_oos, 3)),
                    "avg_stability": float(round(avg_stability, 3)),
                    "pass_rate_pct": float(round(pass_rate, 1)),
                    "n_tests": len(combo_results),
                }

                print(
                    f"{key:25s}: IS={avg_is:.3f}, OOS={avg_oos:.3f}, "
                    f"Stability={avg_stability:.3f}, PassRate={pass_rate:.0f}%"
                )

        # TSMOM baseline summary
        if tsmom_baselines:
            avg_tsmom_oos = np.mean([t["oos_sharpe_net"] for t in tsmom_baselines.values()])
            avg_tsmom_stability = np.mean([t["stability"] for t in tsmom_baselines.values()])
            print(
                f"\nTSMOM BASELINE:          OOS={avg_tsmom_oos:.3f}, Stability={avg_tsmom_stability:.3f}"
            )

        # Best parameters
        if param_aggregates:
            best_params = max(
                param_aggregates.items(),
                key=lambda x: (x[1]["avg_oos_sharpe"], x[1]["avg_stability"]),
            )

            print(f"\nBest MACD parameters: {best_params[0]}")
            print(f"  OOS Sharpe: {best_params[1]['avg_oos_sharpe']:.3f}")
            print(f"  Stability: {best_params[1]['avg_stability']:.3f}")

        # Save results
        output_data = {
            "experiment": "MACD Parameter Stability Analysis",
            "issue": "#518",
            "methodology": {
                "train_period": f"2016-01-01 to {TRAIN_END}",
                "test_period": f"{TEST_START} to 2024-12-31",
                "look_ahead_protection": "signals.shift(1)",
                "transaction_cost_bps": COST_BPS,
                "signal_type": "symmetric (+1/-1)",
                "rsi_filter": "trend-confirming (RSI>50 for long, RSI<50 for short)",
                "validation_criteria": {
                    "oos_sharpe_min": 0.3,
                    "stability_min": 0.5,
                },
                "fixes_applied": [
                    "Symmetric signals (was asymmetric +1/-0.5)",
                    "Trend-confirming RSI (was range-bound 30-70)",
                    "Dynamic warmup calculation",
                    "Transaction costs modeled",
                    "TSMOM baseline comparison added",
                ],
            },
            "parameter_grid": {
                "macd": {k: list(v) for k, v in MACD_PARAMS.items()},
                "rsi": {k: str(v) for k, v in RSI_PARAMS.items()},
            },
            "tsmom_baseline": {
                symbol: {
                    k: float(v) if isinstance(v, (float, np.floating)) else v
                    for k, v in baseline.items()
                }
                for symbol, baseline in tsmom_baselines.items()
            },
            "aggregate_results": {
                k: {
                    kk: float(vv) if isinstance(vv, (float, np.floating)) else vv
                    for kk, vv in v.items()
                }
                for k, v in param_aggregates.items()
            },
            "best_parameters": best_params[0] if param_aggregates else None,
            "detailed_results": {
                symbol: [
                    {
                        "macd": f"{r.macd_name} ({r.macd_fast}/{r.macd_slow}/{r.macd_signal})",
                        "rsi": r.rsi_name,
                        "is_sharpe_net": float(r.is_sharpe_net),
                        "oos_sharpe_net": float(r.oos_sharpe_net),
                        "degradation_pct": float(r.degradation_pct),
                        "stability": float(r.stability_score),
                        "trades_is": int(r.is_trades),
                        "trades_oos": int(r.oos_trades),
                        "passes": bool(r.passes_validation),
                    }
                    for r in results
                ]
                for symbol, results in all_results.items()
            },
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            yaml.dump(output_data, f, default_flow_style=False, sort_keys=False)

        print(f"\n[OK] Results saved: {OUTPUT_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
