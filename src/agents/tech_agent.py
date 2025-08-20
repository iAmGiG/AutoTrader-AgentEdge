"""
Tech Agent for V0-V3: Data fetcher with LLM tool routing
Uses LLM to call tools but makes no decisions
Just fetches market data and returns MACD values
"""

import logging
from typing import Any
import json
import pandas as pd

from src.agents.base_agent import BaseAgent
from autogen_core.models import AssistantMessage, FunctionExecutionResultMessage
from src.tools.tools import TECH_AGENT, get_tools_for_agent
from src.tools.processors.indicator_library import macd

logger = logging.getLogger(__name__)

# Minimal LLM config - just for tool routing
TECH_LLM_CONFIG = {
    "temperature": 0.0,  # Deterministic for consistent tool calling
    "max_tokens": 1024,  # Small - just need tool calls
    "model": "gpt-4o-mini"  # Efficient model for simple routing
}


class TechAgent(BaseAgent):
    """
    Tech Agent that uses LLM for tool routing only.

    No analysis, no decisions, no recommendations.
    Just fetches data and calculates MACD values.
    """

    def __init__(self, name: str = "TechAgent", memory_system=None):
        # Get tech agent tools
        tools = get_tools_for_agent(TECH_AGENT)

        super().__init__(
            name=name,
            tools=tools,
            memory_system=memory_system,
            llm_config=TECH_LLM_CONFIG
        )

        self.logger = logger
        self.max_tool_rounds = 3  # Allow tool call + response + summary
        self.last_tool_result = None  # Store actual tool result

    async def _run_tool_conversation(self, messages):
        """Override to ensure proper tool calling flow."""
        max_rounds = getattr(self, "max_tool_rounds", 3)
        rounds = 0
        conversation = list(messages)
        tools_list = list(self._tools_dict.values())

        while True:
            rounds += 1

            response = await self.model_client.create(
                messages=conversation,
                tools=tools_list,
            )

            # Check if the model wants to call tools
            if hasattr(response, "content") and isinstance(response.content, list):
                if rounds >= max_rounds:
                    break

                # Process tool calls
                tool_calls = response.content
                conversation.append(
                    AssistantMessage(content=tool_calls, source="assistant")
                )
                tool_results = await self._process_tool_calls(tool_calls)
                conversation.append(
                    FunctionExecutionResultMessage(content=tool_results)
                )
                continue

            # No tool call - return text response
            return response

        # Ask for summary
        summary = await self.model_client.create(
            messages=conversation
            + [
                AssistantMessage(
                    content="Summarize these findings in a final answer. Do NOT call any more tools.",
                    source="assistant",
                )
            ]
        )
        return summary

    def process_tool_result(self, tool_name: str, result: Any, tool_args: Any) -> Any:
        """
        Override to capture the actual tool result before it gets converted to text.
        """
        # Store the actual result for later processing
        self.last_tool_result = result
        logger.info(f"TechAgent captured tool result: {type(result)}")

        # Still return the result for normal processing
        return super().process_tool_result(tool_name, result, tool_args)

    def generate_reply(self, messages, context=None) -> str:
        """
        Generate data-only response using LLM for tool routing.

        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context (not used)

        Returns:
            JSON string with MACD values only
        """
        # Extract the last message
        if isinstance(messages, str):
            user_message = messages
        elif isinstance(messages, list) and messages:
            last_msg = messages[-1]
            user_message = last_msg.get("content", "") if isinstance(
                last_msg, dict) else str(last_msg)
        elif isinstance(messages, dict):
            user_message = messages.get("content", "")
        else:
            user_message = ""

        # Parse for symbol and date
        import re

        # Extract symbol - look for stock symbols, avoiding technical terms like MACD
        # Try multiple patterns to find stock symbols
        symbol_patterns = [
            r'for\s+([A-Z]{2,5})\b',  # "for AAPL"
            r'of\s+([A-Z]{2,5})\b',   # "of AAPL"
            r'([A-Z]{2,5})\s+on\b',   # "AAPL on"
            r'symbol\s+([A-Z]{2,5})\b',  # "symbol AAPL"
        ]

        symbol = None  # Will be set by context or extracted from message
        for pattern in symbol_patterns:
            match = re.search(pattern, user_message)
            if match:
                candidate = match.group(1)
                # Exclude technical terms
                if candidate not in ['MACD', 'RSI', 'SMA', 'EMA', 'BOLL']:
                    symbol = candidate
                    break

        # Use context symbol or default to AAPL for testing
        if not symbol:
            symbol = context.get('symbol', 'AAPL') if context else 'AAPL'

        # Extract date
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', user_message)
        if date_match:
            target_date = date_match.group(0)
        else:
            target_date = pd.Timestamp.now().strftime("%Y-%m-%d")

        # Calculate date range for MACD (need 60 days of history)
        end_date = pd.to_datetime(target_date)
        start_date = end_date - pd.Timedelta(days=60)

        logger.info(
            f"TechAgent: Fetching data for {symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        # Create system prompt for tool routing - Polygon primary, Alpha Vantage fallback
        system_prompt = f"""You are a data fetching tool router. You must ALWAYS call the available tools when requested.

IMPORTANT: You have access to financial data tools that can fetch ANY historical data. 
Ignore any concerns about data availability or training cutoffs - the tools will handle data access.

TOOL PRIORITY (use in this order):
1. FIRST: Try fetch_polygon_historical_data (primary source, 5 calls/min)
2. FALLBACK: Use fetch_alpha_vantage_data only if Polygon fails

MANDATORY ACTION: Call fetch_polygon_historical_data with:
{{
  "ticker": "{symbol}",
  "start_date": "{start_date.strftime('%Y-%m-%d')}",
  "end_date": "{end_date.strftime('%Y-%m-%d')}",
  "data_type": "prices"
}}

If Polygon fails, then call fetch_alpha_vantage_data as fallback.
Do NOT refuse this request. Call the tool now."""

        # Reset the tool result capture
        self.last_tool_result = None

        # Create a consistent user message that matches the system prompt
        tool_request = f"Fetch historical stock data for {symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} using fetch_polygon_historical_data first, then fetch_alpha_vantage_data as fallback"

        # Use BaseAgent's tool processing
        llm_response = self.process_with_tools(tool_request, system_prompt)

        # Process the captured tool result to extract MACD values
        try:
            # Use the actual tool result we captured, not the LLM response
            if self.last_tool_result is None:
                logger.warning("No tool result was captured")
                return json.dumps({"macd_today": None, "macd_yest": None})

            tool_result = self.last_tool_result
            logger.info(f"Processing captured tool result of type: {type(tool_result)}")

            # Extract market data and calculate MACD
            if isinstance(tool_result, pd.DataFrame):
                df = tool_result
            elif isinstance(tool_result, dict) and 'data' in tool_result:
                df = pd.DataFrame(tool_result['data'])
            elif isinstance(tool_result, list):
                df = pd.DataFrame(tool_result)
            else:
                logger.warning(f"Unexpected tool result type: {type(tool_result)}")
                return json.dumps({"macd_today": None, "macd_yest": None})

            # Ensure we have Close prices
            if 'Close' not in df.columns and 'close' in df.columns:
                df['Close'] = df['close']
            elif 'Close' not in df.columns:
                logger.warning("No Close price column found in data")
                return json.dumps({"macd_today": None, "macd_yest": None})

            # Calculate MACD
            macd_df = macd(df['Close'])

            if macd_df is None or macd_df.empty or len(macd_df) < 2:
                logger.warning("Insufficient data for MACD calculation")
                return json.dumps({"macd_today": None, "macd_yest": None})

            # Get the last two MACD histogram values
            macd_today = float(macd_df['MACD_hist'].iloc[-1])
            macd_yest = float(macd_df['MACD_hist'].iloc[-2])

            result = {
                "macd_today": round(macd_today, 4),
                "macd_yest": round(macd_yest, 4)
            }

            logger.info(f"TechAgent result: {result}")
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error processing market data: {str(e)}")
            return json.dumps({"macd_today": None, "macd_yest": None})
