"""
Multiple-testing audit of the lag-1 GEX research results (#576).

Collects every hypothesis test of a GEX effect from the lag-1 result YAMLs and treats them
as one family, then applies:

- Holm (family-wise error rate; valid under any dependence between tests)
- Benjamini-Hochberg (false discovery rate; assumes independence or positive dependence)
- Harvey-Liu-Zhu style |t| > 3 hurdle

Included: lag-1 tests of a GEX effect (regime return gaps, overlay vs baseline returns, HAR
regime terms, out-of-sample Diebold-Mariano and VaR tick-loss comparisons).
Excluded: lag-0 runs (look-ahead), VaR calibration tests (Kupiec / Christoffersen test the
model, not GEX), cointegration tests, and files without ``regime_lag_days: 1``.

Full-sample and half-sample tests overlap, so the family has dependent tests; Holm stays
valid, BH is approximate.

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/multiple_testing_audit.py
"""

import datetime
from pathlib import Path

import pandas as pd
import yaml
from statsmodels.stats.multitest import multipletests

RESULTS_DIR = Path("docs/08_research/02_gex_research/results")
ALPHA = 0.05
T_HURDLE = 3.0


def _load(name: str):
    path = RESULTS_DIR / name
    if not path.exists():
        print(f"  missing: {name}")
        return None
    data = yaml.safe_load(open(path))
    lag = (data.get("methodology") or {}).get("regime_lag_days")
    if lag != 1:
        print(f"  skipped (regime_lag_days={lag}): {name}")
        return None
    return data


def _row(study, source, test, t, p, effect=None):
    return {
        "study": study,
        "source": source,
        "test": test,
        "effect": effect,
        "t_statistic": t,
        "p_value": p,
    }


def collect_macd(rows):
    name = "macd_rsi_regime_expanded_lag1.yaml"
    data = _load(name)
    for r in (data or {}).get("results", []):
        nw = r.get("newey_west_test")
        if nw:
            rows.append(
                _row(
                    "#531 MACD+RSI regime gap",
                    name,
                    f"{r['symbol']} bull-bear mean return (NW)",
                    nw["t_statistic"],
                    nw["p_value"],
                    nw["diff_mean"],
                )
            )


def collect_overlays(rows):
    files = {
        "delta_neutral_expanded_lag1.yaml": "#544 delta-neutral overlay, 2011-2026",
        "dispersion_expanded_lag1.yaml": "#545 dispersion overlay, 2011-2026",
        "pairs_trading_expanded_lag1.yaml": "#546 pairs overlay, 2011-2026",
        "delta_neutral_results.yaml": "#544 delta-neutral overlay, 2022-2023",
        "dispersion_results.yaml": "#545 dispersion overlay, 2021-2023",
        "pairs_trading_results.yaml": "#546 pairs overlay, 2022-2023",
    }
    for name, study in files.items():
        data = _load(name)
        for r in (data or {}).get("results", []):
            t = r.get("paired_return_test")
            if not t:
                continue
            label = r.get("symbol") or r.get("pair") or "index"
            rows.append(
                _row(
                    study,
                    name,
                    f"{label} overlay-baseline daily return (NW)",
                    t["t_statistic"],
                    t["p_value"],
                    r.get("sharpe_improvement"),
                )
            )


def collect_volatility(rows):
    name = "var_vol_baseline_lag1.yaml"
    data = _load(name)
    for r in (data or {}).get("results", []):
        sym = r["symbol"]
        for target, res in r["targets"].items():
            for part in ("full", "pre_2020", "from_2020"):
                fit = res.get(part, {})
                d = fit.get("bearish_minus_bullish")
                if d:
                    rows.append(
                        _row(
                            "#543 HAR regime term (in-sample)",
                            name,
                            f"{sym} {target} {part} bear-bull",
                            d["t_statistic"],
                            d["p_value"],
                            d["coef"],
                        )
                    )
            oos = res.get("out_of_sample", {})
            for loss in ("mse", "qlike"):
                dm = (oos.get(loss) or {}).get("diebold_mariano")
                if dm:
                    rows.append(
                        _row(
                            "#543 HAR out-of-sample forecast",
                            name,
                            f"{sym} {target} {loss} DM",
                            dm["t_statistic"],
                            dm["p_value"],
                            dm["mean_loss_diff"],
                        )
                    )
        for level in ("var_95", "var_99"):
            dm = ((r.get("var_backtest") or {}).get(level) or {}).get("quantile_loss_dm")
            if dm:
                rows.append(
                    _row(
                        "#543 VaR tick-loss comparison",
                        name,
                        f"{sym} {level} tick-loss DM",
                        dm["t_statistic"],
                        dm["p_value"],
                        dm["mean_loss_diff"],
                    )
                )


def collect_panel(rows):
    name = "gex_vol_panel_lag1.yaml"
    data = _load(name)
    if not data:
        return
    for sym, res in data["per_symbol"].items():
        for m, r in res.items():
            c = r["in_sample"][m]
            rows.append(
                _row(
                    f"Panel per-symbol {m} (in-sample, leverage controls)",
                    name,
                    f"{sym} {m}",
                    c["t_statistic"],
                    c["p_value"],
                    c["coef"],
                )
            )
            o = r["out_of_sample_qlike"]
            rows.append(
                _row(
                    f"Panel per-symbol {m} (out-of-sample QLIKE)",
                    name,
                    f"{sym} {m} QLIKE DM",
                    o["dm_t_statistic"],
                    o["dm_p_value"],
                    round(o["har"] - o["har_gex"], 5),
                )
            )
    for m, o in (data.get("pooled_out_of_sample") or {}).items():
        rows.append(
            _row(
                "Panel pooled out-of-sample",
                name,
                f"{m} QLIKE DM",
                o["dm_t_statistic"],
                o["dm_p_value"],
                round(o["qlike_base"] - o["qlike_gex"], 5),
            )
        )
    for m, specs in data["pooled"].items():
        c = specs["no_vix"][m]
        rows.append(
            _row("Panel pooled", name, f"{m} (leverage)", c["t_statistic"], c["p_value"], c["coef"])
        )
        ix = specs["with_vix"][f"{m}_x_highvix"]
        rows.append(
            _row(
                "Panel pooled", name, f"{m} x highVIX", ix["t_statistic"], ix["p_value"], ix["coef"]
            )
        )


def collect_intraday(rows):
    name = "intraday_gamma_momentum.yaml"
    data = _load(name)
    for m, res in (data or {}).get("results", {}).items():
        for sample in ("all", "ex_leveraged", "SPY", "QQQ"):
            r = res.get(sample)
            if r:
                ix = r["interaction"]
                rows.append(
                    _row(
                        "#530 intraday momentum x GEX sign",
                        name,
                        f"{sample} {m} interaction",
                        ix["t_statistic"],
                        ix["p_value"],
                        ix["coef"],
                    )
                )
        t = res.get("timing_strategy_all")
        if t:
            rows.append(
                _row(
                    "#530 intraday timing strategy",
                    name,
                    f"{m} timing",
                    t["t_statistic"],
                    t["p_value"],
                    t["mean_daily_bps_gross"],
                )
            )


def collect_pinning(rows):
    name = "expiry_pinning.yaml"
    data = _load(name)
    for outcome, r in (data or {}).get("results", {}).items():
        for key, label in (
            ("expiry_x_long_gamma", "expiry x long gamma"),
            ("expiry_effect_when_long_gamma", "expiry effect, long gamma"),
        ):
            c = r[key]
            rows.append(
                _row(
                    "Expiry-day pinning",
                    name,
                    f"{outcome} {label}",
                    c["t_statistic"],
                    c["p_value"],
                    c["coef"],
                )
            )


def main():
    print("=" * 60)
    print("  MULTIPLE-TESTING AUDIT, LAG-1 GEX TESTS (#576)")
    print("=" * 60)
    rows = []
    collect_macd(rows)
    collect_overlays(rows)
    collect_volatility(rows)
    collect_panel(rows)
    collect_intraday(rows)
    collect_pinning(rows)
    df = pd.DataFrame(rows)
    n = len(df)
    print(f"  Tests in family: {n}")

    p = df["p_value"].clip(lower=1e-12).to_numpy()
    df["holm_reject"], df["holm_p"], _, _ = multipletests(p, alpha=ALPHA, method="holm")
    df["bh_reject"], df["bh_q"], _, _ = multipletests(p, alpha=ALPHA, method="fdr_bh")
    df["raw_reject"] = df["p_value"] < ALPHA
    df["t_above_3"] = df["t_statistic"].abs() > T_HURDLE
    df = df.sort_values("p_value").reset_index(drop=True)

    summary = {
        "n_tests": n,
        "raw_p_below_0.05": int(df["raw_reject"].sum()),
        "expected_by_chance_at_0.05": round(n * ALPHA, 1),
        "holm_rejections": int(df["holm_reject"].sum()),
        "bh_rejections": int(df["bh_reject"].sum()),
        "abs_t_above_3": int(df["t_above_3"].sum()),
    }
    by_study = (
        df.groupby("study")
        .agg(
            n=("p_value", "size"),
            raw=("raw_reject", "sum"),
            holm=("holm_reject", "sum"),
            bh=("bh_reject", "sum"),
            t3=("t_above_3", "sum"),
        )
        .reset_index()
    )

    print(f"\n  {summary}")
    print("\n  By study:")
    print(by_study.to_string(index=False))
    print("\n  Tests surviving BH:")
    keep = ["study", "test", "t_statistic", "p_value", "holm_p", "bh_q", "t_above_3"]
    print(df.loc[df["bh_reject"], keep].to_string(index=False))

    for col in ("holm_p", "bh_q"):
        df[col] = df[col].round(4)
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#576",
        "description": "Multiple-testing audit of lag-1 GEX hypothesis tests",
        "methodology": {
            "family": "all lag-1 tests of a GEX effect in the result YAMLs",
            "excluded": "lag-0 runs, VaR calibration tests, cointegration tests",
            "corrections": ["holm", "benjamini_hochberg", "abs_t > 3"],
            "alpha": ALPHA,
            "dependence_note": "full and half-sample tests overlap; Holm valid, BH approximate",
        },
        "summary": summary,
        "by_study": by_study.to_dict(orient="records"),
        "tests": df.to_dict(orient="records"),
    }
    path = RESULTS_DIR / "multiple_testing_audit.yaml"
    with open(path, "w") as f:
        yaml.dump(
            yaml.safe_load(pd.Series([output]).to_json(orient="records"))[0],
            f,
            default_flow_style=False,
            sort_keys=False,
            width=100,
        )
    print(f"\n  Results saved to {path}")


if __name__ == "__main__":
    main()
