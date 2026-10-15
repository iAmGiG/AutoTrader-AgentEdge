"""
Intraday momentum and reversal by dealer gamma (#530, #576).

Design follows Baltussen, Da, Lammers & Martens (2021) and Barbon & Buraschi ("Gamma
Fragility"): does the return from the previous close to 15:30 ET predict the 15:30 to 16:00
return, and does the sign of dealer gamma flip that relationship?

    r_late = a + b * r_early + c * r_early * negGEX + d * negGEX + e

r_early = log(P_15:30 / P_close,t-1), r_late = log(P_16:00 / P_15:30), in basis points.
Hypothesis (Barbon-Buraschi): c > 0. Momentum when dealers are short gamma (slope b + c > 0),
reversal or weaker momentum when long gamma (slope b).

negGEX is measured two ways:
- prior_close (primary): sign of total_gex at the previous day's 16:00 snapshot (ex-ante)
- snap_1530 (secondary): sign of total_gex at today's 15:30 snapshot (known at 15:30)

Endpoints (previous close, today's close) are official closes from ``equity_prices_daily``;
the 15:30 price is ``intraday_gex_summary.underlying_price``. The 16:00 snapshot price differs
from the official close by more than 10 bps on about a quarter of symbol-days, and endpoint
errors bias this design toward reversal, so the snapshot-only version is kept as a robustness
check (``price_source: snapshots``). Data: 2026-01-13 to
2026-10-09 (vendor break on 2026-10-12). Caveats: stored equity GEX omits 0DTE
(gex-database-infrastructure Issue #74); OI is the prior night's, so intraday GEX moves with
price and gamma, not positions.

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/intraday_gamma_momentum.py
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

END = LAST_VALIDATED_DATE
MEASURES = ("prior_close", "snap_1530")
# Leveraged and inverse products, excluded in the robustness sample
LEVERAGED = {
    "TQQQ",
    "SQQQ",
    "SOXL",
    "SOXS",
    "SPXL",
    "SPXS",
    "SPXU",
    "UPRO",
    "TNA",
    "TZA",
    "FAS",
    "FAZ",
    "TECL",
    "TECS",
    "UVXY",
    "SVXY",
    "LABU",
    "LABD",
    "NUGT",
    "DUST",
    "TMF",
    "TMV",
    "BITX",
}
MAX_ABS_BPS = 2000  # drop symbol-days with |return| > 20% (bad prints)
RESULTS_DIR = Path("docs/08_research/02_gex_research/results")


def _to_native(obj):
    if isinstance(obj, dict):
        return {str(k): _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def load_snapshots(conn) -> pd.DataFrame:
    """15:30 and 16:00 ET snapshots per symbol-day (first row per slot)."""
    cur = conn.cursor()
    cur.execute(
        """
        WITH s AS (
            SELECT symbol,
                   (snapshot_timestamp AT TIME ZONE 'America/New_York')::date AS d,
                   CASE
                     WHEN (snapshot_timestamp AT TIME ZONE 'America/New_York')::time
                          BETWEEN '15:29:00' AND '15:32:00' THEN 'p1530'
                     WHEN snapshot_type = 'market_close' THEN 'p1600'
                   END AS slot,
                   snapshot_timestamp, underlying_price, total_gex
            FROM intraday_gex_summary
            WHERE snapshot_type NOT IN ('test', 'test_direct')
              AND (snapshot_timestamp AT TIME ZONE 'America/New_York')::date <= %s
              AND underlying_price > 0
        )
        SELECT DISTINCT ON (symbol, d, slot) symbol, d, slot, underlying_price, total_gex
        FROM s WHERE slot IS NOT NULL
        ORDER BY symbol, d, slot, snapshot_timestamp
        """,
        (END,),
    )
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["symbol", "date", "slot", "price", "gex"])
    df["price"] = df["price"].astype(float)
    df["gex"] = df["gex"].astype(float)
    wide = df.pivot_table(index=["symbol", "date"], columns="slot", values=["price", "gex"])
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    return wide.reset_index()


def add_official_closes(snaps: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Attach official close and previous official close to the snapshot rows."""
    daily = daily.copy()
    daily["date"] = daily["trading_date"].dt.date
    daily = daily.sort_values(["symbol", "date"])
    daily["prev_close_official"] = daily.groupby("symbol")["close"].shift(1)
    cols = ["symbol", "date", "close", "prev_close_official"]
    return snaps.merge(daily[cols], on=["symbol", "date"], how="left")


def build_panel(snaps: pd.DataFrame, official: bool = True) -> pd.DataFrame:
    snaps = snaps.sort_values(["symbol", "date"]).copy()
    prev = snaps.groupby("symbol")[["price_p1600", "gex_p1600", "date"]].shift(1)
    snaps["prev_close"] = prev["price_p1600"]
    snaps["prev_gex"] = prev["gex_p1600"]
    snaps["prev_date"] = prev["date"]
    gap_days = (pd.to_datetime(snaps["date"]) - pd.to_datetime(snaps["prev_date"])).dt.days
    snaps = snaps[gap_days.between(1, 5)]  # previous trading day, not a data gap
    if official:
        start, end = snaps["prev_close_official"], snaps["close"]
    else:
        start, end = snaps["prev_close"], snaps["price_p1600"]
    snaps["r_early"] = np.log(snaps["price_p1530"] / start) * 1e4
    snaps["r_late"] = np.log(end / snaps["price_p1530"]) * 1e4
    snaps["neg_prior_close"] = (snaps["prev_gex"] < 0).astype(float)
    snaps["neg_snap_1530"] = (snaps["gex_p1530"] < 0).astype(float)
    panel = snaps.dropna(subset=["r_early", "r_late", "prev_gex", "gex_p1530"])
    ok = (panel["r_early"].abs() < MAX_ABS_BPS) & (panel["r_late"].abs() < MAX_ABS_BPS)
    return panel[ok].reset_index(drop=True)


def _coef(fit, name) -> dict:
    return {
        "coef": round(float(fit.params[name]), 5),
        "t_statistic": round(float(fit.tvalues[name]), 3),
        "p_value": float(fit.pvalues[name]),
    }


def fit_interaction(panel: pd.DataFrame, measure: str, single_symbol: bool = False) -> dict:
    neg = panel[f"neg_{measure}"]
    x = pd.DataFrame(
        {
            "r_early": panel["r_early"],
            "r_early_x_neg": panel["r_early"] * neg,
            "neg": neg,
        }
    )
    x = sm.add_constant(x)
    if single_symbol:
        lags = int(np.floor(4 * (len(panel) / 100) ** (2 / 9)))
        fit = sm.OLS(panel["r_late"], x).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    else:
        groups = np.column_stack([pd.factorize(panel["date"])[0], pd.factorize(panel["symbol"])[0]])
        fit = sm.OLS(panel["r_late"], x).fit(cov_type="cluster", cov_kwds={"groups": groups})
    slope_neg = fit.t_test("r_early + r_early_x_neg = 0")
    return {
        "n_obs": int(fit.nobs),
        "n_days": int(panel["date"].nunique()),
        "n_symbols": int(panel["symbol"].nunique()),
        "share_neg_gex": round(float(neg.mean()), 3),
        "slope_long_gamma": _coef(fit, "r_early"),
        "interaction": _coef(fit, "r_early_x_neg"),
        "slope_short_gamma": {
            "coef": round(float(np.squeeze(slope_neg.effect)), 5),
            "t_statistic": round(float(np.squeeze(slope_neg.tvalue)), 3),
            "p_value": float(np.squeeze(slope_neg.pvalue)),
        },
    }


def timing_strategy(panel: pd.DataFrame, measure: str) -> dict:
    """Trade 15:30 to 16:00: follow r_early when GEX < 0, fade it when GEX >= 0 (gross)."""
    neg = panel[f"neg_{measure}"] == 1
    direction = np.where(neg, np.sign(panel["r_early"]), -np.sign(panel["r_early"]))
    pnl = pd.Series(direction * panel["r_late"].to_numpy(), index=panel.index)
    daily = pnl.groupby(panel["date"]).mean()
    lags = int(np.floor(4 * (len(daily) / 100) ** (2 / 9)))
    fit = sm.OLS(daily.to_numpy(), np.ones(len(daily))).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags}
    )
    return {
        "n_days": int(len(daily)),
        "mean_daily_bps_gross": round(float(daily.mean()), 3),
        "t_statistic": round(float(fit.tvalues[0]), 3),
        "p_value": float(fit.pvalues[0]),
        "annualized_sharpe_gross": round(float(np.sqrt(252) * daily.mean() / daily.std()), 3),
        "note": "equal-weight across symbols each day; gross of costs (two trades per day)",
    }


def main():
    print("=" * 60)
    print("  INTRADAY MOMENTUM / REVERSAL BY DEALER GAMMA (#530, #576)")
    print("=" * 60)
    bt = ResearchBacktester()
    try:
        snaps = load_snapshots(bt._get_connection())
        first = str(pd.to_datetime(snaps["date"]).min().date() - datetime.timedelta(days=10))
        # Raw closes, to match the raw snapshot prices (a split day is dropped by the
        # MAX_ABS_BPS filter)
        daily = bt.fetch_equity_prices(
            sorted(snaps["symbol"].unique()), first, END, adjust_splits=False
        )
    finally:
        bt.close()
    snaps = add_official_closes(snaps, daily)
    panel = build_panel(snaps, official=True)
    panel_snap = build_panel(snaps, official=False)
    print(
        f"  Symbol-days: {len(panel)}  days: {panel['date'].nunique()}  "
        f"symbols: {panel['symbol'].nunique()}  {panel['date'].min()} to {panel['date'].max()}"
    )

    samples = {
        "all": panel,
        "ex_leveraged": panel[~panel["symbol"].isin(LEVERAGED)],
    }
    results = {}
    for m in MEASURES:
        res = {name: fit_interaction(df, m) for name, df in samples.items()}
        for sym in ("SPY", "QQQ"):
            sub = panel[panel["symbol"] == sym].sort_values("date")
            if len(sub) > 50 and 0 < sub[f"neg_{m}"].mean() < 1:
                res[sym] = fit_interaction(sub, m, single_symbol=True)
        res["timing_strategy_all"] = timing_strategy(panel, m)
        res["robustness_snapshot_prices_all"] = fit_interaction(panel_snap, m)
        results[m] = res

    for m, res in results.items():
        print(f"\n  GEX measure: {m}")
        for name in ("all", "ex_leveraged", "SPY", "QQQ"):
            r = res.get(name)
            if not r:
                continue
            lg, ix, sg = r["slope_long_gamma"], r["interaction"], r["slope_short_gamma"]
            print(
                f"    {name:13} n={r['n_obs']:>6} negGEX={r['share_neg_gex']:.2f} | "
                f"long-gamma slope {lg['coef']:+.4f} (t={lg['t_statistic']}) | "
                f"short-gamma slope {sg['coef']:+.4f} (t={sg['t_statistic']}) | "
                f"interaction {ix['coef']:+.4f} (t={ix['t_statistic']}, p={ix['p_value']:.4f})"
            )
        t = res["timing_strategy_all"]
        print(
            f"    timing strategy: {t['mean_daily_bps_gross']:+.3f} bps/day gross "
            f"(t={t['t_statistic']}, Sharpe {t['annualized_sharpe_gross']})"
        )

    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#530, #576",
        "description": "Previous close to 15:30 return predicting 15:30 to 16:00, by GEX sign",
        "methodology": {
            "model": "r_late = a + b r_early + c r_early*negGEX + d negGEX (bps)",
            "hypothesis": "c > 0: momentum when dealers short gamma (Barbon-Buraschi)",
            "measures": {
                "prior_close": "sign of total_gex at previous day's 16:00 snapshot (primary)",
                "snap_1530": "sign of total_gex at today's 15:30 snapshot (secondary)",
            },
            "prices": "official closes (equity_prices_daily) as endpoints; 15:30 snapshot price",
            "price_source_robustness": "robustness_snapshot_prices_all uses 16:00 snapshots",
            "errors": "pooled: clustered by date and symbol; single symbol: Newey-West",
            "filters": f"previous snapshot day within 5 calendar days; |return| < {MAX_ABS_BPS} bps",
            "period": f"{panel['date'].min()} to {panel['date'].max()}",
            "regime_lag_days": 1,
            "caveats": "equity GEX omits 0DTE; OI is prior night's; ~180 trading days",
        },
        "results": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "intraday_gamma_momentum.yaml"
    with open(path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {path}")


if __name__ == "__main__":
    main()
