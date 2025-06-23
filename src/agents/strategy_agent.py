from typing import Dict

from .base_agent import BaseAgent


class StrategyAgent(BaseAgent):
    """Simple rule-based trading agent.

    The agent receives aggregated signals from a coordinator and decides on a
    trading action. If the sentiment signal is positive and the technical
    analysis indicates a "go" signal, it returns a BUY order. Otherwise it
    returns a HOLD order.
    """

    def decide_trade(self, aggregated: Dict) -> Dict:
        """Return a trading decision based on aggregated signals.

        Parameters
        ----------
        aggregated : Dict
            Dictionary containing at least ``"sentiment"`` and ``"technical"``
            keys with sub-dictionaries.

        Returns
        -------
        Dict
            Order dictionary with action ("BUY" or "HOLD"), fixed quantity, and
            a reason string.
        """
        sent = aggregated.get("sentiment", {})
        tech = aggregated.get("technical", {})
        action = "BUY" if sent.get("score", 0) > 0 and tech.get("go") else "HOLD"
        return {"action": action, "qty": 100, "reason": "rule_v0"}
