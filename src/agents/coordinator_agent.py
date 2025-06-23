"""Coordinator Agent module.

This agent coordinates the SentimentAgent and TechnicalAgent
and exposes an API to fetch combined signals.
"""

from typing import Any, Dict
import asyncio

from .base_agent import BaseAgent
from .sentiment_agent import SentimentAgent
from .tech_agent import TechAgent


class CoordinatorAgent(BaseAgent):
    """Agent that orchestrates SentimentAgent and TechnicalAgent."""

    def __init__(self, name: str = "CoordinatorAgent", memory_system: Any = None):
        super().__init__(name=name, tools=[], memory_system=memory_system)
        self.sentiment = SentimentAgent()
        self.technical = TechAgent()

    def generate_reply(self, messages, context=None):
        """Trivial implementation to satisfy BaseAgent abstract method."""
        return ""

    async def get_signals(self, date: str, symbol: str) -> Dict[str, Any]:
        """Return sentiment and technical signals for a symbol on a date."""
        prompt = f"analyse {symbol} on {date}"
        try:
            # Call sentiment agent (may be sync or async)
            sentiment_resp = self.sentiment.generate_reply(
                [{"role": "user", "content": prompt}]
            )
            if asyncio.iscoroutine(sentiment_resp):
                sentiment_resp = await sentiment_resp

            # Call technical agent
            tech_resp = self.technical.generate_reply(
                [{"role": "user", "content": prompt}]
            )
            if asyncio.iscoroutine(tech_resp):
                tech_resp = await tech_resp

            # Expect each to return a dict
            return {"ok": True, "sentiment": sentiment_resp, "technical": tech_resp}

        except Exception as e:
            return {"ok": False, "error": str(e)}
