"""Coordinator Agent module.

This agent coordinates the SentimentAgent and TechnicalAgent
and exposes an API to fetch combined signals.
"""

from typing import Any, Dict, Tuple
import json
from datetime import datetime

from .base_agent import BaseAgent
from .sentiment_agent import SentimentAgent  # Using enhanced version with VXX fallback
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
        signals, _ = await self.get_signals_with_reasoning(date, symbol)
        return signals

    async def get_signals_with_reasoning(self, date: str, symbol: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Return both extracted signals and raw LLM responses with full reasoning.

        Returns:
            tuple: (signals_dict, raw_responses_dict)
                - signals_dict: Processed signals with ok/error status
                - raw_responses_dict: Raw LLM responses including tool calls and full analysis
        """
        # More explicit prompts to trigger tool usage and return structured data
        sentiment_prompt = f"""Analyze market sentiment for {symbol} around {date}.

1. Use the fetch_all_news tool to get recent news about {symbol} 
2. Analyze the sentiment of the news articles
3. Provide your analysis including:
   - Key news themes and their sentiment impact
   - Overall sentiment score (-1 to 1)
   - Confidence level in your assessment
   - Any notable events or announcements

Return a JSON object with:
- 'score': average sentiment score (-1 to 1)
- 'analysis': your detailed sentiment analysis
- 'confidence': confidence level (0-1)
- 'key_themes': list of main themes found"""

        tech_prompt = f"""Perform technical analysis for {symbol} around {date}.

1. Use the fetch_market_data tool to get price data for {symbol}
2. Calculate MACD indicators
3. Analyze the technical patterns including:
   - MACD values and trends
   - Price action patterns
   - Volume analysis if available
   - Technical outlook

Return a JSON object with:
- 'macd_today': current MACD value
- 'macd_yest': previous MACD value
- 'analysis': your detailed technical analysis
- 'pattern': any identified patterns
- 'signal_strength': strength of technical signals"""

        try:
            # Build proper system prompts for each agent
            sentiment_system = getattr(self.sentiment, 'config', {}).get("system_prompt",
                                                                         "You are a sentiment analysis agent. Analyze news and market sentiment.")

            tech_system = "You are a technical analysis agent. Calculate technical indicators and provide MACD values."

            # Call sentiment agent using enhanced async method to get full response
            sentiment_resp, sentiment_full = await self._call_agent_with_full_response(
                self.sentiment,
                sentiment_prompt,
                sentiment_system
            )

            # Call technical agent using enhanced async method to get full response
            tech_resp, tech_full = await self._call_agent_with_full_response(
                self.technical,
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
                        json_str = val_clean[start_idx:end_idx + 1]
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

            # Prepare signals dictionary (same as before)
            signals = {"ok": True, "sentiment": sentiment_dict,
                       "technical": tech_dict}

            # Prepare raw responses with full LLM reasoning
            raw_responses = {
                "timestamp": datetime.now().isoformat(),
                "date": date,
                "symbol": symbol,
                "sentiment": {
                    "raw_response": sentiment_full.get("response", sentiment_resp),
                    "tools_called": sentiment_full.get("tools_called", []),
                    "parsed_data": sentiment_dict,
                    "analysis": sentiment_dict.get("analysis", "No detailed analysis captured")
                },
                "technical": {
                    "raw_response": tech_full.get("response", tech_resp),
                    "tools_called": tech_full.get("tools_called", []),
                    "parsed_data": tech_dict,
                    "analysis": tech_dict.get("analysis", "No detailed analysis captured")
                }
            }

            return signals, raw_responses

        except Exception as e:
            error_response = {"ok": False, "error": str(e)}
            empty_raw = {
                "timestamp": datetime.now().isoformat(),
                "date": date,
                "symbol": symbol,
                "error": str(e)
            }
            return error_response, empty_raw

    async def _call_agent_with_full_response(self, agent: BaseAgent, prompt: str, system_prompt: str) -> Tuple[str, Dict[str, Any]]:
        """Call an agent and return both the processed response and full details.

        Returns:
            tuple: (processed_response, full_details)
                - processed_response: The extracted/processed response string
                - full_details: Dictionary with response, tools_called, etc.
        """
        # Store the original process_with_tools_async method response
        processed_response = await agent.process_with_tools_async(
            prompt,
            system_prompt
        )

        # For now, we'll create a structure for the full response
        # In a full implementation, we'd modify BaseAgent to expose more details
        full_details = {
            "response": processed_response,
            "tools_called": [],  # Would be populated from agent's tool call history
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent.name,
            "prompt": prompt,
            "system_prompt": system_prompt
        }

        # Note: To fully capture tool calls and intermediate reasoning,
        # we would need to enhance BaseAgent.process_with_tools_async
        # to return more detailed information about the LLM interaction

        return processed_response, full_details
