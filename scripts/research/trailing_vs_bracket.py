"""
Trailing-stop exits against the fixed bracket, on the live rules (#539).

The #574 stage A baseline (live_rules_baseline.py) simulated the live MACD+RSI rules with a
fixed -5% / +8% bracket. The live positions now exit by trailing stop only (their take-profit
legs lapsed at Alpaca's 90-day GTC limit), so this runs the same signals, sizing, limits and
timing under three exit modes and compares them on the same days:

- bracket: stop -5% / target +8% from the fill, fixed (the baseline)
- trailing: the -5% stop raised by the live trailing tiers, no target (the live positions today)
- trailing_target: trailing tiers plus the +8% target (the live state before the legs lapsed)

The raise is the live code (StateReconciler._trailing_level on the TrailingStopManager the
routines build): one raise a day from the close, in force from the next session. See
src/backtesting/live_rules_sim.py. The signals are computed once and shared by every run.

Each mode is run at 0 / 5 / 10 bps a side, for moderate and conservative sizing, and for the
moderate size with SELL-signal exits switched off (positions then leave only by their stops
and targets, which is how the live positions exit while the entry step is manual).

Paired comparisons, trailing - bracket and trailing_target - bracket, use the daily returns of
the two equity curves: the Sharpe difference with a paired circular block bootstrap (20-day
blocks, 2000 replications), and a Newey-West test of the mean daily return difference (the
test the multiple-testing audit collects).

Data and periods are the baseline's: split-adjusted equity_prices_daily (read-only), decisions
from 2009-01-02 to 2026-10-09, in-sample 2009-2019, out-of-sample 2020 onward.

Usage:
    ~/miniconda3/envs/OptionsCommander/bin/python scripts/research/trailing_vs_bracket.py
"""

import argparse
import dataclasses
import datetime
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # live_rules_baseline sits beside this

# Research never touches the user's state: the voter's ranking manager opens state/user.db
if "AUTOTRADER_STATE_DIR" not in os.environ:
    os.environ["AUTOTRADER_STATE_DIR"] = tempfile.mkdtemp(prefix="trailing_state_")

import live_rules_baseline as baseline  # noqa: E402

from src.backtesting.live_rules_sim import (  # noqa: E402
    EXIT_MODES,
    LiveRules,
    LiveTrailingStop,
    compute_signals,
    paired_sharpe_diff_ci,
    performance,
    simulate,
)
from src.backtesting.research_cli import paired_return_test  # noqa: E402

RESULTS_DIR = REPO_ROOT / "docs/08_research/03_strategy_research/results"
OUTPUT_STEM = "trailing_vs_bracket"
COSTS_BPS = baseline.COSTS_BPS
PERIODS = {
    "full": (None, None),
    "in_sample_2009_2019": (None, "2019-12-31"),
    "out_of_sample_2020_on": (baseline.SPLIT_DATE, None),
}
PERIOD_LABELS = {
    "full": "2009 to 2026-10-09",
    "in_sample_2009_2019": "2009-2019",
    "out_of_sample_2020_on": "2020 on",
}
TRADE_KEYS = {
    "full": "trades_full",
    "in_sample_2009_2019": "trades_in_sample",
    "out_of_sample_2020_on": "trades_out_of_sample",
}
# (exit mode compared, against)
COMPARISONS = [("trailing", "bracket"), ("trailing_target", "bracket")]
VARIANTS = {
    "moderate": {"position_pct": baseline.MODES["moderate"], "signal_exit": True},
    "conservative": {"position_pct": baseline.MODES["conservative"], "signal_exit": True},
    "moderate_no_signal_exit": {"position_pct": baseline.MODES["moderate"], "signal_exit": False},
}
VARIANT_LABELS = {
    "moderate": "Moderate sizing (2% of equity), SELL-signal exits kept",
    "conservative": "Conservative sizing (1% of equity), SELL-signal exits kept",
    "moderate_no_signal_exit": "Moderate sizing, SELL-signal exits off (stops and targets only)",
}
MODE_LABELS = {
    "bracket": "bracket (fixed -5% / +8%)",
    "trailing": "trailing (live today)",
    "trailing_target": "trailing + 8% target",
}


def sliced_returns(equity: pd.Series, start=None, end=None) -> pd.Series:
    """Daily returns of an equity curve cut to a period before differencing, as period_stats does."""
    e = equity
    if start is not None:
        e = e[e.index >= pd.Timestamp(start)]
    if end is not None:
        e = e[e.index <= pd.Timestamp(end)]
    return e.pct_change().dropna()


def sliced_equity(equity: pd.Series, start=None, end=None) -> pd.Series:
    e = equity
    if start is not None:
        e = e[e.index >= pd.Timestamp(start)]
    if end is not None:
        e = e[e.index <= pd.Timestamp(end)]
    return e


def paired_rows(variant: str, equities: dict) -> list:
    """Paired comparisons of each exit mode against the bracket, by cost and period."""
    rows = []
    for cost in COSTS_BPS:
        for mode, base in COMPARISONS:
            for period, span in PERIODS.items():
                ra = sliced_returns(equities[(variant, mode, cost)], *span)
                rb = sliced_returns(equities[(variant, base, cost)], *span)
                boot = paired_sharpe_diff_ci(ra, rb)
                perf_a = performance(sliced_equity(equities[(variant, mode, cost)], *span))
                perf_b = performance(sliced_equity(equities[(variant, base, cost)], *span))
                rows.append(
                    {
                        "comparison": f"{mode} - {base}",
                        "variant": variant,
                        "period": period,
                        "cost_bps": cost,
                        "sharpe_diff": round(boot["diff"], 4),
                        "sharpe_diff_ci95": [round(x, 4) for x in boot["ci95"]],
                        "sharpe_diff_bootstrap_p": round(boot["p_value"], 4),
                        "cagr_diff_pp": round(perf_a["cagr_pct"] - perf_b["cagr_pct"], 4),
                        "max_drawdown_diff_pp": round(
                            perf_a["max_drawdown_pct"] - perf_b["max_drawdown_pct"], 4
                        ),
                        "return_test": paired_return_test(rb, ra),
                        "n_days": boot["n_days"],
                    }
                )
    return rows


def methodology() -> dict:
    tiers = dataclasses.asdict(LiveTrailingStop().manager.trailing_config)
    keep = (
        "enabled",
        "progressive_enabled",
        "progressive_breakeven_pct",
        "progressive_lock_25_pct",
        "progressive_trail_50_pct",
        "climb_rate",
        "never_move_stop_down",
        "volatility_aware",
    )
    return {
        "question": (
            "Do the live trailing-tier exits do better, worse, or no differently than the fixed "
            "-5% / +8% bracket of the #574 baseline, for the same entry signals at live timing?"
        ),
        "signal": baseline_methodology()["signal"],
        "timing": baseline_methodology()["timing"],
        "entries": baseline_methodology()["entries"],
        "exit_modes": {
            "bracket": "stop -5% / target +8% from the fill, fixed (the #574 baseline)",
            "trailing": (
                "initial stop -5% from the fill, raised by the live trailing tiers, no target "
                "(how the live positions exit today)"
            ),
            "trailing_target": "the same tiers plus the +8% target (the live state before the legs lapsed)",
        },
        "signal_exit": "a SELL signal closes the position at the open, in every mode unless the variant switches it off",
        "trailing_raise": (
            "StateReconciler._trailing_level on a TrailingStopManager built as "
            "CostEfficientTradeCycle builds it (no broker, no ATR fetcher, stock TradingConfig); "
            "one raise a day from the close (the evening routine runs ten minutes before it), in "
            "force from the next session; MIN_STOP_GAP floor and the $0.01 rule are the "
            "reconciler's; run at the day's raw price level so the cent rounds as at the broker"
        ),
        "trailing_config": {k: tiers[k] for k in keep},
        "inert_on_the_live_path": [
            "ATR (volatility_aware is off and the routines pass no atr_fetcher)",
            "voter tightening (update_voter_signal is never called by the routines)",
            "support/resistance levels (set_support_resistance is never called)",
        ],
        "stop_fills": "a session whose low reaches the stop fills at min(open, stop); both stop and target touched counts as the stop",
        "initial_capital": LiveRules().initial_capital,
        "variants": {
            name: {**spec, "label": VARIANT_LABELS[name]} for name, spec in VARIANTS.items()
        },
        "costs_bps_per_side": COSTS_BPS,
        "data": "equity_prices_daily, split-adjusted (gex.corporate_events), dividends excluded, read-only",
        "periods": {
            "warmup_from": baseline.WARMUP_START,
            "test": f"{baseline.TEST_START} to {baseline.TEST_END}",
            "out_of_sample_from": baseline.SPLIT_DATE,
        },
        "sharpe": "annualized, rf 0; 95% circular block bootstrap (20-day blocks, 2000 reps)",
        "paired_sharpe": (
            "Sharpe(a) - Sharpe(b) on the daily returns of the two equity curves; the same "
            "20-day blocks are drawn for both in each of 2000 replications (seed 0); p is twice "
            "the smaller share of replications on one side of zero"
        ),
        "paired_return_test": "Newey-West test of the mean daily return difference (research_cli.paired_return_test); this is the test the multiple-testing audit collects",
        "alpha": "daily OLS on equal-weight universe returns, annualized intercept, Newey-West (5 lags) t; cash earns 0",
        "mean_hold_days": "calendar days, closed trades by entry date",
        "not_modelled": [
            "the morning routine's raise from the pre-market price (it uses about the previous close, which the evening raise has already used)",
            "intraday timing of the raise (the stop is in force from the next session, not for the last ten minutes of the day)",
            "intraday decisions (the CLI can also trade on a partial day)",
            "IEX vs consolidated bars",
            "GTC renewal after 80 days (assumed seamless, as #587 does it)",
            "the 90-day lapse of the take-profit leg in trailing_target (the target is kept as in the bracket)",
            "GTT sells (skipped while a broker stop holds the shares)",
            "dividends",
        ],
        "caveats": [
            "universe picked with hindsight; benchmark is buy-and-hold of the same symbols",
            "MACD threshold is in dollars, so signal frequency depends on price level",
            "exit modes change how long positions are held, so the 10-position cap and the exposure limit block different entries: the strategies share signals, not trades",
            "tiers and stops are measured from the open the position filled at, before costs",
        ],
    }


def baseline_methodology() -> dict:
    return {
        "signal": "VoterAgent.evaluate_ranked_voting (MACD 13/34/8 hist beyond +/-0.1, RSI 14 at 30/70), 90-calendar-day window rescaled to the prior day's raw price level",
        "timing": "signal from bars through d-1; fills at day d open",
        "entries": "BUY with no position at the start of the day; whole shares (at the raw price) of position_pct x prior equity at the prior close; max 10 positions and 80% exposure counted before the open; cash",
    }


def fmt_sharpe(stats: dict) -> str:
    low, high = stats["sharpe_ci95"]
    return f"{stats['sharpe']:.3f} [{low:.3f}, {high:.3f}]"


def fmt_alpha(alpha: dict) -> str:
    return f"{alpha['alpha_ann_pct']:+.2f}% ({alpha['alpha_t']:+.2f})"


def scenario_rows(variant_results: dict) -> list:
    """Long table rows: exit mode x period x cost."""
    lines = []
    for mode in EXIT_MODES:
        for period in PERIODS:
            for cost in COSTS_BPS:
                s = variant_results[mode][f"{int(cost)}bps"]
                stats, trades = s[period], s[TRADE_KEYS[period]]
                lines.append(
                    f"| {MODE_LABELS[mode]} | {PERIOD_LABELS[period]} | {cost:g} | "
                    f"{fmt_sharpe(stats)} | {stats['cagr_pct']:.2f}% | {stats['max_drawdown_pct']:.1f}% | "
                    f"{trades.get('n_trades', 0):,} | {trades.get('win_rate_pct', float('nan')):.1f}% | "
                    f"{trades.get('mean_hold_days', float('nan')):.1f} | "
                    f"{fmt_alpha(s['alpha_vs_equal_weight'][period])} |"
                )
    return lines


SCENARIO_HEADER = [
    "| Exit mode | Period | Cost (bps) | Sharpe [95% CI] | CAGR | Max DD | Trades | Win rate | Mean hold (days) | Alpha vs EW, % a year (t) |",
    "| --------- | ------ | ---------- | --------------- | ---- | ------ | ------ | -------- | ---------------- | ------------------------- |",
]
PAIRED_HEADER = [
    "| Comparison | Period | Cost (bps) | Sharpe difference [95% CI] | Bootstrap p | Mean return difference, % a year | NW t | NW p |",
    "| ---------- | ------ | ---------- | -------------------------- | ----------- | -------------------------------- | ---- | ---- |",
]


def paired_table(tests: list, variant: str, costs=None) -> list:
    lines = []
    for t in tests:
        if t["variant"] != variant or (costs is not None and t["cost_bps"] not in costs):
            continue
        low, high = t["sharpe_diff_ci95"]
        rt = t["return_test"] or {}
        diff_pct = rt.get("mean_daily_diff", float("nan")) * 252 * 100
        lines.append(
            f"| {t['comparison']} | {PERIOD_LABELS[t['period']]} | {t['cost_bps']:g} | "
            f"{t['sharpe_diff']:+.3f} [{low:+.3f}, {high:+.3f}] | {t['sharpe_diff_bootstrap_p']:.3f} | "
            f"{diff_pct:+.2f} | {rt.get('t_statistic', float('nan')):+.2f} | "
            f"{rt.get('p_value', float('nan')):.3f} |"
        )
    return lines


def reading(tests: list, variant: str) -> list:
    """One line per comparison at 5 bps, saying only whether the interval covers zero."""
    lines = []
    for t in tests:
        if t["variant"] != variant or t["cost_bps"] != 5.0:
            continue
        low, high = t["sharpe_diff_ci95"]
        side = "includes zero" if low <= 0 <= high else ("above zero" if low > 0 else "below zero")
        lines.append(
            f"- {t['comparison']}, {PERIOD_LABELS[t['period']]}: {t['sharpe_diff']:+.3f} "
            f"[{low:+.3f}, {high:+.3f}], interval {side}"
        )
    return lines


def exit_reason_table(variant_results: dict, cost_key: str = "5bps") -> list:
    reasons = ["signal", "stop", "stop_gap", "trail", "trail_gap", "target", "target_gap"]
    lines = [
        "| Exit mode | " + " | ".join(reasons) + " | Closed trades |",
        "| --------- | " + " | ".join("---" for _ in reasons) + " | -------------- |",
    ]
    for mode in EXIT_MODES:
        t = variant_results[mode][cost_key]["trades_full"]
        counts = t["exit_reasons"]
        lines.append(
            f"| {MODE_LABELS[mode]} | "
            + " | ".join(f"{counts.get(r, 0):,}" for r in reasons)
            + f" | {t['n_trades']:,} |"
        )
    return lines


def render_markdown(output: dict) -> str:
    results, tests = output["scenarios"], output["paired_tests"]
    lines = [
        "# Trailing Exits against the Fixed Bracket (#539)",
        "",
        f"Generated by `scripts/research/trailing_vs_bracket.py` on {output['run_timestamp'][:10]}. "
        "Numbers are in `trailing_vs_bracket.json`.",
        "",
        "The #574 baseline simulated the live rules with a fixed -5% / +8% bracket. The live positions now "
        "exit by trailing stop only. This runs the same signals, sizing, limits and timing under three exit "
        "modes and compares them on the same days.",
        "",
        "| Exit mode | Protective orders | Stands for |",
        "| --------- | ----------------- | ---------- |",
        "| bracket | stop -5% and target +8% from the fill, fixed | the #574 baseline |",
        "| trailing | -5% stop raised by the live trailing tiers, no target | the live positions today |",
        "| trailing_target | the same tiers plus the +8% target | the live state before the 8% legs lapsed |",
        "",
        "The tiers are the live ones (climb rate medium): under 2% profit no change, 2-4% breakeven, 4-6% "
        "lock 25% of the gain, 6-10% lock 50%, 10% and up lock 75%; never down; at least 1% below the price. "
        "The simulation calls the live code for the raise. It raises once a day from the close, and a raised "
        "stop applies from the next session.",
        "",
        f"Universe: {len(output['universe'])} watchlist symbols. Decisions {baseline.TEST_START} to "
        f"{baseline.TEST_END}; in-sample 2009-2019, out-of-sample 2020 on. Costs are per side on every fill.",
        "",
        "## Reading",
        "",
        f"{VARIANT_LABELS['moderate']}, 5 bps a side, paired Sharpe differences:",
        "",
        *reading(tests, "moderate"),
        "",
    ]
    for variant in VARIANTS:
        if variant not in results:
            continue
        lines += [f"## {VARIANT_LABELS[variant]}", "", "### Performance by exit mode", ""]
        lines += SCENARIO_HEADER + scenario_rows(results[variant]) + [""]
        lines += ["### Exits at 5 bps, all periods (closed trades)", ""]
        lines += exit_reason_table(results[variant]) + [""]
        lines += ["### Paired differences against the bracket", ""]
        lines += PAIRED_HEADER + paired_table(tests, variant) + [""]
    bench = output["benchmarks"]
    lines += [
        "## Benchmarks",
        "",
        "| Benchmark | Period | Sharpe [95% CI] | CAGR | Max DD |",
        "| --------- | ------ | --------------- | ---- | ------ |",
    ]
    for name, periods in bench.items():
        for period in PERIODS:
            s = periods[period]
            lines.append(
                f"| {name} | {PERIOD_LABELS[period]} | {fmt_sharpe(s)} | {s['cagr_pct']:.1f}% | "
                f"{s['max_drawdown_pct']:.1f}% |"
            )
    lines += [
        "",
        "## Method and limits",
        "",
        "- Paired Sharpe difference: both equity curves' daily returns are resampled with the same 20-day "
        "blocks (2000 replications), so the shared market and most shared entries cancel. The p-value is "
        "twice the smaller share of replications on one side of zero. The Newey-West columns test the mean "
        "daily return difference; the multiple-testing audit collects those.",
        "- The strategies share signals, not trades: holding periods differ, so the 10-position cap and the "
        "exposure limit block different entries.",
        "- Alpha is the annualized intercept of a daily regression on equal-weight buy-and-hold returns of the "
        "same symbols, with Newey-West t-statistics (5 lags). Mean hold is in calendar days.",
        "- Tiers and stops are measured from the open the position filled at, before costs.",
        "",
        "Not modelled: the morning routine's raise from the pre-market price (about the previous close, "
        "already used by the evening raise); the last ten minutes of the day under the raised stop; intraday "
        "decisions; IEX vs consolidated bars; 80-day GTC renewal (assumed seamless); the 90-day lapse of the "
        "take-profit leg in `trailing_target` (the target is kept); GTT sells; dividends.",
        "",
    ]
    return "\n".join(lines)


def to_native(obj):
    """Python natives for JSON."""
    if isinstance(obj, dict):
        return {str(k): to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_native(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def main():  # noqa: C901
    parser = argparse.ArgumentParser(description="Trailing exits vs the fixed bracket (#539)")
    parser.add_argument("--output", default=OUTPUT_STEM, help="file stem in the results folder")
    parser.add_argument(
        "--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS), help="runs to do"
    )
    args = parser.parse_args()
    logging.disable(logging.WARNING)  # the voter and the trailing manager log every call
    os.chdir(REPO_ROOT)  # the baseline's helpers read config_defaults/ relative to the repo

    print("=" * 60)
    print("  TRAILING EXITS VS FIXED BRACKET ON THE LIVE RULES (#539)")
    print("=" * 60)
    wanted = baseline.watchlist_symbols()
    prices, raw_closes = baseline.load_prices(wanted)
    missing = sorted(set(wanted) - set(prices))
    print(f"  Universe: {len(prices)} of {len(wanted)} watchlist symbols (missing: {missing})")

    print("  Computing live signals once (about 2 ms per symbol-day)...")
    signals = compute_signals(
        {s: p["close"] for s, p in prices.items()},
        raw_closes,
        baseline.live_signal_fn(),
        baseline.TEST_START,
        baseline.TEST_END,
    )
    counts = signals["action"].value_counts().to_dict()
    print(f"  Signals: {len(signals)} symbol-days {counts}")

    calendar = pd.DatetimeIndex(sorted(signals.index.get_level_values("date").unique()))
    bench_equity = baseline.benchmarks(prices, calendar)

    scenarios, equities, paired = {}, {}, []
    for variant in args.variants:
        spec = VARIANTS[variant]
        scenarios[variant] = {}
        for mode in EXIT_MODES:
            scenarios[variant][mode] = {}
            for cost in COSTS_BPS:
                rules = LiveRules(
                    position_pct=spec["position_pct"],
                    cost_bps=cost,
                    exit_mode=mode,
                    signal_exit=spec["signal_exit"],
                )
                equity, trades = simulate(prices, signals, rules, raw_closes=raw_closes)
                exposure = baseline.exposure_series(equity, trades, prices)
                s = baseline.summarize(equity, trades, exposure, bench_equity)
                s["trades_in_sample"] = baseline.trade_stats(trades, end="2019-12-31")
                s["buys_not_taken"] = trades.attrs["blocked"]
                scenarios[variant][mode][f"{int(cost)}bps"] = s
                equities[(variant, mode, cost)] = equity
                oos = s["out_of_sample_2020_on"]
                print(
                    f"  {variant:24} {mode:16} {cost:4.0f} bps  full Sharpe {s['full']['sharpe']:+.3f}  "
                    f"OOS {oos['sharpe']:+.3f}  CAGR {s['full']['cagr_pct']:.2f}%  "
                    f"maxDD {s['full']['max_drawdown_pct']:.1f}%  "
                    f"trades {s['trades_full']['n_trades']}  hold {s['trades_full']['mean_hold_days']}"
                )
        paired += paired_rows(variant, equities)

    print("\n  Paired Sharpe differences at 5 bps (full / in-sample / out-of-sample):")
    for variant in args.variants:
        for mode, base in COMPARISONS:
            cells = []
            for period in PERIODS:
                t = next(
                    t
                    for t in paired
                    if (t["variant"], t["comparison"], t["period"], t["cost_bps"])
                    == (variant, f"{mode} - {base}", period, 5.0)
                )
                low, high = t["sharpe_diff_ci95"]
                cells.append(f"{t['sharpe_diff']:+.3f} [{low:+.3f}, {high:+.3f}]")
            print(f"  {variant:24} {mode} - {base}: " + "  ".join(cells))

    bench = {
        name: {period: baseline.period_stats(eq, *span) for period, span in PERIODS.items()}
        for name, eq in bench_equity.items()
    }
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#539",
        "description": "Trailing-tier exits against the fixed -5% / +8% bracket on the live rules",
        "methodology": methodology(),
        "universe": sorted(prices),
        "missing_symbols": missing,
        "signal_counts": {k: int(v) for k, v in counts.items()},
        "scenarios": scenarios,
        "paired_tests": paired,
        "benchmarks": bench,
    }
    output = to_native(output)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"{args.output}.json"
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")
    md_path = RESULTS_DIR / f"{args.output}.md"
    with open(md_path, "w") as f:
        f.write(render_markdown(output))
    print(f"\n  Results saved to {json_path} and {md_path}")


if __name__ == "__main__":
    main()
