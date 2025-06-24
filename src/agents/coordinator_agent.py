"""Coordinator Agent module.

This agent coordinates the SentimentAgent and TechnicalAgent
and exposes an API to fetch combined signals.
"""

from typing import Any, Dict
import asyncio
import json

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
            # Call sentiment agent
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

            def _ensure_dict(val: Any) -> Dict[str, Any]:
                    if isinstance(val, dict):
                        return val
                    if isinstance(val, str):
                        try:
                            parsed = json.loads(val)
                            if isinstance(parsed, dict):
                                return parsed
                        except json.JSONDecodeError:
                            pass
                    return {}

            sentiment_dict = _ensure_dict(sentiment_resp)
            tech_dict = _ensure_dict(tech_resp)

            return {"ok": True, "sentiment": sentiment_dict, "technical": tech_dict}

        except Exception as e:
            return {"ok": False, "error": str(e)}
