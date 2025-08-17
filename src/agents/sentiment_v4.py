"""
V4 Sentiment Agent: LLM-Based Analysis
The ONLY agent that uses LLM for sentiment decision-making
Provides raw news headlines and VXX data to LLM for reasoning-based sentiment analysis
"""

import json
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime
import re

from src.agents.base_agent import BaseAgent
from src.utils.data_obfuscation import DataObfuscator

logger = logging.getLogger(__name__)


class SentimentV4Agent(BaseAgent):
    """
    V4: LLM-Based Sentiment Agent

    The culmination of the V0-V4 sentiment framework. This is the ONLY agent that uses
    LLM reasoning for sentiment decisions. All previous versions (V0-V3) are mechanical.

    Architecture:
    - Uses BaseAgent for LLM tool calling capabilities
    - Fetches raw news headlines and VXX volatility data
    - Provides ALL data to LLM with comprehensive prompting
    - LLM makes the final sentiment decision with detailed reasoning
    - No mechanical rules or thresholds - pure LLM analysis
    """

    def __init__(self, name: str = "SentimentV4Agent", memory_system=None, enable_obfuscation: bool = True):
        # Set max tool rounds for comprehensive data gathering
        self.max_tool_rounds = 5  # May need multiple tools for complete analysis

        # Call parent constructor with both sentiment tools (Google Search + VXX)
        from src.tools.tools import SENTIMENT_TOOLS
        super().__init__(
            name=name,
            tools=SENTIMENT_TOOLS,  # Google Search + VXX volatility tools
            memory_system=memory_system
        )

        self.logger = logger

        # Initialize data obfuscation for preventing LLM training knowledge leakage
        self.enable_obfuscation = enable_obfuscation
        self.obfuscator = DataObfuscator() if enable_obfuscation else None

        # Track obfuscation mappings for this session
        self.current_date_mapping = {}
        self.current_ticker_mapping = {}

    def process_tool_result(self, tool_name: str, result: Any, tool_args: dict) -> Any:
        """
        Process tool results for V4 LLM analysis with obfuscation support.

        V4 pattern: Collect raw data from tools, apply obfuscation if enabled,
        then let LLM analyze everything. No mechanical processing.
        """
        try:
            self.logger.debug(f"V4 processing tool result for {tool_name}")

            # Apply obfuscation to tool results if enabled
            if self.enable_obfuscation and self.obfuscator:
                result = self._obfuscate_tool_result(result, tool_name, tool_args)

            # For V4, we want to preserve raw data for LLM analysis
            # Don't apply mechanical transformations like V1-V3 do

            if tool_name == "fetch_google_search_news":
                # Pass through raw news data for LLM analysis
                if isinstance(result, dict) and 'articles' in result:
                    return {
                        'tool': 'google_news',
                        'articles': result['articles'],
                        'total_found': len(result['articles']),
                        'date_range': result.get('date_range', 'unknown'),
                        'search_query': tool_args.get('symbol', 'market')
                    }

            elif tool_name == "fetch_vxx_volatility_data":
                # Pass through VXX data for LLM analysis
                if isinstance(result, dict):
                    return {
                        'tool': 'vxx_volatility',
                        'vxx_data': result.get('vxx_data', {}),
                        # V2's mechanical score for reference
                        'raw_sentiment': result.get('sentiment', 0.0),
                        'confidence': result.get('confidence', 0.0),
                        'interpretation': result.get('interpretation', 'unknown'),
                        'date_analyzed': tool_args.get('date', 'unknown')
                    }

            # Default: return result with tool context
            return {
                'tool': tool_name,
                'result': result,
                'args': tool_args
            }

        except Exception as e:
            self.logger.error(f"Error in V4 process_tool_result for {tool_name}: {str(e)}")
            return {
                'tool': tool_name,
                'error': str(e),
                'result': result
            }

    def _obfuscate_tool_result(self, result: Any, tool_name: str, tool_args: dict) -> Any:
        """
        Apply obfuscation to tool results to prevent LLM training knowledge leakage.

        Args:
            result: Raw tool result
            tool_name: Name of the tool
            tool_args: Tool arguments

        Returns:
            Obfuscated result
        """
        try:
            if tool_name == "fetch_google_search_news":
                # Obfuscate news headlines and content
                if isinstance(result, dict) and 'articles' in result:
                    obfuscated_articles = []
                    for article in result['articles']:
                        obfuscated_article = article.copy()

                        # Obfuscate company names and dates in headlines/content
                        if 'title' in obfuscated_article:
                            obfuscated_article['title'] = self._obfuscate_text(
                                obfuscated_article['title'])
                        if 'content' in obfuscated_article:
                            obfuscated_article['content'] = self._obfuscate_text(
                                obfuscated_article['content'])
                        if 'snippet' in obfuscated_article:
                            obfuscated_article['snippet'] = self._obfuscate_text(
                                obfuscated_article['snippet'])

                        obfuscated_articles.append(obfuscated_article)

                    result['articles'] = obfuscated_articles

            elif tool_name == "fetch_vxx_volatility_data":
                # VXX data doesn't need much obfuscation (just numbers)
                # But we can obfuscate any date references
                if isinstance(result, dict) and 'vxx_data' in result:
                    vxx_data = result['vxx_data']
                    if isinstance(vxx_data, dict) and 'date_used' in vxx_data:
                        # Map the actual date to obfuscated date
                        actual_date = vxx_data['date_used']
                        if actual_date in self.current_date_mapping:
                            vxx_data['date_used'] = self.current_date_mapping[actual_date]

            return result

        except Exception as e:
            self.logger.warning(f"Error obfuscating tool result: {str(e)}")
            return result

    def _obfuscate_text(self, text: str) -> str:
        """
        Obfuscate company names, dates, and market events in text.

        Args:
            text: Original text

        Returns:
            Obfuscated text
        """
        if not text:
            return text

        obfuscated = text

        # Apply ticker mappings
        for original_ticker, obfuscated_ticker in self.current_ticker_mapping.items():
            # Replace ticker mentions (case insensitive)
            obfuscated = re.sub(rf'\b{re.escape(original_ticker)}\b',
                                obfuscated_ticker, obfuscated, flags=re.IGNORECASE)

        # Apply date mappings
        for original_date, obfuscated_date in self.current_date_mapping.items():
            obfuscated = re.sub(rf'\b{re.escape(original_date)}\b', obfuscated_date, obfuscated)

        # Remove/obfuscate common company names
        company_names = {
            'Apple': self.current_ticker_mapping.get('AAPL', 'STOCK_A'),
            'Microsoft': self.current_ticker_mapping.get('MSFT', 'STOCK_B'),
            'Google': self.current_ticker_mapping.get('GOOGL', 'STOCK_C'),
            'Alphabet': self.current_ticker_mapping.get('GOOGL', 'STOCK_C'),
            'Amazon': self.current_ticker_mapping.get('AMZN', 'STOCK_D'),
            'NVIDIA': self.current_ticker_mapping.get('NVDA', 'STOCK_E'),
            'Meta': self.current_ticker_mapping.get('META', 'STOCK_F'),
            'Tesla': self.current_ticker_mapping.get('TSLA', 'STOCK_G'),
        }

        for company_name, ticker in company_names.items():
            obfuscated = re.sub(rf'\b{re.escape(company_name)}\b',
                                ticker, obfuscated, flags=re.IGNORECASE)

        return obfuscated

    def generate_reply(self, messages, context=None) -> str:
        """
        Generate V4 LLM-based sentiment response.

        V4 Pattern:
        1. Extract symbol and date from messages
        2. Use LLM to call tools and gather raw data (news + VXX)
        3. Provide comprehensive prompt with ALL raw data
        4. LLM makes final sentiment decision with reasoning
        5. Return structured JSON with LLM's analysis

        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context

        Returns:
            JSON string with LLM-based sentiment analysis
        """
        try:
            # Extract message content
            if isinstance(messages, str):
                message = messages
            elif isinstance(messages, list) and messages:
                message = messages[-1].get("content",
                                           "") if isinstance(messages[-1], dict) else str(messages[-1])
            elif isinstance(messages, dict):
                message = messages.get("content", "")
            else:
                message = ""

            # Extract symbol and date from message
            symbol_match = re.search(r'\b([A-Z]{2,5})\b', message)
            original_symbol = symbol_match.group(1) if symbol_match else "AAPL"

            date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
            original_date = date_match.group(
                0) if date_match else datetime.now().strftime("%Y-%m-%d")

            # Apply obfuscation if enabled (CRITICAL for preventing training knowledge leakage)
            if self.enable_obfuscation and self.obfuscator:
                # Obfuscate date to prevent LLM from using training knowledge
                self.current_date_mapping = self.obfuscator.obfuscate_dates([original_date])
                obfuscated_date = self.current_date_mapping[original_date]

                # Obfuscate ticker to prevent symbol recognition
                self.current_ticker_mapping = self.obfuscator.obfuscate_tickers([original_symbol])
                obfuscated_symbol = self.current_ticker_mapping[original_symbol]

                # Use obfuscated values for LLM prompting
                symbol = obfuscated_symbol
                date = obfuscated_date

                self.logger.info(
                    f"V4 Sentiment: LLM analysis for {original_symbol} ({symbol}) on {original_date} ({date}) - OBFUSCATED")
            else:
                symbol = original_symbol
                date = original_date
                self.logger.info(
                    f"V4 Sentiment: LLM analysis for {symbol} on {date} - NO OBFUSCATION")

            # Create comprehensive system message for V4 LLM analysis
            obfuscation_warning = ""
            if self.enable_obfuscation:
                obfuscation_warning = f"""
⚠️  CRITICAL: This data has been OBFUSCATED to prevent training knowledge leakage.
- You are analyzing {symbol} on {date} (these are anonymized identifiers)
- DO NOT use any external knowledge about market events or company history
- Base your analysis ONLY on the data provided by the tools
- Focus on the patterns and indicators in the raw data itself"""

            # For tool calls, use original values (tools expect real dates)
            # For LLM analysis, use obfuscated values (prevent training knowledge)
            tool_symbol = original_symbol
            tool_date = original_date
            analysis_symbol = symbol
            analysis_date = date

            system_content = f"""You are a V4 LLM-Based Sentiment Analysis Agent - the ONLY agent in our framework that uses LLM reasoning for sentiment decisions.

Your task is to analyze ALL available market data and provide a sentiment score from -1.0 to +1.0 for trading decisions.
{obfuscation_warning}

CRITICAL INSTRUCTIONS:
1. First, call fetch_google_search_news to get news headlines for {tool_symbol} on {tool_date}
2. Then call fetch_vxx_volatility_data to get market volatility data for {tool_date}
3. Analyze ALL the raw data using your LLM reasoning capabilities
4. Base your analysis ONLY on the provided data - do not use external knowledge
5. Provide a final sentiment score with detailed reasoning
6. In your analysis, refer to the asset as {analysis_symbol} and the date as {analysis_date}

ANALYSIS FRAMEWORK:
- News Headlines: What are the implications for {symbol}? Market impact?
- VXX Volatility: What does the volatility level indicate about market fear/confidence?
- Market Context: How do these factors interact? What's the overall picture?
- Confidence: How confident are you in this assessment?

SENTIMENT SCALE:
- -1.0 to -0.7: Strong bearish (avoid/sell)
- -0.7 to -0.3: Moderate bearish (caution)
- -0.3 to +0.3: Neutral (hold)
- +0.3 to +0.7: Moderate bullish (consider buy)
- +0.7 to +1.0: Strong bullish (strong buy)

OUTPUT FORMAT (JSON):
{{
    "sentiment": <score from -1.0 to +1.0>,
    "confidence": <confidence from 0.0 to 1.0>,
    "reasoning": "<detailed explanation of your analysis>",
    "news_analysis": "<summary of news impact>",
    "market_analysis": "<summary of VXX/volatility impact>",
    "synthesis": "<how you combined all factors>",
    "version": "V4",
    "mode": "llm_reasoning"
}}

Remember: You are making the sentiment decision using LLM reasoning, not mechanical rules. Provide thoughtful analysis.

Context: Analyzing {symbol} on {date}"""

            enhanced_messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Provide LLM-based sentiment analysis for {symbol} on {date}"}
            ]

            # Use BaseAgent's process_with_tools method for LLM tool calling
            user_msg = enhanced_messages[-1]['content']
            system_msg = enhanced_messages[0]['content']

            response = self.process_with_tools(user_msg, system_msg)
            
            # Handle async response if needed
            if asyncio.iscoroutine(response):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, response)
                            response = future.result()
                    else:
                        response = loop.run_until_complete(response)
                except RuntimeError:
                    response = asyncio.run(response)

            # Ensure we have a valid JSON response
            if not response:
                response = json.dumps({
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": "No response generated from V4 LLM analysis",
                    "version": "V4",
                    "mode": "llm_reasoning"
                })

            # Try to parse and validate the response
            try:
                # Look for JSON in the response
                json_match = re.search(r'\{[^}]+\}', response)
                if json_match:
                    json_data = json.loads(json_match.group())
                    # Ensure V4 version marking
                    json_data["version"] = "V4"
                    json_data["mode"] = "llm_reasoning"
                    response = json.dumps(json_data)
                else:
                    # If no JSON found, try to extract sentiment score and create structured response
                    sentiment_match = re.search(
                        r'sentiment["\':\s]*([+-]?[0-9]*\.?[0-9]+)', response, re.IGNORECASE)
                    sentiment = float(sentiment_match.group(1)) if sentiment_match else 0.0

                    response = json.dumps({
                        "sentiment": sentiment,
                        "confidence": 0.7,  # Default confidence for parsed responses
                        "reasoning": response,
                        "version": "V4",
                        "mode": "llm_reasoning"
                    })

            except Exception as parse_error:
                self.logger.warning(f"V4 response parsing error: {parse_error}")
                # Wrap the raw response
                response = json.dumps({
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": f"V4 LLM analysis: {response}",
                    "version": "V4",
                    "mode": "llm_reasoning"
                })

            self.logger.info(f"V4 LLM Sentiment completed for {symbol} on {date}")
            return response

        except Exception as e:
            error_msg = f"Error in V4 LLM Sentiment Agent: {str(e)}"
            self.logger.error(error_msg)

            return json.dumps({
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": error_msg,
                "version": "V4",
                "mode": "llm_reasoning",
                "error": str(e)
            })

    def validate_llm_reasoning(self, sentiment_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that V4 LLM reasoning is coherent and consistent.

        Args:
            sentiment_result: The LLM's sentiment analysis result

        Returns:
            Validation report with quality scores and recommendations
        """
        validation = {
            "reasoning_quality": 0.0,
            "consistency_score": 0.0,
            "data_utilization": 0.0,
            "overall_quality": 0.0,
            "issues": [],
            "recommendations": []
        }

        try:
            reasoning = sentiment_result.get("reasoning", "")
            sentiment = sentiment_result.get("sentiment", 0.0)
            confidence = sentiment_result.get("confidence", 0.0)

            # Check reasoning quality
            if len(reasoning) > 100:
                validation["reasoning_quality"] += 0.3
            if "news" in reasoning.lower():
                validation["reasoning_quality"] += 0.2
            if "vxx" in reasoning.lower() or "volatility" in reasoning.lower():
                validation["reasoning_quality"] += 0.2
            if "market" in reasoning.lower():
                validation["reasoning_quality"] += 0.15
            if any(word in reasoning.lower() for word in ["because", "therefore", "due to", "indicates"]):
                validation["reasoning_quality"] += 0.15

            # Check sentiment-reasoning consistency
            reasoning_sentiment_indicators = {
                'positive': ['bullish', 'positive', 'optimistic', 'growth', 'strong', 'good'],
                'negative': ['bearish', 'negative', 'pessimistic', 'decline', 'weak', 'bad', 'fear']
            }

            reasoning_lower = reasoning.lower()
            positive_count = sum(
                1 for word in reasoning_sentiment_indicators['positive'] if word in reasoning_lower)
            negative_count = sum(
                1 for word in reasoning_sentiment_indicators['negative'] if word in reasoning_lower)

            # Sentiment-reasoning alignment
            if sentiment > 0.3 and positive_count > negative_count:
                validation["consistency_score"] += 0.5
            elif sentiment < -0.3 and negative_count > positive_count:
                validation["consistency_score"] += 0.5
            elif -0.3 <= sentiment <= 0.3 and abs(positive_count - negative_count) <= 1:
                validation["consistency_score"] += 0.5
            else:
                validation["issues"].append("Sentiment score doesn't align with reasoning language")

            # Check confidence-sentiment consistency
            if (abs(sentiment) > 0.5 and confidence > 0.7) or (abs(sentiment) < 0.3 and confidence < 0.8):
                validation["consistency_score"] += 0.3
            else:
                validation["issues"].append("Confidence doesn't match sentiment strength")

            # Check data utilization
            if "news_analysis" in sentiment_result or "news" in reasoning_lower:
                validation["data_utilization"] += 0.4
            if "market_analysis" in sentiment_result or "vxx" in reasoning_lower:
                validation["data_utilization"] += 0.4
            if "synthesis" in sentiment_result:
                validation["data_utilization"] += 0.2

            # Calculate overall quality
            validation["overall_quality"] = (
                validation["reasoning_quality"] * 0.4 +
                validation["consistency_score"] * 0.4 +
                validation["data_utilization"] * 0.2
            )

            # Generate recommendations
            if validation["reasoning_quality"] < 0.6:
                validation["recommendations"].append(
                    "Improve reasoning detail and market factor analysis")
            if validation["consistency_score"] < 0.6:
                validation["recommendations"].append("Ensure sentiment score aligns with reasoning")
            if validation["data_utilization"] < 0.6:
                validation["recommendations"].append("Better utilize news and VXX data in analysis")

            return validation

        except Exception as e:
            validation["issues"].append(f"Validation error: {str(e)}")
            return validation
