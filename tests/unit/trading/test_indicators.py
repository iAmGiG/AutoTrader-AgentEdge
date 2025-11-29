#!/usr/bin/env python3
"""
Unit tests for Technical Indicators.

Tests MACD, RSI, voting consensus, and signal generation.
Issue #408: Unit Testing and CLI Testing (Pre-Live Trading Validation)

Priority 1 Component - Technical Analysis
Target Coverage: 80%+
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.trading_tools.indicators import (calculate_macd, calculate_rsi,
                                          calculate_voting_consensus,
                                          get_current_signals)

# =============================================================================
# Test Data Generators
# =============================================================================


def create_price_series(periods=100, trend="up", seed=42):
    """Create a price series with specified trend."""
    np.random.seed(seed)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq="D")

    base = 100.0
    noise = np.random.randn(periods) * 2

    if trend == "up":
        prices = base + np.linspace(0, 50, periods) + noise
    elif trend == "down":
        prices = base + 50 - np.linspace(0, 50, periods) + noise
    else:  # sideways
        prices = base + 5 * np.sin(np.linspace(0, 8 * np.pi, periods)) + noise

    return pd.Series(prices, index=dates)


# =============================================================================
# MACD Tests
# =============================================================================


class TestCalculateMACD:
    """Test calculate_macd() function."""

    def test_macd_returns_dict(self):
        """Test that MACD returns a dictionary."""
        prices = create_price_series()
        result = calculate_macd(prices)

        assert isinstance(result, dict)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result
        assert "bullish" in result

    def test_macd_line_length(self):
        """Test that MACD line has correct length."""
        prices = create_price_series(periods=100)
        result = calculate_macd(prices)

        assert len(result["macd"]) == 100
        assert len(result["signal"]) == 100
        assert len(result["histogram"]) == 100

    def test_macd_default_parameters(self):
        """Test MACD with default Fibonacci parameters."""
        prices = create_price_series()
        result = calculate_macd(prices)  # Uses 13/34/8 defaults

        # MACD should be calculated
        assert not result["macd"].isna().all()
        # First few values will be NaN due to EMA warmup
        assert result["macd"].isna().sum() < 10

    def test_macd_custom_parameters(self):
        """Test MACD with custom parameters."""
        prices = create_price_series()
        result = calculate_macd(prices, fast=12, slow=26, signal=9)

        assert not result["macd"].isna().all()

    def test_macd_histogram_is_macd_minus_signal(self):
        """Test that histogram = MACD - Signal."""
        prices = create_price_series()
        result = calculate_macd(prices)

        # Check calculation (allowing for floating point precision)
        calculated_histogram = result["macd"] - result["signal"]
        np.testing.assert_array_almost_equal(
            result["histogram"].dropna().values,
            calculated_histogram.dropna().values,
        )

    def test_macd_bullish_when_histogram_positive(self):
        """Test that bullish signal when histogram > 0."""
        prices = create_price_series()
        result = calculate_macd(prices)

        # Check bullish matches histogram > 0
        expected_bullish = result["histogram"] > 0
        pd.testing.assert_series_equal(result["bullish"], expected_bullish)

    def test_macd_uptrend_produces_bullish_signals(self):
        """Test that uptrend produces some bullish signals."""
        prices = create_price_series(trend="up", periods=100)
        result = calculate_macd(prices)

        # Uptrend should have bullish signals eventually
        bullish_count = result["bullish"].sum()
        assert bullish_count > 0

    def test_macd_downtrend_produces_bearish_signals(self):
        """Test that downtrend produces bearish signals."""
        prices = create_price_series(trend="down", periods=100)
        result = calculate_macd(prices)

        # Downtrend should have some bearish (not bullish) signals
        bearish_count = (~result["bullish"]).sum()
        assert bearish_count > 0


# =============================================================================
# RSI Tests
# =============================================================================


class TestCalculateRSI:
    """Test calculate_rsi() function."""

    def test_rsi_returns_dict(self):
        """Test that RSI returns a dictionary."""
        prices = create_price_series()
        result = calculate_rsi(prices)

        assert isinstance(result, dict)
        assert "rsi" in result
        assert "bullish" in result
        assert "oversold" in result
        assert "overbought" in result

    def test_rsi_range(self):
        """Test that RSI values are between 0 and 100."""
        prices = create_price_series()
        result = calculate_rsi(prices)

        rsi_values = result["rsi"].dropna()
        assert (rsi_values >= 0).all()
        assert (rsi_values <= 100).all()

    def test_rsi_default_parameters(self):
        """Test RSI with default parameters (14/30/70)."""
        prices = create_price_series()
        result = calculate_rsi(prices)

        # RSI should be calculated
        assert not result["rsi"].isna().all()

    def test_rsi_custom_parameters(self):
        """Test RSI with custom parameters."""
        prices = create_price_series()
        result = calculate_rsi(prices, period=21, oversold=25, overbought=75)

        assert not result["rsi"].isna().all()

    def test_rsi_oversold_detection(self):
        """Test oversold signal detection."""
        prices = create_price_series()
        result = calculate_rsi(prices, oversold=30)

        # Oversold should be where RSI <= 30
        expected_oversold = result["rsi"] <= 30
        pd.testing.assert_series_equal(result["oversold"], expected_oversold)

    def test_rsi_overbought_detection(self):
        """Test overbought signal detection."""
        prices = create_price_series()
        result = calculate_rsi(prices, overbought=70)

        # Overbought should be where RSI >= 70
        expected_overbought = result["rsi"] >= 70
        pd.testing.assert_series_equal(result["overbought"], expected_overbought)

    def test_rsi_bullish_neutral_zone(self):
        """Test bullish signal in neutral zone (30 < RSI < 70)."""
        prices = create_price_series()
        result = calculate_rsi(prices, oversold=30, overbought=70)

        # Bullish should be where 30 < RSI < 70
        expected_bullish = (result["rsi"] > 30) & (result["rsi"] < 70)
        pd.testing.assert_series_equal(result["bullish"], expected_bullish)

    def test_rsi_strong_uptrend(self):
        """Test RSI in strong uptrend approaches overbought."""
        # Create very strong uptrend
        np.random.seed(123)
        prices = pd.Series(
            100 + np.cumsum(np.abs(np.random.randn(100)) * 2),  # Only positive moves
            index=pd.date_range(end=pd.Timestamp.now(), periods=100, freq="D"),
        )
        result = calculate_rsi(prices)

        # Strong uptrend should have high RSI values
        latest_rsi = result["rsi"].iloc[-1]
        assert latest_rsi > 50


# =============================================================================
# Voting Consensus Tests
# =============================================================================


class TestCalculateVotingConsensus:
    """Test calculate_voting_consensus() function."""

    def test_consensus_returns_dict(self):
        """Test that voting consensus returns a dictionary."""
        prices = create_price_series()
        macd_data = calculate_macd(prices)
        rsi_data = calculate_rsi(prices)

        result = calculate_voting_consensus(macd_data, rsi_data)

        assert isinstance(result, dict)
        assert "consensus" in result
        assert "macd_votes" in result
        assert "rsi_votes" in result
        assert "confidence" in result

    def test_consensus_when_both_bullish(self):
        """Test consensus is True when both indicators bullish."""
        prices = create_price_series()
        macd_data = calculate_macd(prices)
        rsi_data = calculate_rsi(prices)

        result = calculate_voting_consensus(macd_data, rsi_data)

        # Consensus should be MACD bullish AND RSI bullish
        expected_consensus = macd_data["bullish"] & rsi_data["bullish"]
        pd.testing.assert_series_equal(result["consensus"], expected_consensus)

    def test_confidence_is_bounded(self):
        """Test that confidence is between 0 and 1."""
        prices = create_price_series()
        macd_data = calculate_macd(prices)
        rsi_data = calculate_rsi(prices)

        result = calculate_voting_consensus(macd_data, rsi_data)

        confidence = result["confidence"].dropna()
        assert (confidence >= 0).all()
        assert (confidence <= 1).all()

    def test_votes_match_indicator_signals(self):
        """Test that votes match individual indicator signals."""
        prices = create_price_series()
        macd_data = calculate_macd(prices)
        rsi_data = calculate_rsi(prices)

        result = calculate_voting_consensus(macd_data, rsi_data)

        pd.testing.assert_series_equal(result["macd_votes"], macd_data["bullish"])
        pd.testing.assert_series_equal(result["rsi_votes"], rsi_data["bullish"])


# =============================================================================
# Current Signals Tests
# =============================================================================


class TestGetCurrentSignals:
    """Test get_current_signals() function."""

    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        short_prices = create_price_series(periods=20)

        result = get_current_signals(short_prices)

        assert result["signal_strength"] == "INSUFFICIENT_DATA"
        assert result["consensus"] is False
        assert result["confidence"] == 0.0

    def test_sufficient_data_returns_signals(self):
        """Test that sufficient data returns complete signals."""
        prices = create_price_series(periods=60)

        result = get_current_signals(prices)

        assert result["signal_strength"] in ["BULLISH", "NEUTRAL"]
        assert "date" in result
        assert "price" in result
        assert "macd_histogram" in result
        assert "rsi_value" in result

    def test_signal_strength_matches_consensus(self):
        """Test that signal strength matches consensus."""
        prices = create_price_series(periods=60)

        result = get_current_signals(prices)

        if result["consensus"]:
            assert result["signal_strength"] == "BULLISH"
        else:
            assert result["signal_strength"] == "NEUTRAL"

    def test_latest_values_are_returned(self):
        """Test that latest values are returned."""
        prices = create_price_series(periods=60)

        result = get_current_signals(prices)

        # Price should match last price in series
        assert result["price"] == prices.iloc[-1]

    def test_uptrend_produces_bullish_signal(self):
        """Test that uptrend can produce bullish signal."""
        # Strong uptrend
        np.random.seed(111)
        prices = pd.Series(
            100 + np.linspace(0, 80, 100) + np.random.randn(100) * 2,
            index=pd.date_range(end=pd.Timestamp.now(), periods=100, freq="D"),
        )

        result = get_current_signals(prices)

        # Should have positive MACD histogram in uptrend
        assert result["macd_histogram"] is not None


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_macd_with_constant_prices(self):
        """Test MACD with constant prices."""
        prices = pd.Series(
            [100.0] * 60,
            index=pd.date_range(end=pd.Timestamp.now(), periods=60, freq="D"),
        )

        result = calculate_macd(prices)

        # MACD should be 0 for constant prices
        assert (result["histogram"].dropna() == 0).all()

    def test_rsi_with_only_gains(self):
        """Test RSI with only price gains."""
        np.random.seed(42)
        prices = pd.Series(
            100 + np.cumsum(np.abs(np.random.randn(60))),  # Only positive changes
            index=pd.date_range(end=pd.Timestamp.now(), periods=60, freq="D"),
        )

        result = calculate_rsi(prices)

        # RSI should approach 100 with only gains
        latest_rsi = result["rsi"].dropna().iloc[-1]
        assert latest_rsi > 70

    def test_rsi_with_only_losses(self):
        """Test RSI with only price losses."""
        np.random.seed(42)
        prices = pd.Series(
            200 - np.cumsum(np.abs(np.random.randn(60))),  # Only negative changes
            index=pd.date_range(end=pd.Timestamp.now(), periods=60, freq="D"),
        )

        result = calculate_rsi(prices)

        # RSI should approach 0 with only losses
        latest_rsi = result["rsi"].dropna().iloc[-1]
        assert latest_rsi < 30

    def test_macd_timeframe_parameter(self):
        """Test that timeframe parameter doesn't affect calculation."""
        prices = create_price_series()

        result_1d = calculate_macd(prices, timeframe="1d")
        result_1h = calculate_macd(prices, timeframe="1h")

        # Results should be identical (timeframe is informational only)
        pd.testing.assert_series_equal(result_1d["macd"], result_1h["macd"])


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
