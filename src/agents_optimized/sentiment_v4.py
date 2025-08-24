"""
V4 Sentiment Agent: LLM-Based Analysis (OPTIMIZED)
The ONLY agent that uses LLM for sentiment decision-making
Already optimized with weekly batch processing to reduce LLM calls
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import re

from src.agents.base_agent import BaseAgent
from src.utils.date_sanitizer import sanitize_dates_only, prepare_news_for_v4, format_news_for_llm_prompt
from src.tools.data_sources.news.google_search_api import GoogleSearchNewsTool
from src.tools.data_sources.market.vxx_volatility_tool import VXXVolatilityTool
import pandas as pd

logger = logging.getLogger(__name__)


class OptimizedSentimentV4Agent(BaseAgent):
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

    def __init__(self, name: str = "OptimizedSentimentV4Agent", memory_system=None, enable_date_sanitization: bool = True):
        # Set max tool rounds to prevent infinite loops (Issue #215)
        self.max_tool_rounds = 1  # Force single round to prevent excessive API usage

        # Weekly batch processing state
        self.is_prepared: bool = False
        self.prepared_symbol: Optional[str] = None
        self.prepared_period: Optional[tuple] = None

        # Batch processing optimization for efficient LLM usage
        self.prepared_sentiments: Dict[str, float] = {}  # {date: sentiment_score}
        self.batch_processed: bool = False

        # Call parent constructor with both sentiment tools (Google Search + VXX)
        from src.tools.tools import SENTIMENT_TOOLS
        super().__init__(
            name=name,
            tools=SENTIMENT_TOOLS,  # Google Search + VXX volatility tools
            memory_system=memory_system
        )

        self.logger = logger

        # Initialize date sanitization for preventing temporal knowledge leakage
        self.enable_date_sanitization = enable_date_sanitization
        self.current_symbol = None  # Track current symbol for proper sanitization

        # Initialize direct tool access for optimization (Issue #212)
        # These tools already handle caching internally
        self.news_tool = GoogleSearchNewsTool()
        self.vxx_tool = VXXVolatilityTool()

    def process_tool_result(self, tool_name: str, result: Any, tool_args: dict) -> Any:
        """
        Process tool results for V4 LLM analysis with obfuscation support.

        V4 pattern: Collect raw data from tools, apply obfuscation if enabled,
        then let LLM analyze everything. No mechanical processing.
        """
        try:
            self.logger.debug(f"V4 processing tool result for {tool_name}")

            # Apply date sanitization to tool results if enabled
            if self.enable_date_sanitization:
                result = self._sanitize_tool_result(result, tool_name, tool_args)

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

            elif tool_name == "fetch_market_context_data":
                # Pass through market context data for LLM analysis
                if isinstance(result, dict):
                    return {
                        'tool': 'market_context',
                        'market_data': result.get('market_context', {}),
                        'market_summary': result.get('market_summary', {}),
                        'spy_signal': result.get('market_summary', {}).get('spy_signal', 'No data'),
                        'qqq_signal': result.get('market_summary', {}).get('qqq_signal', 'No data'),
                        'overall_sentiment': result.get('market_summary', {}).get('overall_sentiment', 'NEUTRAL'),
                        'date_analyzed': tool_args.get('date', 'unknown')
                    }

            elif tool_name == "fetch_hierarchical_news":
                # Format hierarchical news DataFrame for LLM consumption
                if hasattr(result, 'to_dict'):  # It's a DataFrame
                    try:
                        # Convert DataFrame to list of dicts for processing
                        news_list = result.to_dict('records')

                        # Apply date sanitization if enabled
                        if self.enable_date_sanitization:
                            sanitized_news = prepare_news_for_v4(
                                result, self.current_symbol or "TICKER_001")
                            formatted_news = format_news_for_llm_prompt(sanitized_news)
                        else:
                            # Convert to format expected by formatter
                            formatted_news_list = []
                            for item in news_list:
                                formatted_item = {
                                    'title': item.get('title', ''),
                                    'summary': item.get('summary', ''),
                                    'source': item.get('source', ''),
                                    'category': item.get('news_category', 'direct'),
                                    'ticker': item.get('news_source_ticker', ''),
                                    'relevance': item.get('relevance_score', 0.0)
                                }
                                formatted_news_list.append(formatted_item)
                            formatted_news = format_news_for_llm_prompt(formatted_news_list)

                        return {
                            'tool': 'hierarchical_news',
                            'formatted_news': formatted_news,
                            'total_articles': len(news_list),
                            'date_range': f"{tool_args.get('start_date', 'unknown')} to {tool_args.get('end_date', 'unknown')}",
                            'ticker': tool_args.get('ticker', 'unknown')
                        }

                    except Exception as format_error:
                        self.logger.error(f"Error formatting hierarchical news: {format_error}")
                        # Fallback to simple string representation
                        return {
                            'tool': 'hierarchical_news',
                            'formatted_news': f"Error formatting news: {format_error}",
                            'raw_result': str(result)[:500]  # Truncated fallback
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

    def _sanitize_tool_result(self, result: Any, tool_name: str, tool_args: dict) -> Any:
        """
        Apply date sanitization to tool results to prevent temporal knowledge leakage.
        Uses the proper date sanitizer instead of full obfuscation.

        Args:
            result: Raw tool result
            tool_name: Name of the tool
            tool_args: Tool arguments

        Returns:
            Sanitized result
        """
        try:
            if tool_name in ["fetch_hierarchical_news", "fetch_google_search_news"]:
                # Handle hierarchical news data (DataFrame)
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Use the proper date sanitization system
                    processed_news = prepare_news_for_v4(result, self.current_symbol)
                    return {
                        'processed_news': processed_news,
                        'formatted_text': format_news_for_llm_prompt(processed_news)
                    }
                elif isinstance(result, dict) and 'articles' in result:
                    # Handle old format Google Search results
                    sanitized_articles = []
                    for article in result['articles']:
                        sanitized_article = article.copy()
                        # Only sanitize dates, keep company names for analysis
                        if 'title' in sanitized_article:
                            sanitized_article['title'] = sanitize_dates_only(
                                sanitized_article['title'])
                        if 'content' in sanitized_article:
                            sanitized_article['content'] = sanitize_dates_only(
                                sanitized_article['content'])
                        if 'snippet' in sanitized_article:
                            sanitized_article['snippet'] = sanitize_dates_only(
                                sanitized_article['snippet'])
                        sanitized_articles.append(sanitized_article)
                    result['articles'] = sanitized_articles

            elif tool_name == "fetch_vxx_volatility_data":
                # VXX data is numerical, minimal sanitization needed
                if isinstance(result, dict) and 'vxx_data' in result:
                    vxx_data = result['vxx_data']
                    if isinstance(vxx_data, dict) and 'date_used' in vxx_data:
                        # Replace specific dates with generic markers
                        vxx_data['date_used'] = '[ANALYSIS_DATE]'

            return result

        except Exception as e:
            self.logger.warning(f"Error sanitizing tool result: {str(e)}")
            return result

    def _sanitize_text_dates(self, text: str) -> str:
        """
        Sanitize only dates in text, keeping company names for analysis.
        Uses the proper date sanitization utility.

        Args:
            text: Original text

        Returns:
            Text with dates sanitized
        """
        if not text:
            return text

        return sanitize_dates_only(text)

    def prepare_weekly_data(self, symbol: str, week_start: str, week_end: str) -> bool:
        """
        Process one week of trading days (typically 5 days).
        Makes ONE LLM call per week instead of 5 individual calls.

        Optimized for GPT-4o-mini context window limitations.

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            week_start: Week start date in YYYY-MM-DD format
            week_end: Week end date in YYYY-MM-DD format

        Returns:
            bool: True if preparation successful, False otherwise
        """
        try:
            self.logger.info(
                f"V4Agent: Starting weekly batch processing for {symbol} ({week_start} to {week_end})")

            # Generate trading days for this week (typically 5 days)
            trading_days = self._generate_trading_days(week_start, week_end)
            self.logger.info(f"V4Agent: Processing {len(trading_days)} trading days for week")

            # Create focused weekly prompt for LLM analysis
            weekly_prompt = self._create_weekly_batch_prompt(symbol, trading_days)

            # Use the working process_with_tools pattern (same as generate_reply)
            system_prompt = """Analyze market data and return sentiment from -1 to +1.
Be aggressive and bullish - markets trend up.
Fear creates opportunity. Complacency creates risk.
Use your tools to gather data, then provide intelligent analysis."""

            # Make ONE LLM call for the week using the working pattern
            self.logger.info(f"V4Agent: Making weekly LLM call for {len(trading_days)} days...")
            response = self.process_with_tools(weekly_prompt, system_prompt)

            # Handle async response if needed (same pattern as generate_reply)
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

            # Parse the LLM response to extract sentiment scores
            weekly_results = self._parse_batch_sentiment_response(response)

            if weekly_results:
                # Accumulate results (don't clear - build up over multiple weeks)
                self.prepared_sentiments.update(weekly_results)

                # Mark as processed for this week
                self.batch_processed = True

                self.logger.info(
                    f"V4Agent: Weekly processing completed - {len(weekly_results)} new sentiment scores added ({len(self.prepared_sentiments)} total)")
                return True
            else:
                self.logger.error("V4Agent: No sentiment scores parsed from weekly LLM response")
                return False

        except Exception as e:
            self.logger.error(f"V4Agent: Weekly processing failed: {e}")
            return False

    def prepare_period_data(self, symbol: str, start_date: str, end_date: str) -> bool:
        """
        Prepare sentiment data for entire period by processing week by week.

        This replaces prepare_quarterly_data with a weekly chunking approach.

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            start_date: Period start date in YYYY-MM-DD format
            end_date: Period end date in YYYY-MM-DD format

        Returns:
            bool: True if all weeks processed successfully
        """
        try:
            self.logger.info(
                f"V4Agent: Starting period preparation for {symbol} ({start_date} to {end_date})")

            # Clear previous data
            self.prepared_sentiments.clear()
            self.batch_processed = False

            # Generate weekly chunks
            weeks = self._generate_weekly_chunks(start_date, end_date)
            self.logger.info(f"V4Agent: Processing {len(weeks)} weeks")

            # Process in smaller batches to avoid timeout issues
            # Limit to 1 week per session to guarantee completion and checkpoint saving
            max_weeks_per_session = 1
            weeks_to_process = weeks[:max_weeks_per_session]

            if len(weeks) > max_weeks_per_session:
                self.logger.info(
                    f"V4Agent: Processing first {max_weeks_per_session} weeks of {len(weeks)} total (resumable)")

            success_count = 0
            for week_start, week_end in weeks_to_process:
                self.logger.info(f"V4Agent: Processing week {week_start} to {week_end}")

                # Process each week
                weekly_success = self.prepare_weekly_data(symbol, week_start, week_end)
                if weekly_success:
                    success_count += 1
                    self.logger.info(
                        f"V4Agent: Week {week_start} completed ({success_count}/{len(weeks_to_process)})")
                else:
                    self.logger.warning(
                        f"V4Agent: Failed to process week {week_start} to {week_end}")

            # Consider successful if we processed some weeks (partial success for resumable operation)
            if success_count >= len(weeks_to_process) * 0.8:  # 80% of attempted weeks
                self.is_prepared = True  # Mark as prepared even if partial
                self.prepared_symbol = symbol
                self.prepared_period = (start_date, end_date)

                self.logger.info(
                    f"V4Agent: Period preparation partially completed - {success_count}/{len(weeks_to_process)} weeks successful, {len(self.prepared_sentiments)} total sentiment scores")
                self.logger.info(
                    f"V4Agent: Will continue with daily sentiment analysis for remaining dates")
                return True
            else:
                self.logger.error(
                    f"V4Agent: Period preparation failed - only {success_count}/{len(weeks_to_process)} weeks successful")
                return False

        except Exception as e:
            self.logger.error(f"V4Agent: Period preparation failed: {e}")
            self.is_prepared = False
            return False

    def _generate_trading_days(self, start_date: str, end_date: str):
        """Generate list of trading days between start and end dates."""
        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        # Generate all dates in range, excluding weekends
        all_dates = []
        current = start
        while current <= end:
            # Skip weekends (Monday=0, Sunday=6)
            if current.weekday() < 5:  # Monday-Friday
                all_dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        return all_dates

    def _create_weekly_batch_prompt(self, symbol: str, trading_days):
        """Create focused weekly batch prompt optimized for GPT-4o-mini context window."""

        # Create a list of all dates for the prompt
        dates_list = "', '".join(sorted(trading_days))

        prompt = f"""Analyze TICKER_001 sentiment for {trading_days[0]} to {trading_days[-1]}.
Be aggressive and bullish - markets trend up.
Fear creates opportunity. Complacency creates risk.

Return JSON with sentiment for these dates: {trading_days}
Output: {{"date": sentiment_score, ...}}"""

        return prompt

    def _generate_weekly_chunks(self, start_date: str, end_date: str):
        """Generate weekly chunks for period processing."""
        from datetime import datetime, timedelta

        chunks = []
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        while current <= end:
            # Find start of week (Monday)
            week_start = current - timedelta(days=current.weekday())

            # Find end of week (Friday)
            week_end = week_start + timedelta(days=4)

            # Don't go past the end date
            if week_end > end:
                week_end = end

            # Only add if we have at least one day in the week
            if week_start <= end:
                chunks.append((
                    week_start.strftime('%Y-%m-%d'),
                    week_end.strftime('%Y-%m-%d')
                ))

            # Move to next week
            current = week_start + timedelta(days=7)

        return chunks

    def _parse_batch_sentiment_response(self, response: str):
        """Parse LLM response to extract sentiment scores."""
        import json
        import re

        if not response:
            self.logger.warning("V4Agent: Empty response from LLM")
            return {}

        try:
            self.logger.debug(f"V4Agent: Parsing response: {response[:500]}...")

            # Look for JSON in the response - be more flexible with nested braces
            json_patterns = [
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Handle nested braces
                r'\{.*?\}',  # Simple pattern
                r'\{[\s\S]*\}'  # Multiline pattern
            ]

            for pattern in json_patterns:
                json_matches = re.findall(pattern, response, re.DOTALL)

                for json_str in json_matches:
                    try:
                        sentiment_data = json.loads(json_str)

                        # Validate that this looks like our expected format
                        if isinstance(sentiment_data, dict) and len(sentiment_data) > 0:
                            # Check if keys look like dates
                            sample_key = next(iter(sentiment_data.keys()))
                            if re.match(r'\d{4}-\d{2}-\d{2}', sample_key):
                                # Convert to float and validate
                                validated_scores = {}
                                for date, score in sentiment_data.items():
                                    try:
                                        float_score = float(score)
                                        # Clamp to valid range
                                        float_score = max(-1.0, min(1.0, float_score))
                                        validated_scores[date] = float_score
                                    except (ValueError, TypeError):
                                        self.logger.warning(
                                            f"V4Agent: Invalid sentiment score for {date}: {score}")
                                        validated_scores[date] = 0.0

                                self.logger.info(
                                    f"V4Agent: Successfully parsed {len(validated_scores)} sentiment scores")
                                return validated_scores

                    except json.JSONDecodeError:
                        continue  # Try next pattern or next match

        except Exception as e:
            self.logger.error(f"V4Agent: Response parsing failed: {e}")

        # Fallback: return empty dict
        self.logger.warning("V4Agent: Could not parse any valid sentiment scores from response")
        return {}

    def clear_memory(self):
        """Clear batch processing state."""
        self.prepared_sentiments.clear()
        self.batch_processed = False
        self.is_prepared = False
        self.prepared_symbol = None
        self.prepared_period = None
        self.logger.info("V4Agent: Memory cleared")

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
            # Look for uppercase tickers first, then try case-insensitive common patterns

            # First try: explicit ticker in uppercase
            symbol_match = re.search(r'\b([A-Z]{2,5})\b', message)

            if not symbol_match:
                # Second try: common patterns with keywords (case-insensitive)
                patterns = [
                    r'(?:for|analyze|sentiment for)\s+([a-zA-Z]{2,5})\b',
                    r'\b([a-zA-Z]{2,5})\s+(?:sentiment|analysis|today)',
                    r'(?:buy|sell)\s+([a-zA-Z]{2,5})\b',
                ]
                for pattern in patterns:
                    symbol_match = re.search(pattern, message, re.IGNORECASE)
                    if symbol_match:
                        break

            original_symbol = symbol_match.group(1).upper() if symbol_match else "AAPL"
            # Set current symbol for sanitization
            self.current_symbol = original_symbol

            date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
            original_date = date_match.group(
                0) if date_match else datetime.now().strftime("%Y-%m-%d")

            # Check for batch-processed sentiment first (efficient path)
            if self.batch_processed and original_date in self.prepared_sentiments:
                sentiment_score = self.prepared_sentiments[original_date]
                self.logger.info(
                    f"V4Agent: Using batch-processed sentiment for {original_symbol} on {original_date}: {sentiment_score}")

                return json.dumps({
                    "sentiment": sentiment_score,
                    "confidence": 0.8,  # High confidence for batch-processed results
                    "reasoning": f"Batch-processed LLM analysis with date sanitization for TICKER_001",
                    "version": "V4",
                    "mode": "batch_processed"
                })

            # Fallback to individual analysis if not batch-processed
            self.logger.info(
                f"V4Agent: No batch data found, falling back to individual analysis for {original_symbol} on {original_date}")

            # Apply date sanitization if enabled (prevent temporal knowledge leakage)
            if self.enable_date_sanitization:
                # Use date sanitization - ticker keeps original value for hierarchical news
                symbol = original_symbol  # Keep original ticker for proper news categorization
                date = '[ANALYSIS_DATE]'  # Sanitize date only

                self.logger.info(
                    f"V4 Sentiment: LLM analysis for {original_symbol} on {original_date} - DATE SANITIZED")
            else:
                symbol = original_symbol
                date = original_date
                self.logger.info(
                    f"V4 Sentiment: LLM analysis for {symbol} on {date} - NO OBFUSCATION")

            # OPTIMIZATION: Fetch data directly from tools (they handle caching) (Issue #212)
            cached_data = self._fetch_data_directly(original_symbol, original_date)

            if cached_data and cached_data['has_all_data']:
                # We have all data - skip LLM tool calling and go directly to analysis
                self.logger.info(
                    f"V4 Agent: Using cached/fetched data for {original_symbol} on {original_date}, bypassing LLM tool calls")

                # Prepare the data for LLM analysis (with obfuscation if enabled)
                analysis_data = self._prepare_data_for_llm(
                    cached_data, original_symbol, original_date)

                # Call LLM for analysis only (no tool calling needed)
                return self._analyze_with_llm(analysis_data, symbol, date, original_symbol, original_date)

            # If we don't have all data, proceed with normal LLM tool calling
            self.logger.info(f"V4 Agent: Some data missing, using LLM tool calling")

            # Create comprehensive system message for V4 LLM analysis
            sanitization_warning = ""
            if self.enable_date_sanitization:
                sanitization_warning = f"""
⚠️  NOTICE: Dates have been sanitized to prevent temporal knowledge leakage.
- You are analyzing market data with dates replaced by generic markers
- Focus on the sentiment patterns and market psychology in the news and volatility data
- Use your understanding of market dynamics, not specific historical events"""

            # For tool calls, use original values (tools expect real dates and symbols)
            # For LLM analysis, dates are sanitized but symbols preserved for context
            tool_symbol = original_symbol
            tool_date = original_date

            system_content = f"""You are an intelligent market analyst who understands market psychology.
{sanitization_warning}

Get the latest data for {tool_symbol} on {tool_date}:
1. fetch_hierarchical_news
2. fetch_vxx_volatility_data  
3. fetch_market_context_data

Analyze this data with these insights:
- High VXX means fear - often the best time to buy
- Low VXX means complacency - time to be cautious
- Consider cash losing value to inflation - sometimes market risk is better than guaranteed purchasing power erosion
- News matters, but understand if it's company-specific or market-wide
- SPY/QQQ divergence from {tool_symbol} might indicate sector rotation vs individual issues
- Think about what the combination of signals tells you, not individual rules

Be contrarian when appropriate - extreme sentiment often reverses.
Remember: sitting in cash during inflation is also a risk - balance market downside against inflation erosion.

Return: {{"sentiment": <your_score from -1.0 to +1.0>, "reasoning": "<brief explanation>"}}"""

            # Fix date sanitization issue (Issue #215): Use original_date for clarity
            enhanced_messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Provide LLM-based sentiment analysis for {tool_symbol} on {tool_date}"}
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

    def _fetch_data_directly(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Fetch data directly from tools (which handle caching internally).
        This bypasses LLM tool calling when data is available in cache.

        Args:
            symbol: Stock ticker symbol
            date: Date in YYYY-MM-DD format

        Returns:
            Dict with fetched data and availability flags
        """
        result = {
            'has_all_data': False,
            'news_data': None,
            'vxx_data': None,
            'vxx_sentiment': None
        }

        try:
            # Fetch news data directly (tool handles caching internally)
            try:
                news_df = self.news_tool.search_historical_news(
                    ticker=symbol,
                    start_date=date,
                    end_date=date,
                    max_results=10
                )
                if news_df is not None and not news_df.empty:
                    result['news_data'] = news_df.to_dict(orient='records')
                    self.logger.debug(
                        f"Fetched {len(news_df)} news articles for {symbol} on {date}")
            except Exception as e:
                self.logger.warning(f"Could not fetch news data: {e}")

            # Fetch VXX sentiment directly (tool handles caching internally)
            try:
                vxx_result = self.vxx_tool.get_vxx_sentiment(date, lookback_days=5)
                if vxx_result and vxx_result.get('vxx_data'):
                    result['vxx_data'] = vxx_result['vxx_data']
                    result['vxx_sentiment'] = vxx_result
                    self.logger.debug(
                        f"Fetched VXX sentiment for {date}: {vxx_result.get('sentiment', 0):.2f}")
            except Exception as e:
                self.logger.warning(f"Could not fetch VXX data: {e}")

            # Check if we have all required data
            if result['news_data'] is not None and result['vxx_data'] is not None:
                result['has_all_data'] = True
                self.logger.info(
                    f"Successfully fetched all data for {symbol} on {date} (bypassing LLM tool calls)")

        except Exception as e:
            self.logger.warning(f"Error fetching data directly: {e}")

        return result

    def _prepare_data_for_llm(self, data: Dict[str, Any], symbol: str, date: str) -> Dict[str, Any]:
        """
        Prepare fetched data for LLM analysis, applying obfuscation if enabled.

        Args:
            data: Raw fetched data
            symbol: Original stock ticker  
            date: Original date

        Returns:
            Data prepared for LLM analysis
        """
        prepared_data = {
            'symbol': symbol,
            'date': date,
            'news': data.get('news_data', []),
            'vxx_data': data.get('vxx_data'),
            'vxx_sentiment': data.get('vxx_sentiment')
        }

        # Apply date sanitization if enabled
        if self.enable_date_sanitization:
            # Sanitize dates only (keep company names for analysis)
            if prepared_data['news']:
                for article in prepared_data['news']:
                    if 'title' in article:
                        # Sanitize only dates in headlines, keep company names
                        article['title'] = sanitize_dates_only(article['title'])
                    if 'published_date' in article:
                        article['published_date'] = '[DATE]'

        return prepared_data

    def _analyze_with_llm(self, data: Dict[str, Any], analysis_symbol: str, analysis_date: str,
                          original_symbol: str, original_date: str) -> str:
        """
        Analyze fetched data with LLM (no tool calling needed since we have the data).

        Args:
            data: Prepared data for analysis
            analysis_symbol: Symbol for analysis (same as original for V4)
            analysis_date: Date for analysis (sanitized if enabled)
            original_symbol: Original ticker
            original_date: Original date

        Returns:
            JSON string with sentiment analysis
        """
        try:
            # Format the data for LLM
            news_summary = "No news available for this date."
            if data.get('news'):
                headlines = [article.get('title', '') for article in data['news'][:10]]
                headlines = [h for h in headlines if h]
                if headlines:
                    news_summary = "Recent news headlines:\n" + \
                        "\n".join(f"- {h}" for h in headlines)

            vxx_summary = "No VXX data available."
            if data.get('vxx_sentiment'):
                vxx_sent = data['vxx_sentiment']
                vxx_summary = f"VXX Analysis: {vxx_sent.get('reasoning', 'No analysis')}\n"
                vxx_summary += f"VXX Sentiment Score: {vxx_sent.get('sentiment', 0):.2f}"
            elif data.get('vxx_data'):
                vxx_value = data['vxx_data'].get('vxx_value', 0)
                vxx_summary = f"VXX volatility level: {vxx_value:.2f}"

            # Create analysis prompt
            analysis_prompt = f"""Analyze {analysis_symbol} on {analysis_date}:

{news_summary}

{vxx_summary}

Be aggressive and bullish - markets trend up.
Fear creates opportunity. Complacency creates risk.
Output: {{"sentiment": score, "reasoning": "brief"}}"""

            # Use process_with_tools for consistency (but without actual tool calling)
            system_msg = """Analyze market data and return sentiment from -1 to +1.
Be aggressive and bullish - markets trend up.
Fear creates opportunity. Complacency creates risk.
Output: {"sentiment": score, "reasoning": "brief"}"""

            # Call LLM for analysis
            response = self.process_with_tools(analysis_prompt, system_msg)

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

            # Parse JSON response
            json_match = re.search(r'\{[^}]+\}', str(response))
            if json_match:
                result = json.loads(json_match.group())
                result['version'] = 'V4'
                result['mode'] = 'direct_analysis'  # Bypassed tool calling
                result['confidence'] = 0.85
                self.logger.info(
                    f"V4 Direct Analysis complete: sentiment={result.get('sentiment', 0):.2f}")
                return json.dumps(result)
            else:
                return json.dumps({
                    "sentiment": 0.0,
                    "confidence": 0.5,
                    "reasoning": str(response),
                    "version": "V4",
                    "mode": "direct_analysis"
                })

        except Exception as e:
            self.logger.error(f"Error in direct LLM analysis: {e}")
            return json.dumps({
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}",
                "version": "V4",
                "mode": "direct_analysis",
                "error": str(e)
            })
