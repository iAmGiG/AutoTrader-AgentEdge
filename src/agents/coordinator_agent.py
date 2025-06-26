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
        # More explicit prompts to trigger tool usage and return structured data
        sentiment_prompt = f"Use the fetch_all_news tool to get recent news about {symbol} and analyze the sentiment. Focus on news around {date}. Return a JSON object with a 'score' field containing the average sentiment score."
        tech_prompt = f"Use the fetch_market_data tool to get price data for {symbol} around {date}. Calculate and return the MACD values. Return a JSON object with 'macd_today' and 'macd_yest' fields."
        try:
            # Call sentiment agent
            sentiment_resp = self.sentiment.generate_reply(
                [{"role": "user", "content": sentiment_prompt}]
            )
            if asyncio.iscoroutine(sentiment_resp):
                sentiment_resp = await sentiment_resp

            # Call technical agent
            tech_resp = self.technical.generate_reply(
                [{"role": "user", "content": tech_prompt}]
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
                            # If it's a string response, try to extract data from the text
                            import re
                            result = {}
                            
                            # Extract sentiment score
                            score_patterns = [
                                r'(?:Average Sentiment Score:|sentiment score:|Overall Sentiment Assessment:.*?)\s*([-.\d]+)',
                                r'"score":\s*([-.\d]+)',
                                r'sentiment.*?([-.\d]+)'
                            ]
                            for pattern in score_patterns:
                                score_match = re.search(pattern, val, re.IGNORECASE)
                                if score_match:
                                    result["score"] = float(score_match.group(1))
                                    break
                            
                            # Extract MACD values - handle both plain and JSON formats
                            macd_today_patterns = [
                                r'"macd_today":\s*([-.\d]+)',
                                r'macd_today[:"]\s*([-.\d]+)',
                                r'(?:MACD today|current MACD)[:"]\s*([-.\d]+)'
                            ]
                            macd_yest_patterns = [
                                r'"macd_yest":\s*([-.\d]+|null)',
                                r'macd_yest[:"]\s*([-.\d]+|null)',
                                r'(?:MACD yesterday|previous MACD)[:"]\s*([-.\d]+|null)'
                            ]
                            
                            for pattern in macd_today_patterns:
                                macd_today_match = re.search(pattern, val, re.IGNORECASE)
                                if macd_today_match:
                                    try:
                                        result["macd_today"] = float(macd_today_match.group(1))
                                    except ValueError:
                                        pass
                                    break
                                    
                            for pattern in macd_yest_patterns:
                                macd_yest_match = re.search(pattern, val, re.IGNORECASE)
                                if macd_yest_match and macd_yest_match.group(1) != 'null':
                                    try:
                                        result["macd_yest"] = float(macd_yest_match.group(1))
                                    except ValueError:
                                        pass
                                    break
                                
                            # Store raw response for debugging
                            result["raw_response"] = val
                            return result
                    # Return empty dict if we can't parse anything
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
