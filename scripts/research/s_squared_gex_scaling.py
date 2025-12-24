"""
S-Squared GEX Scaling Research (#502)

Test whether academic GEX formula with S² scaling improves trading signals.

Current formula (dask_gex_calculator.py):
    weighted_gamma = gamma * open_interest

Academic formula:
    GEX = OI × Gamma × S² × 0.01 × 100
    where S = underlying price

The S² scaling makes GEX values comparable across different price levels,
which is important for cross-asset analysis.

Usage:
    python scripts/research/s_squared_gex_scaling.py
"""

import datetime
import sqlite3
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import yaml


def now_iso() -> str:
    """Get current timestamp as ISO string."""
    return datetime.datetime.now().isoformat()


# Use main repo database path
GEX_DB_PATH = Path("a:/Projects/AutoGen-Trader/.cache/gex_research.db")

# Test symbols across different price ranges
TEST_SYMBOLS = {
    "high_price": ["SPY", "QQQ"],  # ~$400-500
    "medium_price": ["IWM"],  # ~$200
    "low_price": ["SQQQ", "UVXY"],  # ~$10-30
    "leveraged": ["TQQQ", "SOXL"],  # ~$50-100
}


def fetch_gex_raw_data(symbol: str) -> pd.DataFrame:
    """
    Fetch raw options chain data for GEX calculation.
    """
    conn = sqlite3.connect(GEX_DB_PATH)
    query = """
        SELECT trading_date, strike, option_type, gamma,
               open_interest, underlying_price
        FROM options_chains
        WHERE symbol = ?
          AND gamma IS NOT NULL
          AND underlying_price IS NOT NULL
        ORDER BY trading_date, strike
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))
    conn.close()

    if df.empty:
        return pd.DataFrame()

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    return df


def fetch_daily_summary(symbol: str) -> pd.DataFrame:
    """Fetch pre-calculated daily GEX summary."""
    conn = sqlite3.connect(GEX_DB_PATH)
    query = """
        SELECT trading_date, underlying_price, total_gex, net_call_gex,
               net_put_gex, regime, data_quality_score
        FROM options_daily_summary
        WHERE symbol = ?
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))
    conn.close()

    if df.empty:
        return pd.DataFrame()

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df = df.set_index("trading_date")
    return df


def calculate_gex_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate GEX using both formulas for comparison.

    Current formula: weighted_gamma = gamma * OI
    Academic formula: GEX = OI × Gamma × S² × 0.01 × 100
    """
    # Group by trading date
    results = []

    for date, group in df.groupby("trading_date"):
        price = group["underlying_price"].iloc[0]

        # Current formula (simple weighted gamma)
        current_gex = (group["gamma"] * group["open_interest"]).abs().sum()

        # Academic S² formula
        # GEX = OI × Gamma × S² × 0.01 × 100
        s_squared_gex = (
            (group["open_interest"] * group["gamma"] * (price**2) * 0.01 * 100).abs().sum()
        )

        # Normalized versions (per unit of OI)
        total_oi = group["open_interest"].sum()
        current_gex_norm = current_gex / total_oi if total_oi > 0 else 0
        s_squared_gex_norm = s_squared_gex / total_oi if total_oi > 0 else 0

        # Net gamma (calls - puts)
        calls = group[group["option_type"] == "call"]
        puts = group[group["option_type"] == "put"]

        call_gex_current = (calls["gamma"] * calls["open_interest"]).sum()
        put_gex_current = (puts["gamma"] * puts["open_interest"]).abs().sum()
        net_gamma_current = call_gex_current - put_gex_current

        call_gex_s2 = (calls["open_interest"] * calls["gamma"] * (price**2) * 0.01 * 100).sum()
        put_gex_s2 = (puts["open_interest"] * puts["gamma"] * (price**2) * 0.01 * 100).abs().sum()
        net_gamma_s2 = call_gex_s2 - put_gex_s2

        results.append(
            {
                "trading_date": date,
                "underlying_price": price,
                "current_gex": current_gex,
                "s_squared_gex": s_squared_gex,
                "current_gex_norm": current_gex_norm,
                "s_squared_gex_norm": s_squared_gex_norm,
                "net_gamma_current": net_gamma_current,
                "net_gamma_s2": net_gamma_s2,
                "total_oi": total_oi,
            }
        )

    result_df = pd.DataFrame(results)
    result_df = result_df.set_index("trading_date")
    return result_df


def generate_trading_signals(gex_df: pd.DataFrame, use_s_squared: bool) -> pd.Series:
    """
    Generate trading signals based on GEX regime.

    Signal logic:
    - Positive net gamma: Long bias (mean reversion expected)
    - Negative net gamma: Short/neutral (volatility expansion expected)
    """
    net_gamma_col = "net_gamma_s2" if use_s_squared else "net_gamma_current"

    # Normalize net gamma to z-scores for comparability
    net_gamma = gex_df[net_gamma_col]
    z_scores = (net_gamma - net_gamma.rolling(20).mean()) / net_gamma.rolling(20).std()

    signals = pd.Series(0.0, index=gex_df.index)

    # Strong positive gamma: long bias
    signals[z_scores > 1.0] = 1.0

    # Strong negative gamma: avoid/short
    signals[z_scores < -1.0] = -1.0

    # Moderate: neutral
    signals[(z_scores >= -1.0) & (z_scores <= 1.0)] = 0.0

    return signals


def backtest_gex_signals(
    symbol: str, gex_df: pd.DataFrame, use_s_squared: bool
) -> Dict[str, float]:
    """Run backtest using GEX-based signals."""
    # Get price data
    summary_df = fetch_daily_summary(symbol)
    if summary_df.empty:
        return {}

    # Merge GEX calculations with prices
    merged = gex_df.join(summary_df[["underlying_price"]], how="inner", rsuffix="_price")
    if len(merged) < 60:
        return {}

    signals = generate_trading_signals(merged, use_s_squared)

    # Shift signals to avoid lookahead bias (Signal t-1 -> Trade t)
    signals = signals.shift(1).fillna(0)

    # Simple backtest
    position = 0
    cash = 10000
    holdings = 0.0
    portfolio_values = []

    prices = merged["underlying_price"]

    for i in range(30, len(merged)):
        price = prices.iloc[i]
        signal = signals.iloc[i]
        date = merged.index[i]

        pv = cash + holdings * price
        portfolio_values.append({"date": date, "value": pv})

        if signal > 0.5 and position == 0:
            shares = cash * 0.95 / price
            cash -= shares * price
            holdings = shares
            position = 1

        elif signal < -0.3 and position == 1:
            cash += holdings * price
            holdings = 0
            position = 0

    # Final close
    if holdings > 0:
        cash += holdings * prices.iloc[-1]
        if portfolio_values:
            portfolio_values[-1]["value"] = cash

    if not portfolio_values:
        return {}

    pv_df = pd.DataFrame(portfolio_values).set_index("date")
    pv_series = pv_df["value"]

    strategy_returns = pv_series.pct_change().dropna()

    total_return = (pv_series.iloc[-1] - 10000) / 10000 * 100
    sharpe = (
        np.sqrt(252) * strategy_returns.mean() / strategy_returns.std()
        if strategy_returns.std() > 0
        else 0
    )

    # Max drawdown
    rolling_max = pv_series.cummax()
    drawdowns = (pv_series - rolling_max) / rolling_max
    max_dd = drawdowns.min() * 100

    return {
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "days_tested": len(pv_series),
    }


def analyze_cross_asset_comparability(all_gex_data: Dict[str, pd.DataFrame]) -> Dict:
    """
    Analyze whether S² scaling improves cross-asset comparability.

    Key question: Are GEX values more similar across different price levels
    when using S² scaling?
    """
    comparison = []

    for symbol, gex_df in all_gex_data.items():
        if gex_df.empty:
            continue

        avg_price = gex_df["underlying_price"].mean()

        # Coefficient of variation (CV) for each formula
        # Lower CV = more stable/comparable values
        cv_current = (
            gex_df["current_gex_norm"].std() / gex_df["current_gex_norm"].mean()
            if gex_df["current_gex_norm"].mean() != 0
            else np.nan
        )
        cv_s_squared = (
            gex_df["s_squared_gex_norm"].std() / gex_df["s_squared_gex_norm"].mean()
            if gex_df["s_squared_gex_norm"].mean() != 0
            else np.nan
        )

        comparison.append(
            {
                "symbol": symbol,
                "avg_price": avg_price,
                "current_gex_mean": gex_df["current_gex_norm"].mean(),
                "s_squared_gex_mean": gex_df["s_squared_gex_norm"].mean(),
                "cv_current": cv_current,
                "cv_s_squared": cv_s_squared,
            }
        )

    return pd.DataFrame(comparison)


def run_s_squared_analysis():
    """Run comprehensive S² scaling analysis."""
    print("=" * 70)
    print("S-SQUARED GEX SCALING RESEARCH (#502)")
    print("=" * 70)
    print("\nComparing GEX formulas:")
    print("  Current: weighted_gamma = gamma × OI")
    print("  Academic: GEX = OI × Gamma × S² × 0.01 × 100")

    results = {
        "run_timestamp": now_iso(),
        "issue": "#502",
        "description": "S-Squared GEX Scaling Impact Analysis",
        "formulas": {
            "current": "weighted_gamma = gamma × open_interest",
            "academic": "GEX = OI × Gamma × S² × 0.01 × 100",
        },
        "symbol_results": {},
    }

    all_gex_data = {}
    backtest_results = []

    for category, symbols in TEST_SYMBOLS.items():
        print(f"\n{'=' * 50}")
        print(f"CATEGORY: {category.upper()}")
        print("=" * 50)

        for symbol in symbols:
            print(f"\n{symbol}:")

            try:
                # Fetch raw data
                raw_df = fetch_gex_raw_data(symbol)
                if raw_df.empty:
                    print("  No raw options data")
                    continue

                print(f"  Data points: {len(raw_df):,}")

                # Calculate both GEX formulas
                gex_df = calculate_gex_formulas(raw_df)
                if gex_df.empty:
                    print("  Failed to calculate GEX")
                    continue

                all_gex_data[symbol] = gex_df
                avg_price = gex_df["underlying_price"].mean()
                print(f"  Avg price: ${avg_price:.2f}")

                # Backtest both formulas
                current_metrics = backtest_gex_signals(symbol, gex_df, use_s_squared=False)
                s_squared_metrics = backtest_gex_signals(symbol, gex_df, use_s_squared=True)

                if current_metrics and s_squared_metrics:
                    print(f"  Current formula Sharpe: {current_metrics['sharpe_ratio']:.3f}")
                    print(f"  S² formula Sharpe: {s_squared_metrics['sharpe_ratio']:.3f}")

                    diff = s_squared_metrics["sharpe_ratio"] - current_metrics["sharpe_ratio"]
                    print(f"  Difference: {diff:+.3f}")

                    backtest_results.append(
                        {
                            "symbol": symbol,
                            "category": category,
                            "avg_price": avg_price,
                            "current_sharpe": current_metrics["sharpe_ratio"],
                            "s_squared_sharpe": s_squared_metrics["sharpe_ratio"],
                            "improvement": diff,
                            "current_return": current_metrics["total_return"],
                            "s_squared_return": s_squared_metrics["total_return"],
                        }
                    )

                    results["symbol_results"][symbol] = {
                        "category": category,
                        "avg_price": float(avg_price),
                        "current_formula": {k: float(v) for k, v in current_metrics.items()},
                        "s_squared_formula": {k: float(v) for k, v in s_squared_metrics.items()},
                        "s_squared_better": bool(diff > 0),
                    }

            except Exception as e:
                print(f"  ERROR: {e}")

    # Cross-asset comparability analysis
    print("\n" + "=" * 70)
    print("CROSS-ASSET COMPARABILITY ANALYSIS")
    print("=" * 70)

    if all_gex_data:
        comparison_df = analyze_cross_asset_comparability(all_gex_data)
        if not comparison_df.empty:
            print("\nCoefficient of Variation (lower = more stable):")
            print(comparison_df.to_string(index=False))

            avg_cv_current = comparison_df["cv_current"].mean()
            avg_cv_s_squared = comparison_df["cv_s_squared"].mean()

            print(f"\nAverage CV - Current formula: {avg_cv_current:.3f}")
            print(f"Average CV - S² formula: {avg_cv_s_squared:.3f}")

            results["cross_asset_analysis"] = {
                "avg_cv_current": float(avg_cv_current),
                "avg_cv_s_squared": float(avg_cv_s_squared),
                "s_squared_more_stable": bool(avg_cv_s_squared < avg_cv_current),
            }

    # Summary
    print("\n" + "=" * 70)
    print("BACKTEST SUMMARY")
    print("=" * 70)

    if backtest_results:
        bt_df = pd.DataFrame(backtest_results)

        s_squared_wins = sum(1 for r in backtest_results if r["improvement"] > 0)
        total = len(backtest_results)

        print(f"\nSymbols tested: {total}")
        print(f"S² formula wins: {s_squared_wins}/{total} ({s_squared_wins / total * 100:.0f}%)")

        avg_improvement = np.mean([r["improvement"] for r in backtest_results])
        print(f"Average Sharpe improvement: {avg_improvement:+.3f}")

        # By price category
        print("\nBy price category:")
        for cat in bt_df["category"].unique():
            cat_data = bt_df[bt_df["category"] == cat]
            cat_improvement = cat_data["improvement"].mean()
            print(f"  {cat}: {cat_improvement:+.3f} avg improvement")

        results["summary"] = {
            "symbols_tested": total,
            "s_squared_wins": s_squared_wins,
            "s_squared_win_rate": s_squared_wins / total * 100,
            "avg_sharpe_improvement": float(avg_improvement),
        }

        # Conclusion
        results["conclusion"] = {
            "s_squared_recommended": bool(avg_improvement > 0),
            "cross_asset_comparability_improved": results.get("cross_asset_analysis", {}).get(
                "s_squared_more_stable", False
            ),
            "recommendation": (
                "Consider adopting S² scaling for cross-asset GEX analysis"
                if avg_improvement > 0
                else "Current formula performs adequately for single-asset analysis"
            ),
            "causal_mechanism": {
                "who": "Market makers hedging gamma exposure",
                "whom": "Price movement through delta hedging",
                "what": "S² scaling normalizes dollar gamma across price levels",
                "rationale": (
                    "Dollar gamma (∂Delta × $) matters for hedging flows. "
                    "S² naturally appears when converting gamma to dollar terms."
                ),
            },
        }

    # Save results
    output = Path("docs/08_research/02_gex_research/s_squared_scaling_results.yaml")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        yaml.dump(results, f, default_flow_style=False, sort_keys=False)
    print(f"\nResults saved to: {output}")

    return results


def main():
    """Run S-squared scaling analysis."""
    return run_s_squared_analysis()


if __name__ == "__main__":
    main()
