"""
Intraday GEX Validation — Practitioner Use Case (#530).

Tests whether prior-day GEX z-score predicts same-day (open→close) returns.
Previous tests (#516-519) used overnight swing (close→close+1), but the
practitioner-relevant timeframe is intraday: enter at open, exit at close.

Strategy:
- High GEX z-score (positive gamma) → expect mean reversion → fade gap
- Low GEX z-score (negative gamma) → expect trend → follow gap

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/gex_intraday_validation.py
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats as sp_stats

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtesting.research_backtester import ResearchBacktester


def _to_native(obj):
    """Recursively convert numpy types to Python natives for YAML serialization."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


SYMBOLS = ["SPY", "QQQ", "IWM"]
START = "2021-01-04"
END = "2023-12-29"
GEX_LOOKBACK = 60  # rolling z-score window
COMMISSION_BPS = 2.0
RESULTS_DIR = Path("docs/08_research/03_gex_research")


def load_gex_data(conn, symbol: str, start: str, end: str) -> pd.DataFrame:
    """Load total_gex from options_daily_summary."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT trading_date, total_gex
        FROM options_daily_summary
        WHERE symbol = %s
          AND trading_date BETWEEN %s AND %s
          AND total_gex IS NOT NULL
        ORDER BY trading_date
        """,
        (symbol, start, end),
    )
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["trading_date", "total_gex"])
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df = df.set_index("trading_date")
    return df


def analyze_symbol(bt: ResearchBacktester, symbol: str) -> dict:
    """Run intraday GEX analysis for one symbol."""
    print(f"\n  --- {symbol} ---")

    # Need data from before test period for z-score warmup
    warmup_start = "2020-06-01"
    ohlc = bt.fetch_equity_prices([symbol], warmup_start, END)
    ohlc = ohlc[ohlc["symbol"] == symbol].set_index("trading_date").sort_index()

    if len(ohlc) < 200:
        print(f"  Insufficient OHLC data ({len(ohlc)} days)")
        return {}

    # Calculate intraday return: (close - open) / open
    ohlc["intraday_return"] = (ohlc["close"] - ohlc["open"]) / ohlc["open"]
    # Overnight gap: (open - prev_close) / prev_close
    ohlc["overnight_gap"] = (ohlc["open"] - ohlc["close"].shift(1)) / ohlc["close"].shift(1)

    # Load GEX data
    gex_data = load_gex_data(bt._get_connection(), symbol, warmup_start, END)
    if len(gex_data) < 100:
        print(f"  Insufficient GEX data ({len(gex_data)} days)")
        return {}

    # Calculate GEX z-score (rolling)
    gex_data["gex_zscore"] = (
        gex_data["total_gex"] - gex_data["total_gex"].rolling(GEX_LOOKBACK).mean()
    ) / gex_data["total_gex"].rolling(GEX_LOOKBACK).std()

    # Align: prior-day GEX z-score with today's intraday return
    gex_data["prior_gex_zscore"] = gex_data["gex_zscore"].shift(1)

    # Merge
    merged = (
        ohlc[["intraday_return", "overnight_gap"]]
        .join(gex_data[["prior_gex_zscore"]], how="inner")
        .dropna()
    )

    # Filter to test period
    merged = merged[merged.index >= pd.Timestamp(START)]
    print(f"  Merged days: {len(merged)}")

    if len(merged) < 100:
        print("  Insufficient merged data")
        return {}

    # Partition into quintiles by prior-day GEX z-score
    merged["quintile"] = pd.qcut(merged["prior_gex_zscore"], 5, labels=[1, 2, 3, 4, 5])

    quintile_results = {}
    for q in [1, 2, 3, 4, 5]:
        q_data = merged[merged["quintile"] == q]
        rets = q_data["intraday_return"]
        n = len(rets)
        if n < 10:
            continue

        mean_ret = float(rets.mean())
        std_ret = float(rets.std())
        sharpe = float(np.sqrt(252) * mean_ret / std_ret) if std_ret > 0 else 0.0

        # Apply commission
        net_ret = mean_ret - (COMMISSION_BPS / 10_000)
        net_sharpe = float(np.sqrt(252) * net_ret / std_ret) if std_ret > 0 else 0.0

        quintile_results[f"Q{q}"] = {
            "n_days": n,
            "mean_gex_zscore": round(float(q_data["prior_gex_zscore"].mean()), 3),
            "mean_intraday_return_pct": round(mean_ret * 100, 4),
            "std_intraday_return_pct": round(std_ret * 100, 4),
            "gross_sharpe": round(sharpe, 3),
            "net_sharpe": round(net_sharpe, 3),
            "win_rate_pct": round(float((rets > 0).mean()) * 100, 1),
        }
        print(
            f"    Q{q} (z={q_data['prior_gex_zscore'].mean():.2f}): "
            f"mean={mean_ret*100:.4f}%, Sharpe={sharpe:.3f}, n={n}"
        )

    # Monotonicity test: Spearman correlation of quintile number vs mean return
    if len(quintile_results) >= 3:
        q_nums = []
        q_means = []
        for k, v in sorted(quintile_results.items()):
            q_nums.append(int(k[1]))
            q_means.append(v["mean_intraday_return_pct"])
        spearman_corr, spearman_p = sp_stats.spearmanr(q_nums, q_means)
        monotonicity = {
            "spearman_correlation": round(float(spearman_corr), 3),
            "p_value": round(float(spearman_p), 4),
        }
        print(f"    Monotonicity: Spearman r={spearman_corr:.3f}, p={spearman_p:.4f}")
    else:
        monotonicity = None

    # Long-short strategy: long Q5 (high GEX, mean reversion), short Q1 (low GEX, trend)
    q5_ret = quintile_results.get("Q5", {}).get("mean_intraday_return_pct", 0)
    q1_ret = quintile_results.get("Q1", {}).get("mean_intraday_return_pct", 0)
    long_short_spread = q5_ret - q1_ret

    return {
        "symbol": symbol,
        "n_days": len(merged),
        "quintiles": quintile_results,
        "monotonicity_test": monotonicity,
        "long_short_spread_pct": round(long_short_spread, 4),
    }


def main():
    print("=" * 60)
    print("  INTRADAY GEX VALIDATION — PRACTITIONER USE CASE (#530)")
    print("=" * 60)
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}")
    print(f"  Period: {START} → {END}")
    print(f"  GEX z-score lookback: {GEX_LOOKBACK} days")

    bt = ResearchBacktester(initial_capital=100_000, commission_bps=COMMISSION_BPS)
    results = []

    try:
        for symbol in SYMBOLS:
            r = analyze_symbol(bt, symbol)
            if r:
                results.append(r)
    except Exception as e:
        print(f"\n  Error: {e}")
        import traceback

        traceback.print_exc()

    bt.close()

    if not results:
        print("\nNo results.")
        return

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for r in results:
        ls = r.get("long_short_spread_pct", 0)
        mt = r.get("monotonicity_test", {})
        p = mt.get("p_value", "N/A") if mt else "N/A"
        print(f"  {r['symbol']}: Q5-Q1 spread={ls:+.4f}%, monotonicity p={p}")

    # Save YAML
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#530",
        "description": "Intraday GEX Validation — Practitioner Use Case",
        "methodology": {
            "entry": "Market Open",
            "exit": "Market Close (same day)",
            "gex_signal": f"Prior-day GEX z-score (rolling {GEX_LOOKBACK}d)",
            "quintile_partition": "Prior-day GEX z-score quintiles",
            "symbols": SYMBOLS,
            "period": f"{START} to {END}",
            "commission": f"{COMMISSION_BPS} bps round-trip",
            "data_source": "equity_prices_daily (OHLC) + options_daily_summary (total_gex)",
            "hypothesis": "High GEX z-score → mean reversion (positive intraday), "
            "Low GEX z-score → trend continuation",
        },
        "results": results,
        "comparison_with_swing": "Previous tests (#516-519) used close→close+1 (overnight swing). "
        "This test uses open→close (intraday only).",
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = RESULTS_DIR / "intraday_gex_results.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {yaml_path}")


if __name__ == "__main__":
    main()
