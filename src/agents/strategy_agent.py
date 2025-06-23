from typing import Dict
from .base_agent import BaseAgent


class StrategyAgent(BaseAgent):
    """Simple rule-based trading agent.

    This agent is purely rule-based. It receives aggregated signals from a
    coordinator and decides on a trading action. If the sentiment signal is
    positive and the technical analysis indicates a "go" signal, it returns a
    BUY order. Otherwise it returns a HOLD order.
    """

    def __init__(self, name: str = "StrategyAgent", memory_system=None):
        super().__init__(name=name, tools=[], memory_system=memory_system)

    def decide_trade(self, aggregated: Dict) -> Dict:
        """Return a trading decision based on aggregated signals."""
        sent = aggregated.get("sentiment", {})
        tech = aggregated.get("technical", {})
        action = "BUY" if sent.get("score", 0) > 0 and tech.get("go") else "HOLD"
        return {"action": action, "qty": 100, "reason": "rule_v0"}

    def generate_reply(self, messages, context=None):
        """StrategyAgent does not support chat-based interactions."""
        raise NotImplementedError("StrategyAgent is rule based and not chat-driven")
