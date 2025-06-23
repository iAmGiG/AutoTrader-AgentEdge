"""Placeholder coordinator agent."""

from .base_agent import BaseAgent


class CoordinatorAgent(BaseAgent):
    """Minimal coordinator agent that returns dummy signals."""

    def __init__(self, name: str = "CoordinatorAgent", memory_system=None):
        super().__init__(name=name, memory_system=memory_system)

    def get_signals(self, date_str: str, ticker: str):
        """Return stub signals for a given date and ticker."""
        return {"date": date_str, "ticker": ticker, "signal": "neutral"}
