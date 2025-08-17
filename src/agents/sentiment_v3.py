"""
V3 Sentiment Agent: Heuristic Combination
Combines V1 (VADER NLP) and V2 (Market Fear) with adaptive weighting
Uses LLM for tool calling but mechanical combination algorithm for final sentiment
"""

import json
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime
import re

from src.agents.base_agent import BaseAgent
from src.agents.sentiment_v1 import SentimentV1Agent
from src.agents.sentiment_v2 import SentimentV2Agent

logger = logging.getLogger(__name__)


class SentimentV3Agent(BaseAgent):
    """
    V3: Heuristic Combination Sentiment Agent

    Architecture:
    - Inherits from BaseAgent for LLM tool calling capabilities
    - Uses LLM to coordinate V1 and V2 sentiment analysis
    - Mechanical adaptive weighting algorithm (no LLM decision-making)
    - Combines news sentiment (V1) + market fear (V2) with volatility-based weights
    """

    def __init__(self, name: str = "SentimentV3Agent", memory_system=None):
        # Set max tool rounds for efficient processing
        self.max_tool_rounds = 3

        # Call parent constructor with sentiment tools only (both Google Search and VXX)
        from src.tools.tools import SENTIMENT_TOOLS
        super().__init__(
            name=name,
            tools=SENTIMENT_TOOLS,  # Only Google Search and VXX tools for sentiment
            memory_system=memory_system
        )

        self.logger = logger

        # Initialize V1 and V2 agents for combination logic
        self.v1_agent = SentimentV1Agent()
        self.v2_agent = SentimentV2Agent()

    def process_tool_result(self, tool_name: str, result: Any, tool_args: dict) -> Any:
        """
        Process tool results and apply V3 heuristic combination logic.

        Args:
            tool_name: Name of the tool that was executed
            result: Raw result from the tool
            tool_args: Arguments passed to the tool

        Returns:
            Processed result with V3 heuristic combination applied
        """
        # For V3, we need to get both V1 and V2 results and combine them
        # The LLM will call tools to get both news and VXX data
        # Then we mechanically combine the results using adaptive weighting

        if tool_name in ["fetch_google_search_news", "fetch_vxx_volatility_data"]:
            # Let the tool result pass through - combination happens in generate_reply
            return result
        
        # For other tools, return result as-is
        return result

    def calculate_adaptive_weights(self, v1_result: Dict, v2_result: Dict) -> tuple:
        """
        Calculate adaptive weights based on confidence and market conditions.

        Args:
            v1_result: V1 sentiment analysis result
            v2_result: V2 sentiment analysis result

        Returns:
            Tuple of (v1_weight, v2_weight)
        """
        v1_confidence = v1_result.get("confidence", 0)
        v2_confidence = v2_result.get("confidence", 0)

        # Base weights on confidence
        if v1_confidence == 0 and v2_confidence == 0:
            # No data from either source
            return 0.5, 0.5
        elif v1_confidence == 0:
            # Only V2 has data
            return 0.0, 1.0
        elif v2_confidence == 0:
            # Only V1 has data
            return 1.0, 0.0
        else:
            # Both have data - weight by confidence
            total_confidence = v1_confidence + v2_confidence
            v1_weight = v1_confidence / total_confidence
            v2_weight = v2_confidence / total_confidence

            # Adjust weights based on market conditions
            # V2 uses VXX values, adapt thresholds accordingly
            vxx_level = v2_result.get("vxx_value", 30)

            if vxx_level and vxx_level > 40:
                # High volatility/fear (VXX > 40) - give more weight to market fear
                v2_weight = min(0.7, v2_weight * 1.3)
                v1_weight = 1 - v2_weight
            elif vxx_level and vxx_level < 25:
                # Low volatility/fear (VXX < 25) - give more weight to news sentiment
                v1_weight = min(0.7, v1_weight * 1.3)
                v2_weight = 1 - v1_weight

            return v1_weight, v2_weight


    def generate_reply(self, messages, context=None) -> str:
        """
        Generate V3 heuristic combination response using LLM tool calling.

        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context

        Returns:
            JSON string with V3 heuristic combination analysis
        """
        # Extract message content
        if isinstance(messages, str):
            message = messages
        elif isinstance(messages, list) and messages:
            message = messages[-1].get("content", "") if isinstance(messages[-1],
                                                                    dict) else str(messages[-1])
        elif isinstance(messages, dict):
            message = messages.get("content", "")
        else:
            message = ""

        # Extract symbol and date from message
        symbol_match = re.search(r'\b([A-Z]{2,5})\b', message)
        symbol = symbol_match.group(1) if symbol_match else "SPY"

        date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
        date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")

        self.logger.info(f"V3 Sentiment: Heuristic combination for {symbol} on {date} with fallback to V1/V2")

        # For V3, use direct V1/V2 agent calls for now (simpler and more reliable)
        # Future enhancement: implement full LLM tool calling
        try:
            # Get V1 sentiment (news-based)
            v1_message = f"{symbol} on {date}"
            v1_response = self.v1_agent.generate_reply(v1_message)
            
            # Handle async response if needed
            if asyncio.iscoroutine(v1_response):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, v1_response)
                            v1_response = future.result()
                    else:
                        v1_response = loop.run_until_complete(v1_response)
                except RuntimeError:
                    v1_response = asyncio.run(v1_response)
                    
            v1_result = json.loads(v1_response)

            # Get V2 sentiment (VXX-based)
            v2_message = f"market fear on {date}"
            v2_response = self.v2_agent.generate_reply(v2_message)
            
            # Handle async response if needed
            if asyncio.iscoroutine(v2_response):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, v2_response)
                            v2_response = future.result()
                    else:
                        v2_response = loop.run_until_complete(v2_response)
                except RuntimeError:
                    v2_response = asyncio.run(v2_response)
                    
            v2_result = json.loads(v2_response)

            # Mechanically combine the results using adaptive weighting
            final_result = self._combine_processed_results(v1_result, v2_result)

            return json.dumps(final_result)

        except Exception as e:
            self.logger.error(f"Error in V3 sentiment generation: {str(e)}")

            # Return fallback response
            fallback_result = {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error in V3 analysis: {str(e)}",
                "version": "V3",
                "mode": "heuristic_combination"
            }

            return json.dumps(fallback_result)

    def _combine_processed_results(self, v1_result: Dict, v2_result: Dict) -> Dict:
        """Mechanically combine V1 and V2 results using adaptive weighting."""
        try:
            # Calculate adaptive weights
            v1_weight, v2_weight = self.calculate_adaptive_weights(v1_result, v2_result)

            # Combine sentiments
            v1_sentiment = v1_result.get("sentiment", 0)
            v2_sentiment = v2_result.get("sentiment", 0)
            combined_sentiment = (v1_sentiment * v1_weight) + (v2_sentiment * v2_weight)

            # Combine confidence scores
            v1_confidence = v1_result.get("confidence", 0)
            v2_confidence = v2_result.get("confidence", 0)
            combined_confidence = (v1_confidence * v1_weight) + (v2_confidence * v2_weight)

            # Generate reasoning
            reasoning_parts = []
            if v1_weight > 0:
                reasoning_parts.append(
                    f"News sentiment ({v1_weight:.0%} weight): {v1_sentiment:.3f}"
                )
            if v2_weight > 0:
                vxx_val = v2_result.get("vxx_value", "N/A")
                reasoning_parts.append(
                    f"Market fear/VXX ({v2_weight:.0%} weight): {v2_sentiment:.3f} (VXX: {vxx_val})"
                )

            reasoning = f"Heuristic combination - {' | '.join(reasoning_parts)}"

            result = {
                "sentiment": round(combined_sentiment, 4),
                "confidence": round(combined_confidence, 4),
                "reasoning": reasoning,
                "v1_sentiment": round(v1_sentiment, 4),
                "v1_weight": round(v1_weight, 4),
                "v1_confidence": round(v1_confidence, 4),
                "v2_sentiment": round(v2_sentiment, 4),
                "v2_weight": round(v2_weight, 4),
                "v2_confidence": round(v2_confidence, 4),
                "articles_analyzed": v1_result.get("articles_analyzed", 0),
                "vxx_value": v2_result.get("vxx_value"),
                "mode": "heuristic_combination",
                "version": "V3"
            }

            # Log the result
            self.logger.info(
                f"V3 Result: sentiment={result['sentiment']}, "
                f"V1={result['v1_sentiment']} ({result['v1_weight']:.0%}), "
                f"V2={result['v2_sentiment']} ({result['v2_weight']:.0%})"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error combining V3 results: {str(e)}")
            return {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error combining sentiments: {str(e)}",
                "mode": "heuristic_combination",
                "version": "V3"
            }
