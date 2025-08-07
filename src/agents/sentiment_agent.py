"""
SentimentAgent - Pure text-based sentiment analysis.

This agent performs sentiment analysis exclusively from news articles and text sources.
When no news is available, it returns neutral sentiment (0.0) with zero confidence.

Key features:
1. Multi-source news aggregation and analysis
2. LLM-driven sentiment scoring with explanations
3. Confidence scoring based on news availability and relevance
4. No market indicators - purely text-based analysis
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
# Import MarketDataTool only for market heat calculation (SPY momentum, sector rotation)
from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.tools.cache.news_cache import NewsCache

# Set up logging
logger = logging.getLogger(__name__)

# LLM config optimized for sentiment analysis and narrative generation
SENTIMENT_LLM_CONFIG = {
    "temperature": 0.3,  # Slightly higher for creative narratives
    "max_tokens": 4096,  # Ensure enough tokens for complex responses
    "top_p": 0.9,        # Allow for some creative variety
}

# Removed VXX thresholds - sentiment is now purely text-based


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

        # Removed VXX fallback - sentiment is now purely text-based

        # Initialize news cache
        self.news_cache = NewsCache()

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

    # Removed VXX fallback method - sentiment is now purely text-based

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

        # Note: Sentiment is now purely text-based
        context.append(
            "\nNOTE: Sentiment analysis is purely text-based. If no news is available, neutral sentiment (0.0) will be returned.")

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

    async def _execute_tool(self, tool_name: str, tool_args: Any) -> Any:
        """
        Override to add news caching for fetch_all_news tool.
        Only caches relevant news (relevance_score >= 0.5).
        """
        # Check if this is a news fetch that can be cached
        if tool_name == "fetch_all_news" and isinstance(tool_args, dict):
            # Extract parameters
            keywords = tool_args.get("keywords", [])
            if isinstance(keywords, str):
                keywords = [keywords]
            ticker = tool_args.get("ticker", "")
            count = tool_args.get("count", 10)

            # Extract date range from tool args
            # The sentiment agent typically queries for a specific date
            # but we'll cache with a small range around it
            start_date = tool_args.get("start_date", "")
            end_date = tool_args.get("end_date", "")

            # If only one date provided, create a small range
            if start_date and not end_date:
                end_date = start_date
            elif not start_date and not end_date:
                # Default to today
                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                start_date = end_date = today

            # Check cache first
            cached_data = self.news_cache.get(
                keywords=keywords,
                ticker=ticker,
                start=start_date,
                end=end_date,
                source="unified"
            )

            if cached_data is not None:
                # Convert DataFrame back to the expected format
                if not cached_data.empty:
                    # Filter by relevance score if present
                    if 'relevance_score' in cached_data.columns:
                        relevant_data = cached_data[cached_data['relevance_score'] >= 0.5]
                    else:
                        relevant_data = cached_data

                    # Limit to requested count
                    relevant_data = relevant_data.head(count)

                    result = {
                        "articles": relevant_data.to_dict(orient="records"),
                        "count": len(relevant_data),
                        "total_articles": len(relevant_data),
                        "sources_used": ["cache"],
                        "search_guidance": f"Using cached news data for {ticker} from {start_date} to {end_date}"
                    }
                else:
                    # Empty cache means no news was found previously
                    result = {
                        "articles": [],
                        "count": 0,
                        "total_articles": 0,
                        "sources_used": ["cache"],
                        "search_guidance": "No cached news found for this period"
                    }

                logger.info(f"Using cached news for {ticker} ({start_date} to {end_date})")
                return result

        # Call the parent method for actual tool execution
        result = await super()._execute_tool(tool_name, tool_args)

        # Cache the result if it's from fetch_all_news
        if tool_name == "fetch_all_news" and isinstance(result, dict) and isinstance(tool_args, dict):
            # Extract parameters for caching
            cache_keywords = tool_args.get("keywords", [])
            if isinstance(cache_keywords, str):
                cache_keywords = [cache_keywords]
            cache_ticker = tool_args.get("ticker", "")
            cache_start_date = tool_args.get("start_date", "")
            cache_end_date = tool_args.get("end_date", "")

            # If only one date provided, create a small range
            if cache_start_date and not cache_end_date:
                cache_end_date = cache_start_date
            elif not cache_start_date and not cache_end_date:
                # Default to today
                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                cache_start_date = cache_end_date = today

            # Only cache if we have articles
            if result.get("articles"):
                articles_df = pd.DataFrame(result["articles"])

                # Only cache relevant articles (relevance_score >= 0.5)
                if 'relevance_score' in articles_df.columns:
                    relevant_articles = articles_df[articles_df['relevance_score'] >= 0.5]
                else:
                    relevant_articles = articles_df

                # Only cache if we have relevant articles
                if not relevant_articles.empty:
                    self.news_cache.set(
                        keywords=cache_keywords,
                        ticker=cache_ticker,
                        start=cache_start_date,
                        end=cache_end_date,
                        source="unified",
                        data=relevant_articles
                    )
                    logger.info(
                        f"Cached {len(relevant_articles)} relevant news articles for {cache_ticker}")
            else:
                # Cache empty result to avoid repeated API calls
                self.news_cache.set(
                    keywords=cache_keywords,
                    ticker=cache_ticker,
                    start=cache_start_date,
                    end=cache_end_date,
                    source="unified",
                    data=pd.DataFrame()
                )
                logger.info(f"Cached empty news result for {cache_ticker}")

        return result

    def analyze_market_heat(self, date: str) -> Dict[str, Any]:
        """
        Market heat assessment using SPY momentum and sector rotation.
        
        Formula: heat = 0.5 * spy_momentum + 0.5 * sector_rotation
        
        Args:
            date: Target date in YYYY-MM-DD format
            
        Returns:
            Dictionary with heat level (-1 to +1), components, and interpretation
        """
        try:
            # Component 1: SPY momentum (50% weight)
            spy_component = self._calculate_spy_momentum_component(date)
            
            # Component 2: Sector rotation (50% weight)
            sector_component = self._calculate_sector_rotation_component(date)
            
            # Calculate weighted heat score (no VXX)
            heat_score = (
                0.5 * spy_component['score'] +
                0.5 * sector_component['score']
            )
            
            # Determine interpretation
            if heat_score > 0.6:
                interpretation = "Very Hot - Strong bullish conditions"
            elif heat_score > 0.2:
                interpretation = "Hot - Bullish market sentiment"
            elif heat_score > -0.2:
                interpretation = "Neutral - Mixed market conditions"
            elif heat_score > -0.6:
                interpretation = "Cold - Bearish market sentiment"
            else:
                interpretation = "Very Cold - Strong bearish conditions"
            
            return {
                "heat_level": round(heat_score, 3),
                "interpretation": interpretation,
                "components": {
                    "spy_momentum": spy_component,
                    "sector_rotation": sector_component
                },
                "date": date,
                "analysis_type": "rule-based"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market heat: {str(e)}")
            return {
                "heat_level": 0.0,
                "interpretation": f"Error calculating market heat: {str(e)}",
                "components": {},
                "date": date
            }
    
    # Removed VXX heat component calculation - sentiment is now purely text-based
    
    def _calculate_spy_momentum_component(self, date: str) -> Dict[str, Any]:
        """Calculate SPY momentum component using 20-day price change."""
        try:
            # Get SPY data for the last 20 trading days
            end_date = pd.to_datetime(date)
            start_date = end_date - timedelta(days=30)  # Extra days for weekends
            
            market_data_tool = MarketDataTool()
            spy_data = market_data_tool.fetch_market_data(
                symbol="SPY", 
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d")
            )
            
            if spy_data.empty or len(spy_data) < 20:
                return {"score": 0.0, "value": None, "description": "Insufficient SPY data"}
            
            # Calculate 20-day return
            current_price = spy_data.iloc[-1]['Close']
            price_20d_ago = spy_data.iloc[-20]['Close']
            momentum_pct = ((current_price - price_20d_ago) / price_20d_ago) * 100
            
            # Normalize to -1 to +1 scale
            # -10% or worse: -1.0
            # -5%: -0.5
            # 0%: 0.0
            # +5%: +0.5
            # +10% or better: +1.0
            
            score = max(-1.0, min(1.0, momentum_pct / 10))
            
            return {
                "score": round(score, 3),
                "value": round(momentum_pct, 2),
                "description": f"SPY 20d: {momentum_pct:+.1f}%"
            }
            
        except Exception as e:
            logger.error(f"Error calculating SPY momentum: {str(e)}")
            return {"score": 0.0, "value": None, "description": f"Error: {str(e)}"}
    
    def _calculate_sector_rotation_component(self, date: str) -> Dict[str, Any]:
        """Calculate sector rotation component by comparing defensive vs growth sectors."""
        try:
            # Define sector ETFs
            growth_sectors = ["XLK", "XLY"]  # Tech, Consumer Discretionary
            defensive_sectors = ["XLU", "XLP"]  # Utilities, Consumer Staples
            
            end_date = pd.to_datetime(date)
            start_date = end_date - timedelta(days=30)
            
            market_data_tool = MarketDataTool()
            
            # Calculate average performance for each group
            growth_perf = []
            defensive_perf = []
            
            for sector in growth_sectors:
                try:
                    data = market_data_tool.fetch_market_data(
                        symbol=sector,
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d")
                    )
                    if not data.empty and len(data) >= 20:
                        perf = ((data.iloc[-1]['Close'] - data.iloc[-20]['Close']) / 
                               data.iloc[-20]['Close']) * 100
                        growth_perf.append(perf)
                except:
                    pass
            
            for sector in defensive_sectors:
                try:
                    data = market_data_tool.fetch_market_data(
                        symbol=sector,
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d")
                    )
                    if not data.empty and len(data) >= 20:
                        perf = ((data.iloc[-1]['Close'] - data.iloc[-20]['Close']) / 
                               data.iloc[-20]['Close']) * 100
                        defensive_perf.append(perf)
                except:
                    pass
            
            if not growth_perf or not defensive_perf:
                return {"score": 0.0, "value": None, "description": "Insufficient sector data"}
            
            # Calculate rotation score
            avg_growth = sum(growth_perf) / len(growth_perf)
            avg_defensive = sum(defensive_perf) / len(defensive_perf)
            rotation_diff = avg_growth - avg_defensive
            
            # Normalize to -1 to +1
            # Growth outperforming by 5%+: +1.0
            # Growth outperforming by 2.5%: +0.5
            # Equal performance: 0.0
            # Defensive outperforming by 2.5%: -0.5
            # Defensive outperforming by 5%+: -1.0
            
            score = max(-1.0, min(1.0, rotation_diff / 5))
            
            return {
                "score": round(score, 3),
                "value": round(rotation_diff, 2),
                "description": f"Growth vs Defensive: {rotation_diff:+.1f}%"
            }
            
        except Exception as e:
            logger.error(f"Error calculating sector rotation: {str(e)}")
            return {"score": 0.0, "value": None, "description": f"Error: {str(e)}"}

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
                        logger.info(
                            f"Low confidence sentiment detected: score={json_data.get('score')}, confidence={json_data.get('confidence')}")
            except:
                pass

            if no_news_found:
                logger.info(
                    f"No relevant news found for {symbol} on {date}, returning neutral sentiment")
                
                # Return neutral sentiment when no news is available
                # This ensures sentiment is purely text-based
                response = json.dumps({
                    "score": 0.0,
                    "analysis": f"No relevant news articles were found for {symbol} on {date}. Without text-based information, sentiment cannot be determined.",
                    "confidence": 0.0,
                    "key_themes": [],
                    "data_source": "no_news"
                })
                
                # Log the sentiment source
                logger.info(
                    f"Sentiment source for {symbol} on {date}: No news (neutral)")
            else:
                # Log that news was used (sources: Google Search, Yahoo scraper, Finnhub, NewsAPI)
                logger.info(
                    f"Sentiment source for {symbol} on {date}: News data (checking Google Search, Yahoo scraper, Finnhub, NewsAPI)")

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
