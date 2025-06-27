"""Coordinator Agent module.

This agent coordinates the SentimentAgent and TechnicalAgent
and exposes an API to fetch combined signals.
"""

from typing import Any, Dict
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
        # More explicit prompts to trigger tool usage and return structured data
        sentiment_prompt = f"Use the fetch_all_news tool to get recent news about {symbol} and analyze the sentiment. Focus on news around {date}. Return a JSON object with a 'score' field containing the average sentiment score."
        tech_prompt = f"Use the fetch_market_data tool to get price data for {symbol} around {date}. Calculate and return the MACD values. Return a JSON object with 'macd_today' and 'macd_yest' fields."
        try:
            # Build proper system prompts for each agent
            sentiment_system = getattr(self.sentiment, 'config', {}).get("system_prompt",
                                                                         "You are a sentiment analysis agent. Analyze news and market sentiment.")

            tech_system = "You are a technical analysis agent. Calculate technical indicators and provide MACD values."

            # Call sentiment agent using async method
            sentiment_resp = await self.sentiment.process_with_tools_async(
                sentiment_prompt,
                sentiment_system
            )

            # Call technical agent using async method
            tech_resp = await self.technical.process_with_tools_async(
                tech_prompt,
                tech_system
            )

            def _ensure_dict(val: Any) -> Dict[str, Any]:
                """Simple JSON parsing with error handling."""
                if isinstance(val, dict):
                    return val
                if isinstance(val, str):
                    # Remove markdown code blocks if present
                    val_clean = val.strip()
                    if val_clean.startswith("```json"):
                        val_clean = val_clean[7:]  # Remove ```json
                    elif val_clean.startswith("```"):
                        val_clean = val_clean[3:]  # Remove ```
                    if val_clean.endswith("```"):
                        val_clean = val_clean[:-3]  # Remove closing ```
                    val_clean = val_clean.strip()

                    # Try to find JSON object in the text
                    start_idx = val_clean.find('{')
                    end_idx = val_clean.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        json_str = val_clean[start_idx:end_idx+1]
                        try:
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict):
                                return parsed
                        except json.JSONDecodeError as e:
                            print(f"JSON parsing failed: {e}")
                            print(f"Actual response: {val}")
                # Return empty dict on any parsing error
                return {}

            sentiment_dict = _ensure_dict(sentiment_resp)
            tech_dict = _ensure_dict(tech_resp)

            # Extract MACD values from technical response
            if "latest_row" in tech_dict:
                latest = tech_dict["latest_row"]
                if "MACD" in latest:
                    tech_dict["macd_today"] = latest["MACD"]
                if "MACD_prev" in latest:
                    tech_dict["macd_yest"] = latest["MACD_prev"]

            return {"ok": True, "sentiment": sentiment_dict, "technical": tech_dict}

        except Exception as e:
            return {"ok": False, "error": str(e)}
