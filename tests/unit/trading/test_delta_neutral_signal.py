"""
CI-safe unit tests for DeltaNeutralSignal (#544).

Tests IV-RV spread signal logic with synthetic data — no PostgreSQL required.
"""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.signals.delta_neutral_signal import DeltaNeutralSignal

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def signal():
    return DeltaNeutralSignal(vol_spread_window=30, entry_threshold=0.02, exit_threshold=0.005)


@pytest.fixture
def signal_with_data(signal):
    """Signal with synthetic vol data loaded via mock DataFrame."""
    np.random.seed(42)
    n = 250
    dates = pd.bdate_range("2024-01-02", periods=n)
    # Simulate IV-HV spread that oscillates around 0
    spread = np.cumsum(np.random.normal(0, 0.003, n))
    signal._vol_data = pd.DataFrame(
        {
            "underlying_price": np.linspace(580, 600, n),
            "iv_hv_spread": spread,
            "hv": np.full(n, 0.15),
            "rv": np.full(n, 0.14),
            "regime": ["bullish_gamma"] * (n // 2) + ["bearish_gamma"] * (n - n // 2),
            "total_gex": np.full(n, 5e9),
            "iv_skew": np.full(n, -0.05),
            "put_call_ratio": np.full(n, 1.1),
        },
        index=dates,
    )
    return signal


# =============================================================================
# Initialization Tests
# =============================================================================


class TestInitialization:
    """Test signal constructor validation."""

    def test_valid_windows(self):
        for w in (10, 20, 30):
            s = DeltaNeutralSignal(vol_spread_window=w)
            assert s.spread_col == f"iv_hv_spread_{w}"

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError, match="10, 20, or 30"):
            DeltaNeutralSignal(vol_spread_window=15)

    def test_default_thresholds(self):
        s = DeltaNeutralSignal()
        assert s.entry_threshold == 0.02
        assert s.exit_threshold == 0.005


# =============================================================================
# Signal Generation Tests
# =============================================================================


class TestSignalGeneration:
    """Test generate_signal() logic with synthetic data."""

    def test_hold_without_data(self, signal):
        """Should HOLD if vol data not loaded."""
        prices = pd.DataFrame({"SPY": [600] * 10}, index=pd.bdate_range("2024-01-02", periods=10))
        result = signal.generate_signal(prices, 5)
        assert result["action"] == "HOLD"
        assert result["daily_pnl_pct"] == 0.0

    def test_sell_on_high_spread(self):
        """Should SELL vol when IV >> RV (spread above entry threshold)."""
        sig = DeltaNeutralSignal(entry_threshold=0.02, exit_threshold=0.005)
        dates = pd.bdate_range("2024-01-02", periods=10)
        sig._vol_data = pd.DataFrame(
            {
                "iv_hv_spread": [0.05] * 10,  # Well above 0.02 threshold
                "hv": [0.15] * 10,
                "rv": [0.10] * 10,
                "regime": ["bullish_gamma"] * 10,
                "total_gex": [5e9] * 10,
                "iv_skew": [-0.05] * 10,
                "put_call_ratio": [1.1] * 10,
                "underlying_price": [600] * 10,
            },
            index=dates,
        )
        prices = pd.DataFrame({"SPY": [600] * 10}, index=dates)
        result = sig.generate_signal(prices, 5)
        assert result["action"] == "SELL"
        assert "Short vol" in result["reasoning"]

    def test_buy_on_low_spread(self):
        """Should BUY vol when IV << RV (spread below negative entry threshold)."""
        sig = DeltaNeutralSignal(entry_threshold=0.02, exit_threshold=0.005)
        dates = pd.bdate_range("2024-01-02", periods=10)
        sig._vol_data = pd.DataFrame(
            {
                "iv_hv_spread": [-0.05] * 10,  # Well below -0.02 threshold
                "hv": [0.10] * 10,
                "rv": [0.15] * 10,
                "regime": ["bearish_gamma"] * 10,
                "total_gex": [-5e9] * 10,
                "iv_skew": [-0.08] * 10,
                "put_call_ratio": [1.3] * 10,
                "underlying_price": [580] * 10,
            },
            index=dates,
        )
        prices = pd.DataFrame({"SPY": [580] * 10}, index=dates)
        result = sig.generate_signal(prices, 5)
        assert result["action"] == "BUY"
        assert "Long vol" in result["reasoning"]

    def test_exit_on_reverted_spread(self):
        """Should EXIT when spread reverts near zero."""
        sig = DeltaNeutralSignal(entry_threshold=0.02, exit_threshold=0.005)
        dates = pd.bdate_range("2024-01-02", periods=10)
        sig._vol_data = pd.DataFrame(
            {
                "iv_hv_spread": [0.001] * 10,  # Within ±0.005
                "hv": [0.12] * 10,
                "rv": [0.12] * 10,
                "regime": ["neutral"] * 10,
                "total_gex": [0] * 10,
                "iv_skew": [-0.03] * 10,
                "put_call_ratio": [1.0] * 10,
                "underlying_price": [590] * 10,
            },
            index=dates,
        )
        prices = pd.DataFrame({"SPY": [590] * 10}, index=dates)
        result = sig.generate_signal(prices, 5)
        assert result["action"] == "EXIT"

    def test_hold_between_thresholds(self):
        """Should HOLD when spread is between exit and entry thresholds."""
        sig = DeltaNeutralSignal(entry_threshold=0.02, exit_threshold=0.005)
        dates = pd.bdate_range("2024-01-02", periods=10)
        sig._vol_data = pd.DataFrame(
            {
                "iv_hv_spread": [0.01] * 10,  # Between 0.005 and 0.02
                "hv": [0.12] * 10,
                "rv": [0.11] * 10,
                "regime": ["bullish_gamma"] * 10,
                "total_gex": [3e9] * 10,
                "iv_skew": [-0.04] * 10,
                "put_call_ratio": [1.05] * 10,
                "underlying_price": [595] * 10,
            },
            index=dates,
        )
        prices = pd.DataFrame({"SPY": [595] * 10}, index=dates)
        result = sig.generate_signal(prices, 5)
        assert result["action"] == "HOLD"

    def test_signal_has_required_keys(self, signal_with_data):
        """Signal dict must have action, position_size, daily_pnl_pct, confidence, reasoning."""
        prices = pd.DataFrame(
            {"SPY": signal_with_data._vol_data["underlying_price"].values},
            index=signal_with_data._vol_data.index,
        )
        result = signal_with_data.generate_signal(prices, 100)
        required = {"action", "position_size", "daily_pnl_pct", "confidence", "reasoning"}
        assert required.issubset(result.keys())

    def test_confidence_bounded(self, signal_with_data):
        """Confidence should be between 0 and 1."""
        prices = pd.DataFrame(
            {"SPY": signal_with_data._vol_data["underlying_price"].values},
            index=signal_with_data._vol_data.index,
        )
        for i in range(10, 200, 10):
            result = signal_with_data.generate_signal(prices, i)
            assert 0.0 <= result["confidence"] <= 1.0


# =============================================================================
# Spread Stats Tests
# =============================================================================


class TestSpreadStats:
    """Test calculate_spread_stats()."""

    def test_stats_without_data_raises(self, signal):
        with pytest.raises(RuntimeError, match="load_vol_data"):
            signal.calculate_spread_stats()

    def test_stats_keys(self, signal_with_data):
        stats = signal_with_data.calculate_spread_stats()
        expected = {
            "mean",
            "std",
            "min",
            "max",
            "median",
            "pct_positive",
            "pct_above_entry",
            "pct_below_neg_entry",
            "n_obs",
        }
        assert expected.issubset(stats.keys())

    def test_stats_n_obs_matches(self, signal_with_data):
        stats = signal_with_data.calculate_spread_stats()
        assert stats["n_obs"] == len(signal_with_data._vol_data)
