"""
V4 Sentiment Agent: LLM-Based Analysis
The ONLY agent that uses LLM for sentiment decision-making
Provides raw news headlines and VXX data to LLM for reasoning-based sentiment analysis
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
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

        # Memory-based queuing system for quarterly data
        self.quarterly_memory: Dict[str, Dict] = {}  # {symbol_period: {date: sentiment_data}}
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
            system_prompt = """You are an expert financial analyst. 
            Analyze the provided data and return sentiment scores for ALL dates in the exact JSON format requested.
            Use your tools to gather current market data, then provide comprehensive analysis."""

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

        prompt = f"""I need sentiment analysis for TICKER_001 for this week's trading days from {trading_days[0]} to {trading_days[-1]}.

🛡️ CRITICAL INSTRUCTIONS:
- You are analyzing TICKER_001 (obfuscated company ticker)  
- Use your tools to gather focused news, VXX volatility, and market context
- Analyze sentiment for each day based on available data up to that date
- Return sentiment scores from -1.0 (very bearish) to +1.0 (very bullish)

📋 ANALYSIS DATES (this week):
['{dates_list}']

🎯 REQUIRED OUTPUT FORMAT:
Return a single JSON object with sentiment scores for ALL {len(trading_days)} trading days:
{{
  "{trading_days[0]}": 0.3,
  "{trading_days[1] if len(trading_days) > 1 else trading_days[0]}": -0.1,
  "{trading_days[2] if len(trading_days) > 2 else trading_days[0]}": 0.7
  {', "' + trading_days[3] + '": 0.2' if len(trading_days) > 3 else ''}
  {', "' + trading_days[4] + '": 0.5' if len(trading_days) > 4 else ''}
}}

💡 WEEKLY ANALYSIS APPROACH:
1. Use fetch_hierarchical_news for TICKER_001 weekly news
2. Use fetch_vxx_volatility_data for each day's market fear level
3. Use fetch_market_context_data for SPY/QQQ trends
4. Apply contrarian logic: High VXX = opportunity, Low VXX = caution

⚠️ IMPORTANT: Return complete JSON with sentiment for ALL {len(trading_days)} dates."""

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

    async def _gather_quarterly_context(self, symbol: str, start_date: str, end_date: str) -> Dict:
        """
        Gather comprehensive quarterly context (news + VXX + SPY/QQQ) for LLM analysis.

        This replaces multiple individual API calls with batch data gathering.
        """
        try:
            self.logger.info("V4Agent: Gathering quarterly news, VXX, and market context...")

            # Use process_with_tools() instead of broken async wrapper
            # This is the same pattern that works in individual mode

            # Gather news data for entire quarter
            news_prompt = f"Fetch comprehensive financial news for {symbol} from {start_date} to {end_date}"
            news_system = "You are gathering quarterly news data. Call fetch_google_news to get comprehensive news for the date range."

            self.logger.info(f"V4Agent: Fetching quarterly news...")
            quarterly_news = await asyncio.create_task(
                self._run_process_with_tools_async(news_prompt, news_system)
            )

            # Gather VXX data for representative date (quarter start)
            vxx_prompt = f"Fetch VXX volatility data for {start_date} to analyze market fear context"
            vxx_system = "You are gathering market volatility data. Call fetch_vxx_volatility_data for the specified date."

            self.logger.info(f"V4Agent: Fetching quarterly VXX data...")
            quarterly_vxx = await asyncio.create_task(
                self._run_process_with_tools_async(vxx_prompt, vxx_system)
            )

            # Gather SPY/QQQ market context for the quarter
            market_prompt = f"Fetch market context data (SPY and QQQ) for {start_date} to understand broader market direction"
            market_system = "You are gathering market context data. Call fetch_market_context_data for SPY and QQQ indices."

            self.logger.info(f"V4Agent: Fetching quarterly SPY/QQQ market context...")
            quarterly_market = await asyncio.create_task(
                self._run_process_with_tools_async(market_prompt, market_system)
            )

            return {
                "news_data": quarterly_news,
                "vxx_data": quarterly_vxx,
                "market_data": quarterly_market,
                "symbol": symbol,
                "period": f"{start_date} to {end_date}"
            }

        except Exception as e:
            self.logger.error(f"V4Agent: Failed to gather quarterly context: {e}")
            return {}

    async def _run_process_with_tools_async(self, prompt: str, system_prompt: str) -> str:
        """Async wrapper for process_with_tools (the working pattern)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.process_with_tools, prompt, system_prompt
        )

    async def _get_tool_response_async(self, messages) -> str:
        """DEPRECATED: Broken async wrapper - use _run_process_with_tools_async instead."""
        self.logger.warning("Using deprecated _get_tool_response_async - this returns None")
        return None

    def _generate_reply_sync(self, messages) -> str:
        """DEPRECATED: Broken sync wrapper - use process_with_tools instead."""
        self.logger.warning("Using deprecated _generate_reply_sync - this returns None")
        return None

    async def _compute_quarterly_llm_analysis(self, symbol: str, start_date: str, end_date: str,
                                              quarterly_context: Dict) -> Dict[str, Dict]:
        """
        Pre-compute LLM sentiment decisions for each day in the quarter.

        This is where V4's LLM reasoning happens - during preparation, not during simulation.
        """
        daily_sentiments = {}

        try:
            # Generate date range for the quarter
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            current = start

            self.logger.info("V4Agent: Computing LLM sentiment decisions for quarter...")

            while current <= end:
                date_str = current.strftime("%Y-%m-%d")

                # For each date, create comprehensive LLM prompt with quarterly context
                llm_prompt = self._create_llm_sentiment_prompt(
                    symbol, date_str, quarterly_context
                )

                # Get LLM's sentiment decision for this specific date
                llm_decision = await self._get_llm_sentiment_decision(llm_prompt)

                daily_sentiments[date_str] = {
                    "sentiment": llm_decision.get("sentiment", 0.0),
                    "confidence": llm_decision.get("confidence", 0.0),
                    "reasoning": llm_decision.get("reasoning", ""),
                    "version": "V4",
                    "mode": "llm_reasoning_batch",
                    "date_obfuscated": self.enable_obfuscation
                }

                current += timedelta(days=1)

            self.logger.info(f"V4Agent: Completed LLM analysis for {len(daily_sentiments)} days")

        except Exception as e:
            self.logger.error(f"V4Agent: Error in LLM analysis: {e}")

        return daily_sentiments

    def _create_llm_sentiment_prompt(self, symbol: str, date: str, quarterly_context: Dict) -> str:
        """Create comprehensive LLM prompt for sentiment analysis."""
        # Apply date obfuscation if enabled
        display_date = date
        if self.enable_obfuscation and self.obfuscator:
            date_mapping = self.obfuscator.obfuscate_dates([date])
            display_date = date_mapping.get(date, date)
            self.current_date_mapping[date] = display_date

        # Safely handle quarterly context data
        news_data = quarterly_context.get('news_data', 'No news data available')
        vxx_data = quarterly_context.get('vxx_data', 'No VXX data available')
        market_data = quarterly_context.get('market_data', 'No market context available')

        # Ensure data is string-convertible
        if news_data is None:
            news_data = 'No news data available'
        if vxx_data is None:
            vxx_data = 'No VXX data available'
        if market_data is None:
            market_data = 'No market context available'

        prompt = f"""You are an intelligent market analyst. Here's the data for {symbol} on {display_date}:

NEWS DATA:
{news_data}

VXX VOLATILITY DATA:
{vxx_data}

MARKET CONTEXT (SPY/QQQ):
{market_data}

Use your understanding of markets to provide a sentiment score from -1.0 to +1.0.

Key insights to consider:
- When VXX is high, fear often creates opportunity
- When VXX is low, watch out below - complacency is dangerous
- If {symbol} diverges from SPY/QQQ, determine if it's sector rotation or company-specific
- Bad news during high fear might already be priced in
- Good news during low volatility might not move prices much

Think about what these signals mean together, not as isolated rules.

Return: {{"sentiment": <your_score>, "reasoning": "<brief explanation>"}}"""

        return prompt

    async def _get_llm_sentiment_decision(self, prompt: str) -> Dict:
        """Get LLM's sentiment decision for a specific prompt."""
        try:
            # Use the working process_with_tools pattern instead of broken async wrapper
            system_prompt = """You are an intelligent trader who understands market psychology and relationships.
            Consider: What does high fear mean for future returns? What does complacency signal?
            How do individual stocks relate to broader market moves? Think, don't just follow rules.
            Return: {"decision": "BUY|SELL|HOLD", "sentiment": <-1.0 to 1.0>, "reasoning": "<your analysis>"}"""

            # Use the working async wrapper
            response = await asyncio.create_task(
                self._run_process_with_tools_async(prompt, system_prompt)
            )

            # Handle None response (graceful fallback)
            if not response:
                self.logger.warning("V4Agent: LLM response was None, using neutral sentiment")
                return {"sentiment": 0.0, "confidence": 0.5, "reasoning": "LLM response was None"}

            # Log the raw response for debugging
            self.logger.debug(f"V4Agent: Raw LLM response: {response[:200]}...")

            # Parse LLM response for sentiment decision
            if "{" in response and "}" in response:
                # Extract JSON from response
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]

                try:
                    decision = json.loads(json_str)
                    self.logger.debug(f"V4Agent: Parsed decision: {decision}")
                    return decision
                except json.JSONDecodeError as je:
                    self.logger.error(f"V4Agent: JSON parse error: {je}")
                    return {"sentiment": 0.0, "confidence": 0.5, "reasoning": f"JSON parse error: {je}"}

            # Fallback if JSON parsing fails
            self.logger.warning(f"V4Agent: No JSON found in response: {response[:100]}...")
            return {"sentiment": 0.0, "confidence": 0.5, "reasoning": "LLM response parsing failed"}

        except Exception as e:
            self.logger.error(f"V4Agent: LLM decision failed: {e}")
            return {"sentiment": 0.0, "confidence": 0.0, "reasoning": f"Error: {e}"}

    def get_sentiment_for_date(self, date: str, symbol: str = None) -> Dict:
        """
        Fast lookup of pre-computed LLM sentiment decision for a specific date.

        Args:
            date: Date in YYYY-MM-DD format
            symbol: Stock symbol (optional, uses prepared symbol if not provided)

        Returns:
            Dict with LLM sentiment decision for the date
        """
        if not self.is_prepared:
            self.logger.warning("V4Agent: Not prepared - falling back to single-day mode")
            return {"sentiment": 0.0, "confidence": 0.0, "version": "V4", "mode": "fallback"}

        # Use prepared symbol if not provided
        lookup_symbol = symbol or self.prepared_symbol
        memory_key = f"{lookup_symbol}_{self.prepared_period[0]}_{self.prepared_period[1]}"

        if memory_key in self.quarterly_memory and date in self.quarterly_memory[memory_key]:
            return self.quarterly_memory[memory_key][date]
        else:
            self.logger.warning(f"V4Agent: Date {date} not in prepared data")
            return {"sentiment": 0.0, "confidence": 0.0, "version": "V4", "mode": "date_miss"}

    def clear_memory(self):
        """Clear quarterly memory and obfuscation mappings."""
        self.quarterly_memory.clear()
        self.is_prepared = False
        self.prepared_symbol = None
        self.prepared_period = None
        self.current_date_mapping.clear()
        self.logger.info("V4Agent: Memory cleared (including obfuscation mappings)")

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

            system_content = f"""You are an intelligent market analyst who understands market psychology.
{obfuscation_warning}

Get the latest data for {tool_symbol} on {tool_date}:
1. fetch_google_search_news
2. fetch_vxx_volatility_data  
3. fetch_market_context_data

Analyze this data with these insights:
- High VXX means fear - often the best time to buy
- Low VXX means complacency - time to be cautious
- News matters, but understand if it's company-specific or market-wide
- SPY/QQQ divergence from {tool_symbol} might indicate sector rotation vs individual issues
- Think about what the combination of signals tells you, not individual rules

Be contrarian when appropriate - extreme sentiment often reverses.

Return: {{"sentiment": <your_score from -1.0 to +1.0>, "reasoning": "<brief explanation>"}}"""

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
