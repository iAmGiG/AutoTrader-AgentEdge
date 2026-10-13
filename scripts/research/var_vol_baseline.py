"""
Does the GEX regime predict next-day risk beyond trailing volatility? (#576, #543)

The lagged VaR study found bearish_gamma days carry about 2x the VaR of bullish_gamma days.
Volatility clusters, and dealer gamma regimes are partly a function of recent moves, so that
gap may only restate trailing volatility. This runner fits a HAR-style regression:

    RV_t = b0 + b_d RV_{t-1} + b_w mean(RV_{t-5..t-1}) + b_m mean(RV_{t-22..t-1})
           + g_bear * bearish_{t-lag} + g_bull * bullish_{t-lag} + e_t

with neutral as the omitted regime and Newey-West (HAC) standard errors. RV proxies:
squared close-to-close return and the Parkinson high-low range estimator. The regime is
lagged (default 1 observation) because it is computed from end-of-day options data.

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/var_vol_baseline.py
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/var_vol_baseline.py --regime-lag 0
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.research_cli import parse_window_args

SYMBOLS = ["SPY", "QQQ", "IWM"]
START = "2008-01-02"
END = "2026-10-09"
SPLIT_DATE = "2020-01-01"
RESULTS_DIR = Path("docs/08_research/03_gex_research")


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
    return obj


def build_frame(bt: ResearchBacktester, symbol: str) -> pd.DataFrame:
    """Daily RV proxies, HAR terms and lagged regime dummies for one symbol."""
    raw = bt.fetch_equity_prices([symbol], START, END).set_index("trading_date").sort_index()
    df = pd.DataFrame(index=raw.index)
    ret = raw["close"].pct_change()
    # Annualised-free daily variance proxies, scaled to percent^2 for readable coefficients
    df["rv_sq"] = (ret * 100) ** 2
    df["rv_park"] = (np.log(raw["high"] / raw["low"]) * 100) ** 2 / (4 * np.log(2))

    overlay = bt.get_gex_overlay()
    df["regime"] = [overlay.get_regime(symbol, d) for d in df.index]
    df["bearish"] = (df["regime"] == "bearish_gamma").astype(float)
    df["bullish"] = (df["regime"] == "bullish_gamma").astype(float)
    return df.dropna(subset=["rv_sq", "rv_park", "regime"])


def fit_har(df: pd.DataFrame, target: str, with_regime: bool) -> dict:
    """HAR regression on ``target`` with optional regime dummies, Newey-West errors."""
    rv = df[target]
    x = pd.DataFrame(
        {
            "rv_d": rv.shift(1),
            "rv_w": rv.shift(1).rolling(5).mean(),
            "rv_m": rv.shift(1).rolling(22).mean(),
        },
        index=df.index,
    )
    if with_regime:
        x["bearish"] = df["bearish"]
        x["bullish"] = df["bullish"]
    data = pd.concat([rv.rename("y"), x], axis=1).dropna()
    model = sm.OLS(data["y"], sm.add_constant(data.drop(columns="y")))
    lags = int(np.floor(4 * (len(data) / 100) ** (2 / 9)))
    fit = model.fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    out = {"n_obs": int(fit.nobs), "r_squared": round(float(fit.rsquared), 4)}
    if with_regime:
        for name in ("bearish", "bullish"):
            out[name] = {
                "coef": round(float(fit.params[name]), 4),
                "t_statistic": round(float(fit.tvalues[name]), 3),
                "p_value": round(float(fit.pvalues[name]), 4),
            }
        diff = fit.t_test("bearish - bullish = 0")
        out["bearish_minus_bullish"] = {
            "coef": round(float(np.squeeze(diff.effect)), 4),
            "t_statistic": round(float(np.squeeze(diff.tvalue)), 3),
            "p_value": round(float(np.squeeze(diff.pvalue)), 4),
        }
    return out


def raw_regime_gap(df: pd.DataFrame, target: str) -> dict:
    """Mean RV by regime with no volatility controls, for comparison."""
    means = df.groupby("regime")[target].mean()
    bull, bear = means.get("bullish_gamma"), means.get("bearish_gamma")
    return {
        "mean_bullish": round(float(bull), 4) if bull is not None else None,
        "mean_bearish": round(float(bear), 4) if bear is not None else None,
        "ratio_bearish_to_bullish": round(float(bear / bull), 3) if bull and bear else None,
    }


def analyze_symbol(bt: ResearchBacktester, symbol: str) -> dict:
    print(f"\n  --- {symbol} ---")
    df = build_frame(bt, symbol)
    counts = df["regime"].value_counts().to_dict()
    print(f"  Days: {len(df)}  regimes: {counts}")
    result = {"symbol": symbol, "n_days": len(df), "regime_counts": counts, "targets": {}}

    for target in ("rv_sq", "rv_park"):
        res = {"raw_gap": raw_regime_gap(df, target)}
        for label, part in (
            ("full", df),
            ("pre_2020", df[df.index < SPLIT_DATE]),
            ("from_2020", df[df.index >= SPLIT_DATE]),
        ):
            if part["bullish"].sum() < 20 or part["bearish"].sum() < 20:
                res[label] = {"skipped": "fewer than 20 bullish or bearish days"}
                continue
            base = fit_har(part, target, with_regime=False)
            full = fit_har(part, target, with_regime=True)
            full["r_squared_gain"] = round(full["r_squared"] - base["r_squared"], 4)
            res[label] = full
        result["targets"][target] = res

        gap, f = res["raw_gap"], res["full"]
        if "skipped" in f:
            print(f"    {target}: raw bear/bull {gap['ratio_bearish_to_bullish']}x; HAR skipped")
            continue
        d = f["bearish_minus_bullish"]
        print(
            f"    {target}: raw bear/bull {gap['ratio_bearish_to_bullish']}x | HAR bear-bull "
            f"{d['coef']:+.4f} (t={d['t_statistic']}, p={d['p_value']}), "
            f"R2 gain {f['r_squared_gain']:+.4f}"
        )
    return result


def main():
    global SYMBOLS, START, END
    args = parse_window_args(
        "GEX regime vs trailing-volatility baseline (#576)",
        {"symbols": SYMBOLS, "start": START, "end": END},
        "var_vol_baseline_results.yaml",
    )
    SYMBOLS, START, END = args.symbols, args.start, args.end

    print("=" * 60)
    print("  GEX REGIME VS TRAILING-VOLATILITY BASELINE (#576)")
    print("=" * 60)
    print(f"  Period: {START} → {END}   regime lag: {args.regime_lag}")

    bt = ResearchBacktester()
    bt.regime_lag = args.regime_lag
    results = []
    try:
        for symbol in SYMBOLS:
            results.append(analyze_symbol(bt, symbol))
    finally:
        bt.close()

    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#576",
        "description": "Does the GEX regime predict next-day variance beyond a HAR baseline?",
        "methodology": {
            "model": "HAR: RV_t on RV_{t-1}, 5-day and 22-day trailing means, plus regime dummies",
            "omitted_regime": "neutral",
            "rv_proxies": {
                "rv_sq": "squared close-to-close return (percent^2)",
                "rv_park": "Parkinson high-low variance (percent^2)",
            },
            "standard_errors": "Newey-West HAC, maxlags = floor(4 (n/100)^(2/9))",
            "regime_lag_days": args.regime_lag,
            "period": f"{START} to {END}",
            "split_date": SPLIT_DATE,
            "symbols": SYMBOLS,
        },
        "results": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = RESULTS_DIR / args.output
    with open(yaml_path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {yaml_path}")


if __name__ == "__main__":
    main()
