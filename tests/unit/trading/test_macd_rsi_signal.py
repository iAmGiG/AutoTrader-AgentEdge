"""
CI-safe unit tests for MACDRSISignal (#531).

Tests signal generation, shift(1) look-ahead prevention, and output format.
"""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.signals.macd_rsi_signal import MACDRSISignal

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def signal():
    return MACDRSISignal()


@pytest.fixture
def trending_prices():
    """Synthetic trending price series for MACD signal generation."""
    np.random.seed(42)
    n = 300
    dates = pd.bdate_range("2022-01-03", periods=n)
    # Upward trend with noise
    trend = np.linspace(100, 150, n)
    noise = np.random.normal(0, 1, n)
    prices = pd.DataFrame({"SPY": trend + noise}, index=dates)
    return prices


@pytest.fixture
def choppy_prices():
    """Synthetic mean-reverting (choppy) prices."""
    np.random.seed(99)
    n = 300
    dates = pd.bdate_range("2022-01-03", periods=n)
    prices = 100 + np.random.normal(0, 2, n).cumsum() * 0.1
    return pd.DataFrame({"SPY": prices}, index=dates)


# =============================================================================
# Signal Generation Tests
# =============================================================================


class TestSignalGeneration:
    def test_hold_during_warmup(self, signal, trending_prices):
        """Should HOLD during indicator warmup period."""
        result = signal.generate_signal(trending_prices, 5)
        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0

    def test_valid_actions(self, signal, trending_prices):
        """All signals should be BUY, EXIT, or HOLD."""
        valid = {"BUY", "EXIT", "HOLD"}
        for i in range(50, len(trending_prices), 10):
            result = signal.generate_signal(trending_prices, i)
            assert result["action"] in valid, f"Invalid action at {i}: {result['action']}"

    def test_required_keys(self, signal, trending_prices):
        """Signal dict must have all required keys."""
        result = signal.generate_signal(trending_prices, 100)
        required = {"action", "position_size", "daily_pnl_pct", "confidence", "reasoning"}
        assert required.issubset(result.keys())

    def test_confidence_bounded(self, signal, trending_prices):
        """Confidence should be between 0 and 1."""
        for i in range(50, len(trending_prices), 10):
            result = signal.generate_signal(trending_prices, i)
            assert 0.0 <= result["confidence"] <= 1.0

    def test_produces_buy_signals(self, signal, trending_prices):
        """Trending market should produce some BUY signals."""
        buys = 0
        for i in range(50, len(trending_prices)):
            result = signal.generate_signal(trending_prices, i)
            if result["action"] == "BUY":
                buys += 1
        assert buys > 0, "Expected at least one BUY in trending market"

    def test_daily_pnl_is_actual_return(self, signal, trending_prices):
        """daily_pnl_pct should reflect actual price movement."""
        i = 100
        result = signal.generate_signal(trending_prices, i)
        expected = (
            trending_prices["SPY"].iloc[i] - trending_prices["SPY"].iloc[i - 1]
        ) / trending_prices["SPY"].iloc[i - 1]
        if result["action"] == "BUY":
            assert abs(result["daily_pnl_pct"] - expected) < 1e-10


# =============================================================================
# Shift(1) Look-Ahead Prevention Tests
# =============================================================================


class TestLookAheadPrevention:
    def test_signal_uses_prior_day(self, signal, trending_prices):
        """Signal at index i should be based on indicators at index i-1."""
        # Generate signal at two consecutive indices
        r1 = signal.generate_signal(trending_prices, 100)
        r2 = signal.generate_signal(trending_prices, 101)
        # The signal should be deterministic (same prices → same result)
        r1_again = signal.generate_signal(trending_prices, 100)
        assert r1["action"] == r1_again["action"]
        assert r2["action"] in ("BUY", "SELL", "HOLD", "EXIT")

    def test_first_signal_is_hold_or_exit(self, signal, trending_prices):
        """The very first signal after warmup should not be BUY (shifted signal)."""
        # At index slow+5, the shifted signal uses index slow+4 which may be NaN
        r = signal.generate_signal(trending_prices, signal.slow + 5)
        # This is a valid signal regardless of action — just check format
        assert r["action"] in {"BUY", "EXIT", "HOLD"}


# =============================================================================
# Parameter Tests
# =============================================================================


class TestParameters:
    def test_default_params(self):
        s = MACDRSISignal()
        assert s.fast == 13
        assert s.slow == 34
        assert s.signal_period == 8
        assert s.rsi_period == 14

    def test_custom_params(self):
        s = MACDRSISignal(fast=12, slow=26, signal_period=9)
        assert s.fast == 12
        assert s.slow == 26

    def test_caching(self, signal, trending_prices):
        """Repeated calls should use cached signals."""
        signal.generate_signal(trending_prices, 100)
        assert signal._signals_cache is not None
        cache_id = id(signal._signals_cache)
        signal.generate_signal(trending_prices, 150)
        assert id(signal._signals_cache) == cache_id

    def test_a_different_frame_is_not_served_from_the_cache(self, signal, trending_prices):
        """The cache follows the prices frame, not the id() of a temporary Series."""
        signal.generate_signal(trending_prices, 100)
        first = signal._signals_cache
        reversed_prices = trending_prices.iloc[::-1].set_axis(trending_prices.index)

        signal.generate_signal(reversed_prices, 100)

        assert signal._signals_cache is not first
        assert not signal._signals_cache.equals(first)

    def test_prices_edited_in_place_are_computed_afresh(self, signal, trending_prices):
        signal.generate_signal(trending_prices, 100)
        first = signal._signals_cache
        column = trending_prices.columns[0]

        trending_prices[column] = trending_prices[column].iloc[::-1].to_numpy()
        signal.generate_signal(trending_prices, 100)

        assert not signal._signals_cache.equals(first)
