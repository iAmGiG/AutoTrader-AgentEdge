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

    def get_signals(self, date: str, symbol: str) -> Dict[str, Any]:
        """Return sentiment and technical signals for a symbol on a date."""
        prompt = f"analyse {symbol} on {date}"
        try:
            sentiment_resp = self.sentiment.generate_reply([{"role": "user", "content": prompt}])
            tech_resp = self.technical.generate_reply([{"role": "user", "content": prompt}])

            # Expect these responses to be dicts containing "score" and "go" keys.
            sent_score = sentiment_resp.get("score") if isinstance(sentiment_resp, dict) else 0
            tech_go = tech_resp.get("go_flag") if isinstance(tech_resp, dict) else False

            return {"ok": True, "sentiment": {"score": sent_score}, "technical": {"go": tech_go}}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def generate_reply(self, messages, context=None):
        """Placeholder implementation to satisfy BaseAgent requirements."""
        raise NotImplementedError("CoordinatorAgent is orchestration-only")
