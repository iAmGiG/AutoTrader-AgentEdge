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
