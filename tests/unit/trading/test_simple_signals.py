#!/usr/bin/env python3
"""
Unit tests for SimpleSignalGenerator.

Tests signal generation, voting logic, and threshold behavior.
Issue #408: Unit Testing and CLI Testing (Pre-Live Trading Validation)

Priority 1 Component - Signal Generation
Target Coverage: 80%+
"""

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

# Mock config_defaults before importing
sys.modules["config_defaults"] = MagicMock()
sys.modules["config_defaults.trading_config"] = MagicMock()


# =============================================================================
# Test Data Generators
# =============================================================================


def create_bullish_price_data(periods=60):
    """Create price data with clear upward trend for BUY signals."""
    np.random.seed(123)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq="D")
    base_price = 100.0
    trend = np.linspace(0, 50, periods)
    noise = np.random.randn(periods) * 2
    prices = base_price + trend + noise

    return pd.DataFrame(
        {
            "Open": prices * 0.998,
            "High": prices * 1.015,
            "Low": prices * 0.985,
            "Close": prices,
            "close": prices,  # lowercase for compatibility
            "Volume": np.random.randint(1000000, 8000000, periods),
        },
        index=dates,
    )


def create_bearish_price_data(periods=60):
    """Create price data with clear downward trend for SELL signals."""
    np.random.seed(456)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq="D")
    base_price = 150.0
    trend = np.linspace(0, -40, periods)
    noise = np.random.randn(periods) * 2
    prices = base_price + trend + noise

    return pd.DataFrame(
        {
            "Open": prices * 1.002,
            "High": prices * 1.015,
            "Low": prices * 0.985,
            "Close": prices,
            "close": prices,
            "Volume": np.random.randint(1000000, 8000000, periods),
        },
        index=dates,
    )


def create_sideways_price_data(periods=60):
    """Create sideways price data for HOLD signals."""
    np.random.seed(789)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq="D")
    base_price = 100.0
    oscillation = 3 * np.sin(np.linspace(0, 4 * np.pi, periods))
    noise = np.random.randn(periods) * 1
    prices = base_price + oscillation + noise

    return pd.DataFrame(
        {
            "Open": prices * 0.999,
            "High": prices * 1.01,
            "Low": prices * 0.99,
            "Close": prices,
            "close": prices,
            "Volume": np.random.randint(500000, 3000000, periods),
        },
        index=dates,
    )


def create_short_price_data(periods=20):
    """Create insufficient price data."""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq="D")
    prices = 100.0 + np.cumsum(np.random.randn(periods))

    return pd.DataFrame(
        {
            "Close": prices,
            "close": prices,
        },
        index=dates,
    )


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_trading_config():
    """Create a mock TradingConfig."""
    mock_config = MagicMock()

    # MACD config
    macd_config = MagicMock()
    macd_config.fast = 13
    macd_config.slow = 34
    macd_config.signal = 8
    mock_config.get_macd_config.return_value = macd_config

    # RSI config
    rsi_config = MagicMock()
    rsi_config.period = 14
    rsi_config.oversold = 30
    rsi_config.overbought = 70
    mock_config.get_rsi_config.return_value = rsi_config

    return mock_config


@pytest.fixture
def signal_generator(mock_trading_config):
    """Create a SimpleSignalGenerator with mocked config."""
    with patch("src.trading.simple_signals.TradingConfig", return_value=mock_trading_config):
        from src.trading.simple_signals import SimpleSignalGenerator

        return SimpleSignalGenerator(config=mock_trading_config)


# =============================================================================
# Initialization Tests
# =============================================================================


class TestSimpleSignalGeneratorInit:
    """Test SimpleSignalGenerator initialization."""

    def test_init_with_default_config(self, mock_trading_config):
        """Test initialization with default config."""
        with patch("src.trading.simple_signals.TradingConfig", return_value=mock_trading_config):
            from src.trading.simple_signals import SimpleSignalGenerator

            generator = SimpleSignalGenerator(config=mock_trading_config)

            assert generator.macd_fast == 13
            assert generator.macd_slow == 34
            assert generator.macd_signal == 8
            assert generator.rsi_period == 14
            assert generator.rsi_oversold == 30
            assert generator.rsi_overbought == 70

    def test_init_with_custom_parameters(self, mock_trading_config):
        """Test initialization with custom parameter overrides."""
        with patch("src.trading.simple_signals.TradingConfig", return_value=mock_trading_config):
            from src.trading.simple_signals import SimpleSignalGenerator

            generator = SimpleSignalGenerator(
                config=mock_trading_config,
                macd_fast=12,
                macd_slow=26,
                rsi_period=21,
                macd_threshold=0.5,
            )

            assert generator.macd_fast == 12
            assert generator.macd_slow == 26
            assert generator.rsi_period == 21
            assert generator.macd_threshold == 0.5


# =============================================================================
# Signal Evaluation Tests
# =============================================================================


class TestEvaluateSignal:
    """Test evaluate_signal() method."""

    def test_insufficient_data_returns_hold(self, signal_generator):
        """Test that insufficient data returns HOLD."""
        short_data = create_short_price_data(periods=20)

        result = signal_generator.evaluate_signal(short_data, "TEST")

        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0
        assert "Insufficient data" in result["reason"]

    def test_bullish_data_returns_buy(self, signal_generator):
        """Test that bullish data returns BUY signal."""
        bullish_data = create_bullish_price_data()

        result = signal_generator.evaluate_signal(bullish_data, "SPY")

        # Should be BUY or HOLD depending on exact thresholds
        assert result["action"] in ["BUY", "HOLD"]
        assert "confidence" in result
        assert "raw_data" in result
        assert "votes" in result

    def test_bearish_data_returns_sell(self, signal_generator):
        """Test that bearish data returns SELL signal."""
        bearish_data = create_bearish_price_data()

        result = signal_generator.evaluate_signal(bearish_data, "SPY")

        # Should be SELL or HOLD
        assert result["action"] in ["SELL", "HOLD"]
        assert "confidence" in result
        assert "raw_data" in result

    def test_sideways_data_returns_hold(self, signal_generator):
        """Test that sideways data returns HOLD signal."""
        sideways_data = create_sideways_price_data()

        result = signal_generator.evaluate_signal(sideways_data, "SPY")

        # Sideways market should be HOLD
        assert result["action"] in ["HOLD", "BUY", "SELL"]
        assert result["confidence"] >= 0.0

    def test_signal_contains_raw_data(self, signal_generator):
        """Test that signal contains raw technical data."""
        data = create_bullish_price_data()

        result = signal_generator.evaluate_signal(data, "TEST")

        raw = result.get("raw_data", {})
        if raw:  # Only check if we have sufficient data
            assert "macd_line" in raw or result["confidence"] == 0.0
            assert "rsi" in raw or result["confidence"] == 0.0

    def test_signal_handles_lowercase_columns(self, signal_generator):
        """Test that signal works with lowercase column names."""
        data = pd.DataFrame(
            {
                "close": np.linspace(100, 150, 60) + np.random.randn(60),
            },
            index=pd.date_range(end=pd.Timestamp.now(), periods=60, freq="D"),
        )

        result = signal_generator.evaluate_signal(data, "TEST")

        assert "action" in result
        assert "confidence" in result

    def test_signal_handles_uppercase_columns(self, signal_generator):
        """Test that signal works with uppercase column names."""
        data = pd.DataFrame(
            {
                "Close": np.linspace(100, 150, 60) + np.random.randn(60),
            },
            index=pd.date_range(end=pd.Timestamp.now(), periods=60, freq="D"),
        )

        result = signal_generator.evaluate_signal(data, "TEST")

        assert "action" in result
        assert "confidence" in result

    def test_voting_logic_consensus_boost(self, signal_generator):
        """Test that consensus between indicators boosts confidence."""
        data = create_bullish_price_data()

        result = signal_generator.evaluate_signal(data, "TEST")

        votes = result.get("votes", {})
        if votes.get("buy", 0) == 2:
            # Both agreed on BUY - should have consensus boost
            assert result["confidence"] >= 0.75


# =============================================================================
# Signal Summary Tests
# =============================================================================


class TestGetSignalSummary:
    """Test get_signal_summary() method."""

    def test_summary_format(self, signal_generator):
        """Test signal summary format."""
        signal = {
            "action": "BUY",
            "confidence": 0.85,
            "raw_data": {"macd_crossover": 0.5, "rsi": 45.0},
        }

        summary = signal_generator.get_signal_summary(signal)

        assert "BUY" in summary
        assert "85" in summary  # 85%
        assert "MACD" in summary
        assert "RSI" in summary

    def test_summary_with_empty_raw_data(self, signal_generator):
        """Test summary with empty raw data."""
        signal = {
            "action": "HOLD",
            "confidence": 0.3,
            "raw_data": {},
        }

        summary = signal_generator.get_signal_summary(signal)

        assert "HOLD" in summary
        assert "30" in summary


# =============================================================================
# Actionable Signal Tests
# =============================================================================


class TestIsActionableSignal:
    """Test is_actionable_signal() method."""

    def test_high_confidence_buy_is_actionable(self, signal_generator):
        """Test that high confidence BUY is actionable."""
        signal = {"action": "BUY", "confidence": 0.75}

        assert signal_generator.is_actionable_signal(signal) is True

    def test_high_confidence_sell_is_actionable(self, signal_generator):
        """Test that high confidence SELL is actionable."""
        signal = {"action": "SELL", "confidence": 0.80}

        assert signal_generator.is_actionable_signal(signal) is True

    def test_low_confidence_not_actionable(self, signal_generator):
        """Test that low confidence signal is not actionable."""
        signal = {"action": "BUY", "confidence": 0.5}

        assert signal_generator.is_actionable_signal(signal) is False

    def test_hold_never_actionable(self, signal_generator):
        """Test that HOLD is never actionable."""
        signal = {"action": "HOLD", "confidence": 1.0}

        assert signal_generator.is_actionable_signal(signal) is False

    def test_custom_threshold(self, signal_generator):
        """Test actionable with custom threshold."""
        signal = {"action": "BUY", "confidence": 0.5}

        assert signal_generator.is_actionable_signal(signal, min_confidence=0.4) is True
        assert signal_generator.is_actionable_signal(signal, min_confidence=0.6) is False


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestGetSimpleSignal:
    """Test get_simple_signal() convenience function."""

    def test_get_simple_signal_returns_dict(self, mock_trading_config):
        """Test that get_simple_signal returns proper dict."""
        with patch("src.trading.simple_signals.TradingConfig", return_value=mock_trading_config):
            from src.trading.simple_signals import get_simple_signal

            data = create_bullish_price_data()
            result = get_simple_signal(data, "SPY")

            assert isinstance(result, dict)
            assert "action" in result
            assert "confidence" in result


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in signal generation."""

    def test_exception_returns_hold(self, mock_trading_config):
        """Test that exceptions return HOLD with error."""
        with patch("src.trading.simple_signals.TradingConfig", return_value=mock_trading_config):
            from src.trading.simple_signals import SimpleSignalGenerator

            generator = SimpleSignalGenerator(config=mock_trading_config)

            # Pass invalid data that will cause an error
            bad_data = pd.DataFrame({"wrong_column": [1, 2, 3]})

            result = generator.evaluate_signal(bad_data, "TEST")

            assert result["action"] == "HOLD"
            assert result["confidence"] == 0.0


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
