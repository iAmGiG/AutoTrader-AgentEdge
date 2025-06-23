"""Simple placeholder strategy agent."""

from .base_agent import BaseAgent


class StrategyAgent(BaseAgent):
    """Placeholder StrategyAgent implementation."""

    def __init__(self, name: str = "StrategyAgent", memory_system=None):
        super().__init__(name=name, memory_system=memory_system)

    def decide_trade(self, signals):
        """Return a dummy trade decision based on signals."""
        return {"decision": "hold", "signals": signals}
