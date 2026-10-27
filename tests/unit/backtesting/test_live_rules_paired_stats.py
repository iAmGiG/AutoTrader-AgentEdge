"""Paired Sharpe-difference bootstrap for the exit-mode comparison (#539)."""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.live_rules_sim import paired_sharpe_diff_ci, sharpe_ci


def _returns(seed, n=1500, mean=0.0005, sd=0.01):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, sd, n), index=pd.bdate_range("2015-01-01", periods=n))


def _sharpe(r):
    return float(np.sqrt(252) * r.mean() / r.std())


def test_identical_series_have_no_difference():
    r = _returns(1)

    out = paired_sharpe_diff_ci(r, r)

    assert out["diff"] == 0.0
    assert out["ci95"] == [0.0, 0.0]
    assert out["p_value"] == 1.0
    assert out["n_days"] == len(r)


def test_difference_is_the_sharpe_gap_and_flips_with_the_order():
    a, b = _returns(1, mean=0.001), _returns(2, mean=0.0)

    ab, ba = paired_sharpe_diff_ci(a, b), paired_sharpe_diff_ci(b, a)

    assert ab["diff"] == pytest.approx(_sharpe(a) - _sharpe(b))
    assert ba["diff"] == pytest.approx(-ab["diff"])
    # the same resampled days, so the interval mirrors
    assert ba["ci95"] == pytest.approx([-ab["ci95"][1], -ab["ci95"][0]])
    assert ab["ci95"][0] < ab["diff"] < ab["ci95"][1]


def test_a_shift_the_series_share_is_found_and_noise_is_not():
    r = _returns(3)

    shifted = paired_sharpe_diff_ci(r + 0.002, r)
    assert shifted["ci95"][0] > 0
    assert shifted["p_value"] == 1 / 2000  # no replication on the other side of zero

    unrelated = paired_sharpe_diff_ci(_returns(4), _returns(5))
    assert unrelated["ci95"][0] < 0 < unrelated["ci95"][1]
    assert unrelated["p_value"] > 0.05


def test_pairing_narrows_the_interval_of_strategies_that_share_days():
    rng = np.random.default_rng(6)
    base = _returns(7)
    other = 0.9 * base + 0.1 * pd.Series(rng.normal(0, 0.01, len(base)), index=base.index)

    paired = paired_sharpe_diff_ci(other, base)
    widths = [np.subtract(*sharpe_ci(r)[::-1]) for r in (other, base)]

    assert paired["ci95"][1] - paired["ci95"][0] < min(widths)


def test_only_the_dates_in_both_series_are_used():
    r = _returns(8)

    out = paired_sharpe_diff_ci(r, r.iloc[10:].copy())

    assert out["n_days"] == len(r) - 10


def test_too_few_days_give_no_interval():
    r = _returns(9, n=30)

    out = paired_sharpe_diff_ci(r, r * 0.5)

    assert np.isnan(out["diff"]) and np.isnan(out["p_value"])
    assert all(np.isnan(out["ci95"])) and out["n_days"] == 30


def test_a_series_without_variance_gives_no_p_value_rather_than_a_false_one():
    flat = pd.Series(0.0, index=_returns(1).index)

    out = paired_sharpe_diff_ci(flat, _returns(2))

    assert np.isnan(out["p_value"]) and all(np.isnan(out["ci95"]))


def test_replications_without_variance_are_left_out_and_counted():
    mostly_flat = pd.Series(0.0, index=pd.bdate_range("2015-01-01", periods=200))
    mostly_flat.iloc[[3, 150]] = [0.01, -0.01]  # many 20-day resamples miss both days

    out = paired_sharpe_diff_ci(mostly_flat, _returns(2, n=200), reps=300)

    assert 0 < out["dropped_reps"] < 300
    assert np.isfinite(out["p_value"]) and all(np.isfinite(out["ci95"]))
