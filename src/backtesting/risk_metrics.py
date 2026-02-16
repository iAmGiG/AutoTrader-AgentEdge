"""
Research Risk Metrics: VaR, CVaR (Expected Shortfall), and Cornish-Fisher adjustment (#543).

Implements historical and parametric risk measures for regime-stratified analysis.
Separate from production risk_calculator.py — this module is for research backtesting.

References:
- Rockafellar & Uryasev (2000). "Optimization of Conditional Value-at-Risk."
- Basel FRTB guidelines (ES replaces VaR for market risk capital).
"""

from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats


def calculate_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historical Value at Risk.

    Args:
        returns: Daily return series.
        confidence: Confidence level (default 0.95 = 95% VaR).

    Returns:
        VaR as a positive number (magnitude of loss at the given percentile).
    """
    if len(returns) < 2:
        return 0.0
    clean = returns.dropna()
    if len(clean) < 2:
        return 0.0
    quantile = np.percentile(clean, (1 - confidence) * 100)
    return -float(quantile)


def calculate_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """Conditional Value at Risk (Expected Shortfall).

    Average loss in the worst (1-confidence) fraction of days.
    CVaR >= VaR by construction; the ratio reveals tail heaviness.

    Args:
        returns: Daily return series.
        confidence: Confidence level (default 0.95).

    Returns:
        CVaR as a positive number (average loss beyond VaR).
    """
    if len(returns) < 2:
        return 0.0
    clean = returns.dropna()
    if len(clean) < 2:
        return 0.0
    threshold = np.percentile(clean, (1 - confidence) * 100)
    tail_losses = clean[clean <= threshold]
    if len(tail_losses) == 0:
        return -float(threshold)
    return -float(tail_losses.mean())


def calculate_parametric_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Parametric (Gaussian) VaR.

    Assumes returns are normally distributed. Useful as a baseline to compare
    with historical VaR — divergence indicates fat tails.

    Args:
        returns: Daily return series.
        confidence: Confidence level.

    Returns:
        Parametric VaR as a positive number.
    """
    if len(returns) < 2:
        return 0.0
    clean = returns.dropna()
    if len(clean) < 2:
        return 0.0
    mu = clean.mean()
    sigma = clean.std()
    z = stats.norm.ppf(1 - confidence)
    return -float(mu + z * sigma)


def calculate_cornish_fisher_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Cornish-Fisher adjusted VaR.

    Adjusts the Gaussian z-score for skewness and excess kurtosis,
    capturing fat tails without a full distributional assumption.

    Args:
        returns: Daily return series.
        confidence: Confidence level.

    Returns:
        Cornish-Fisher VaR as a positive number.
    """
    if len(returns) < 10:
        return calculate_parametric_var(returns, confidence)
    clean = returns.dropna()
    if len(clean) < 10:
        return calculate_parametric_var(returns, confidence)

    mu = clean.mean()
    sigma = clean.std()
    s = float(stats.skew(clean))
    k = float(stats.kurtosis(clean))  # excess kurtosis
    z = stats.norm.ppf(1 - confidence)

    # Cornish-Fisher expansion
    z_cf = z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24 - (2 * z**3 - 5 * z) * s**2 / 36
    return -float(mu + z_cf * sigma)


def calculate_es_var_ratio(returns: pd.Series, confidence: float = 0.95) -> Optional[float]:
    """ES/VaR ratio — measures tail heaviness.

    For normal distributions, ES/VaR ≈ 1.26 at 95% confidence.
    Higher ratios indicate fatter tails (more tail risk than VaR suggests).

    Args:
        returns: Daily return series.
        confidence: Confidence level.

    Returns:
        ES/VaR ratio, or None if VaR is zero.
    """
    var = calculate_var(returns, confidence)
    cvar = calculate_cvar(returns, confidence)
    if var == 0:
        return None
    return cvar / var


def calculate_all_risk_metrics(returns: pd.Series, confidence: float = 0.95) -> dict:
    """Calculate all risk metrics in one call.

    Args:
        returns: Daily return series.
        confidence: Confidence level.

    Returns:
        Dict with all metrics.
    """
    clean = returns.dropna()
    var = calculate_var(clean, confidence)
    cvar = calculate_cvar(clean, confidence)
    p_var = calculate_parametric_var(clean, confidence)
    cf_var = calculate_cornish_fisher_var(clean, confidence)
    ratio = cvar / var if var > 0 else None

    result = {
        "historical_var": round(var, 6),
        "cvar": round(cvar, 6),
        "parametric_var": round(p_var, 6),
        "cornish_fisher_var": round(cf_var, 6),
        "es_var_ratio": round(ratio, 4) if ratio is not None else None,
        "n_obs": len(clean),
        "mean_return": round(float(clean.mean()), 6) if len(clean) > 0 else 0.0,
        "std_return": round(float(clean.std()), 6) if len(clean) > 0 else 0.0,
        "skewness": round(float(stats.skew(clean)), 4) if len(clean) > 2 else 0.0,
        "kurtosis": round(float(stats.kurtosis(clean)), 4) if len(clean) > 2 else 0.0,
    }
    return result
