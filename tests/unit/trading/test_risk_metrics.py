"""
CI-safe unit tests for risk_metrics module (#543).

Tests VaR, CVaR, Cornish-Fisher, and ES/VaR ratio on known distributions.
"""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from src.backtesting.risk_metrics import (
    calculate_all_risk_metrics,
    calculate_cornish_fisher_var,
    calculate_cvar,
    calculate_es_var_ratio,
    calculate_parametric_var,
    calculate_var,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def normal_returns():
    """Large sample of normally distributed returns."""
    np.random.seed(42)
    return pd.Series(np.random.normal(0.0005, 0.01, 10000))


@pytest.fixture
def fat_tail_returns():
    """Student-t distributed returns (df=3, heavy tails)."""
    np.random.seed(42)
    raw = stats.t.rvs(df=3, size=10000)
    return pd.Series(raw * 0.01)  # scale to ~1% daily vol


@pytest.fixture
def short_returns():
    """Very short return series."""
    return pd.Series([0.01, -0.02])


# =============================================================================
# VaR Tests
# =============================================================================


class TestVaR:
    def test_var_positive(self, normal_returns):
        """VaR should be a positive number (magnitude of loss)."""
        var = calculate_var(normal_returns)
        assert var > 0

    def test_var_approximately_correct_normal(self, normal_returns):
        """For normal returns, VaR should be close to z * sigma."""
        var = calculate_var(normal_returns, confidence=0.95)
        expected = -(normal_returns.mean() + stats.norm.ppf(0.05) * normal_returns.std())
        assert abs(var - expected) < 0.002, f"VaR={var:.4f}, expected~{expected:.4f}"

    def test_var_empty_returns(self):
        """VaR of empty series should be 0."""
        assert calculate_var(pd.Series(dtype=float)) == 0.0

    def test_var_single_value(self):
        """VaR of single value should be 0."""
        assert calculate_var(pd.Series([0.01])) == 0.0

    def test_higher_confidence_higher_var(self, normal_returns):
        """99% VaR should exceed 95% VaR."""
        var_95 = calculate_var(normal_returns, 0.95)
        var_99 = calculate_var(normal_returns, 0.99)
        assert var_99 > var_95


# =============================================================================
# CVaR Tests
# =============================================================================


class TestCVaR:
    def test_cvar_exceeds_var(self, normal_returns):
        """CVaR >= VaR by construction."""
        var = calculate_var(normal_returns)
        cvar = calculate_cvar(normal_returns)
        assert cvar >= var - 1e-10

    def test_cvar_positive(self, normal_returns):
        """CVaR should be positive."""
        assert calculate_cvar(normal_returns) > 0

    def test_cvar_empty_returns(self):
        assert calculate_cvar(pd.Series(dtype=float)) == 0.0


# =============================================================================
# ES/VaR Ratio Tests
# =============================================================================


class TestESVaRRatio:
    def test_normal_ratio_approximately_1_26(self, normal_returns):
        """For normal distribution, ES/VaR ≈ 1.26 at 95% confidence."""
        ratio = calculate_es_var_ratio(normal_returns)
        assert ratio is not None
        assert 1.15 < ratio < 1.40, f"Expected ~1.26 for normal, got {ratio:.3f}"

    def test_fat_tail_ratio_exceeds_normal(self, fat_tail_returns):
        """Fat-tailed distribution should have ES/VaR > 1.26."""
        ratio = calculate_es_var_ratio(fat_tail_returns)
        assert ratio is not None
        assert ratio > 1.26, f"Expected > 1.26 for fat tails, got {ratio:.3f}"


# =============================================================================
# Parametric VaR Tests
# =============================================================================


class TestParametricVaR:
    def test_parametric_matches_historical_for_normal(self, normal_returns):
        """Parametric and historical VaR should be close for normal data."""
        p_var = calculate_parametric_var(normal_returns)
        h_var = calculate_var(normal_returns)
        assert abs(p_var - h_var) < 0.003, f"Parametric={p_var:.4f}, Historical={h_var:.4f}"

    def test_parametric_positive(self, normal_returns):
        assert calculate_parametric_var(normal_returns) > 0


# =============================================================================
# Cornish-Fisher Tests
# =============================================================================


class TestCornishFisher:
    def test_cf_close_to_parametric_for_normal(self, normal_returns):
        """For normal data (skew~0, kurtosis~0), CF ≈ parametric."""
        cf = calculate_cornish_fisher_var(normal_returns)
        p = calculate_parametric_var(normal_returns)
        assert abs(cf - p) < 0.003, f"CF={cf:.4f}, Parametric={p:.4f}"

    def test_cf_differs_for_fat_tails(self, fat_tail_returns):
        """CF should diverge from parametric for fat-tailed data."""
        cf = calculate_cornish_fisher_var(fat_tail_returns)
        p = calculate_parametric_var(fat_tail_returns)
        # Fat tails → CF should be larger (more conservative)
        assert cf != p

    def test_cf_fallback_short_series(self, short_returns):
        """Short series should fall back to parametric."""
        cf = calculate_cornish_fisher_var(short_returns)
        p = calculate_parametric_var(short_returns)
        assert cf == p


# =============================================================================
# All Metrics Tests
# =============================================================================


class TestAllMetrics:
    def test_all_keys_present(self, normal_returns):
        """calculate_all_risk_metrics should return all expected keys."""
        metrics = calculate_all_risk_metrics(normal_returns)
        expected_keys = {
            "historical_var",
            "cvar",
            "parametric_var",
            "cornish_fisher_var",
            "es_var_ratio",
            "n_obs",
            "mean_return",
            "std_return",
            "skewness",
            "kurtosis",
        }
        assert expected_keys == set(metrics.keys())

    def test_n_obs_correct(self, normal_returns):
        metrics = calculate_all_risk_metrics(normal_returns)
        assert metrics["n_obs"] == len(normal_returns)

    def test_skewness_near_zero_for_normal(self, normal_returns):
        metrics = calculate_all_risk_metrics(normal_returns)
        assert abs(metrics["skewness"]) < 0.1

    def test_kurtosis_near_zero_for_normal(self, normal_returns):
        """Excess kurtosis of normal distribution should be ~0."""
        metrics = calculate_all_risk_metrics(normal_returns)
        assert abs(metrics["kurtosis"]) < 0.2
