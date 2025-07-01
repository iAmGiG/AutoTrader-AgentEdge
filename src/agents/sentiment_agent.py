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
from src.utils.agent_utils import load_agent_config, load_market_sectors, QueryParser, DataProcessor

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
        # Limit this agent to a single tool round
        # Temporarily increased for debugging
        self.max_tool_rounds = 2
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
                # If it's a DataFrame for some reason, provide a sample
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
                    ticker = tool_args.get("ticker", "N/A")
                    search_terms = tool_args.get("search_terms", ["N/A"])
                    if isinstance(search_terms, list) and search_terms:
                        search_terms_str = ", ".join(
                            str(term) for term in search_terms)
                    else:
                        search_terms_str = str(search_terms)

                    # Create search result summary
                    search_results = []
                    for idx, row in result.iterrows():
                        if idx >= 5:  # Limit to first 5 results
                            break
                        search_results.append({
                            "filing_date": str(row.get('filing_date', 'N/A')),
                            "form_type": str(row.get('form_type', 'N/A')),
                            "search_term": str(row.get('search_term', 'N/A')),
                            "section": str(row.get('section', 'N/A')),
                            # Limit context
                            "context": str(row.get('context', 'N/A'))[:300]
                        })

                    return {
                        "ticker": ticker,
                        "search_terms": search_terms_str,
                        "total_matches": len(result),
                        "search_results": search_results
                    }
                elif isinstance(result, pd.DataFrame) and result.empty:
                    ticker = tool_args.get("ticker", "N/A")
                    search_terms = tool_args.get("search_terms", ["N/A"])
                    return {
                        "ticker": ticker,
                        "search_terms": search_terms if isinstance(search_terms, str) else ", ".join(search_terms),
                        "message": "No matches found in SEC filings"
                    }

            # Other Sentiment Tools
            elif tool_name == "fetch_alpha_vantage_news":
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # This tool returns news with sentiment scores
                    news_items = []
                    for idx, row in result.head(5).iterrows():
                        news_items.append({
                            "title": str(row.get('title', 'N/A')),
                            "published": str(row.get('time_published', 'N/A')),
                            "sentiment_score": float(row.get('overall_sentiment_score', 0)),
                            "sentiment_label": str(row.get('overall_sentiment_label', 'N/A'))
                        })
                    return {
                        "total_articles": len(result),
                        "news_items": news_items
                    }

            # News Tool Result Processing
            elif tool_name == "fetch_news":
                if isinstance(result, pd.DataFrame) and not result.empty:
                    news_items = []
                    for idx, row in result.head(5).iterrows():
                        news_items.append({
                            "title": str(row.get('title', 'N/A')),
                            "published": str(row.get('publishedAt', row.get('published', 'N/A'))),
                            "source": str(row.get('source', {}).get('name', 'N/A') if isinstance(row.get('source'), dict) else 'N/A')
                        })
                    return {
                        "total_articles": len(result),
                        "news_items": news_items
                    }

            # Finnhub News Tools
            elif tool_name.startswith("fetch_finnhub"):
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Finnhub returns news headlines
                    news_items = []
                    for idx, row in result.head(5).iterrows():
                        news_items.append({
                            "title": str(row.get('title', row.get('headline', 'N/A'))),
                            "published": str(row.get('published_at', row.get('datetime', 'N/A'))),
                            "category": str(row.get('category', 'N/A'))
                        })
                    return {
                        "total_articles": len(result),
                        "news_items": news_items
                    }

            # FMP Tools (if they return results)
            elif tool_name.startswith("fetch_fmp"):
                if isinstance(result, pd.DataFrame) and not result.empty:
                    return {
                        "total_results": len(result),
                        "sample_data": result.head(3).to_dict(orient="records")
                    }

            # Default DataFrame handling
            if isinstance(result, pd.DataFrame):
                if not result.empty:
                    # For unhandled DataFrames, provide a basic summary
                    return {
                        "summary": f"DataFrame with {len(result)} rows and columns: {', '.join(list(result.columns))}",
                        "sample_data": result.head(3).to_dict(orient="records")
                    }
                return {"summary": "Empty DataFrame"}

            # Default dict handling
            if isinstance(result, dict):
                return result

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
            messages: List of message dicts or a single message
            context: Optional context (not used currently)

        Returns:
            Generated response string
        """
        try:
            print(f"\n{self.name} processing request...")

            # Convert single message to list
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
                return "I couldn't find a user message to process."

            # Pre-process the message
            query_details = self.preprocess_message(user_message)
            supplementary_context = self.format_supplementary_context(
                query_details)

            # Create enhanced messages with system context
            enhanced_messages = []

            # Add system message with agent role, tools, and context
            system_content = self.config.get(
                "system_prompt", "You are a sentiment analysis agent.")
            system_content += f"\n\n{supplementary_context}"

            enhanced_messages.append({
                "role": "system",
                "content": system_content
            })

            # Add the original messages
            enhanced_messages.extend(messages)

            # Let the LLM generate a response with tool calls
            response = super().generate_reply(enhanced_messages, context)

            # Narrative polish based on query type
            # (This is handled by the LLM now with better prompting)
            return response

        except Exception as e:
            traceback.print_exc()
            error_msg = f"Error in {self.name}: {str(e)}"
            print(error_msg)
            return error_msg
