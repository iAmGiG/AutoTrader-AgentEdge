"""
TSMOM + GEX Hybrid Strategy (#516)

This script tests a hybrid strategy combining Time-Series Momentum (TSMOM) with
a Gamma Exposure (GEX) regime filter.

Based on counter-intuitive findings from #523, which suggested:
- TSMOM performs BETTER in NEGATIVE gamma regimes (1.656 avg Sharpe)
- TSMOM performs WORSE in POSITIVE gamma regimes (0.339 avg Sharpe)

Strategy Logic (INVERSE of naive approach):
- NEGATIVE_GAMMA: Full position (dealers amplify momentum follow-through)
- NEUTRAL: 50% position
- POSITIVE_GAMMA: 25% position or exit (dealers dampen moves)

METHODOLOGY:
- Transaction costs are modeled (default 5bps per trade).
- Costs are applied proportionally to portfolio turnover (rebalancing).
"""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# Constants
EPSILON = 1e-9  # Div-by-zero protection
MIN_DATA_POINTS = 300  # Minimum days for valid analysis (TSMOM needs 252 lookback + buffer)
COST_BPS = 5  # Transaction cost per rebalance

DB_PATH = Path(".cache/gex_research.db")
OUTPUT_PATH = Path("docs/08_research/03_strategy_research/tsmom_gex_hybrid_results.yaml")


@dataclass
class HybridResult:
    """Results from TSMOM+GEX hybrid strategy."""

    symbol: str
    period: str

    # Pure TSMOM baseline (net of costs)
    tsmom_only_sharpe_net: float
    tsmom_only_return: float
    tsmom_only_max_dd: float
    tsmom_trades: int

    # Hybrid strategy (net of costs)
    hybrid_sharpe_net: float
    hybrid_return: float
    hybrid_max_dd: float
    hybrid_trades: int

    # Regime exposure
    days_negative_gamma: int
    days_positive_gamma: int
    days_neutral: int

    # Improvement metrics (based on net Sharpe)
    sharpe_improvement: float
    drawdown_improvement: float


def safe_sharpe(returns: pd.Series, annualize: int = 252) -> float:
    """Calculate Sharpe ratio with proper safeguards."""
    if len(returns) < 2:
        return 0.0

    returns = returns.dropna()
    if len(returns) < 2:
        return 0.0

    std = returns.std()
    if std < EPSILON:
        return 0.0

    sharpe = (returns.mean() / std) * np.sqrt(annualize)

    # Clip extreme values
    return float(np.clip(sharpe, -10.0, 10.0))


def safe_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate max drawdown with safeguards."""
    if len(equity_curve) < 2:
        return 0.0

    equity_curve = equity_curve.dropna()
    if len(equity_curve) < 2:
        return 0.0

    rolling_max = equity_curve.cummax()

    # Avoid div-by-zero when rolling_max is 0
    drawdown = (equity_curve - rolling_max) / (rolling_max + EPSILON)

    return float(drawdown.min()) * 100  # Return as percentage


def get_price_and_regime_data(conn: sqlite3.Connection, symbol: str) -> Optional[pd.DataFrame]:
    """Fetch price and regime data from database."""
    query = """
        SELECT trading_date, underlying_price, regime
        FROM options_daily_summary
        WHERE symbol = ? AND underlying_price IS NOT NULL
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))

    if len(df) < MIN_DATA_POINTS:
        return None

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df.set_index("trading_date", inplace=True)

    return df


def calculate_tsmom_signal(prices: pd.Series, lookback: int = 252) -> pd.Series:
    """
    Calculate TSMOM signal: sign of past 12-month return. This is the unscaled
    version of TSMOM, distinct from the volatility-scaled version in other
    research scripts (e.g., multi_asset_tsmom.py), highlighting a project-wide
    inconsistency in the TSMOM definition.
    """
    signals = pd.Series(0.0, index=prices.index)

    if len(prices) < lookback + 1:
        return signals

    # Vectorized past return calculation
    past_return = (prices - prices.shift(lookback)) / (prices.shift(lookback) + EPSILON)

    # Signal: +1 if positive momentum, -1 if negative
    signals = np.sign(past_return)

    # First lookback days have no signal
    signals.iloc[:lookback] = 0.0

    # Shift by 1 to avoid look-ahead bias (signal at t, execute at t+1)
    signals = signals.shift(1).fillna(0)

    return signals


def apply_regime_weights(
    signals: pd.Series,
    regimes: pd.Series,
    negative_weight: float = 1.0,
    neutral_weight: float = 0.5,
    positive_weight: float = 0.25,
) -> pd.Series:
    """
    Apply GEX regime-based position sizing.

    INVERSE strategy: more aggressive in negative gamma.

    Args:
        signals: Base TSMOM signals (-1, 0, +1)
        regimes: GEX regime classification
        negative_weight: Weight in NEGATIVE_GAMMA (default 1.0 = full)
        neutral_weight: Weight in NEUTRAL (default 0.5)
        positive_weight: Weight in POSITIVE_GAMMA (default 0.25 = quarter)
    """
    # Shift regimes by 1 to use T-1 regime for T trading (avoid look-ahead)
    regime_shifted = regimes.shift(1)

    weights = pd.Series(neutral_weight, index=signals.index)

    weights[regime_shifted == "NEGATIVE_GAMMA"] = negative_weight
    weights[regime_shifted == "POSITIVE_GAMMA"] = positive_weight
    weights[regime_shifted == "NEUTRAL"] = neutral_weight

    # Handle NaN regimes (use neutral)
    weights = weights.fillna(neutral_weight)

    return signals * weights


def run_backtest(
    prices: pd.Series, signals: pd.Series, cost_bps: int = 0, initial_capital: float = 10000.0
) -> Tuple[pd.Series, pd.Series, pd.Series, int]:
    """
    Run vectorized backtest with t+1 execution and transaction costs.

    Returns:
        Tuple of (equity_curve, gross_returns, net_returns, trade_count)
    """
    # Daily returns
    daily_returns = prices.pct_change()

    # Strategy returns: signal at t-1, return at t (already shifted in signal calc)
    gross_returns = signals * daily_returns

    # Apply transaction costs proportional to turnover
    turnover = signals.diff().abs()
    trade_mask = turnover > EPSILON
    trade_count = int(trade_mask.sum())

    cost_per_100_pct_turnover = cost_bps / 10000
    transaction_costs = turnover * cost_per_100_pct_turnover
    net_returns = gross_returns - transaction_costs

    # Build equity curve (using net returns)
    equity = initial_capital * (1 + net_returns).cumprod()

    return equity, gross_returns, net_returns, trade_count


def analyze_symbol(conn: sqlite3.Connection, symbol: str) -> Optional[HybridResult]:
    """Run hybrid strategy analysis for a single symbol."""
    data = get_price_and_regime_data(conn, symbol)
    if data is None:
        return None

    prices = data["underlying_price"]
    regimes = data["regime"]

    # Calculate TSMOM signals
    tsmom_signals = calculate_tsmom_signal(prices)

    # Apply hybrid regime weighting
    hybrid_signals = apply_regime_weights(tsmom_signals, regimes)

    # Run backtests with transaction costs
    tsmom_equity, _, tsmom_net_returns, tsmom_trades = run_backtest(
        prices, tsmom_signals, cost_bps=COST_BPS
    )
    hybrid_equity, _, hybrid_net_returns, hybrid_trades = run_backtest(
        prices, hybrid_signals, cost_bps=COST_BPS
    )

    # Calculate metrics (using net returns)
    tsmom_sharpe = safe_sharpe(tsmom_net_returns)
    hybrid_sharpe = safe_sharpe(hybrid_net_returns)

    tsmom_total_return = ((tsmom_equity.iloc[-1] / 10000) - 1) * 100
    hybrid_total_return = ((hybrid_equity.iloc[-1] / 10000) - 1) * 100

    tsmom_max_dd = safe_max_drawdown(tsmom_equity)
    hybrid_max_dd = safe_max_drawdown(hybrid_equity)

    # Regime counts
    regime_shifted = regimes.shift(1)
    days_neg = int((regime_shifted == "NEGATIVE_GAMMA").sum())
    days_pos = int((regime_shifted == "POSITIVE_GAMMA").sum())
    days_neutral = int((regime_shifted == "NEUTRAL").sum())

    # Improvements (based on net Sharpe).
    # NOTE: This metric can be volatile if the baseline Sharpe is near zero.
    # The median improvement across all symbols is a more robust measure.
    sharpe_improvement = (
        ((hybrid_sharpe - tsmom_sharpe) / abs(tsmom_sharpe + EPSILON)) * 100
        if abs(tsmom_sharpe) > EPSILON
        else 0.0
    )

    # Drawdown improvement: A smaller (less negative) DD is an improvement.
    # (e.g., tsmom_dd=-20, hybrid_dd=-15. Improvement = (-15 - (-20)) / |-20| = 5/20 = 25%)
    dd_improvement = (
        ((hybrid_max_dd - tsmom_max_dd) / abs(tsmom_max_dd + EPSILON)) * 100
        if abs(tsmom_max_dd) > EPSILON
        else 0.0
    )

    return HybridResult(
        symbol=symbol,
        period=f"{data.index.min().date()} to {data.index.max().date()}",
        tsmom_only_sharpe_net=round(tsmom_sharpe, 3),
        tsmom_only_return=round(tsmom_total_return, 2),
        tsmom_only_max_dd=round(tsmom_max_dd, 2),
        tsmom_trades=tsmom_trades,
        hybrid_sharpe_net=round(hybrid_sharpe, 3),
        hybrid_return=round(hybrid_total_return, 2),
        hybrid_max_dd=round(hybrid_max_dd, 2),
        hybrid_trades=hybrid_trades,
        days_negative_gamma=days_neg,
        days_positive_gamma=days_pos,
        days_neutral=days_neutral,
        sharpe_improvement=round(sharpe_improvement, 1),
        drawdown_improvement=round(dd_improvement, 1),
    )


def main():
    """Main entry point."""
    print("=" * 70)
    print("TSMOM + GEX HYBRID STRATEGY (#516)")
    print(f"Inverse Regime Weighting | Transaction Cost: {COST_BPS} bps")
    print("=" * 70)

    if not DB_PATH.exists():
        print(f"ERROR: Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    try:
        # Get symbols with sufficient data
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT symbol, COUNT(*) as days
            FROM options_daily_summary
            WHERE underlying_price IS NOT NULL AND regime IS NOT NULL
            GROUP BY symbol
            HAVING days >= ?
            ORDER BY days DESC
        """,
            (MIN_DATA_POINTS,),
        )

        symbols = [(row[0], row[1]) for row in cursor.fetchall()]
        print(f"\nSymbols with sufficient data: {len(symbols)}")

        results: List[HybridResult] = []

        for symbol, days in symbols:
            print(f"\nAnalyzing {symbol} ({days} days)...")
            result = analyze_symbol(conn, symbol)

            if result:
                results.append(result)
                print(
                    f"  TSMOM-only Net Sharpe: {result.tsmom_only_sharpe_net:.3f} ({result.tsmom_trades} trades)"
                )
                print(
                    f"  Hybrid Net Sharpe:     {result.hybrid_sharpe_net:.3f} ({result.hybrid_trades} trades)"
                )
                print(f"  Improvement:           {result.sharpe_improvement:+.1f}%")

        if not results:
            print("\nNo valid results. Check database has regime data.")
            sys.exit(1)

        # Filter out results where both strategies have zero Sharpe (insufficient data)
        valid_results = [
            r
            for r in results
            if abs(r.tsmom_only_sharpe_net) > EPSILON or abs(r.hybrid_sharpe_net) > EPSILON
        ]

        if not valid_results:
            print("\nNo valid results after filtering zero-Sharpe entries.")
            sys.exit(1)

        # Aggregate statistics - use MEDIAN to avoid outlier skew
        improvements = [r.sharpe_improvement for r in valid_results]
        avg_tsmom_sharpe = float(np.mean([r.tsmom_only_sharpe_net for r in valid_results]))
        avg_hybrid_sharpe = float(np.mean([r.hybrid_sharpe_net for r in valid_results]))
        median_improvement = float(np.median(improvements))
        mean_improvement = float(np.mean(improvements))

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Symbols analyzed: {len(valid_results)} (filtered from {len(results)})")
        print(f"Avg TSMOM-only Sharpe: {avg_tsmom_sharpe:.3f}")
        print(f"Avg Hybrid Sharpe:     {avg_hybrid_sharpe:.3f}")
        print(f"Median Improvement:    {median_improvement:+.1f}%")
        print(f"Mean Improvement:      {mean_improvement:+.1f}% (caution: outlier-sensitive)")

        # Save results
        output_data = {
            "experiment": "TSMOM + GEX Hybrid Strategy",
            "issue": "#516",
            "methodology": {
                "base_strategy": "TSMOM 12-month momentum (unscaled)",
                "regime_weighting": {
                    "NEGATIVE_GAMMA": 1.0,
                    "NEUTRAL": 0.5,
                    "POSITIVE_GAMMA": 0.25,
                },
                "look_ahead_protection": "signals.shift(1), regimes.shift(1)",
                "execution": "t+1 (signal at close, execute next day)",
                "transaction_cost_bps": COST_BPS,
                "note": "Uses unscaled TSMOM (sign of 12-mo return), distinct from vol-scaled version in multi_asset_tsmom.py",
            },
            "summary": {
                "symbols_analyzed": len(valid_results),
                "symbols_total": len(results),
                "avg_tsmom_sharpe_net": round(avg_tsmom_sharpe, 3),
                "avg_hybrid_sharpe_net": round(avg_hybrid_sharpe, 3),
                "median_improvement_pct": round(median_improvement, 1),
                "mean_improvement_pct": round(mean_improvement, 1),
            },
            "results": [
                {
                    "symbol": r.symbol,
                    "period": r.period,
                    "tsmom_only": {
                        "sharpe_net": float(r.tsmom_only_sharpe_net),
                        "return_pct": float(r.tsmom_only_return),
                        "max_dd_pct": float(r.tsmom_only_max_dd),
                        "trades": int(r.tsmom_trades),
                    },
                    "hybrid": {
                        "sharpe_net": float(r.hybrid_sharpe_net),
                        "return_pct": float(r.hybrid_return),
                        "max_dd_pct": float(r.hybrid_max_dd),
                        "trades": int(r.hybrid_trades),
                    },
                    "regime_exposure": {
                        "negative_gamma_days": int(r.days_negative_gamma),
                        "positive_gamma_days": int(r.days_positive_gamma),
                        "neutral_days": int(r.days_neutral),
                    },
                    "sharpe_improvement_pct": float(r.sharpe_improvement),
                    "drawdown_improvement_pct": float(r.drawdown_improvement),
                }
                for r in valid_results
            ],
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            yaml.dump(output_data, f, default_flow_style=False, sort_keys=False)

        print(f"\n[OK] Results saved: {OUTPUT_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
