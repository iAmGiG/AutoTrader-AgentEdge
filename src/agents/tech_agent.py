"""
Tech Agent for V0-V3: Data fetcher with LLM tool routing
Uses LLM to call tools but makes no decisions
Just fetches market data and returns MACD values
"""

import logging
from typing import Any, Dict, List
import json
import pandas as pd

from src.agents.base_agent import BaseAgent
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
        self.max_tool_rounds = 1  # Single tool call to fetch data
    
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
            user_message = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)
        elif isinstance(messages, dict):
            user_message = messages.get("content", "")
        else:
            user_message = ""
        
        # Parse for symbol and date
        import re
        
        # Extract symbol
        symbol_match = re.search(r'\b([A-Z]{2,5})\b', user_message)
        symbol = symbol_match.group(1) if symbol_match else "SPY"
        
        # Extract date
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', user_message)
        if date_match:
            target_date = date_match.group(0)
        else:
            target_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        
        # Calculate date range for MACD (need 60 days of history)
        end_date = pd.to_datetime(target_date)
        start_date = end_date - pd.Timedelta(days=60)
        
        logger.info(f"TechAgent: Fetching data for {symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Create system prompt for tool routing only
        system_prompt = f"""You are a data fetching agent. Your ONLY job is to:
1. Call the appropriate tool to fetch market data
2. Return the raw data without any analysis

Fetch market data for {symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.
Use fetch_polygon_historical_data if available, otherwise use fetch_alpha_vantage_data.

DO NOT:
- Provide analysis or recommendations
- Make trading decisions
- Interpret the data
- Add commentary

Just fetch the data and return it."""

        # Use BaseAgent's tool processing
        tool_result = self.process_with_tools(user_message, system_prompt)
        
        # Process the result to extract MACD values
        try:
            # The tool should return a DataFrame or dict with market data
            if isinstance(tool_result, str):
                # Try to parse if it's JSON
                try:
                    tool_result = json.loads(tool_result)
                except:
                    pass
            
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