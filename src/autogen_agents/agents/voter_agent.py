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


from ..core.base_agent import BaseAgent

# Agent Bus for event publishing (Issue #390)
from ..orchestration.agent_bus import EventType, create_message, get_agent_bus
from src.trading.instruments.voting_signal import VotingSignal
from src.utils.agent_utils import load_agent_config

logger = logging.getLogger(__name__)


def _signal_attribute(name: str) -> property:
    """An agent attribute stored on its VotingSignal (self.signal)."""
    return property(
        lambda self: getattr(self.signal, name),
        lambda self, value: setattr(self.signal, name, value),
        doc=f"VotingSignal.{name}",
    )


class VoterAgent(BaseAgent):
    """
    Fully parameterizable trading decision agent using MACD+RSI voting.

    Key features:
    - Accepts custom MACD/RSI parameters for testing
    - Preserves the experiment 293 voting logic
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

        # The signal maths (parameters, both voting methods) lives in VotingSignal,
        # free of the agent framework (#606); this agent adds LLM replies and events
        self.signal = VotingSignal(
            timeframe=timeframe,
            macd_params=macd_params,
            rsi_params=rsi_params,
            voting_thresholds=voting_thresholds,
            use_config_file=use_config_file,
        )
        if use_config_file:
            self.config = self.signal.config

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

    # Signal parameters live on self.signal; these keep the agent's attributes working
    timeframe = _signal_attribute("timeframe")
    macd_params = _signal_attribute("macd_params")
    rsi_params = _signal_attribute("rsi_params")
    voting_thresholds = _signal_attribute("voting_thresholds")
    current_config = _signal_attribute("current_config")

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
        self.signal.reconfigure(
            timeframe=timeframe,
            macd_params=macd_params,
            rsi_params=rsi_params,
            voting_thresholds=voting_thresholds,
        )

    def evaluate_voting(
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
        result = self.signal.evaluate_voting(symbol, price_data, return_components)
        self._publish_if_actionable(symbol, result)
        return result

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

    def _publish_if_actionable(self, symbol: str, result: dict) -> None:
        """Publish a BUY/SELL decision to the agent bus, when events are on."""
        if self._publish_events and result.get("action") != "HOLD":
            self._publish_voting_result(symbol, result)

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
        return self.signal.get_current_configuration()

    def reset_to_defaults(self, use_config_file: bool = True) -> None:
        """Reset parameters to defaults."""
        self.signal.reset_to_defaults(use_config_file=use_config_file)

    def evaluate_ranked_voting(
        self, symbol: str, price_data: pd.DataFrame, return_components: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate voting using the indicator registry and ranked voter config.

        Issue #364: Ranked Voter System for Technical Indicators

        This method uses the pluggable indicator registry instead of hardcoded
        MACD/RSI calls. Active voters from RankedVoterManager participate in
        decisions, while review-only voters are shown but don't affect the outcome.

        Args:
            symbol: Stock symbol being evaluated
            price_data: DataFrame with price data (must have 'close' or 'Close' column)
            return_components: If True, return individual indicator signals

        Returns:
            Trading decision with confidence, reasoning, and all voter signals
        """
        result = self.signal.evaluate_ranked_voting(symbol, price_data, return_components)
        self._publish_if_actionable(symbol, result)
        return result


def create_voter_agent(name: str = "voter_agent", **kwargs) -> VoterAgent:
    """Factory function to create a properly configured voter agent."""
    return VoterAgent(name=name, **kwargs)
