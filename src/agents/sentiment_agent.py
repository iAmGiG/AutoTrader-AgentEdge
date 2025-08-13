"""
Sentiment Agent
Pure news-based sentiment analysis using Google Search API only
Clean architecture - no market heat, no SPY momentum, no VXX fallback
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Project imports
from .base_agent import BaseAgent
from src.tools.tools import SENTIMENT_AGENT, get_tools_for_agent
from src.tools.processors.sentiment_analyzer import SentimentAnalyzer
from src.utils.agent_utils import load_agent_config, load_market_sectors, QueryParser, DataProcessor
from src.tools.cache.news_cache import NewsCache

# Set up logging
logger = logging.getLogger(__name__)

# LLM config optimized for sentiment analysis
SENTIMENT_LLM_CONFIG = {
    "temperature": 0.3,
    "max_tokens": 4096,
    "model": "gpt-4o-mini"
}


class SentimentAgent(BaseAgent):
    """
    Simplified Sentiment Agent - Pure news-based analysis

    Uses Google Search API to fetch financial news and analyzes sentiment
    No market heat, no technical indicators, just news sentiment
    """

    def __init__(self, name="SentimentAgent", memory_system=None):
        # Load configurations
        self.config = load_agent_config("sentiment_agent")
        self.max_tool_rounds = 2
        self.market_sectors = load_market_sectors().get("sectors", {})
        self.query_parser = QueryParser(self.market_sectors)

        # Initialize sentiment analyzer
        self.sentiment_analyzer = SentimentAnalyzer()

        # Initialize news cache
        self.news_cache = NewsCache()

        # Use only Google Search tool for sentiment
        tools = get_tools_for_agent(SENTIMENT_AGENT)

        # Initialize BaseAgent
        super().__init__(
            name=name,
            tools=tools,
            memory_system=memory_system,
            llm_config=SENTIMENT_LLM_CONFIG
        )

        self.data_processor = DataProcessor()

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
        Pre-process message to extract key information for news search.

        Args:
            message: User's query message

        Returns:
            Dictionary with extracted query details
        """
        # Parse the message for key components
        query_details = self.query_parser.extract_query_details(message)

        # Extract date
        date = self._extract_date_from_message(message)
        if date:
            query_details["date"] = date

        # Ensure ticker is uppercase
        if query_details.get("ticker"):
            query_details["ticker"] = query_details["ticker"].upper()

        logger.info(f"Preprocessed query: {query_details}")
        return query_details

    def format_supplementary_context(self, query_details: Dict[str, Any]) -> str:
        """
        Format supplementary context for the LLM based on extracted query details.

        Args:
            query_details: Extracted query information

        Returns:
            Formatted context string
        """
        context_parts = []

        if query_details.get("ticker"):
            context_parts.append(f"Analyzing sentiment for {query_details['ticker']}")

        if query_details.get("date"):
            context_parts.append(f"Date of interest: {query_details['date']}")

        if query_details.get("sector"):
            context_parts.append(f"Sector: {query_details['sector']}")

        # Add instruction for news-based analysis
        context_parts.append(
            "Use the Google Search news tool to fetch relevant financial news articles. "
            "Analyze the sentiment based on news headlines and content. "
            "Return a JSON response with sentiment score (-1 to 1), confidence, and reasoning."
        )

        return "\n".join(context_parts)

    def generate_reply(self, messages, context=None) -> str:
        """
        Generate sentiment analysis based purely on news data.

        Args:
            messages: List of message dicts or a single message
            context: Optional context (not used)

        Returns:
            JSON response with sentiment analysis
        """
        try:
            print(f"\n{self.name} processing request...")

            # Convert single message to list
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            elif isinstance(messages, dict):
                messages = [messages]

            # Extract user message
            user_message = None
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break

            if not user_message:
                return json.dumps({
                    "score": 0.0,
                    "confidence": 0.0,
                    "reasoning": "No user message found",
                    "sources": 0
                })

            # Pre-process the message
            query_details = self.preprocess_message(user_message)

            # Extract date and symbol
            date = query_details.get("date", datetime.now().strftime("%Y-%m-%d"))
            symbol = query_details.get("ticker", "SPY")

            # Format context
            supplementary_context = self.format_supplementary_context(query_details)

            # Create system message
            system_content = self.config.get(
                "system_prompt",
                "You are a financial sentiment analysis agent."
            )
            system_content += f"\n\n{supplementary_context}"

            # Add requirement for JSON response
            system_content += """
            
CRITICAL: Always return a JSON response with this exact structure:
{
    "score": <float between -1 and 1>,
    "confidence": <float between 0 and 1>,
    "reasoning": "<explanation based on news>",
    "sources": <number of news articles analyzed>
}

- Score: -1 (very bearish) to +1 (very bullish)
- Confidence: Based on quantity and quality of news
- If no news found, use score: 0.0, confidence: 0.0
"""

            # Create enhanced messages
            enhanced_messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_message}
            ]

            # Process with tools (Google Search)
            response = self.process_with_tools(
                enhanced_messages[-1]['content'],
                enhanced_messages[0]['content']
            )

            # Validate response is JSON
            if response:
                try:
                    # Try to parse as JSON to validate
                    json_response = json.loads(response)
                    # Ensure required fields
                    if not all(k in json_response for k in ["score", "confidence", "reasoning", "sources"]):
                        raise ValueError("Missing required fields")
                    return response
                except:
                    # If not valid JSON, wrap it
                    return json.dumps({
                        "score": 0.0,
                        "confidence": 0.0,
                        "reasoning": str(response),
                        "sources": 0
                    })
            else:
                return json.dumps({
                    "score": 0.0,
                    "confidence": 0.0,
                    "reasoning": "No response generated",
                    "sources": 0
                })

        except Exception as e:
            logger.error(f"Error in generate_reply: {str(e)}")
            return json.dumps({
                "score": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}",
                "sources": 0
            })


# Export the sentiment agent
__all__ = ['SentimentAgent']
