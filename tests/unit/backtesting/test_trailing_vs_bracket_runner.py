"""Bookkeeping of the #539 runner: which mode is compared with which, over which days."""

import importlib
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
