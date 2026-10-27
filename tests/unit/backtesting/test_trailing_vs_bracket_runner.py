"""Bookkeeping of the #539 runner: which mode is compared with which, over which days."""

import importlib
import json
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[3]
DAYS = pd.bdate_range("2019-01-02", periods=700)  # 2019 to 2021: covers both sub-periods


@pytest.fixture
def runner(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(REPO / "scripts" / "research"))  # beside live_rules_baseline
    monkeypatch.setenv("AUTOTRADER_STATE_DIR", str(tmp_path / "state"))
    module = importlib.import_module("trailing_vs_bracket")
    monkeypatch.setattr(module, "COSTS_BPS", [5.0])  # one cost and a short bootstrap: fast
    monkeypatch.setattr(
        module, "paired_sharpe_diff_ci", partial(module.paired_sharpe_diff_ci, reps=200)
    )
    return module


def _equities(runner, shifts, variant="moderate"):
    rng = np.random.default_rng(3)
    base = pd.Series(rng.normal(0.0004, 0.01, len(DAYS)), index=DAYS)
    return {
        (variant, mode, cost): 100_000 * (1 + base + shift).cumprod()
        for mode, shift in shifts.items()
        for cost in runner.COSTS_BPS
    }


def test_slices_are_cut_before_differencing(runner):
    equity = pd.Series(np.linspace(100, 200, len(DAYS)), index=DAYS)

    returns = runner.sliced_returns(equity, "2020-01-01")

    # the first day of a slice has no return
    assert len(returns) == (DAYS >= "2020-01-01").sum() - 1
    assert returns.index[0] == DAYS[DAYS >= "2020-01-01"][1]
    assert len(runner.sliced_returns(equity, end="2019-12-31")) == (DAYS <= "2019-12-31").sum() - 1


def test_each_trailing_mode_is_compared_with_the_bracket_in_that_order(runner):
    equities = _equities(runner, {"bracket": 0.0, "trailing": 0.0003, "trailing_target": -0.0003})

    rows = runner.paired_rows("moderate", equities)

    assert len(rows) == 2 * len(runner.COSTS_BPS) * len(runner.PERIODS)
    assert {r["comparison"] for r in rows} == {"trailing - bracket", "trailing_target - bracket"}
    assert {r["period"] for r in rows} == set(runner.PERIODS)
    for r in rows:
        sign = 1 if r["comparison"] == "trailing - bracket" else -1
        assert sign * r["sharpe_diff"] > 0  # trailing is the better curve, trailing_target worse
        assert sign * r["sharpe_diff_ci95"][0] > 0 or sign * r["sharpe_diff_ci95"][1] > 0
        assert sign * r["return_test"]["mean_daily_diff"] > 0
        assert sign * r["return_test"]["t_statistic"] > 0
        assert sign * r["cagr_diff_pp"] > 0
        assert r["variant"] == "moderate"


def test_periods_use_the_baselines_split_and_each_comparison_its_own_days(runner):
    equities = _equities(runner, {"bracket": 0.0, "trailing": 0.0001, "trailing_target": 0.0})
    rows = runner.paired_rows("moderate", equities)
    days = {r["period"]: r["n_days"] for r in rows if r["cost_bps"] == 5.0}

    assert days["in_sample_2009_2019"] == (DAYS <= "2019-12-31").sum() - 1
    assert days["out_of_sample_2020_on"] == (DAYS >= "2020-01-01").sum() - 1
    assert days["full"] == len(DAYS) - 1
    assert runner.baseline.SPLIT_DATE == "2020-01-01"


def test_identical_curves_show_no_difference(runner):
    equities = _equities(runner, {"bracket": 0.0, "trailing": 0.0, "trailing_target": 0.0})

    for r in runner.paired_rows("moderate", equities):
        assert r["sharpe_diff"] == 0.0 and r["sharpe_diff_ci95"] == [0.0, 0.0]
        assert r["return_test"] is None  # a constant zero difference has no test statistic


# ---------------------------------------------------------------------------
# The morning-raise sensitivity
# ---------------------------------------------------------------------------

MORNING_SHIFTS = {
    "bracket": 0.0,
    "trailing": 0.0003,
    "trailing_target": 0.0002,
    "trailing+morning": 0.0001,  # the morning raise costs both trailing modes
    "trailing_target+morning": 0.00005,
}


def test_morning_runs_are_compared_with_the_bracket_and_with_their_own_evening_only_run(runner):
    equities = _equities(runner, MORNING_SHIFTS)

    vs_bracket = runner.paired_rows("moderate", equities, runner.MORNING_COMPARISONS)
    effect = runner.paired_rows("moderate", equities, runner.MORNING_EFFECTS)

    assert {r["comparison"] for r in vs_bracket} == {
        "trailing+morning - bracket",
        "trailing_target+morning - bracket",
    }
    assert {r["comparison"] for r in effect} == {
        "trailing+morning - trailing",
        "trailing_target+morning - trailing_target",
    }
    assert len(vs_bracket) == len(effect) == 2 * len(runner.COSTS_BPS) * len(runner.PERIODS)
    for r in vs_bracket:
        assert r["sharpe_diff"] > 0  # both morning curves sit above the bracket's here
    for r in effect:
        assert r["sharpe_diff"] < 0  # and below their own evening-only curves
        assert r["return_test"]["mean_daily_diff"] < 0 and r["return_test"]["t_statistic"] < 0
        assert r["cagr_diff_pp"] < 0


def test_the_default_comparisons_are_unchanged_by_the_sensitivity(runner):
    equities = _equities(runner, MORNING_SHIFTS)

    rows = runner.paired_rows("moderate", equities)

    assert {r["comparison"] for r in rows} == {"trailing - bracket", "trailing_target - bracket"}
    assert runner.COMPARISONS == [("trailing", "bracket"), ("trailing_target", "bracket")]


def _market(seed=11, n_symbols=3):
    """Random daily bars and BUY / SELL signals over DAYS (day 0 is the warm-up)."""
    rng = np.random.default_rng(seed)
    n = len(DAYS)
    prices, raw, rows = {}, {}, []
    for k in range(n_symbols):
        close = 50 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
        open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.012, n))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
        frame = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=DAYS)
        prices[f"S{k}"], raw[f"S{k}"] = frame, frame["close"]
    for day in DAYS[1:]:
        for symbol in prices:
            action = rng.choice(["BUY", "SELL", "HOLD"], p=[0.2, 0.08, 0.72])
            rows.append((day, symbol, action, 0.5 if action != "HOLD" else 0.0))
    cols = ["date", "symbol", "action", "position_size"]
    return prices, raw, pd.DataFrame(rows, columns=cols).set_index(["date", "symbol"])


@pytest.fixture(scope="module")
def market():
    return _market()


def test_the_sensitivity_is_kept_out_of_the_paired_tests_the_audit_collects(runner, market):
    prices, raw, signals = market

    output = runner.analyze(prices, raw, signals, ["moderate"])
    json.dumps(output)  # natives all through

    assert {t["comparison"] for t in output["paired_tests"]} == {
        "trailing - bracket",
        "trailing_target - bracket",
    }
    sens = output["morning_raise_sensitivity"]
    assert sens["modes"] == ["trailing+morning", "trailing_target+morning"]
    assert set(sens["scenarios"]["moderate"]) == set(sens["modes"])
    assert {t["comparison"] for t in sens["paired_tests_vs_bracket"]} == {
        "trailing+morning - bracket",
        "trailing_target+morning - bracket",
    }
    assert {t["comparison"] for t in sens["effect_of_morning_raise"]} == {
        "trailing+morning - trailing",
        "trailing_target+morning - trailing_target",
    }
    # the three exit modes of the main results are untouched: no "+morning" key among them
    assert set(output["scenarios"]["moderate"]) == set(runner.EXIT_MODES)


def test_a_morning_run_is_the_evening_only_run_plus_the_morning_raise(runner, market):
    prices, raw, signals = market
    inputs = (prices, raw, signals, runner.baseline.benchmarks(prices, DAYS[1:]))
    spec = runner.VARIANTS["moderate"]

    plain, _ = runner.run_modes("moderate", spec, ["trailing"], inputs)
    morning, _ = runner.run_modes("moderate", spec, ["trailing"], inputs, morning=True)

    p, m = plain["trailing"]["5bps"], morning["trailing+morning"]["5bps"]
    assert m["full"] != p["full"]  # the morning raise moves the curve on these paths
    assert m["trades_full"]["exit_reasons"].get("trail", 0) > p["trades_full"]["exit_reasons"].get(
        "trail", 0
    )


def test_the_report_puts_the_sensitivity_beside_the_main_results(runner, market):
    prices, raw, signals = market
    output = runner.analyze(prices, raw, signals, ["moderate"])

    md = runner.render_markdown(output)

    reading = md.split("## Reading")[1].split("\n## ")[0]
    assert "- trailing+morning - bracket, 2009 to 2026-10-09:" in reading
    assert "- trailing_target+morning - bracket, 2020 on:" in reading
    assert "not redundant" in reading and "runs against the trailing modes" in reading
    assert "## Morning-raise sensitivity" in md
    section = md.split("## Morning-raise sensitivity")[1].split("\n## ")[0]
    assert "| trailing + morning raise at the open | 2009 to 2026-10-09 | 5 |" in section
    assert "| trailing+morning - trailing | 2020 on | 5 |" in section
    assert "trailing_target+morning - bracket" in section
    tail = md.split("Not modelled:")[1]
    assert "pre-market" in tail and "morning-raise sensitivity" in tail
    # the claim the sensitivity replaces
    for stale in ("already used", "adds nothing", "about the previous close"):
        assert stale not in md
    methodology = output["methodology"]
    assert any("morning_raise_sensitivity" in line for line in methodology["not_modelled"])
    assert not any("already used" in line for line in methodology["not_modelled"])


def test_the_report_renders_for_a_variant_subset_without_the_readings_variant(runner, market):
    prices, raw, signals = market
    output = runner.analyze(prices, raw, signals, ["conservative"])

    md = runner.render_markdown(output)

    assert "## Morning-raise sensitivity" in md
    assert "### Conservative sizing (1% of equity), SELL-signal exits kept" in md
    assert "### Moderate sizing" not in md  # not run: nothing to show for it
    assert runner.morning_reading(output) == []  # the Reading is about the moderate variant


def _output(effects, sharpes):
    """A minimal output holding the morning-raise effects (full period, 5 bps, moderate)."""
    cost = "5bps"
    scenarios = {"moderate": {}}
    morning = {"moderate": {}}
    for mode, (plain, with_morning) in sharpes.items():
        scenarios["moderate"][mode] = {cost: {"full": {"sharpe": plain}}}
        morning["moderate"][f"{mode}+morning"] = {cost: {"full": {"sharpe": with_morning}}}
    rows = []
    for (mode, period), (diff, ci) in effects.items():
        rows.append(
            {
                "comparison": f"{mode}+morning - {mode}",
                "variant": "moderate",
                "period": period,
                "cost_bps": 5.0,
                "sharpe_diff": diff,
                "sharpe_diff_ci95": ci,
            }
        )
    return {
        "scenarios": scenarios,
        "morning_raise_sensitivity": {
            "scenarios": morning,
            "effect_of_morning_raise": rows,
            "paired_tests_vs_bracket": [],
        },
    }


def test_the_reading_quotes_the_loss_and_counts_the_negative_effects(runner):
    output = _output(
        {
            ("trailing", "full"): (-0.092, [-0.200, 0.012]),
            ("trailing_target", "full"): (-0.114, [-0.210, -0.020]),
            ("trailing", "out_of_sample_2020_on"): (0.010, [-0.100, 0.120]),
        },
        {"trailing": (0.644, 0.552), "trailing_target": (0.691, 0.577)},
    )

    low, high = runner.morning_effect_range(output["morning_raise_sensitivity"])
    text = " ".join(runner.morning_reading(output))

    assert (low, high) == (pytest.approx(0.092), pytest.approx(0.114))  # losses, positive
    assert (
        "trailing from 0.644 to 0.552 (-0.092 [-0.200, +0.012] paired, interval includes zero)"
        in text
    )
    assert (
        "trailing_target from 0.691 to 0.577 (-0.114 [-0.210, -0.020] paired, interval below zero)"
        in text
    )
    assert "by 0.09 to 0.11 at 5 bps" in text
    assert "negative in 2 of 3 comparisons" in text  # the out-of-sample row is positive


def test_the_runner_points_state_and_cache_at_scratch_dirs_and_removes_them(tmp_path):
    """Run without the test suite's isolation: the module itself must keep off real state."""
    import os
    import subprocess
    import sys

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("AUTOTRADER_STATE_DIR", "AUTOTRADER_CACHE_DIR")
    }
    code = (
        "import os, sys; sys.path[:0] = [sys.argv[1], sys.argv[2]];"
        "import trailing_vs_bracket;"
        "print(os.environ['AUTOTRADER_STATE_DIR']); print(os.environ['AUTOTRADER_CACHE_DIR'])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, str(REPO / "scripts" / "research"), str(REPO)],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=True,
    )

    state, cache = out.stdout.split()[-2:]
    assert "trailing_state_" in state and "trailing_cache_" in cache
    assert not Path(state).exists() and not Path(cache).exists()  # removed at exit
