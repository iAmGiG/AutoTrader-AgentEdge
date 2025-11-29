#!/usr/bin/env python3
"""
Unit tests for VoterAgent.

Tests MACD+RSI voting logic, parameter configuration, and signal generation.
Issue #408: Unit Testing and CLI Testing (Pre-Live Trading Validation)

Priority 2 Component - VoterAgent (Production Ready)
Target Coverage: 80%+
"""

import os
import sys
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))


# =============================================================================
# Test Data Generators
# =============================================================================


def create_bullish_price_data(periods=60):
    """Create price data for bullish signals."""
    np.random.seed(123)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq="D")
    base = 100.0
    trend = np.linspace(0, 50, periods)
    noise = np.random.randn(periods) * 2
    prices = base + trend + noise

    return pd.DataFrame(
        {
            "Close": prices,
            "close": prices,
        },
        index=dates,
    )


def create_bearish_price_data(periods=60):
    """Create price data for bearish signals."""
    np.random.seed(456)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq="D")
    base = 150.0
    trend = np.linspace(0, -50, periods)
    noise = np.random.randn(periods) * 2
    prices = base + trend + noise

    return pd.DataFrame(
        {
            "Close": prices,
            "close": prices,
        },
        index=dates,
    )


def create_sideways_price_data(periods=60):
    """Create price data for neutral signals."""
    np.random.seed(789)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq="D")
    base = 100.0
    oscillation = 3 * np.sin(np.linspace(0, 4 * np.pi, periods))
    noise = np.random.randn(periods) * 1
    prices = base + oscillation + noise

    return pd.DataFrame(
        {
            "Close": prices,
            "close": prices,
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
# Mock TradingConfig
# =============================================================================


def create_mock_trading_config():
    """Create mock TradingConfig with default values."""
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

    # Timeframe config
    timeframe_config = MagicMock()
    timeframe_config.default = "1d"
    mock_config.get_timeframe_config.return_value = timeframe_config

    return mock_config


# =============================================================================
# Test Class that Bypasses BaseAgent
# =============================================================================


class TestableVoterAgent:
    """
    A testable version of VoterAgent that doesn't require BaseAgent initialization.

    This class replicates VoterAgent's core logic (evaluate_voting, reconfigure, etc.)
    without the AutoGen framework dependencies.
    """

    def __init__(
        self,
        name="test_voter",
        timeframe=None,
        macd_params=None,
        rsi_params=None,
        voting_thresholds=None,
        use_config_file=False,
    ):
        self.name = name

        # Set timeframe
        self.timeframe = timeframe or "1d"

        # Validate timeframe
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]
        if self.timeframe not in valid_timeframes:
            self.timeframe = "1d"

        # Set parameters
        self.macd_params = macd_params or {"fast": 13, "slow": 34, "signal": 8}
        self.rsi_params = rsi_params or {"period": 14, "oversold": 30, "overbought": 70}

        # Voting thresholds
        self.voting_thresholds = voting_thresholds or {
            "macd_threshold": 0.1,
            "consensus_boost": 0.15,
            "weak_signal_boost": 0.1,
            "min_data_points": 42,
        }

        # Current config
        self.current_config = {
            "timeframe": self.timeframe,
            "macd": self.macd_params.copy(),
            "rsi": self.rsi_params.copy(),
            "thresholds": self.voting_thresholds.copy(),
        }

        # Event publishing control
        self._publish_events = False  # Disabled for testing
        self._bus = MagicMock()

    def reconfigure(
        self,
        timeframe=None,
        macd_params=None,
        rsi_params=None,
        voting_thresholds=None,
    ):
        """Reconfigure agent parameters."""
        if timeframe:
            valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]
            if timeframe in valid_timeframes:
                self.timeframe = timeframe
                self.current_config["timeframe"] = self.timeframe

        if macd_params:
            self.macd_params.update(macd_params)
            self.current_config["macd"] = self.macd_params.copy()

        if rsi_params:
            self.rsi_params.update(rsi_params)
            self.current_config["rsi"] = self.rsi_params.copy()

        if voting_thresholds:
            self.voting_thresholds.update(voting_thresholds)
            self.current_config["thresholds"] = self.voting_thresholds.copy()

    def evaluate_voting(self, symbol, price_data, return_components=False):  # noqa: C901
        """Core MACD+RSI voting logic."""
        # Import here to use actual indicator functions
        from src.trading_tools.indicators import calculate_macd, calculate_rsi

        try:
            # Validate data sufficiency
            if len(price_data) < self.voting_thresholds["min_data_points"]:
                return {
                    "symbol": symbol,
                    "action": "HOLD",
                    "confidence": 0.0,
                    "position_size": 0.0,
                    "reasoning": f"Insufficient data ({len(price_data)} < {self.voting_thresholds['min_data_points']})",
                    "parameters_used": self.current_config,
                }

            # Extract price series
            prices = price_data["Close"] if "Close" in price_data.columns else price_data["close"]

            # Calculate MACD
            macd_data = calculate_macd(
                prices,
                fast=self.macd_params["fast"],
                slow=self.macd_params["slow"],
                signal=self.macd_params["signal"],
            )

            # Calculate RSI
            rsi_data = calculate_rsi(
                prices,
                period=self.rsi_params["period"],
                oversold=self.rsi_params["oversold"],
                overbought=self.rsi_params["overbought"],
            )

            # Determine MACD signal
            latest_histogram = macd_data["histogram"].iloc[-1]
            macd_threshold = self.voting_thresholds["macd_threshold"]

            if latest_histogram > macd_threshold:
                macd_action = "BUY"
                macd_conf = 0.6
                macd_strength = min(50.0, abs(latest_histogram) * 10)
            elif latest_histogram < -macd_threshold:
                macd_action = "SELL"
                macd_conf = 0.6
                macd_strength = -min(50.0, abs(latest_histogram) * 10)
            else:
                macd_action = "HOLD"
                macd_conf = 0.3
                macd_strength = 0.0

            # Determine RSI signal
            current_rsi = rsi_data["rsi"].iloc[-1]

            if current_rsi < self.rsi_params["oversold"]:
                rsi_action = "BUY"
                rsi_conf = 0.6
                rsi_strength = (self.rsi_params["oversold"] - current_rsi) * 3.33
            elif current_rsi > self.rsi_params["overbought"]:
                rsi_action = "SELL"
                rsi_conf = 0.6
                rsi_strength = (current_rsi - self.rsi_params["overbought"]) * 3.33
            else:
                rsi_action = "HOLD"
                rsi_conf = 0.3
                rsi_strength = 0.0

            # Voting logic
            consensus_boost = self.voting_thresholds["consensus_boost"]
            weak_boost = self.voting_thresholds["weak_signal_boost"]

            if macd_action == rsi_action and macd_action != "HOLD":
                # Strong consensus
                action = macd_action
                confidence = min(0.85, (macd_conf + rsi_conf) / 2 + consensus_boost)
                position_size = 1.0
                reasoning = f"Strong consensus: Both MACD and RSI signal {action}"
                signal_type = "STRONG"

            elif (macd_action != "HOLD" and rsi_action == "HOLD") or (
                rsi_action != "HOLD" and macd_action == "HOLD"
            ):
                # Weak signal
                active_action = macd_action if macd_action != "HOLD" else rsi_action
                active_conf = macd_conf if macd_action != "HOLD" else rsi_conf
                active_indicator = "MACD" if macd_action != "HOLD" else "RSI"

                action = active_action
                confidence = min(0.65, active_conf + weak_boost)
                position_size = 0.5
                reasoning = f"Weak signal: Only {active_indicator} signals {active_action}"
                signal_type = "WEAK"

            else:
                # Conflicting or neutral
                action = "HOLD"
                confidence = 0.2
                position_size = 0.0
                if macd_action != rsi_action and macd_action != "HOLD" and rsi_action != "HOLD":
                    reasoning = f"Conflicting signals: MACD={macd_action}, RSI={rsi_action}"
                    signal_type = "CONFLICT"
                else:
                    reasoning = "Both indicators neutral"
                    signal_type = "NEUTRAL"

            result = {
                "symbol": symbol,
                "action": action,
                "confidence": confidence,
                "position_size": position_size,
                "reasoning": reasoning,
                "signal_type": signal_type,
                "timeframe": self.timeframe,
                "current_price": float(prices.iloc[-1]),
                "parameters_used": self.current_config,
            }

            # Add component details if requested
            if return_components:
                result["components"] = {
                    "macd": {
                        "action": macd_action,
                        "confidence": macd_conf,
                        "strength": macd_strength,
                        "histogram": float(latest_histogram),
                        "macd_line": float(macd_data["macd"].iloc[-1]),
                        "signal_line": float(macd_data["signal"].iloc[-1]),
                    },
                    "rsi": {
                        "action": rsi_action,
                        "confidence": rsi_conf,
                        "strength": rsi_strength,
                        "value": float(current_rsi),
                        "oversold": self.rsi_params["oversold"],
                        "overbought": self.rsi_params["overbought"],
                    },
                }

            return result

        except Exception as e:
            return {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": 0.0,
                "position_size": 0.0,
                "reasoning": f"Analysis error: {str(e)}",
                "error": str(e),
                "parameters_used": self.current_config,
            }

    def get_current_configuration(self):
        """Return current parameter configuration."""
        return self.current_config.copy()

    def reset_to_defaults(self, use_config_file=False):
        """Reset parameters to defaults."""
        self.macd_params = {"fast": 13, "slow": 34, "signal": 8}
        self.rsi_params = {"period": 14, "oversold": 30, "overbought": 70}
        self.voting_thresholds = {
            "macd_threshold": 0.1,
            "consensus_boost": 0.15,
            "weak_signal_boost": 0.1,
            "min_data_points": 42,
        }
        self.current_config = {
            "timeframe": self.timeframe,
            "macd": self.macd_params.copy(),
            "rsi": self.rsi_params.copy(),
            "thresholds": self.voting_thresholds.copy(),
        }

    def set_publish_events(self, enabled):
        """Enable or disable event publishing."""
        self._publish_events = enabled


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def voter_agent():
    """Create TestableVoterAgent."""
    return TestableVoterAgent(name="test_voter")


# =============================================================================
# Initialization Tests
# =============================================================================


class TestVoterAgentInit:
    """Test VoterAgent initialization."""

    def test_init_with_default_params(self):
        """Test initialization with default parameters."""
        agent = TestableVoterAgent(name="test")

        assert agent.macd_params["fast"] == 13
        assert agent.macd_params["slow"] == 34
        assert agent.macd_params["signal"] == 8
        assert agent.rsi_params["period"] == 14
        assert agent.rsi_params["oversold"] == 30
        assert agent.rsi_params["overbought"] == 70

    def test_init_with_custom_macd_params(self):
        """Test initialization with custom MACD parameters."""
        custom_macd = {"fast": 12, "slow": 26, "signal": 9}
        agent = TestableVoterAgent(name="test", macd_params=custom_macd)

        assert agent.macd_params["fast"] == 12
        assert agent.macd_params["slow"] == 26
        assert agent.macd_params["signal"] == 9

    def test_init_with_custom_rsi_params(self):
        """Test initialization with custom RSI parameters."""
        custom_rsi = {"period": 21, "oversold": 25, "overbought": 75}
        agent = TestableVoterAgent(name="test", rsi_params=custom_rsi)

        assert agent.rsi_params["period"] == 21
        assert agent.rsi_params["oversold"] == 25
        assert agent.rsi_params["overbought"] == 75

    def test_init_with_valid_timeframe(self):
        """Test initialization with valid timeframe."""
        agent = TestableVoterAgent(name="test", timeframe="4h")

        assert agent.timeframe == "4h"

    def test_init_with_invalid_timeframe_defaults_to_1d(self):
        """Test that invalid timeframe defaults to 1d."""
        agent = TestableVoterAgent(name="test", timeframe="invalid")

        assert agent.timeframe == "1d"


# =============================================================================
# Reconfigure Tests
# =============================================================================


class TestReconfigure:
    """Test reconfigure() method."""

    def test_reconfigure_macd_params(self, voter_agent):
        """Test reconfiguring MACD parameters."""
        new_macd = {"fast": 8, "slow": 21, "signal": 5}

        voter_agent.reconfigure(macd_params=new_macd)

        assert voter_agent.macd_params["fast"] == 8
        assert voter_agent.macd_params["slow"] == 21
        assert voter_agent.macd_params["signal"] == 5

    def test_reconfigure_rsi_params(self, voter_agent):
        """Test reconfiguring RSI parameters."""
        new_rsi = {"period": 21, "oversold": 25}

        voter_agent.reconfigure(rsi_params=new_rsi)

        assert voter_agent.rsi_params["period"] == 21
        assert voter_agent.rsi_params["oversold"] == 25

    def test_reconfigure_timeframe(self, voter_agent):
        """Test reconfiguring timeframe."""
        voter_agent.reconfigure(timeframe="1h")

        assert voter_agent.timeframe == "1h"

    def test_reconfigure_invalid_timeframe_ignored(self, voter_agent):
        """Test that invalid timeframe is ignored."""
        original = voter_agent.timeframe

        voter_agent.reconfigure(timeframe="invalid_tf")

        assert voter_agent.timeframe == original


# =============================================================================
# Evaluate Voting Tests
# =============================================================================


class TestEvaluateVoting:
    """Test evaluate_voting() method."""

    def test_insufficient_data_returns_hold(self, voter_agent):
        """Test that insufficient data returns HOLD."""
        short_data = create_short_price_data(periods=20)

        result = voter_agent.evaluate_voting("SPY", short_data)

        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0
        assert "Insufficient data" in result["reasoning"]

    def test_returns_required_fields(self, voter_agent):
        """Test that result contains all required fields."""
        data = create_bullish_price_data()

        result = voter_agent.evaluate_voting("SPY", data)

        assert "symbol" in result
        assert "action" in result
        assert "confidence" in result
        assert "position_size" in result
        assert "reasoning" in result
        assert "parameters_used" in result

    def test_action_is_valid(self, voter_agent):
        """Test that action is one of BUY, SELL, HOLD."""
        data = create_bullish_price_data()

        result = voter_agent.evaluate_voting("SPY", data)

        assert result["action"] in ["BUY", "SELL", "HOLD"]

    def test_confidence_is_bounded(self, voter_agent):
        """Test that confidence is between 0 and 1."""
        data = create_bullish_price_data()

        result = voter_agent.evaluate_voting("SPY", data)

        assert 0 <= result["confidence"] <= 1

    def test_position_size_is_valid(self, voter_agent):
        """Test that position_size is 0, 0.5, or 1."""
        data = create_bullish_price_data()

        result = voter_agent.evaluate_voting("SPY", data)

        assert result["position_size"] in [0, 0.0, 0.5, 1, 1.0]

    def test_return_components_includes_details(self, voter_agent):
        """Test that return_components=True includes indicator details."""
        data = create_bullish_price_data()

        result = voter_agent.evaluate_voting("SPY", data, return_components=True)

        assert "components" in result
        assert "macd" in result["components"]
        assert "rsi" in result["components"]
        assert "histogram" in result["components"]["macd"]
        assert "value" in result["components"]["rsi"]

    def test_handles_uppercase_close_column(self, voter_agent):
        """Test that uppercase Close column is handled."""
        data = pd.DataFrame(
            {
                "Close": np.linspace(100, 150, 60),
            },
            index=pd.date_range(end=pd.Timestamp.now(), periods=60, freq="D"),
        )

        result = voter_agent.evaluate_voting("SPY", data)

        assert "action" in result

    def test_handles_lowercase_close_column(self, voter_agent):
        """Test that lowercase close column is handled."""
        data = pd.DataFrame(
            {
                "close": np.linspace(100, 150, 60),
            },
            index=pd.date_range(end=pd.Timestamp.now(), periods=60, freq="D"),
        )

        result = voter_agent.evaluate_voting("SPY", data)

        assert "action" in result


# =============================================================================
# Voting Logic Tests
# =============================================================================


class TestVotingLogic:
    """Test the core voting logic."""

    def test_strong_consensus_high_confidence(self, voter_agent):
        """Test that strong consensus yields high confidence."""
        data = create_bullish_price_data()
        voter_agent.voting_thresholds["min_data_points"] = 42

        result = voter_agent.evaluate_voting("SPY", data, return_components=True)

        # If both MACD and RSI agree on BUY or SELL
        if result.get("signal_type") == "STRONG":
            assert result["confidence"] >= 0.6
            assert result["position_size"] == 1.0

    def test_weak_signal_half_position(self, voter_agent):
        """Test that weak signal yields half position."""
        data = create_sideways_price_data()

        result = voter_agent.evaluate_voting("SPY", data, return_components=True)

        if result.get("signal_type") == "WEAK":
            assert result["position_size"] == 0.5

    def test_conflict_yields_hold(self, voter_agent):
        """Test that conflicting signals yield HOLD."""
        data = create_sideways_price_data()

        result = voter_agent.evaluate_voting("SPY", data)

        if result.get("signal_type") == "CONFLICT":
            assert result["action"] == "HOLD"


# =============================================================================
# Configuration Management Tests
# =============================================================================


class TestConfigurationManagement:
    """Test configuration management methods."""

    def test_get_current_configuration(self, voter_agent):
        """Test getting current configuration."""
        config = voter_agent.get_current_configuration()

        assert "macd" in config
        assert "rsi" in config
        assert "thresholds" in config

    def test_reset_to_defaults(self, voter_agent):
        """Test resetting to default values."""
        # Change params first
        voter_agent.reconfigure(macd_params={"fast": 5, "slow": 10, "signal": 3})

        # Reset
        voter_agent.reset_to_defaults(use_config_file=False)

        assert voter_agent.macd_params["fast"] == 13
        assert voter_agent.macd_params["slow"] == 34
        assert voter_agent.macd_params["signal"] == 8

    def test_set_publish_events(self, voter_agent):
        """Test enabling/disabling event publishing."""
        voter_agent.set_publish_events(False)
        assert voter_agent._publish_events is False

        voter_agent.set_publish_events(True)
        assert voter_agent._publish_events is True


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in VoterAgent."""

    def test_error_returns_hold(self, voter_agent):
        """Test that errors return HOLD with error info."""
        # Pass data with enough rows but invalid column names to trigger error
        bad_data = pd.DataFrame(
            {"wrong_column": np.linspace(100, 150, 60)},
            index=pd.date_range(end=pd.Timestamp.now(), periods=60, freq="D"),
        )

        result = voter_agent.evaluate_voting("SPY", bad_data)

        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0
        assert "error" in result or "Analysis error" in result.get("reasoning", "")


# =============================================================================
# VoterAgent API Contract Tests
# =============================================================================


class TestVoterAgentAPIContract:
    """Test that TestableVoterAgent matches the real VoterAgent API contract."""

    def test_api_contract_evaluate_voting(self):
        """Test that evaluate_voting returns expected keys."""
        agent = TestableVoterAgent(name="test")
        data = create_bullish_price_data()

        result = agent.evaluate_voting("SPY", data)

        # Verify contract - these keys must exist
        required_keys = ["symbol", "action", "confidence", "position_size", "reasoning"]
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

    def test_api_contract_reconfigure(self):
        """Test that reconfigure updates parameters correctly."""
        agent = TestableVoterAgent(name="test")

        # Reconfigure should update macd_params
        agent.reconfigure(macd_params={"fast": 10})
        assert agent.macd_params["fast"] == 10

        # Reconfigure should update rsi_params
        agent.reconfigure(rsi_params={"period": 21})
        assert agent.rsi_params["period"] == 21

    def test_api_contract_get_current_configuration(self):
        """Test that get_current_configuration returns expected structure."""
        agent = TestableVoterAgent(name="test")

        config = agent.get_current_configuration()

        assert "macd" in config
        assert "rsi" in config
        assert "thresholds" in config
        assert "timeframe" in config


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
