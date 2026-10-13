"""
CI-safe unit tests for DispersionSignal (#545).

Tests realized correlation calculation, z-score, and signal generation
with synthetic data — no PostgreSQL required.
"""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.signals.dispersion_signal import DispersionSignal

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def signal():
    return DispersionSignal(correlation_lookback=60, zscore_lookback=120, entry_z=1.5, exit_z=0.5)


@pytest.fixture
def correlated_returns():
    """Synthetic returns with known correlation structure."""
    np.random.seed(42)
    n = 500
    dates = pd.bdate_range("2022-01-03", periods=n)

    # Common factor + idiosyncratic noise
    common = np.random.normal(0, 0.01, n)
    returns = pd.DataFrame(
        {
            "SPY": common + np.random.normal(0, 0.005, n),
            "XLF": 0.8 * common + np.random.normal(0, 0.008, n),
            "XLE": 0.6 * common + np.random.normal(0, 0.012, n),
            "XLK": 0.9 * common + np.random.normal(0, 0.004, n),
        },
        index=dates,
    )
    return returns


@pytest.fixture
def uncorrelated_returns():
    """Synthetic independent returns (low correlation)."""
    np.random.seed(99)
    n = 500
    dates = pd.bdate_range("2022-01-03", periods=n)
    returns = pd.DataFrame(
        {
            "SPY": np.random.normal(0, 0.01, n),
            "XLF": np.random.normal(0, 0.01, n),
            "XLE": np.random.normal(0, 0.01, n),
            "XLK": np.random.normal(0, 0.01, n),
        },
        index=dates,
    )
    return returns


# =============================================================================
# Realized Correlation Tests
# =============================================================================


class TestRealizedCorrelation:
    """Test rolling realized correlation calculation."""

    def test_high_correlation_detected(self, signal, correlated_returns):
        """Strongly correlated returns should produce high avg correlation."""
        corr = signal.calculate_realized_correlation(
            correlated_returns, "SPY", ["XLF", "XLE", "XLK"]
        )
        assert corr.mean() > 0.4, f"Expected high avg correlation, got {corr.mean():.3f}"

    def test_low_correlation_detected(self, signal, uncorrelated_returns):
        """Independent returns should produce low avg correlation."""
        corr = signal.calculate_realized_correlation(
            uncorrelated_returns, "SPY", ["XLF", "XLE", "XLK"]
        )
        assert abs(corr.mean()) < 0.3, f"Expected low avg correlation, got {corr.mean():.3f}"

    def test_correlation_bounded(self, signal, correlated_returns):
        """Realized correlation should be between -1 and 1."""
        corr = signal.calculate_realized_correlation(
            correlated_returns, "SPY", ["XLF", "XLE", "XLK"]
        )
        assert corr.dropna().min() >= -1.0
        assert corr.dropna().max() <= 1.0

    def test_output_length(self, signal, correlated_returns):
        """One value per day from the first full window (the window includes day t, #576)."""
        corr = signal.calculate_realized_correlation(
            correlated_returns, "SPY", ["XLF", "XLE", "XLK"]
        )
        expected_len = len(correlated_returns) - signal.correlation_lookback + 1
        assert len(corr) == expected_len


# =============================================================================
# Fit and Z-Score Tests
# =============================================================================


class TestFit:
    """Test fit() method and z-score computation."""

    def test_fit_returns_stats(self, signal, correlated_returns):
        """Fit should return correlation statistics."""
        stats = signal.fit(correlated_returns, "SPY", ["XLF", "XLE", "XLK"])
        expected_keys = {
            "mean_correlation",
            "std_correlation",
            "min_correlation",
            "max_correlation",
            "n_obs",
            "index",
            "components",
        }
        assert expected_keys.issubset(stats.keys())

    def test_zscore_computed_after_fit(self, signal, correlated_returns):
        """Z-score series should exist after fit."""
        signal.fit(correlated_returns, "SPY", ["XLF", "XLE", "XLK"])
        assert signal._zscore_series is not None
        assert signal._corr_series is not None

    def test_zscore_mean_near_zero(self, signal, correlated_returns):
        """Z-score should have mean near zero over full sample."""
        signal.fit(correlated_returns, "SPY", ["XLF", "XLE", "XLK"])
        zscores = signal._zscore_series.dropna()
        assert abs(zscores.mean()) < 1.0, f"Z-score mean should be ~0, got {zscores.mean():.3f}"


# =============================================================================
# Signal Generation Tests
# =============================================================================


class TestSignalGeneration:
    """Test generate_signal() logic."""

    def test_hold_without_fit(self, signal):
        """Should HOLD if model not fitted."""
        prices = pd.DataFrame({"SPY": [600] * 10}, index=pd.bdate_range("2024-01-02", periods=10))
        result = signal.generate_signal(prices, 5)
        assert result["action"] == "HOLD"

    def test_signal_has_required_keys(self, signal, correlated_returns):
        """Signal dict must have required keys."""
        signal.fit(correlated_returns, "SPY", ["XLF", "XLE", "XLK"])
        prices = pd.DataFrame(
            {"SPY": np.cumsum(correlated_returns["SPY"]) + 600},
            index=correlated_returns.index,
        )
        result = signal.generate_signal(prices, 300)
        required = {"action", "position_size", "daily_pnl_pct", "confidence", "reasoning"}
        assert required.issubset(result.keys())

    def test_valid_actions_only(self, signal, correlated_returns):
        """All generated actions should be valid."""
        signal.fit(correlated_returns, "SPY", ["XLF", "XLE", "XLK"])
        prices = pd.DataFrame(
            {"SPY": np.cumsum(correlated_returns["SPY"]) + 600},
            index=correlated_returns.index,
        )
        valid_actions = {"BUY", "SELL", "HOLD", "EXIT"}
        for i in range(200, len(prices), 20):
            result = signal.generate_signal(prices, i)
            assert (
                result["action"] in valid_actions
            ), f"Invalid action at idx {i}: {result['action']}"

    def test_confidence_bounded(self, signal, correlated_returns):
        """Confidence should be between 0 and 1."""
        signal.fit(correlated_returns, "SPY", ["XLF", "XLE", "XLK"])
        prices = pd.DataFrame(
            {"SPY": np.cumsum(correlated_returns["SPY"]) + 600},
            index=correlated_returns.index,
        )
        for i in range(200, len(prices), 20):
            result = signal.generate_signal(prices, i)
            assert 0.0 <= result["confidence"] <= 1.0
