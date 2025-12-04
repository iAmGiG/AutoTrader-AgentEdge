#!/usr/bin/env python3
"""
Voter Agent - Fully parameterizable MACD+RSI voting functionality
Properly implemented using base_agent.py inheritance with flexible parameter testing
"""

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config_defaults.trading_config import TradingConfig

from ..core.base_agent import BaseAgent

# Agent Bus for event publishing (Issue #390)
from ..orchestration.agent_bus import EventType, create_message, get_agent_bus
from src.trading.instruments.indicators import calculate_macd, calculate_rsi
from src.utils.agent_utils import load_agent_config

logger = logging.getLogger(__name__)


class VoterAgent(BaseAgent):
    """
    Fully parameterizable trading decision agent using MACD+RSI voting.

    Key features:
    - Accepts custom MACD/RSI parameters for testing
    - Preserves validated logic that achieved 0.856 Sharpe
    - Can be reconfigured on the fly for A/B testing
    - Not a fixed calculator - truly reusable agent
    """

    def __init__(
        self,
        name: str = "voter_agent",
        timeframe: Optional[str] = None,
        macd_params: Optional[Dict[str, int]] = None,
        rsi_params: Optional[Dict[str, int]] = None,
        voting_thresholds: Optional[Dict[str, float]] = None,
        use_config_file: bool = True,
        **kwargs,
    ):
        """
        Initialize parameterizable voter agent.

        Args:
            name: Agent identifier
            timeframe: Timeframe for analysis (5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M). Default: 1d
            macd_params: Override MACD parameters {"fast": 13, "slow": 34, "signal": 8}
            rsi_params: Override RSI parameters {"period": 14, "oversold": 30, "overbought": 70}
            voting_thresholds: Override decision thresholds {"macd_threshold": 0.1, "consensus_boost": 0.15}
            use_config_file: Whether to load from config file as fallback
            **kwargs: Additional BaseAgent parameters
        """
        super().__init__(name=name, **kwargs)

        # Load from config file if requested
        if use_config_file:
            self.config = TradingConfig()
            default_macd = self.config.get_macd_config()
            default_rsi = self.config.get_rsi_config()

            # Load timeframe from config or use provided
            timeframe_config = self.config.get_timeframe_config()
            config_timeframe = timeframe_config.default
            self.timeframe = timeframe or config_timeframe

            # Convert config objects to dicts
            self.macd_params = macd_params or {
                "fast": default_macd.fast,
                "slow": default_macd.slow,
                "signal": default_macd.signal,
            }
            self.rsi_params = rsi_params or {
                "period": default_rsi.period,
                "oversold": default_rsi.oversold,
                "overbought": default_rsi.overbought,
            }
        else:
            # Use provided params or hardcoded defaults
            self.timeframe = timeframe or "1d"
            self.macd_params = macd_params or {"fast": 13, "slow": 34, "signal": 8}
            self.rsi_params = rsi_params or {"period": 14, "oversold": 30, "overbought": 70}

        # Validate timeframe
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]
        if self.timeframe not in valid_timeframes:
            logger.warning(
                f"Invalid timeframe '{self.timeframe}', defaulting to '1d'. "
                f"Valid options: {valid_timeframes}"
            )
            self.timeframe = "1d"

        # Voting thresholds (can be tuned for optimization)
        self.voting_thresholds = voting_thresholds or {
            "macd_threshold": 0.1,  # Histogram threshold for signal
            "consensus_boost": 0.15,  # Confidence boost for consensus
            "weak_signal_boost": 0.1,  # Confidence boost for weak signals
            "min_data_points": 42,  # Minimum data for reliable signals
        }

        # Track configuration for logging
        self.current_config = {
            "timeframe": self.timeframe,
            "macd": self.macd_params.copy(),
            "rsi": self.rsi_params.copy(),
            "thresholds": self.voting_thresholds.copy(),
        }

        # Agent Bus for event publishing
        self._bus = get_agent_bus()
        self._publish_events = True  # Can be disabled for backtesting

        logger.info(f"VoterAgent '{name}' initialized with:")
        logger.info(f"  Timeframe: {self.timeframe}")
        logger.info(
            f"  MACD({self.macd_params['fast']}/{self.macd_params['slow']}/{self.macd_params['signal']})"
        )
        logger.info(
            f"  RSI({self.rsi_params['period']}) [{self.rsi_params['oversold']}/{self.rsi_params['overbought']}]"
        )

    def reconfigure(
        self,
        timeframe: Optional[str] = None,
        macd_params: Optional[Dict[str, int]] = None,
        rsi_params: Optional[Dict[str, int]] = None,
        voting_thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Reconfigure agent parameters on the fly for testing.

        This allows dynamic parameter testing without recreating the agent.

        Args:
            timeframe: New timeframe (5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            macd_params: New MACD parameters
            rsi_params: New RSI parameters
            voting_thresholds: New voting thresholds
        """
        if timeframe:
            valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]
            if timeframe in valid_timeframes:
                self.timeframe = timeframe
                self.current_config["timeframe"] = self.timeframe
            else:
                logger.warning(
                    f"Invalid timeframe '{timeframe}' ignored. Valid options: {valid_timeframes}"
                )

        if macd_params:
            self.macd_params.update(macd_params)
            self.current_config["macd"] = self.macd_params.copy()

        if rsi_params:
            self.rsi_params.update(rsi_params)
            self.current_config["rsi"] = self.rsi_params.copy()

        if voting_thresholds:
            self.voting_thresholds.update(voting_thresholds)
            self.current_config["thresholds"] = self.voting_thresholds.copy()

        logger.info(f"VoterAgent reconfigured: {self.current_config}")

    def evaluate_voting(  # noqa: C901  # noqa: C901
        self, symbol: str, price_data: pd.DataFrame, return_components: bool = False
    ) -> Dict[str, Any]:
        """
        Core MACD+RSI voting logic with current parameters.

        Args:
            symbol: Stock symbol being evaluated
            price_data: DataFrame with price data (must have 'close' or 'Close' column)
            return_components: If True, return individual indicator signals

        Returns:
            Trading decision with confidence and reasoning
        """
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

            # Calculate MACD with current parameters
            macd_data = calculate_macd(
                prices,
                fast=self.macd_params["fast"],
                slow=self.macd_params["slow"],
                signal=self.macd_params["signal"],
            )

            # Calculate RSI with current parameters
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

            # VOTING LOGIC (preserved from validated system)
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
                "timeframe": self.timeframe,  # Issue #365: Explicit timeframe in results
                "current_price": float(prices.iloc[-1]),
                "parameters_used": self.current_config,
            }

            # Publish voting complete event via bus
            if self._publish_events and action != "HOLD":
                self._publish_voting_result(symbol, result)

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
            logger.error(f"Error in evaluate_voting for {symbol}: {e}")
            return {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": 0.0,
                "position_size": 0.0,
                "reasoning": f"Analysis error: {str(e)}",
                "error": str(e),
                "parameters_used": self.current_config,
            }

    def _publish_voting_result(self, symbol: str, result: dict) -> None:
        """Publish voting result to the agent bus."""
        try:
            msg = create_message(
                source_agent=self.name,
                event_type=EventType.VOTING_COMPLETE,
                symbol=symbol,
                payload={
                    "action": result["action"],
                    "confidence": result["confidence"],
                    "position_size": result["position_size"],
                    "signal_type": result["signal_type"],
                    "reasoning": result["reasoning"],
                },
            )
            self._bus.publish_sync(msg)
            logger.debug(f"Published voting result for {symbol}: {result['action']}")
        except Exception as e:
            logger.warning(f"Failed to publish voting result: {e}")

    def set_publish_events(self, enabled: bool) -> None:
        """Enable or disable event publishing (useful for backtesting)."""
        self._publish_events = enabled

    def generate_reply(self, messages, context=None) -> str:  # noqa: C901
        """
        AutoGen's required method for handling incoming messages.
        Can accept parameter overrides in the message.

        Expected message format for parameter override:
        {
            "command": "evaluate",
            "symbol": "AAPL",
            "override_params": {
                "macd": {"fast": 8, "slow": 21, "signal": 5},
                "rsi": {"period": 21, "oversold": 25, "overbought": 75}
            }
        }
        """
        if not messages:
            return json.dumps({"error": "No messages to process"})

        # Get the latest message
        latest_message = messages[-1]
        if hasattr(latest_message, "content"):
            content = latest_message.content
        else:
            content = str(latest_message)

        # Try to parse as JSON for structured commands
        try:
            if isinstance(content, str):
                command_data = json.loads(content)
            else:
                command_data = content

            # Check for parameter overrides
            if "override_params" in command_data:
                overrides = command_data["override_params"]
                if "macd" in overrides:
                    self.reconfigure(macd_params=overrides["macd"])
                if "rsi" in overrides:
                    self.reconfigure(rsi_params=overrides["rsi"])
                if "thresholds" in overrides:
                    self.reconfigure(voting_thresholds=overrides["thresholds"])

            # Get evaluation parameters
            symbol = command_data.get("symbol", "UNKNOWN")
            return_components = command_data.get("return_components", True)

            # Fetch market data if not provided
            if "price_data" in command_data:
                price_data = pd.DataFrame(command_data["price_data"])
            else:
                # Use tool to fetch data
                return self._fetch_and_evaluate(symbol, return_components)

            # Evaluate with current parameters
            result = self.evaluate_voting(symbol, price_data, return_components)
            return json.dumps(result, indent=2)

        except json.JSONDecodeError:
            # Fallback to natural language processing
            # Load system prompt from YAML configuration
            agent_config = load_agent_config("agents")
            prompt_template = agent_config.get("voter_agent", {}).get("system_prompt", "")

            # Fallback to default if YAML not available
            if not prompt_template:
                prompt_template = """You are a parameterizable trading decision agent using MACD+RSI voting.

Current configuration:
- MACD: {macd}
- RSI: {rsi}
- Thresholds: {thresholds}

Your role:
1. Parse requests for trading analysis
2. Apply the configured MACD+RSI voting logic
3. Return structured trading decisions

Always return results in JSON format with action, confidence, and reasoning."""

            system_prompt = prompt_template.format(
                macd=self.macd_params, rsi=self.rsi_params, thresholds=self.voting_thresholds
            )

            return self.process_with_tools(content, system_prompt)

    def _fetch_and_evaluate(self, symbol: str, return_components: bool = True) -> str:
        """
        Fetch market data and evaluate using tools.
        """
        try:
            # Use the unified market data tool through base agent
            _ = self.process_with_tools(
                f"Fetch 60 days of price data for {symbol} and calculate MACD and RSI signals",
                "You are fetching market data for technical analysis.",
            )

            # Parse the tool result and evaluate
            # This would need proper parsing of the tool response
            return json.dumps(
                {
                    "symbol": symbol,
                    "action": "HOLD",
                    "confidence": 0.0,
                    "reasoning": "Data fetch in progress",
                    "note": "Implement full tool integration for production",
                }
            )

        except Exception as e:
            return json.dumps({"error": f"Failed to fetch and evaluate: {str(e)}"})

    def get_current_configuration(self) -> Dict[str, Any]:
        """Return current parameter configuration."""
        return self.current_config.copy()

    def reset_to_defaults(self, use_config_file: bool = True) -> None:
        """Reset parameters to defaults."""
        if use_config_file and hasattr(self, "config"):
            default_macd = self.config.get_macd_config()
            default_rsi = self.config.get_rsi_config()

            self.macd_params = {
                "fast": default_macd.fast,
                "slow": default_macd.slow,
                "signal": default_macd.signal,
            }
            self.rsi_params = {
                "period": default_rsi.period,
                "oversold": default_rsi.oversold,
                "overbought": default_rsi.overbought,
            }
        else:
            self.macd_params = {"fast": 13, "slow": 34, "signal": 8}
            self.rsi_params = {"period": 14, "oversold": 30, "overbought": 70}

        self.voting_thresholds = {
            "macd_threshold": 0.1,
            "consensus_boost": 0.15,
            "weak_signal_boost": 0.1,
            "min_data_points": 42,
        }

        self.current_config = {
            "macd": self.macd_params.copy(),
            "rsi": self.rsi_params.copy(),
            "thresholds": self.voting_thresholds.copy(),
        }

        logger.info(f"VoterAgent reset to defaults: {self.current_config}")


def create_voter_agent(name: str = "voter_agent", **kwargs) -> VoterAgent:
    """Factory function to create a properly configured voter agent."""
    return VoterAgent(name=name, **kwargs)
