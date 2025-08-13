"""
V2 Sentiment Agent: Market Fear Based (VXX Volatility)
Uses VXX ETF volatility data to gauge market fear-based sentiment

ARCHITECTURE: V2-V3 inherit from BaseAgent for LLM tool calling
- Use LLM to route and call VXX volatility tools
- Mechanical calculation of sentiment from VXX values
- No LLM decisions in final sentiment score (same as V1 pattern)
- VXX provides more stable volatility measure than VIX index
"""

import json
import logging
import traceback
from typing import Any
from datetime import datetime
import re

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SentimentV2Agent(BaseAgent):
    """
    V2: Market Fear-based Sentiment Agent

    Uses VXX (S&P 500 VIX Short-Term Futures ETN) to determine market sentiment
    High VXX = High fear = Bearish sentiment  
    Low VXX = Low fear = Bullish sentiment

    VXX provides more stable and reliable volatility data than VIX index directly.
    """

    def __init__(self, name: str = "SentimentV2Agent", memory_system=None):
        self.max_tool_rounds = 3
        from src.tools.tools import ALL_TOOLS
        super().__init__(name=name, tools=ALL_TOOLS, memory_system=memory_system)
        self.logger = logger

    def _extract_date_from_message(self, message: str) -> str:
        """Extract date from message using various patterns."""
        import re

        # Look for YYYY-MM-DD pattern
        date_pattern = r'\d{4}-\d{2}-\d{2}'
        matches = re.findall(date_pattern, message)
        if matches:
            return matches[0]

        # Look for "on [date]" pattern
        on_pattern = r'on (\d{4}-\d{2}-\d{2})'
        matches = re.findall(on_pattern, message)
        if matches:
            return matches[0]

        # Default to today if no date found
        return datetime.now().strftime("%Y-%m-%d")

    def process_tool_result(self, tool_name: str, result: Any, tool_args: dict) -> Any:
        """
        Process tool results with V2-specific handling for VXX data.
        V2 uses VXX volatility tool for mechanical sentiment calculation.

        Args:
            tool_name: The name of the tool that was called
            result: The raw result from the tool
            tool_args: The arguments that were passed to the tool

        Returns:
            Processed result in V2 sentiment format
        """
        try:
            print(f"V2 processing tool result for {tool_name}")

            # VXX Volatility Tool
            if tool_name == "fetch_vxx_volatility_data":
                if isinstance(result, dict):
                    # VXX tool returns complete sentiment analysis
                    # Convert to V2 format for consistency
                    sentiment = result.get("sentiment", 0.0)
                    confidence = result.get("confidence", 0.0)
                    reasoning = result.get("reasoning", "VXX volatility analysis")
                    vxx_data = result.get("vxx_data", {})

                    return {
                        "sentiment": sentiment,
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "version": "V2",
                        "mode": "vxx_volatility",
                        "vxx_value": vxx_data.get("vxx_value") if vxx_data else None,
                        "date_used": vxx_data.get("date_used") if vxx_data else None,
                        "interpretation": result.get("interpretation", "unknown")
                    }

                # Handle unexpected result format
                return {
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": f"Unexpected VXX tool result format: {type(result)}",
                    "version": "V2",
                    "mode": "vxx_volatility",
                    "error": "format_error"
                }

            # Default handling for other tools
            if isinstance(result, dict):
                return result
            else:
                return {"result": str(result), "tool": tool_name}

        except Exception as e:
            traceback.print_exc()
            print(f"Error in V2 process_tool_result: {str(e)}")
            return {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error processing {tool_name} result: {str(e)}",
                "version": "V2",
                "error": str(e)
            }

    def generate_reply(self, messages, context=None) -> str:
        """
        Generate VXX volatility-based sentiment response using LLM tool calling.

        V2 Pattern:
        - LLM calls VXX volatility tool to fetch market fear data
        - Mechanical calculation of sentiment from VXX values
        - No LLM decisions in final sentiment score

        Args:
            messages: Input messages (expects date and context)
            context: Optional context (not used)

        Returns:
            JSON string with VXX-based sentiment analysis
        """
        try:
            print(f"\n{self.name} processing request...")

            # Convert single message to list format
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            elif isinstance(messages, dict):
                messages = [messages]

            # Extract the most recent user message
            user_message = None
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break

            if not user_message:
                return json.dumps({
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": "No user message found to process",
                    "version": "V2",
                    "mode": "vxx_volatility"
                })

            # Extract date from message
            date = self._extract_date_from_message(user_message)
            symbol = "market"  # VXX is market-wide sentiment

            # Create system message for V2 behavior
            system_content = f"""You are a V2 Market Fear Sentiment Agent that uses VXX volatility data for sentiment analysis.

CRITICAL INSTRUCTIONS:
1. Call the fetch_vxx_volatility_data tool to get VXX volatility data for the requested date
2. The tool will return mechanical sentiment calculations based on VXX levels
3. Return the sentiment analysis in JSON format
4. You MUST use the VXX tool - do not attempt other sentiment analysis methods

Context: Analyzing market fear sentiment for {symbol} on {date}
Date to analyze: {date}

ALWAYS call fetch_vxx_volatility_data with symbol="{symbol}" and date="{date}"."""

            enhanced_messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_message}
            ]

            # Use BaseAgent's process_with_tools method
            user_msg = enhanced_messages[-1]['content']
            system_msg = enhanced_messages[0]['content']

            response = self.process_with_tools(user_msg, system_msg)

            # Ensure we have a valid JSON response
            if not response:
                response = json.dumps({
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": "No response generated from VXX analysis",
                    "version": "V2",
                    "mode": "vxx_volatility"
                })

            # Try to parse and validate the response
            try:
                # Look for JSON in the response
                json_match = re.search(r'\{[^}]+\}', response)
                if json_match:
                    json_data = json.loads(json_match.group())
                    # Ensure V2 version marking
                    json_data["version"] = "V2"
                    json_data["mode"] = "vxx_volatility"
                    response = json.dumps(json_data)
            except:
                # If parsing fails, wrap the response
                response = json.dumps({
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": f"V2 analysis complete: {response}",
                    "version": "V2",
                    "mode": "vxx_volatility"
                })

            logger.info(f"V2 Sentiment completed for {symbol} on {date}")
            return response

        except Exception as e:
            traceback.print_exc()
            error_msg = f"Error in {self.name}: {str(e)}"
            print(error_msg)
            return json.dumps({
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": error_msg,
                "version": "V2",
                "mode": "vxx_volatility",
                "error": str(e)
            })
