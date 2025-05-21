"""
SentimentAgent module for sentiment analysis on market data and news.

This agent is designed to:
1. Retrieve market news and analyze sentiment
2. Perform contextual analysis on news and SEC filings
3. Present a coherent summary of market sentiment with explanations
"""

# Standard library imports
import json
import traceback
from typing import Dict, Any

# Third-party imports
import pandas as pd

# Project imports
from .base_agent import BaseAgent
from src.tools.tools import SENTIMENT_AGENT, get_tools_for_agent
from src.tools.processors.sentiment_analyzer import SentimentAnalyzer
from src.tools.agent_utils import load_agent_config, load_market_sectors, QueryParser, DataProcessor

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
    - Retrieve news and analyze sentiment
    - Search for relevant information in SEC filings
    - Generate explanations of market sentiment
    """

    def __init__(self, name="SentimentAgent", memory_system=None):
        # Load configurations and utilities
        self.config = load_agent_config("sentiment_agent")
        self.market_sectors = load_market_sectors().get("sectors", {})
        self.query_parser = QueryParser(self.market_sectors)

        # Initialize the sentiment analyzer
        self.sentiment_analyzer = SentimentAnalyzer()

        # Use only the tools appropriate for sentiment analysis
        tools = get_tools_for_agent(SENTIMENT_AGENT)

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
            query_details["leveraged_etfs"] = sector_data.get(
                "leveraged_etfs", [])

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
        context.append(
            f"Default date range: {query_details.get('start_date')} to {query_details.get('end_date') or 'present'}")

        # Add clarification about available tools
        context.append("\nAvailable sentiment analysis tools:")
        context.append(
            "- fetch_all_news: Unified tool that gets news from multiple sources in one call")
        context.append(
            "- search_sec_filings: Search for specific terms in SEC filings to get context about company disclosures")

        # Add reminder about one-tool-per-prompt policy
        context.append(
            "\nREMINDER: Use only ONE tool call per prompt to get comprehensive results.")
        context.append(
            "The unified news tool (fetch_all_news) is designed to get all needed news in a single call.")

        return "\n".join(context)

    def process_tool_result(self, tool_name: str, result: Any, tool_args: dict) -> Any:
        """
        Process tool results with sentiment-specific handling.
        Specialized for unified news (fetch_all_news) and SEC filings (search_sec_filings).

        Args:
            tool_name: The name of the tool that was called
            result: The raw result from the tool
            tool_args: The arguments that were passed to the tool

        Returns:
            Processed result in a simple, JSON-serializable format
        """
        try:
            # Ensure tool_args is a dictionary for safe access
            if isinstance(tool_args, str):
                try:
                    parsed_args = json.loads(tool_args)
                    if isinstance(parsed_args, dict):
                        tool_args = parsed_args
                    else:
                        tool_args = {}
                except json.JSONDecodeError:
                    tool_args = {}
            elif not isinstance(tool_args, dict):
                tool_args = {}

            print(f"Processing tool result for {tool_name}")

            # Unified News Tool (fetch_all_news)
            if tool_name == "fetch_all_news":
                # Result should be a dict with headlines, sentiment, etc.
                if isinstance(result, dict):
                    # Optionally post-process or summarize, else just return
                    return result
                # If it’s a DataFrame for some reason, provide a sample
                if isinstance(result, pd.DataFrame):
                    if not result.empty:
                        return {
                            "summary": f"DataFrame with {len(result)} rows and columns: {', '.join(list(result.columns))}",
                            "sample_data": result.head(3).to_dict(orient="records")
                        }
                    return {"summary": "Empty DataFrame"}
                # Otherwise just return whatever was given
                return result

            # SEC Search Tool (search_sec_filings)
            elif tool_name == "search_sec_filings":
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Extract arguments in a more robust way
                    ticker = None
                    search_terms = []
                    
                    # Try different possible locations for the ticker and search_terms
                    if isinstance(tool_args, dict):
                        ticker = tool_args.get("ticker", "")
                        search_terms = tool_args.get("search_terms", [])
                        
                        # Check if arguments were nested one level deeper
                        if not ticker and "arguments" in tool_args and isinstance(tool_args["arguments"], dict):
                            args_dict = tool_args["arguments"]
                            ticker = args_dict.get("ticker", "")
                            search_terms = args_dict.get("search_terms", [])
                    
                    # If we still couldn't extract the ticker, try to infer from the result
                    if not ticker and "ticker" in result.columns:
                        ticker = result["ticker"].iloc[0]
                    
                    # If search_terms is a string, convert to list
                    if isinstance(search_terms, str):
                        try:
                            # Try to parse as JSON array
                            parsed_terms = json.loads(search_terms)
                            if isinstance(parsed_terms, list):
                                search_terms = parsed_terms
                            else:
                                search_terms = [search_terms]
                        except json.JSONDecodeError:
                            # Just use as a single term
                            search_terms = [search_terms]
                    
                    # If we still don't have search terms, try to extract from results
                    if not search_terms and "search_term" in result.columns:
                        search_terms = list(result["search_term"].unique())
                    
                    search_summary = {
                        "ticker": ticker,
                        "search_terms": search_terms,
                        "total_matches": len(result),
                        "filing_dates": sorted(result["filing_date"].astype(str).unique().tolist()) if "filing_date" in result.columns else [],
                        "sections_with_matches": sorted(result["section"].unique().tolist()) if "section" in result.columns else [],
                        "sample_contexts": []
                    }

                    # Process matches for each search term
                    for term in search_terms:
                        term_matches = result
                        if "search_term" in result.columns:
                            term_matches = result[result["search_term"] == term]
                        
                        if not term_matches.empty:
                            contexts = []
                            if "context" in term_matches.columns:
                                contexts = term_matches["context"].tolist()[:3]  # Increased from 2 to 3
                            
                            for context in contexts:
                                search_summary["sample_contexts"].append({
                                    "term": term,
                                    "context": context
                                })
                    
                    return search_summary

                # No matches found or empty DataFrame
                ticker = tool_args.get("ticker", "")
                search_terms = tool_args.get("search_terms", [])
                
                # Handle case where the result is a string error message
                if isinstance(result, str) and "error" in result.lower():
                    return {
                        "ticker": ticker,
                        "search_terms": search_terms,
                        "total_matches": 0,
                        "error": result,
                        "message": "Error occurred while searching SEC filings"
                    }
                
                # Standard empty result
                return {
                    "ticker": ticker,
                    "search_terms": search_terms,
                    "total_matches": 0,
                    "message": "No matches found in SEC filings"
                }

            # Fallback: handle DataFrames generically
            if isinstance(result, pd.DataFrame):
                if not result.empty:
                    return {
                        "summary": f"DataFrame with {len(result)} rows and columns: {', '.join(list(result.columns))}",
                        "sample_data": result.head(3).to_dict(orient="records")
                    }
                return {"summary": "Empty DataFrame"}

            # Final fallback: just return the result as-is
            return result

        except Exception as e:
            traceback.print_exc()
            print(f"Error in process_tool_result: {str(e)}")
            return {"error": f"Failed to process result: {str(e)}"}

    def generate_reply(self, messages, context=None) -> str:
        """
        Primary entry point for generating replies to user messages.
        Lets the LLM decide which tools to call based on the query.

        Args:
            messages: List of conversation messages
            context: Optional context information

        Returns:
            Generated response or coroutine to be awaited
        """
        if not messages:
            return self.config.get("default_response", "I can help with analyzing market sentiment from news and SEC filings.")

        # Get the last message
        if isinstance(messages[-1], dict):
            last_message = messages[-1].get("content", "")
        else:
            last_message = str(messages[-1])

        # Preprocess the message to extract key information
        query_details = self.preprocess_message(last_message)

        # Format supplementary context for the LLM
        supplementary_context = self.format_supplementary_context(
            query_details)

        # Log the extracted information
        print(f"Extracted query details: {query_details}")

        # Create a system prompt with supplementary context
        system_prompt = self.config.get("system_prompt", "")
        system_prompt += f"\n\nSupplementary context for this query:\n{supplementary_context}"

        # Add specific guidance based on extracted entities
        if query_details.get("ticker"):
            ticker = query_details["ticker"]
            system_prompt += f"\n\nThis query mentions the stock ticker {ticker}. Use the unified news tool for comprehensive analysis:"
            system_prompt += f"\n1. fetch_all_news(ticker=\"{ticker}\", keywords=\"{query_details.get('topic', '')}\", start_date=\"{query_details.get('start_date')}\") - This will get news from multiple sources in a single call"

        elif query_details.get("topic"):
            topic = query_details["topic"]
            system_prompt += f"\n\nThis query mentions the topic '{topic}'. Use the unified news tool for comprehensive coverage:"
            system_prompt += f"\n1. fetch_all_news(keywords=\"{topic}\", count=10) - This will get news from multiple sources in a single call"

        # Add guidance for SEC filings search if appropriate
        if query_details.get("ticker") and any(term in last_message.lower() for term in ["risk", "sec", "filing", "10-k", "10k", "report", "earnings", "er"]):
            ticker = query_details["ticker"]
            system_prompt += f"\n\nThis query appears to be asking about SEC filings or earnings. Consider using the SEC search tool instead of the news tool:"
            system_prompt += f"\n1. search_sec_filings(ticker=\"{ticker}\", search_terms=[\"risk\", \"earnings\"], form_type=\"10-K\") - For regulatory disclosures"

        # Reinforce one-tool-per-prompt constraint
        system_prompt += f"\n\nIMPORTANT: Use only ONE tool call to get all needed information. The fetch_all_news tool is designed to get comprehensive news data in a single call."

        # Let the LLM generate a response with tool usage
        return self.process_with_tools(last_message, system_prompt)
