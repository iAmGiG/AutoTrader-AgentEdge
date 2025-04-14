"""
SentimentAgent module for sentiment analysis on market data and news.

This agent is designed to:
1. Retrieve market news and stock data
2. Apply sentiment analysis on news and price movements
3. Present a coherent summary with technical metrics and market behavior explanations
"""

from .base_agent import BaseAgent
from config.config_loader import ConfigLoader
from typing import Dict, List, Any, Optional
import pandas as pd
import json
import os

from src.tools.tools import (
    news_tool, yahoo_finance_tool, alpha_vantage_tool,
    alpha_vantage_news_tool, market_data_tool
)
from src.tools.tools import (
    fetch_news, fetch_yahoo_data, fetch_alpha_vantage_data,
    fetch_alpha_vantage_news, fetch_market_data
)
from src.tools.text_processing.sentiment_analyzer import SentimentAnalyzer
from src.tools.agent_utils import load_agent_config, load_market_sectors, QueryParser, DataProcessor

# Instantiate ConfigLoader for API keys
_loader = ConfigLoader()

# LLM config optimized for sentiment analysis and narrative generation
SENTIMENT_LLM_CONFIG = {
    "temperature": 0.3,  # Slightly higher for creative narratives
    "max_tokens": 4096,  # Ensure enough tokens for complex responses
    "top_p": 0.9,        # Allow for some creative variety
}

class SentimentAgent(BaseAgent):
    """
    Agent for sentiment analysis and market behavior explanation.
    
    Uses LLM-driven function calling to:
    - Retrieve news and market data based on user queries
    - Analyze sentiment in news articles
    - Generate explanations of market behavior
    """

    def __init__(self, name="SentimentAgent", memory_system=None):
        # Load configurations and utilities
        self.config = load_agent_config("sentiment_agent")
        self.market_sectors = load_market_sectors().get("sectors", {})
        self.query_parser = QueryParser(self.market_sectors)
        
        # Initialize the sentiment analyzer
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Register available tools for this agent
        from src.tools.tools import ALL_TOOLS
        
        # Use the pre-defined tools from tools.py
        tools = ALL_TOOLS
        
        # Initialize BaseAgent with system prompt from config
        super().__init__(
            name=name, 
            tools=tools, 
            memory_system=memory_system,
            llm_config=SENTIMENT_LLM_CONFIG
        )
        
        # Store the data processor
        self.data_processor = DataProcessor()
    
    def preprocess_message(self, message: str) -> Dict[str, Any]:
        """
        Pre-process a user message to extract key information.
        This helps guide the LLM's tool selection without being overly prescriptive.
        
        Args:
            message: User's query message
            
        Returns:
            Dictionary with extracted query details
        """
        # Extract query details from the message
        query_details = self.query_parser.extract_query_details(message)
        
        # Add sector information if available
        if query_details["sector"] and query_details["sector"] in self.market_sectors:
            sector_data = self.market_sectors[query_details["sector"]]
            query_details["etfs"] = sector_data.get("etfs", [])
            query_details["blue_chips"] = sector_data.get("blue_chips", [])
            query_details["leveraged_etfs"] = sector_data.get("leveraged_etfs", [])
        
        return query_details
    
    def format_supplementary_context(self, query_details: Dict[str, Any]) -> str:
        """
        Format supplementary context for the LLM based on extracted query details.
        This helps the LLM make better decisions about which tools to call.
        
        Args:
            query_details: Extracted query details
            
        Returns:
            Formatted context string
        """
        context = []
        
        # Add ticker and sector information
        if query_details.get("ticker"):
            context.append(f"Relevant ticker: {query_details['ticker']}")
        
        if query_details.get("sector"):
            context.append(f"Relevant sector: {query_details['sector']}")
            
            # Add ETF information if available
            if query_details.get("etfs"):
                etfs_str = ", ".join(query_details["etfs"][:3])
                context.append(f"Sector ETFs: {etfs_str}")
            
            # Add blue chip information if available
            if query_details.get("blue_chips"):
                blue_chips_str = ", ".join(query_details["blue_chips"][:3])
                context.append(f"Sector blue chips: {blue_chips_str}")
        
        # Add date range
        context.append(f"Default date range: {query_details.get('start_date')} to {query_details.get('end_date') or 'present'}")
        
        return "\n".join(context)
    
    def process_tool_result(self, tool_name: str, result: Any, tool_args: dict) -> Any:
        """
        Process tool results with sentiment-specific handling.
        This override adds specialized processing for news and market data.
        
        Args:
            tool_name: The name of the tool that was called
            result: The raw result from the tool
            tool_args: The arguments that were passed to the tool
            
        Returns:
            Processed result in a simple, JSON-serializable format
        """
        try:
            # First, ensure tool_args is a dictionary for safe access
            if isinstance(tool_args, str):
                try:
                    import json
                    parsed_args = json.loads(tool_args)
                    if isinstance(parsed_args, dict):
                        tool_args = parsed_args
                    else:
                        tool_args = {}
                except:
                    tool_args = {}
            elif not isinstance(tool_args, dict):
                tool_args = {}
                
            # For debugging
            print(f"Processing tool result for {tool_name}")
            
            # Process the result based on tool type
            if tool_name == "fetch_news":
                # Simple formatted results for news data
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Extract headlines
                    headlines = []
                    headline_cols = ["Headline", "title", "Title", "headline"]
                    for col in headline_cols:
                        if col in result.columns:
                            headlines = result[col].tolist()[:5]  # Limit to 5 headlines
                            break
                    
                    # Extract sentiment if available
                    sentiment = None
                    sentiment_cols = ["Sentiment Score", "sentiment_score", "overall_sentiment_score", "score"]
                    for col in sentiment_cols:
                        if col in result.columns:
                            sentiment = float(result[col].mean())
                            break
                            
                    # Build a simple news summary
                    news_summary = {
                        "headlines": headlines if headlines else ["No headlines available"],
                        "count": len(result),
                        "average_sentiment": sentiment,
                        "sources": result["Source"].tolist()[:5] if "Source" in result.columns else []
                    }
                    
                    return news_summary
                return {"headlines": [], "count": 0, "message": "No news data available"}
                
            elif tool_name in ["fetch_market_data", "fetch_yahoo_data", "fetch_alpha_vantage_data"]:
                # Simple formatted results for market data
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Extract key metrics
                    if 'Close' in result.columns or 'close' in result.columns:
                        # Normalize column names
                        close_col = 'Close' if 'Close' in result.columns else 'close'
                        
                        first_price = float(result[close_col].iloc[-1])
                        last_price = float(result[close_col].iloc[0])
                        percent_change = ((last_price - first_price) / first_price) * 100
                        
                        # Build a simple market summary
                        ticker = tool_args.get("symbol", "") or tool_args.get("ticker", "")
                        market_summary = {
                            "ticker": ticker,
                            "start_date": result.index[-1].strftime("%Y-%m-%d") if hasattr(result.index[-1], "strftime") else "N/A",
                            "end_date": result.index[0].strftime("%Y-%m-%d") if hasattr(result.index[0], "strftime") else "N/A",
                            "days": len(result),
                            "start_price": round(first_price, 2),
                            "end_price": round(last_price, 2),
                            "percent_change": round(percent_change, 2),
                            "trend": "up" if percent_change > 0 else "down"
                        }
                        
                        return market_summary
                return {"ticker": tool_args.get("symbol", ""), "days": 0, "message": "No market data available"}
            
            # Handle other cases - ensure result is simple and serializable
            if isinstance(result, pd.DataFrame):
                # Generic DataFrame handling - convert to simple dict with limited rows
                if not result.empty:
                    return {
                        "summary": f"DataFrame with {len(result)} rows and columns: {', '.join(list(result.columns))}",
                        "sample_data": result.head(3).to_dict(orient="records")
                    }
                return {"summary": "Empty DataFrame"}
                    
            # Return the result as is if it's already serializable
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error in process_tool_result: {str(e)}")
            return {"error": f"Failed to process result: {str(e)}"}
    
    def generate_reply(self, messages, context=None) -> str:
        """
        Primary entry point for generating replies to user messages.
        Let's the LLM decide which tools to call based on the query.
        
        Args:
            messages: List of conversation messages
            context: Optional context information
            
        Returns:
            Generated response
        """
        if not messages:
            return self.config.get("default_response", "I can help with analyzing market sentiment and stock data.")
        
        # Get the last message
        if isinstance(messages[-1], dict):
            last_message = messages[-1].get("content", "")
        else:
            last_message = str(messages[-1])
        
        # Preprocess the message to extract key information
        query_details = self.preprocess_message(last_message)
        
        # Format supplementary context for the LLM
        supplementary_context = self.format_supplementary_context(query_details)
        
        # Log the extracted information
        print(f"Extracted query details: {query_details}")
        
        # Create a system prompt with supplementary context
        system_prompt = self.config.get("system_prompt", "")
        system_prompt += f"\n\nSupplementary context for this query:\n{supplementary_context}"
        
        # Add specific guidance based on extracted entities
        if query_details.get("ticker"):
            ticker = query_details["ticker"]
            system_prompt += f"\n\nThis query mentions the stock ticker {ticker}. You should consider using fetch_market_data(symbol=\"{ticker}\", start_date=\"{query_details['start_date']}\") to get relevant market data."
        
        if query_details.get("topic"):
            topic = query_details["topic"]
            system_prompt += f"\n\nThis query mentions the topic '{topic}'. You should consider using fetch_news(keyword=\"{topic}\", count=5) to get relevant news articles."
        
        if query_details.get("sector"):
            sector = query_details["sector"]
            system_prompt += f"\n\nThis query relates to the {sector} sector. Consider fetching data for sector ETFs and major companies in this sector."
            
            # Add suggested stocks/ETFs to analyze
            if query_details.get("etfs") and len(query_details["etfs"]) > 0:
                system_prompt += f" Consider analyzing these sector ETFs: {', '.join(query_details['etfs'][:3])}"
            
            if query_details.get("blue_chips") and len(query_details["blue_chips"]) > 0:
                system_prompt += f" Consider analyzing these major stocks: {', '.join(query_details['blue_chips'][:3])}"
        
        # Let the LLM generate a response with tool usage
        # Use process_with_tools instead of process_with_llm to enable tool calling
        return self.process_with_tools(last_message, system_prompt)
    
    # We no longer need the custom use_tool method as the processing logic
    # has been moved to the process_tool_result method that's called by 
    # the BaseAgent's process_with_tools method