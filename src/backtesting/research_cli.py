"""Shared command-line options for the GEX research runners (#576)."""

import argparse
from typing import Dict, Optional

import numpy as np


def parse_window_args(description: str, defaults: Dict[str, object], output_default: str):
    """Parse window/lag/output options; ``defaults`` maps option names (e.g. test_start) to values.

    Keys present in ``defaults`` become ``--test-start`` style flags; ``symbols`` takes a list.
    """
    parser = argparse.ArgumentParser(description=description)
    for key, value in defaults.items():
        flag = "--" + key.replace("_", "-")
        if isinstance(value, list):
            parser.add_argument(flag, nargs="+", default=value)
        else:
            parser.add_argument(flag, default=value)
    parser.add_argument(
        "--regime-lag",
        type=int,
        default=1,
        help="GEX regime lag in observations; 0 = same-day (look-ahead, comparison only)",
    )
    parser.add_argument("--output", default=output_default)
    return parser.parse_args()


def newey_west_diff(returns, is_a, max_lags: Optional[int] = None) -> Optional[dict]:
    """Mean return difference between two regimes with a Newey-West (HAC) standard error.

    ``returns`` holds the returns of the days in either regime, in date order, and ``is_a``
    flags the days in the first regime. Daily returns are autocorrelated and regimes are
    persistent, so the Welch t-test overstates significance. Days outside both regimes are
    dropped before calling, so gaps between non-adjacent days are ignored (an approximation).
    """
    import statsmodels.api as sm

    y = np.asarray(returns, dtype=float)
    flag = np.asarray(is_a, dtype=float)
    if flag.sum() < 10 or (1 - flag).sum() < 10:
        return None
    lags = max_lags if max_lags is not None else int(np.floor(4 * (len(y) / 100) ** (2 / 9)))
    fit = sm.OLS(y, sm.add_constant(flag)).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {
        "diff_mean": round(float(fit.params[1]), 6),
        "t_statistic": round(float(fit.tvalues[1]), 3),
        "p_value": round(float(fit.pvalues[1]), 4),
        "maxlags": lags,
    }


def paired_return_test(baseline_returns, overlay_returns) -> Optional[dict]:
    """Newey-West test that the overlay's mean daily return differs from the baseline's.

    Both strategies trade the same days, so the paired difference removes common market
    moves. This tests mean return, not Sharpe; with similar volatility the two agree.
    """
    import pandas as pd
    import statsmodels.api as sm

    diff = (pd.Series(overlay_returns) - pd.Series(baseline_returns)).dropna()
    diff = diff[np.isfinite(diff)]
    if len(diff) < 30 or float(diff.std()) == 0.0:
        return None
    lags = int(np.floor(4 * (len(diff) / 100) ** (2 / 9)))
    fit = sm.OLS(diff.to_numpy(), np.ones(len(diff))).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags}
    )
    return {
        "mean_daily_diff": round(float(fit.params[0]), 7),
        "t_statistic": round(float(fit.tvalues[0]), 3),
        "p_value": round(float(fit.pvalues[0]), 4),
        "n_days": int(len(diff)),
        "maxlags": lags,
    }
