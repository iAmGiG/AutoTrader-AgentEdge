"""
V1 Sentiment Agent: NLP Analysis with VADER + Google Search
Uses LLM for tool calling but mechanical VADER sentiment processing
No LLM decisions in final sentiment score
"""

import json
import logging
import re
from datetime import datetime
from typing import Any

from src.agents.base_agent import BaseAgent
from src.tools.processors.sentiment_analyzer import SentimentAnalyzer


logger = logging.getLogger(__name__)


class SentimentV1Agent(BaseAgent):
    """
    V1: NLP-based Sentiment Agent using VADER + financial lexicon

    Architecture:
    - Inherits from BaseAgent for LLM tool calling capabilities
    - Uses LLM to route and call Google Search news tool
    - Mechanical VADER sentiment processing (no LLM decision-making)
    - Enhanced financial lexicon with Austrian economics terms

    Tool Calling Pattern:
    - LLM determines which tools to call based on request
    - LLM fetches news data via Google Search tool
    - Mechanical sentiment analysis via SentimentAnalyzer
    - Returns aggregated sentiment score (-1.0 to +1.0)
    """

    def __init__(self, name: str = "SentimentV1Agent", memory_system=None):
        # Initialize enhanced sentiment analyzer with financial lexicon
        self.sentiment_analyzer = SentimentAnalyzer()

        # Set max tool rounds for efficient processing
        self.max_tool_rounds = 3

        # Call parent constructor with sentiment-specific tools only
        from src.tools.tools import SENTIMENT_TOOLS
        super().__init__(
            name=name,
            tools=SENTIMENT_TOOLS,  # Only Google Search and VXX tools for sentiment
            memory_system=memory_system
        )

        self.logger = logger

    def process_tool_result(self, tool_name: str, result: Any, tool_args: Any) -> Any:
        """
        Process tool results and apply mechanical VADER sentiment analysis.

        Args:
            tool_name: Name of the tool that was executed
            result: Raw result from the tool
            tool_args: Arguments passed to the tool

        Returns:
            Processed result with sentiment analysis applied
        """
        # V1 should only be using Google Search tool, but tool access is controlled by tools configuration
        # If this is news data from Google Search, apply sentiment analysis
        if tool_name == "fetch_google_news" and result is not None:
            try:
                import pandas as pd

                # Convert result to DataFrame if needed
                if isinstance(result, str):
                    # Try to parse JSON string
                    try:
                        import json
                        data = json.loads(result)
                        if isinstance(data, list):
                            df = pd.DataFrame(data)
                        else:
                            df = pd.DataFrame([data])
                    except:
                        # If not JSON, treat as single text entry
                        df = pd.DataFrame([{"title": result, "snippet": ""}])
                elif isinstance(result, list):
                    df = pd.DataFrame(result)
                elif isinstance(result, pd.DataFrame):
                    df = result
                else:
                    # Convert other types to DataFrame
                    df = pd.DataFrame([{"title": str(result), "snippet": ""}])

                # Apply sentiment analysis to each article
                if not df.empty and 'title' in df.columns:
                    # Combine title and snippet for analysis
                    df['combined_text'] = df.apply(
                        lambda row: f"{row.get('title', '')} {row.get('snippet', '')}".strip(),
                        axis=1
                    )

                    # Analyze sentiment for each article
                    sentiments = []
                    for _, row in df.iterrows():
                        text = row['combined_text']
                        if text:
                            sentiment_score = self.sentiment_analyzer.analyze_text(text)
                            sentiments.append(sentiment_score)

                    # Calculate aggregate sentiment
                    if sentiments:
                        avg_sentiment = sum(sentiments) / len(sentiments)

                        # Calculate confidence based on consistency and volume
                        if len(sentiments) > 1:
                            import pandas as pd
                            sentiment_std = pd.Series(sentiments).std()
                            consistency_score = max(0, 1 - sentiment_std)
                            volume_score = min(1, len(sentiments) / 10)
                            confidence = (consistency_score + volume_score) / 2
                        else:
                            confidence = 0.3

                        # Create enhanced result with sentiment analysis
                        sentiment_result = {
                            "sentiment": round(avg_sentiment, 4),
                            "confidence": round(confidence, 4),
                            "articles_analyzed": len(sentiments),
                            "version": "V1",
                            "mode": "vader_nlp_enhanced",
                            "raw_news_data": result,
                            "sentiment_scores": sentiments[:5]  # Top 5 for transparency
                        }

                        # Log the sentiment analysis
                        self.logger.info(
                            f"V1 Sentiment Analysis: {avg_sentiment:.3f} "
                            f"(confidence: {confidence:.3f}, articles: {len(sentiments)})"
                        )

                        return sentiment_result

            except Exception as e:
                self.logger.error(f"Error in sentiment analysis: {str(e)}")
                # Return fallback result
                return {
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "articles_analyzed": 0,
                    "version": "V1",
                    "mode": "vader_nlp_enhanced",
                    "error": str(e),
                    "raw_news_data": result
                }

        # For non-news tools, return result as-is
        return result

    def generate_reply(self, messages, context=None) -> str:
        """
        Generate V1 sentiment response using LLM tool calling + mechanical VADER.

        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context

        Returns:
            JSON string with V1 sentiment analysis
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
        symbol = symbol_match.group(1) if symbol_match else None
        
        # Use context symbol or default to AAPL for testing
        if not symbol:
            symbol = context.get('symbol', 'AAPL') if context else 'AAPL'

        date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
        date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")

        self.logger.info(f"V1 Sentiment: Analyzing {symbol} for {date} with VADER+LLM tools")

        # Create system prompt for LLM tool calling
        system_prompt = f"""You are a V1 sentiment analysis agent that analyzes financial news for {symbol}.

Your task: Call fetch_google_news to get recent news for {symbol} on {date}, then return the sentiment analysis result.

The news tool will automatically apply VADER sentiment analysis and return structured results.

Response format:
{{"sentiment": -0.2345, "confidence": 0.7, "articles_analyzed": 5, "version": "V1", "mode": "vader_nlp_enhanced"}}
"""

        # Use LLM tool calling to fetch and process news
        try:
            prompt = f"Analyze sentiment for {symbol} stock on {date}. Fetch recent news and apply sentiment analysis."

            response = self.process_with_tools(prompt, system_prompt)

            # The response should contain the processed sentiment data
            return response

        except Exception as e:
            self.logger.error(f"Error in V1 sentiment generation: {str(e)}")

            # Return fallback response
            fallback_result = {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error in V1 analysis: {str(e)}",
                "articles_analyzed": 0,
                "version": "V1",
                "mode": "vader_nlp_enhanced"
            }

            return json.dumps(fallback_result)
