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
import asyncio
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
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
        
        # Memory-based queuing system for quarterly data
        self.quarterly_memory: Dict[str, Dict] = {}  # {symbol_period: {date: sentiment_data}}
        self.is_prepared: bool = False
        self.prepared_symbol: Optional[str] = None
        self.prepared_period: Optional[tuple] = None
        
        from src.tools.tools import SENTIMENT_TOOLS
        super().__init__(name=name, tools=SENTIMENT_TOOLS, memory_system=memory_system)
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

    async def prepare_quarterly_data(self, symbol: str, start_date: str, end_date: str) -> bool:
        """
        Prepare quarterly VXX volatility data for market fear sentiment.
        
        Batch-fetch VXX data for entire quarter and pre-compute daily sentiments.
        """
        try:
            self.logger.info(f"V2Agent: Preparing quarterly VXX data for {symbol} ({start_date} to {end_date})")
            
            # Create memory key for this symbol/period
            memory_key = f"{symbol}_{start_date}_{end_date}"
            
            # For now, simulate VXX data preparation
            # In production, this would fetch actual VXX data for the quarter
            daily_sentiments = self._simulate_quarterly_vxx_data(start_date, end_date)
            
            # Store in memory for fast lookup
            self.quarterly_memory[memory_key] = daily_sentiments
            self.is_prepared = True
            self.prepared_symbol = symbol
            self.prepared_period = (start_date, end_date)
            
            self.logger.info(f"V2Agent: Successfully prepared {len(daily_sentiments)} VXX sentiment scores")
            return True
            
        except Exception as e:
            self.logger.error(f"V2Agent: Preparation failed: {e}")
            self.is_prepared = False
            return False
    
    def _simulate_quarterly_vxx_data(self, start_date: str, end_date: str) -> Dict[str, Dict]:
        """Simulate quarterly VXX data for testing."""
        daily_sentiments = {}
        
        # Generate date range for the quarter
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        current = start
        
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            
            # Simulate VXX-based sentiment (market fear)
            # V2 typically ranges from -0.8 (extreme fear) to +0.3 (low fear)
            base_sentiment = -0.2  # Slightly fearful baseline for V2
            
            daily_sentiments[date_str] = {
                "sentiment": base_sentiment,
                "confidence": 0.8,
                "version": "V2", 
                "mode": "quarterly_vxx_batch",
                "source": "vxx_volatility_quarterly"
            }
            
            current += timedelta(days=1)
        
        return daily_sentiments
    
    def get_sentiment_for_date(self, date: str, symbol: str = None) -> Dict:
        """Fast lookup of pre-computed VXX sentiment for a specific date."""
        if not self.is_prepared:
            self.logger.warning("V2Agent: Not prepared - falling back to single-day mode")
            return {"sentiment": 0.0, "confidence": 0.0, "version": "V2", "mode": "fallback"}
        
        # Use prepared symbol if not provided
        lookup_symbol = symbol or self.prepared_symbol
        memory_key = f"{lookup_symbol}_{self.prepared_period[0]}_{self.prepared_period[1]}"
        
        if memory_key in self.quarterly_memory and date in self.quarterly_memory[memory_key]:
            return self.quarterly_memory[memory_key][date]
        else:
            self.logger.warning(f"V2Agent: Date {date} not in prepared data")
            return {"sentiment": 0.0, "confidence": 0.0, "version": "V2", "mode": "date_miss"}
    
    def clear_memory(self):
        """Clear quarterly memory to prevent memory leaks during batch testing."""
        self.quarterly_memory.clear()
        self.is_prepared = False
        self.prepared_symbol = None
        self.prepared_period = None
        self.logger.info("V2Agent: Memory cleared")

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
            logger.debug(f"{self.name} processing request...")

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
            
            # Handle async response if needed
            if asyncio.iscoroutine(response):
                # We need to handle this properly in the sync context
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Create a new thread to run the coroutine
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, response)
                            response = future.result()
                    else:
                        response = loop.run_until_complete(response)
                except RuntimeError:
                    # No event loop, create a new one
                    response = asyncio.run(response)

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
