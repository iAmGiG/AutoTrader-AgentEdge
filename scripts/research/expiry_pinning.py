"""
Expiry-day pinning by dealer gamma (#576).

Ni, Pearson & Poteshman (2005, JFE) find that closing prices of optionable stocks cluster at
strike prices on option expiration dates, consistent with hedge rebalancing by market makers
who are net long options. This runner tests the same idea on the gex_options chains:

- Expiry day E: last trading day on or before the third Friday of each month (pre-2015
  chains store the Saturday after it).
- Placebo day: five trading days before E, same expiry.
- For each day X, the previous trading day's chain for the monthly expiry gives the listed
  strikes, open interest and gamma (ex-ante).
- Outcomes: distance from the official close at X to the nearest listed strike, in units of
  the local strike spacing (uniform on [0, 0.5], mean 0.25, under no pinning); and log
  distance to the max open-interest strike within 5% of spot.
- Conditioning: sign of net expiring dealer gamma within 5% of spot under the usual
  convention (dealers long calls, short puts): sum of OI x gamma x (+1 call, -1 put).

    distance = a + b * expiry + c * long_gamma + k * expiry * long_gamma + e

NPP predict b < 0. Gamma-hedging pinning predicts k < 0 (stronger pinning when dealers are
long expiring gamma). Errors clustered by month and symbol. Data end at 2026-10-09.

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/expiry_pinning.py
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
MIN_DAYS = 3000  # options_daily_summary history required
NEAR = 0.05  # strikes within 5% of spot for spacing, max-OI strike and gamma sign
PLACEBO_OFFSET = 5  # trading days before expiry
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


def third_friday(year: int, month: int) -> datetime.date:
    d = datetime.date(year, month, 15)
    return d + datetime.timedelta(days=(4 - d.weekday()) % 7)


def select_symbols(conn) -> list:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT symbol FROM options_daily_summary
        WHERE trading_date <= %s GROUP BY symbol HAVING count(*) > %s ORDER BY symbol
        """,
        (END, MIN_DAYS),
    )
    return [r[0] for r in cur.fetchall()]


def event_days(trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    """Monthly expiry day, placebo day and their previous trading days for one symbol."""
    days = pd.DatetimeIndex(sorted(trading_days))
    pos = {d: i for i, d in enumerate(days)}
    rows = []
    for y in range(days[0].year, days[-1].year + 1):
        for m in range(1, 13):
            tf = pd.Timestamp(third_friday(y, m))
            on_or_before = days[days <= tf]
            if len(on_or_before) == 0 or (tf - on_or_before[-1]).days > 3:
                continue
            e = on_or_before[-1]
            i = pos[e]
            if i < PLACEBO_OFFSET + 1:
                continue
            p = days[i - PLACEBO_OFFSET]
            rows.append(
                {
                    "month": f"{y}-{m:02d}",
                    "third_friday": tf.date(),
                    "expiry_keys": (tf.date(), (tf + pd.Timedelta(days=1)).date()),
                    "events": [
                        ("expiry", e, days[i - 1]),
                        ("placebo", p, days[i - PLACEBO_OFFSET - 1]),
                    ],
                }
            )
    return rows


def load_chains(conn, symbol: str, chain_dates: list, expiries: list) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT trading_date, expiration, strike, option_type, open_interest, gamma
        FROM gex.options_chains_partitioned
        WHERE symbol = %s AND trading_date = ANY(%s) AND expiration = ANY(%s)
          AND open_interest > 0
        """,
        (symbol, chain_dates, expiries),
    )
    df = pd.DataFrame(
        cur.fetchall(),
        columns=["trading_date", "expiration", "strike", "option_type", "oi", "gamma"],
    )
    for col in ("strike", "oi", "gamma"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def measure(chain: pd.DataFrame, spot_prev: float, close: float):
    """Nearest-strike distance (spacing units), max-OI distance (bps), dealer gamma sign."""
    near = chain[(chain["strike"] - spot_prev).abs() <= NEAR * spot_prev]
    strikes = np.sort(near["strike"].unique())
    if len(strikes) < 3:
        return None
    spacing = float(np.median(np.diff(strikes)))
    if spacing <= 0:
        return None
    all_strikes = np.sort(chain["strike"].unique())
    nearest = all_strikes[np.argmin(np.abs(all_strikes - close))]
    d_norm = min(abs(close - nearest) / spacing, 0.5)
    oi = near.groupby("strike")["oi"].sum()
    k_star = float(oi.idxmax())
    d_maxoi = abs(close - k_star) / close * 1e4
    sign = np.where(near["option_type"].str.lower().str.startswith("c"), 1.0, -1.0)
    net_gamma = float(np.nansum(near["oi"] * near["gamma"] * sign))
    return {
        "d_norm": d_norm,
        "log_d_maxoi": float(np.log1p(d_maxoi)),
        "long_gamma": float(net_gamma > 0),
        "spacing_bps": spacing / spot_prev * 1e4,
    }


def fit(panel: pd.DataFrame, y: str) -> dict:
    x = pd.DataFrame(
        {
            "expiry": panel["expiry"],
            "long_gamma": panel["long_gamma"],
            "expiry_x_long_gamma": panel["expiry"] * panel["long_gamma"],
        }
    )
    groups = np.column_stack([pd.factorize(panel["month"])[0], pd.factorize(panel["symbol"])[0]])
    res = sm.OLS(panel[y], sm.add_constant(x)).fit(cov_type="cluster", cov_kwds={"groups": groups})
    out = {"n_obs": int(res.nobs)}
    for name in ("expiry", "long_gamma", "expiry_x_long_gamma"):
        out[name] = {
            "coef": round(float(res.params[name]), 5),
            "t_statistic": round(float(res.tvalues[name]), 3),
            "p_value": float(res.pvalues[name]),
        }
    pin_long = res.t_test("expiry + expiry_x_long_gamma = 0")
    out["expiry_effect_when_long_gamma"] = {
        "coef": round(float(np.squeeze(pin_long.effect)), 5),
        "t_statistic": round(float(np.squeeze(pin_long.tvalue)), 3),
        "p_value": float(np.squeeze(pin_long.pvalue)),
    }
    return out


def collect_symbol(bt, conn, sym: str) -> list:
    """Measured expiry and placebo rows for one symbol."""
    px = bt.fetch_equity_prices([sym], START, END).set_index("trading_date")["close"]
    px = px[~px.index.duplicated()].astype(float)
    if len(px) < 500:
        return []
    events = event_days(px.index)
    chain_dates = sorted({ev[2].date() for e in events for ev in e["events"]})
    expiries = sorted({k for e in events for k in e["expiry_keys"]})
    chains = load_chains(conn, sym, chain_dates, expiries)
    if chains.empty:
        return []
    by_key = dict(list(chains.groupby(["trading_date", "expiration"])))
    rows = []
    for e in events:
        for kind, day, prev in e["events"]:
            chain = next(
                (by_key[(prev.date(), k)] for k in e["expiry_keys"] if (prev.date(), k) in by_key),
                None,
            )
            if chain is None or prev not in px.index:
                continue
            m = measure(chain, float(px[prev]), float(px[day]))
            if m:
                rows.append(
                    {"symbol": sym, "month": e["month"], "expiry": float(kind == "expiry"), **m}
                )
    return rows


def main():
    print("=" * 60)
    print("  EXPIRY-DAY PINNING BY DEALER GAMMA (#576)")
    print("=" * 60)
    bt = ResearchBacktester()
    conn = bt._get_connection()
    rows = []
    try:
        symbols = select_symbols(conn)
        print(f"  Symbols: {len(symbols)}")
        for sym in symbols:
            rows.extend(collect_symbol(bt, conn, sym))
    finally:
        bt.close()

    panel = pd.DataFrame(rows)
    # Keep months where both the expiry and placebo day were measured
    both = panel.groupby(["symbol", "month"])["expiry"].transform("nunique") == 2
    panel = panel[both].reset_index(drop=True)
    exp, plc = panel[panel["expiry"] == 1], panel[panel["expiry"] == 0]
    print(
        f"  Symbol-months: {len(exp)}  symbols: {panel['symbol'].nunique()}  "
        f"months: {panel['month'].nunique()}"
    )
    print(
        f"  Mean nearest-strike distance (spacing units, 0.25 = no pinning): "
        f"expiry {exp['d_norm'].mean():.4f}, placebo {plc['d_norm'].mean():.4f}"
    )
    print(
        f"  Share within 0.1 spacing: expiry {(exp['d_norm'] < 0.1).mean():.3f}, "
        f"placebo {(plc['d_norm'] < 0.1).mean():.3f}"
    )

    results = {"nearest_strike": fit(panel, "d_norm"), "max_oi_strike": fit(panel, "log_d_maxoi")}
    for name, r in results.items():
        print(
            f"  {name:15} expiry {r['expiry']['coef']:+.4f} (t={r['expiry']['t_statistic']}) | "
            f"expiry x long gamma {r['expiry_x_long_gamma']['coef']:+.4f} "
            f"(t={r['expiry_x_long_gamma']['t_statistic']}, p={r['expiry_x_long_gamma']['p_value']:.4f})"
            f" | expiry effect when long gamma {r['expiry_effect_when_long_gamma']['coef']:+.4f} "
            f"(t={r['expiry_effect_when_long_gamma']['t_statistic']})"
        )

    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#576",
        "description": "Expiry-day clustering at strikes, conditioned on expiring dealer gamma",
        "methodology": {
            "model": "distance = a + b expiry + c long_gamma + k expiry*long_gamma",
            "hypotheses": "b < 0 (NPP 2005 clustering); k < 0 (stronger when dealers long gamma)",
            "expiry_day": "last trading day on or before the third Friday (monthly options)",
            "placebo_day": f"{PLACEBO_OFFSET} trading days before expiry, same expiry contracts",
            "chain": "previous trading day's chain for the monthly expiry (ex-ante)",
            "outcomes": {
                "d_norm": "distance to nearest listed strike / local strike spacing, capped 0.5",
                "log_d_maxoi": "log(1 + bps distance to max-OI strike within 5% of spot)",
            },
            "gamma_sign": "sum OI x gamma x (+1 call, -1 put) within 5% of spot",
            "errors": "clustered by month and symbol",
            "period": f"{START} to {END}",
            "regime_lag_days": 1,
        },
        "summary": {
            "symbol_months": int(len(exp)),
            "n_symbols": int(panel["symbol"].nunique()),
            "mean_d_norm_expiry": round(float(exp["d_norm"].mean()), 5),
            "mean_d_norm_placebo": round(float(plc["d_norm"].mean()), 5),
            "share_within_0.1_expiry": round(float((exp["d_norm"] < 0.1).mean()), 4),
            "share_within_0.1_placebo": round(float((plc["d_norm"] < 0.1).mean()), 4),
            "share_long_gamma_expiry": round(float(exp["long_gamma"].mean()), 3),
            "median_spacing_bps": round(float(panel["spacing_bps"].median()), 1),
        },
        "results": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "expiry_pinning.yaml"
    with open(path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {path}")


if __name__ == "__main__":
    main()
