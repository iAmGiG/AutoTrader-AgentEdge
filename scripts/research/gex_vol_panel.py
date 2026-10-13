"""
Multi-symbol GEX volatility panel (#576, #543).

``options_daily_summary.regime`` uses a fixed $1B threshold on ``total_gex``, so only SPY (and
QQQ after 2020) get meaningful bullish/bearish labels. This runner uses scale-free measures of
the previous day's GEX instead:

- ``neg_gex``: 1 if total_gex < 0 (dealers net short gamma under the usual sign convention)
- ``gex_pct``: percentile of total_gex within its trailing 252 observations (0 to 1)

For each measure it fits a log-HAR on Parkinson variance,

    log RV_t = a + b_d log RV_{t-1} + b_w log mean(RV_{t-5..t-1}) + b_m log mean(RV_{t-22..t-1})
               + leverage terms + c * measure_{t-1} [+ v * log VIX_{t-1} + h * highVIX_{t-1}
               + k * measure_{t-1} x highVIX_{t-1}] + e_t

Leverage terms (main specification): the previous day's negative return and its 5- and
22-day means, plus the trailing 22-day return. Negative GEX tends to follow selloffs, and
negative returns predict higher variance on their own, so these control for that channel.

per symbol (Newey-West errors; out-of-sample QLIKE Diebold-Mariano, fit before 2020, test
after) and pooled across symbols (symbol fixed effects, errors clustered by date and symbol).
highVIX = VIX above its 2008-2019 median. Data end at 2026-10-09 (vendor break).

Expected signs: c > 0 for neg_gex (short gamma, more variance), c < 0 for gex_pct.

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/gex_vol_panel.py
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtesting.research_backtester import LAST_VALIDATED_DATE, ResearchBacktester

START = "2008-01-02"
END = LAST_VALIDATED_DATE
SPLIT_DATE = "2020-01-01"
MIN_SIGN_DAYS = 200  # positive and negative GEX days required in each half
PCT_WINDOW = 252
MEASURES = ("neg_gex", "gex_pct")
RESULTS_DIR = Path("docs/08_research/02_gex_research/results")


def _to_native(obj):
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def _nw_lags(n: int) -> int:
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


def select_symbols(conn) -> list:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT symbol FROM options_daily_summary
        WHERE trading_date <= %s AND total_gex IS NOT NULL
        GROUP BY symbol
        HAVING count(*) FILTER (WHERE total_gex > 0 AND trading_date < %s) >= %s
           AND count(*) FILTER (WHERE total_gex < 0 AND trading_date < %s) >= %s
           AND count(*) FILTER (WHERE total_gex > 0 AND trading_date >= %s) >= %s
           AND count(*) FILTER (WHERE total_gex < 0 AND trading_date >= %s) >= %s
        ORDER BY symbol
        """,
        (END, SPLIT_DATE, MIN_SIGN_DAYS, SPLIT_DATE, MIN_SIGN_DAYS)
        + (SPLIT_DATE, MIN_SIGN_DAYS, SPLIT_DATE, MIN_SIGN_DAYS),
    )
    return [r[0] for r in cur.fetchall()]


def load_vix(conn) -> pd.Series:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT observation_date, value FROM market_data.fred_economic_data
        WHERE series_id = 'VIXCLS' AND value IS NOT NULL AND observation_date <= %s
        ORDER BY observation_date
        """,
        (END,),
    )
    rows = cur.fetchall()
    s = pd.Series([float(v) for _, v in rows], index=pd.to_datetime([d for d, _ in rows]))
    return s[~s.index.duplicated()]


def build_symbol_frame(bt, conn, symbol: str, vix: pd.Series, vix_median: float):
    """Daily frame with HAR terms, lagged GEX measures and lagged VIX for one symbol."""
    px = bt.fetch_equity_prices([symbol], START, END).set_index("trading_date").sort_index()
    px = px[(px["high"] > 0) & (px["low"] > 0)]
    rv = (np.log(px["high"] / px["low"]) * 100) ** 2 / (4 * np.log(2))
    rv = rv.where(rv > 0)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT trading_date, total_gex FROM options_daily_summary
        WHERE symbol = %s AND trading_date BETWEEN %s AND %s AND total_gex IS NOT NULL
        ORDER BY trading_date
        """,
        (symbol, START, END),
    )
    rows = cur.fetchall()
    gex = pd.Series(
        [float(g) for _, g in rows], index=pd.to_datetime([d for d, _ in rows])
    ).sort_index()
    gex = gex[~gex.index.duplicated()]
    gex_pct = gex.rolling(PCT_WINDOW, min_periods=PCT_WINDOW).rank(pct=True)

    df = pd.DataFrame(index=px.index)
    df["y"] = np.log(rv)
    df["rv_d"] = np.log(rv.shift(1))
    df["rv_w"] = np.log(rv.shift(1).rolling(5).mean())
    df["rv_m"] = np.log(rv.shift(1).rolling(22).mean())
    # Previous trading day's GEX (end-of-day options data, known before today)
    g = gex.reindex(df.index).shift(1)
    df["neg_gex"] = (g < 0).astype(float).where(g.notna())
    df["gex_pct"] = gex_pct.reindex(df.index).shift(1)
    v = vix.reindex(df.index).ffill(limit=3).shift(1)
    df["log_vix"] = np.log(v)
    df["high_vix"] = (v > vix_median).astype(float).where(v.notna())
    ret = (px["close"].pct_change() * 100).reindex(df.index)
    neg = ret.clip(upper=0)
    df["lev_d"] = neg.shift(1)
    df["lev_w"] = neg.shift(1).rolling(5).mean()
    df["lev_m"] = neg.shift(1).rolling(22).mean()
    df["ret_m"] = ret.shift(1).rolling(22).sum()
    df["symbol"] = symbol
    return df.replace([np.inf, -np.inf], np.nan)


LEVERAGE = ["lev_d", "lev_w", "lev_m", "ret_m"]


def _design(df: pd.DataFrame, measure, with_vix: bool, leverage: bool = True) -> list:
    cols = ["rv_d", "rv_w", "rv_m"] + (LEVERAGE if leverage else [])
    if measure:
        cols.append(measure)
    if with_vix:
        cols += ["log_vix", "high_vix"]
        if measure:
            cols.append(f"{measure}_x_highvix")
    return cols


def _with_interactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for m in MEASURES:
        df[f"{m}_x_highvix"] = df[m] * df["high_vix"]
    return df


def _coef(fit, name) -> dict:
    return {
        "coef": round(float(fit.params[name]), 5),
        "t_statistic": round(float(fit.tvalues[name]), 3),
        "p_value": float(fit.pvalues[name]),
    }


def per_symbol(df: pd.DataFrame, measure: str) -> dict:
    """In-sample NW fits (with and without VIX) and an out-of-sample QLIKE DM test."""
    out = {}
    for label, with_vix in (("in_sample", False), ("in_sample_vix", True)):
        cols = _design(df, measure, with_vix)
        data = df[["y"] + cols].dropna()
        fit = sm.OLS(data["y"], sm.add_constant(data[cols])).fit(
            cov_type="HAC", cov_kwds={"maxlags": _nw_lags(len(data))}
        )
        res = {"n_obs": int(fit.nobs), measure: _coef(fit, measure)}
        if with_vix:
            res[f"{measure}_x_highvix"] = _coef(fit, f"{measure}_x_highvix")
        out[label] = res

    split = pd.Timestamp(SPLIT_DATE)
    cols_m = _design(df, measure, False)
    data = df[["y"] + cols_m].dropna()
    train, test = data[data.index < split], data[data.index >= split]
    losses = {}
    for name, cols in (("har", [c for c in cols_m if c != measure]), ("har_gex", cols_m)):
        fit = sm.OLS(train["y"], sm.add_constant(train[cols])).fit()
        pred = fit.predict(sm.add_constant(test[cols], has_constant="add"))
        f = np.exp(pred + fit.mse_resid / 2)
        y = np.exp(test["y"])
        losses[name] = np.log(f) + y / f
    d = (losses["har"] - losses["har_gex"]).dropna()
    dm = sm.OLS(d.to_numpy(), np.ones(len(d))).fit(
        cov_type="HAC", cov_kwds={"maxlags": _nw_lags(len(d))}
    )
    out["out_of_sample_qlike"] = {
        "n_test": int(len(d)),
        "har": round(float(losses["har"].mean()), 5),
        "har_gex": round(float(losses["har_gex"].mean()), 5),
        "dm_t_statistic": round(float(dm.tvalues[0]), 3),
        "dm_p_value": float(dm.pvalues[0]),
    }
    return out


def pooled(panel: pd.DataFrame, measure: str, with_vix: bool, leverage: bool = True) -> dict:
    """Pooled log-HAR with symbol fixed effects (within transform), two-way clustered SEs."""
    cols = _design(panel, measure, with_vix, leverage)
    data = panel[["y", "symbol"] + cols].dropna().copy()
    demeaned = data[["y"] + cols] - data.groupby("symbol")[["y"] + cols].transform("mean")
    groups = np.column_stack(
        [
            pd.factorize(data.index)[0],
            pd.factorize(data["symbol"])[0],
        ]
    )
    fit = sm.OLS(demeaned["y"], demeaned[cols]).fit(cov_type="cluster", cov_kwds={"groups": groups})
    res = {
        "n_obs": int(fit.nobs),
        "n_symbols": int(data["symbol"].nunique()),
        measure: _coef(fit, measure),
    }
    if with_vix:
        res["log_vix"] = _coef(fit, "log_vix")
        res[f"{measure}_x_highvix"] = _coef(fit, f"{measure}_x_highvix")
    return res


def main():
    print("=" * 60)
    print("  MULTI-SYMBOL GEX VOLATILITY PANEL (#576)")
    print("=" * 60)
    bt = ResearchBacktester()
    conn = bt._get_connection()
    try:
        symbols = select_symbols(conn)
        vix = load_vix(conn)
        vix_median = float(vix[vix.index < SPLIT_DATE].median())
        print(f"  Symbols: {len(symbols)}  VIX median 2008-2019: {vix_median:.2f}")
        frames = []
        for sym in symbols:
            frames.append(_with_interactions(build_symbol_frame(bt, conn, sym, vix, vix_median)))
    finally:
        bt.close()

    per = {}
    for df in frames:
        sym = df["symbol"].iloc[0]
        per[sym] = {m: per_symbol(df, m) for m in MEASURES}

    panel = pd.concat(frames)
    pooled_res = {
        m: {
            "har_only": pooled(panel, m, False, leverage=False),
            "no_vix": pooled(panel, m, False),
            "with_vix": pooled(panel, m, True),
        }
        for m in MEASURES
    }

    summary = {}
    for m in MEASURES:
        expect_pos = m == "neg_gex"
        coefs = np.array([per[s][m]["in_sample"][m]["coef"] for s in per])
        pvals = np.array([per[s][m]["in_sample"][m]["p_value"] for s in per])
        dm_t = np.array([per[s][m]["out_of_sample_qlike"]["dm_t_statistic"] for s in per])
        right = coefs > 0 if expect_pos else coefs < 0
        summary[m] = {
            "expected_sign": "+" if expect_pos else "-",
            "share_expected_sign": round(float(right.mean()), 3),
            "n_expected_sign_p05": int((right & (pvals < 0.05)).sum()),
            "n_wrong_sign_p05": int((~right & (pvals < 0.05)).sum()),
            "share_oos_qlike_improved": round(float((dm_t > 0).mean()), 3),
            "n_oos_dm_t_above_2": int((dm_t > 1.96).sum()),
            "n_oos_dm_t_below_minus_2": int((dm_t < -1.96).sum()),
            "median_coef": round(float(np.median(coefs)), 5),
        }

    print("\n  Per-symbol summary (log-HAR, Newey-West):")
    for m, s in summary.items():
        print(f"    {m}: {s}")
    print("\n  Pooled (symbol FE, errors clustered by date and symbol):")
    for m, r in pooled_res.items():
        h, a, b = r["har_only"][m], r["no_vix"][m], r["with_vix"][m]
        ix = r["with_vix"][f"{m}_x_highvix"]
        print(
            f"    {m}: HAR c={h['coef']:+.4f} (t={h['t_statistic']}) | +leverage "
            f"c={a['coef']:+.4f} (t={a['t_statistic']}) | +VIX c={b['coef']:+.4f} "
            f"(t={b['t_statistic']}), x highVIX {ix['coef']:+.4f} (t={ix['t_statistic']})"
        )

    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#576",
        "description": "Scale-free GEX measures vs next-day variance across symbols",
        "methodology": {
            "model": "log-HAR on Parkinson variance plus leverage terms and lagged GEX measure",
            "leverage_controls": "lagged negative return (1, 5, 22-day means), trailing 22-day return",
            "pooled_specs": "har_only (no leverage), no_vix (leverage), with_vix (leverage + VIX)",
            "measures": {
                "neg_gex": "1 if previous day's total_gex < 0",
                "gex_pct": f"previous day's percentile of total_gex in trailing {PCT_WINDOW} obs",
            },
            "vix": "lagged log VIXCLS and highVIX (above 2008-2019 median) with interaction",
            "per_symbol_errors": "Newey-West HAC",
            "pooled": "symbol fixed effects, errors clustered by date and symbol",
            "out_of_sample": "fit before split_date, QLIKE, Diebold-Mariano (positive = GEX better)",
            "symbol_rule": f">= {MIN_SIGN_DAYS} positive and negative GEX days in each half",
            "period": f"{START} to {END}",
            "split_date": SPLIT_DATE,
            "regime_lag_days": 1,
            "vix_median_2008_2019": round(vix_median, 3),
        },
        "symbols": symbols,
        "summary": summary,
        "pooled": pooled_res,
        "per_symbol": per,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "gex_vol_panel_lag1.yaml"
    with open(path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {path}")


if __name__ == "__main__":
    main()
