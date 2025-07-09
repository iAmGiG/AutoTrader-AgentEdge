"""
SentimentAgent V2 - Enhanced with market-based sentiment indicators.

This enhanced version adds VXX (volatility) based sentiment when news data is unavailable.
It maintains backward compatibility with the original SentimentAgent output format.

Key enhancements:
1. Falls back to VXX market sentiment when news is unavailable
2. Maintains the same JSON output format for compatibility
3. Adds logging to track which sentiment source is used
"""

# Standard library imports
import json
import traceback
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Third-party imports
import pandas as pd

# Project imports
from .base_agent import BaseAgent
from src.tools.tools import SENTIMENT_AGENT, get_tools_for_agent
from src.tools.processors.sentiment_analyzer import SentimentAnalyzer
from src.utils.agent_utils import load_agent_config, load_market_sectors, QueryParser, DataProcessor
from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.tools.cache import MarketDataCache

# Set up logging
logger = logging.getLogger(__name__)

# LLM config optimized for sentiment analysis and narrative generation
SENTIMENT_LLM_CONFIG = {
    "temperature": 0.3,  # Slightly higher for creative narratives
    "max_tokens": 4096,  # Ensure enough tokens for complex responses
    "top_p": 0.9,        # Allow for some creative variety
}

# VXX thresholds for sentiment interpretation
VXX_THRESHOLDS = {
    "extreme_fear": 50,    # VXX > 50: Extreme market fear
    "high_fear": 40,       # VXX > 40: High fear/volatility
    "moderate_fear": 30,   # VXX > 30: Moderate concern
    "low_fear": 20,        # VXX < 20: Low fear/complacency
}


class SentimentAgent(BaseAgent):
    """
    Enhanced Agent for sentiment analysis with market-based fallback.

    Uses LLM-driven function calling to:
    - Retrieve news and analyze sentiment (primary)
    - Use VXX volatility as sentiment indicator when news unavailable (fallback)
    - Generate explanations of market sentiment from available data
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

        # Initialize market data tool for VXX fallback
        self.market_data_tool = MarketDataTool()
        
        # Initialize cache for VXX data
        self.market_cache = MarketDataCache()

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

    def _get_vix_sentiment(self, date: str) -> Dict[str, Any]:
        """
        Get VXX-based market sentiment for a given date.

        Args:
            date: Target date in YYYY-MM-DD format

        Returns:
            Dictionary with VXX data and interpretation
        """
        try:
            # Get VXX data around the target date (3 days before to 1 day after)
            target_date = datetime.strptime(date, "%Y-%m-%d")
            start_date = (target_date - timedelta(days=3)).strftime("%Y-%m-%d")
            end_date = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")

            logger.info(
                f"Fetching VXX data for sentiment analysis: {start_date} to {end_date}")

            # Try to get VXX data from cache first
            vxx_data = self.market_cache.get("VXX", start_date, end_date, "yahoo")
            
            if vxx_data is None or vxx_data.empty:
                # Fetch VXX data from market tool
                vxx_data = self.market_data_tool.fetch_market_data(
                    "VXX", start_date, end_date)
                
                # Cache the data if successfully fetched
                if vxx_data is not None and not vxx_data.empty:
                    self.market_cache.set("VXX", start_date, end_date, "yahoo", vxx_data)
                    logger.info(f"Cached VXX data for {start_date} to {end_date}")

            if vxx_data is not None and not vxx_data.empty:
                # Find the closest date to target
                vxx_data.index = pd.to_datetime(
                    vxx_data.index).tz_localize(None)
                target_datetime = pd.to_datetime(target_date)

                # Get the row closest to target date
                date_diffs = abs(vxx_data.index - target_datetime)
                closest_idx = date_diffs.argmin()
                closest_date = vxx_data.index[closest_idx]
                vxx_value = float(vxx_data.loc[closest_date, 'Close'])

                # Calculate sentiment based on VXX levels
                if vxx_value > VXX_THRESHOLDS["extreme_fear"]:
                    sentiment_score = -0.8
                    interpretation = "Extreme market fear - highly bearish conditions"
                elif vxx_value > VXX_THRESHOLDS["high_fear"]:
                    sentiment_score = -0.6
                    interpretation = "High market fear - bearish sentiment"
                elif vxx_value > VXX_THRESHOLDS["moderate_fear"]:
                    sentiment_score = -0.3
                    interpretation = "Moderate market concern - slightly bearish"
                elif vxx_value > VXX_THRESHOLDS["low_fear"]:
                    sentiment_score = 0.1
                    interpretation = "Normal market conditions - neutral sentiment"
                else:
                    sentiment_score = 0.3
                    interpretation = "Low market fear - complacent/bullish conditions"

                return {
                    "vxx_value": vxx_value,
                    "date_used": closest_date.strftime("%Y-%m-%d"),
                    "sentiment_score": sentiment_score,
                    "interpretation": interpretation,
                    "confidence": 0.7  # VXX provides good but not perfect sentiment signal
                }
            else:
                logger.warning(f"No VXX data available for {date}")
                return {
                    "vxx_value": None,
                    "sentiment_score": 0.0,
                    "interpretation": "No volatility data available",
                    "confidence": 0.0
                }

        except Exception as e:
            logger.error(f"Error fetching VXX sentiment: {str(e)}")
            return {
                "vxx_value": None,
                "sentiment_score": 0.0,
                "interpretation": f"Error retrieving market sentiment: {str(e)}",
                "confidence": 0.0
            }

    def _extract_date_from_message(self, message: str) -> Optional[str]:
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

        # Add note about VXX fallback
        context.append(
            "\nNOTE: If news data is unavailable, market sentiment will be derived from VXX volatility levels.")

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
                    # Check if news data is empty or has no articles
                    if (result.get("total_articles", 0) == 0 or
                        not result.get("articles") or
                            (isinstance(result.get("articles"), list) and len(result["articles"]) == 0)):
                        # Mark as no news available
                        result["no_news_available"] = True
                    return result
                # If it's a DataFrame for some reason, provide a sample
                if isinstance(result, pd.DataFrame):
                    if not result.empty:
                        return {
                            "summary": f"DataFrame with {len(result)} rows and columns: {', '.join(list(result.columns))}",
                            "sample_data": result.head(3).to_dict(orient="records")
                        }
                    return {"summary": "Empty DataFrame", "no_news_available": True}
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
                elif isinstance(result, pd.DataFrame) and result.empty:
                    return {"total_articles": 0, "no_news_available": True}

            # Default DataFrame handling
            if isinstance(result, pd.DataFrame):
                if not result.empty:
                    # For unhandled DataFrames, provide a basic summary
                    return {
                        "summary": f"DataFrame with {len(result)} rows and columns: {', '.join(list(result.columns))}",
                        "sample_data": result.head(3).to_dict(orient="records")
                    }
                return {"summary": "Empty DataFrame", "no_news_available": True}

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
        Enhanced to use VXX sentiment when news is unavailable.

        Args:
            messages: List of message dicts or a single message
            context: Optional context (not used currently)

        Returns:
            Generated response string with JSON sentiment data
        """
        try:
            print(f"\n{self.name} V2 processing request...")

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

            # Extract date and symbol from message
            date = self._extract_date_from_message(user_message)
            symbol = query_details.get("ticker", "market")

            supplementary_context = self.format_supplementary_context(
                query_details)

            # Create enhanced messages with system context
            enhanced_messages = []

            # Add system message with agent role, tools, and context
            system_content = self.config.get(
                "system_prompt", "You are a sentiment analysis agent.")
            system_content += f"\n\n{supplementary_context}"

            # Add specific instructions for V2 behavior
            system_content += "\n\nCRITICAL REQUIREMENT: You MUST ALWAYS return a JSON response with the following structure, even if no news is found:"
            system_content += '\n{"score": <float between -1 and 1>, "confidence": <float between 0 and 1>, "reasoning": "<explanation>", "sources": <number of sources>}'
            system_content += '\n\nIf no news is found, return: {"score": 0.0, "confidence": 0.0, "reasoning": "No news data available", "sources": 0}'
            system_content += '\nNEVER return a message saying you cannot provide analysis. ALWAYS return the JSON structure.'

            enhanced_messages.append({
                "role": "system",
                "content": system_content
            })

            # Add the original messages
            enhanced_messages.extend(messages)

            # Let the LLM generate a response with tool calls
            # Extract just the user message for processing
            user_msg = enhanced_messages[-1]['content'] if enhanced_messages else user_message
            system_msg = enhanced_messages[0]['content'] if enhanced_messages else system_content
            
            response = self.process_with_tools(user_msg, system_msg)

            # Check if response is None or empty
            if not response:
                response = json.dumps({
                    "score": 0.0,
                    "confidence": 0.0,
                    "reasoning": "No response generated",
                    "sources": 0
                })

            # Check if the response indicates no news data
            no_news_indicators = [
                "no news data available",
                "no news found",
                "unable to find news",
                "news data is unavailable",
                "0 articles found",
                "no articles found",
                "empty news results",
                "lack of significant news coverage",
                "only one article",
                "yielded only one article",
                "absence of relevant news"
            ]

            response_lower = response.lower()
            no_news_found = any(
                indicator in response_lower for indicator in no_news_indicators)

            # Also check if we got a score of 0 with low confidence
            try:
                # Try to parse JSON from response
                import re
                json_match = re.search(r'\{[^}]+\}', response)
                if json_match:
                    json_data = json.loads(json_match.group())
                    # Check for low confidence (< 0.3) OR score of 0
                    if (json_data.get("confidence", 1) < 0.3 or 
                        (json_data.get("score", 1) == 0 and json_data.get("confidence", 1) <= 0.2)):
                        no_news_found = True
                        logger.info(f"Low confidence sentiment detected: score={json_data.get('score')}, confidence={json_data.get('confidence')}")
            except:
                pass

            if no_news_found:
                logger.info(
                    f"No news found for {symbol} on {date}, using VXX sentiment fallback")

                # Get VXX sentiment
                vix_sentiment = self._get_vix_sentiment(date)

                # Create a new prompt for the LLM to synthesize VXX sentiment
                vxx_prompt = f"""
                No news data was available for {symbol} on {date}.
                
                Using market volatility indicator (VXX) as sentiment proxy:
                - VXX value: {vix_sentiment['vxx_value']}
                - Date used: {vix_sentiment['date_used']}
                - Market interpretation: {vix_sentiment['interpretation']}
                - Suggested sentiment score: {vix_sentiment['sentiment_score']}
                
                Please provide a sentiment analysis in JSON format based on this market volatility data.
                Consider that high VXX (>40) indicates fear/bearish sentiment, while low VXX (<20) indicates complacency/bullish sentiment.
                
                Return JSON with: score, confidence, reasoning, sources (set sources=1 for VXX).
                """

                # Get LLM to synthesize the VXX data
                vxx_messages = [
                    {"role": "system", "content": "You are a sentiment analysis agent. Provide market sentiment based on volatility indicators."},
                    {"role": "user", "content": vxx_prompt}
                ]

                # Extract user and system messages
                vxx_user_msg = vxx_messages[-1]['content']
                vxx_system_msg = vxx_messages[0]['content']
                
                response = self.process_with_tools(vxx_user_msg, vxx_system_msg)

                # Log the sentiment source
                logger.info(
                    f"Sentiment source for {symbol} on {date}: VXX (market volatility)")
            else:
                # Log that news was used
                logger.info(
                    f"Sentiment source for {symbol} on {date}: news data")

            return response

        except Exception as e:
            traceback.print_exc()
            error_msg = f"Error in {self.name} V2: {str(e)}"
            print(error_msg)
            # Return a valid JSON response even on error
            return json.dumps({
                "score": 0.0,
                "confidence": 0.0,
                "reasoning": error_msg,
                "sources": 0
            })
