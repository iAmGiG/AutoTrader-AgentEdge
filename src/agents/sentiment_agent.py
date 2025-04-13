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
        tools = [
            market_data_tool,  # Unified market data tool
            news_tool,         # News headlines tool
            # Additional tools can be added here as they are created
        ]
        
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
    
    def generate_reply(self, messages, context=None) -> str:
        """
        Primary entry point for generating replies to user messages.
        Uses the LLM to decide which tools to call based on the query.
        
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
        
        # Instead of using AssistantAgent's generate_reply, which depends on 
        # specific AutoGen functionality, we'll use the direct process_with_llm method
        
        # Create a system prompt with supplementary context
        system_prompt = self.config.get("system_prompt", "")
        system_prompt += f"\n\nSupplementary context for this query:\n{supplementary_context}"
        
        # If we have a specific ticker or topic, use direct tool calls
        if query_details.get("ticker") or query_details.get("topic"):
            prompt = f"I need information about "
            
            if query_details.get("ticker"):
                ticker = query_details["ticker"]
                prompt += f"the stock {ticker}. "
                
                # Fetch stock data
                try:
                    stock_data = self.use_tool("fetch_market_data", 
                                               symbol=ticker, 
                                               start_date=query_details["start_date"],
                                               end_date=query_details.get("end_date"))
                    
                    # Format the stock data for the LLM
                    if isinstance(stock_data, dict) and not stock_data.get("error"):
                        prompt += f"\n\nStock Data for {ticker}:\n"
                        prompt += f"Latest Price: ${stock_data.get('latest_close', 'N/A')}\n"
                        prompt += f"Price Range: ${stock_data.get('range_low', 'N/A')} - ${stock_data.get('range_high', 'N/A')}\n"
                        prompt += f"Volume: {stock_data.get('volume', 'N/A')}\n"
                        
                        if 'price_change' in stock_data:
                            prompt += f"Price Change: {stock_data['price_change']:.2f}%\n"
                except Exception as e:
                    prompt += f"\nError fetching stock data: {str(e)}\n"
            
            if query_details.get("topic"):
                topic = query_details["topic"]
                prompt += f"the topic '{topic}'. "
                
                # Fetch news
                try:
                    news_data = self.use_tool("fetch_news", keyword=topic, count=5)
                    
                    # Format the news data for the LLM
                    if isinstance(news_data, dict) and not news_data.get("error"):
                        prompt += f"\n\nNews Data for '{topic}':\n"
                        prompt += f"Article Count: {news_data.get('article_count', 0)}\n"
                        
                        headlines = news_data.get("headlines", [])
                        if headlines:
                            prompt += "Sample Headlines:\n"
                            for headline in headlines[:3]:
                                prompt += f"- {headline}\n"
                        
                        if 'average_sentiment' in news_data and news_data['average_sentiment'] is not None:
                            prompt += f"Average Sentiment Score: {news_data['average_sentiment']:.2f}\n"
                except Exception as e:
                    prompt += f"\nError fetching news data: {str(e)}\n"
            
            # Add sector context if available
            if query_details.get("sector") and query_details.get("sector") in self.market_sectors:
                sector = query_details["sector"]
                sector_data = self.market_sectors[sector]
                
                prompt += f"\n\nSector Context:\n"
                prompt += f"Sector: {sector}\n"
                
                # Add ETFs
                etfs = sector_data.get("etfs", [])
                if etfs:
                    prompt += f"Sector ETFs: {', '.join(etfs[:3])}\n"
                
                # Add blue chips
                blue_chips = sector_data.get("blue_chips", [])
                if blue_chips:
                    prompt += f"Major Companies: {', '.join(blue_chips[:5])}\n"
            
            # Request for a comprehensive analysis
            prompt += "\n\nBased on this information, please provide:\n"
            prompt += "1. A brief technical summary of the data\n"
            prompt += "2. A 'Market Behavior Explanation' that interprets the sentiment and price movements\n"
            prompt += "3. Potential implications for investors\n"
            
            # Process with the LLM
            return self.process_with_llm(prompt, system_prompt)
        else:
            # For general queries without specific tickers or topics,
            # process the original query with enhanced context
            return self.process_with_llm(last_message, system_prompt)
    
    def use_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Manually invoke a tool and process its results.
        This is used when we want to bypass the LLM for direct tool calls.
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments for the tool
            
        Returns:
            Processed results from the tool
        """
        # Call the tool
        result = super().use_tool(tool_name, **kwargs)
        
        # Process the result based on tool type
        if tool_name == "fetch_news":
            return self.data_processor.preprocess_news_data(result)
        elif tool_name in ["fetch_market_data", "fetch_yahoo_data", "fetch_alpha_vantage_data"]:
            return self.data_processor.preprocess_market_data(result, kwargs.get("symbol", ""))
        
        # Return unprocessed result for other tools
        return result