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
from scipy import stats as sp_stats

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
    df["ret"] = ret * 100
    df["rv_sq"] = (ret * 100) ** 2
    df["rv_park"] = (np.log(raw["high"] / raw["low"]) * 100) ** 2 / (4 * np.log(2))

    overlay = bt.get_gex_overlay()
    df["regime"] = [overlay.get_regime(symbol, d) for d in df.index]
    df["bearish"] = (df["regime"] == "bearish_gamma").astype(float)
    df["bullish"] = (df["regime"] == "bullish_gamma").astype(float)
    return df.dropna(subset=["rv_sq", "rv_park", "regime"])


def har_design(df: pd.DataFrame, target: str, with_regime: bool) -> pd.DataFrame:
    """Target ``y`` plus HAR regressors (and regime dummies), rows with full history only.

    A ``log_`` prefix (e.g. ``log_rv_park``) fits log-HAR: the log of the variance on the logs
    of its trailing averages, so regime dummies scale variance and forecasts stay positive.
    """
    log = target.startswith("log_")
    rv = df[target[4:]] if log else df[target]
    x = pd.DataFrame(
        {
            "rv_d": rv.shift(1),
            "rv_w": rv.shift(1).rolling(5).mean(),
            "rv_m": rv.shift(1).rolling(22).mean(),
        },
        index=df.index,
    )
    if log:
        rv = np.log(rv.where(rv > 0))
        x = np.log(x.where(x > 0))
    if with_regime:
        x["bearish"] = df["bearish"]
        x["bullish"] = df["bullish"]
    return pd.concat([rv.rename("y"), x], axis=1).dropna()


def fit_har(df: pd.DataFrame, target: str, with_regime: bool) -> dict:
    """HAR regression on ``target`` with optional regime dummies, Newey-West errors."""
    data = har_design(df, target, with_regime)
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


def _dm_test(loss_base: pd.Series, loss_model: pd.Series) -> dict:
    """Diebold-Mariano: mean(loss_base - loss_model) with a Newey-West t-statistic.

    Positive mean and t mean the regime model forecasts better.
    """
    d = (loss_base - loss_model).dropna()
    lags = int(np.floor(4 * (len(d) / 100) ** (2 / 9)))
    fit = sm.OLS(d.to_numpy(), np.ones(len(d))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {
        "mean_loss_diff": round(float(fit.params[0]), 5),
        "t_statistic": round(float(fit.tvalues[0]), 3),
        "p_value": round(float(fit.pvalues[0]), 4),
    }


def oos_forecast(df: pd.DataFrame, target: str) -> dict:
    """Fit HAR with and without regime before SPLIT_DATE, forecast after it, compare losses.

    Coefficients are fixed at the in-sample estimates (no re-estimation). Linear forecasts
    are floored at 1% of the in-sample mean so QLIKE (log f + y/f) stays defined. Log-HAR
    forecasts are mapped back to variance as exp(pred + s^2/2) and losses use variance levels.
    """
    log = target.startswith("log_")
    split = pd.Timestamp(SPLIT_DATE)
    forecasts = {}
    for name, with_regime in (("har", False), ("har_regime", True)):
        data = har_design(df, target, with_regime)
        train, test = data[data.index < split], data[data.index >= split]
        fit = sm.OLS(train["y"], sm.add_constant(train.drop(columns="y"))).fit()
        pred = fit.predict(sm.add_constant(test.drop(columns="y"), has_constant="add"))
        if log:
            forecasts[name] = np.exp(pred + fit.mse_resid / 2)
        else:
            forecasts[name] = pred.clip(lower=0.01 * train["y"].mean())
    y = har_design(df, target, False)["y"]
    y = y[y.index >= split]
    if log:
        y = np.exp(y)
    common = y.index.intersection(forecasts["har"].index).intersection(
        forecasts["har_regime"].index
    )
    y = y.loc[common]
    forecasts = {k: f.loc[common] for k, f in forecasts.items()}
    out = {"n_test": len(y), "train_end": SPLIT_DATE}
    for loss_name, loss in (
        ("mse", lambda f: (y - f) ** 2),
        ("qlike", lambda f: np.log(f) + y / f),
    ):
        base, model = loss(forecasts["har"]), loss(forecasts["har_regime"])
        out[loss_name] = {
            "har": round(float(base.mean()), 4),
            "har_regime": round(float(model.mean()), 4),
            "diebold_mariano": _dm_test(base, model),
        }
    return out


def _kupiec_christoffersen(hits: np.ndarray, alpha: float) -> dict:
    """Unconditional coverage (Kupiec POF), independence and conditional coverage LR tests."""
    n, x = len(hits), int(hits.sum())
    pi = x / n

    def _ll(p, k, m):  # log-likelihood of k hits in m trials at rate p
        p = min(max(p, 1e-12), 1 - 1e-12)
        return k * np.log(p) + (m - k) * np.log(1 - p)

    lr_uc = -2 * (_ll(alpha, x, n) - _ll(pi, x, n))
    h0, h1 = hits[:-1], hits[1:]
    n00 = int(((h0 == 0) & (h1 == 0)).sum())
    n01 = int(((h0 == 0) & (h1 == 1)).sum())
    n10 = int(((h0 == 1) & (h1 == 0)).sum())
    n11 = int(((h0 == 1) & (h1 == 1)).sum())
    pi01 = n01 / max(n00 + n01, 1)
    pi11 = n11 / max(n10 + n11, 1)
    pi_all = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    lr_ind = -2 * (
        _ll(pi_all, n01 + n11, n00 + n01 + n10 + n11)
        - _ll(pi01, n01, n00 + n01)
        - _ll(pi11, n11, n10 + n11)
    )
    lr_cc = lr_uc + lr_ind
    return {
        "n": n,
        "breaches": x,
        "breach_rate": round(pi, 4),
        "expected_rate": alpha,
        "kupiec_p": round(float(sp_stats.chi2.sf(lr_uc, 1)), 4),
        "christoffersen_ind_p": round(float(sp_stats.chi2.sf(lr_ind, 1)), 4),
        "conditional_coverage_p": round(float(sp_stats.chi2.sf(lr_cc, 2)), 4),
    }


def var_backtest(df: pd.DataFrame, target: str = "log_rv_park") -> dict:
    """Out-of-sample VaR from log-HAR forecasts, with and without regime dummies.

    Filtered historical simulation: VaR_t = -q_alpha(train returns / train sigma) * sigma_t,
    so the Parkinson scale (no overnight gap) and fat tails are absorbed by the quantile.
    Coefficients and quantiles come from data before SPLIT_DATE; breaches are scored after it.
    Models are compared by quantile (tick) loss with a Diebold-Mariano test (positive t =
    regime model better).
    """
    split = pd.Timestamp(SPLIT_DATE)
    ret = df["ret"]
    sigmas = {}
    for name, with_regime in (("har", False), ("har_regime", True)):
        data = har_design(df, target, with_regime)
        x = sm.add_constant(data.drop(columns="y"))
        train = data.index < split
        fit = sm.OLS(data.loc[train, "y"], x[train]).fit()
        sigmas[name] = np.sqrt(np.exp(fit.predict(x) + fit.mse_resid / 2))
    common = sigmas["har"].index.intersection(sigmas["har_regime"].index)
    common = common[ret.loc[common].notna().to_numpy()]
    train_idx, test_idx = common[common < split], common[common >= split]
    out = {"train_end": SPLIT_DATE, "n_test": len(test_idx)}
    for alpha in (0.05, 0.01):
        level = {}
        losses = {}
        for name, sig in sigmas.items():
            z = ret.loc[train_idx] / sig.loc[train_idx]
            q = float(np.quantile(z, alpha))
            var = q * sig.loc[test_idx]  # negative number: return threshold
            r = ret.loc[test_idx]
            hits = (r < var).astype(int).to_numpy()
            level[name] = _kupiec_christoffersen(hits, alpha)
            level[name]["mean_var_pct"] = round(float(-var.mean()), 4)
            losses[name] = (alpha - (r < var).astype(float)) * (r - var)
        level["quantile_loss_dm"] = _dm_test(losses["har"], losses["har_regime"])
        out[f"var_{int((1 - alpha) * 100)}"] = level
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

    for target in ("rv_sq", "rv_park", "log_rv_park"):
        res = {"raw_gap": raw_regime_gap(df, target.removeprefix("log_"))}
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
        if df.loc[df.index < SPLIT_DATE, "bullish"].sum() >= 20:
            res["out_of_sample"] = oos_forecast(df, target)
        else:
            res["out_of_sample"] = {"skipped": "fewer than 20 bullish days before the split"}
        result["targets"][target] = res
        if target == "log_rv_park" and "skipped" not in res["out_of_sample"]:
            result["var_backtest"] = var_backtest(df)
            for key in ("var_95", "var_99"):
                lv = result["var_backtest"][key]
                dm = lv["quantile_loss_dm"]
                print(
                    f"      {key}: breaches HAR {lv['har']['breach_rate']:.4f} "
                    f"(Kupiec p={lv['har']['kupiec_p']}, CC p={lv['har']['conditional_coverage_p']})"
                    f" | +regime {lv['har_regime']['breach_rate']:.4f} "
                    f"(Kupiec p={lv['har_regime']['kupiec_p']}, "
                    f"CC p={lv['har_regime']['conditional_coverage_p']})"
                    f" | tick-loss DM t={dm['t_statistic']}, p={dm['p_value']}"
                )

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
        oos = res["out_of_sample"]
        if "skipped" not in oos:
            for loss_name in ("mse", "qlike"):
                dm = oos[loss_name]["diebold_mariano"]
                print(
                    f"      OOS {loss_name}: HAR {oos[loss_name]['har']} vs +regime "
                    f"{oos[loss_name]['har_regime']} | DM t={dm['t_statistic']}, p={dm['p_value']}"
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
                "log_rv_park": "log-HAR on Parkinson variance; dummies are log variance ratios",
            },
            "standard_errors": "Newey-West HAC, maxlags = floor(4 (n/100)^(2/9))",
            "regime_lag_days": args.regime_lag,
            "period": f"{START} to {END}",
            "split_date": SPLIT_DATE,
            "out_of_sample": "fit before split_date, fixed coefficients, forecast after; "
            "MSE and QLIKE losses, Diebold-Mariano with Newey-West errors (positive = regime better)",
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
