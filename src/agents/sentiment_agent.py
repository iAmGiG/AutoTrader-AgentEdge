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
            "- fetch_news: Get general news articles on a specific topic or keyword")
        context.append(
            "- fetch_alpha_vantage_news: Get news specifically about a stock ticker with pre-calculated sentiment")
        context.append(
            "- search_sec_filings: Search for specific terms in SEC filings to get context about company disclosures")

        return "\n".join(context)

    def process_tool_result(self, tool_name: str, result: Any, tool_args: dict) -> Any:
        """
        Process tool results with sentiment-specific handling.
        This override adds specialized processing for news and filing data.

        Args:
            tool_name: The name of the tool that was called
            result: The raw result from the tool
            tool_args: The arguments that were passed to the tool

        Returns:
            Processed result in a simple, JSON-serializable format
        """
        try:
            # First, ensure tool_args is a dictionary for safe access
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

            # For debugging
            print(f"Processing tool result for {tool_name}")

            # Process the result based on tool type
            if tool_name == "fetch_news":
                # Simple formatted results for news data
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Extract headlines
                    headlines = []
                    headline_cols = ["Headline", "title", "Title", "headline"]
                    for col in headline_cols:
                        if col in result.columns:
                            # Limit to 5 headlines
                            headlines = result[col].tolist()[:5]
                            break
                    # Extract sentiment if available
                    sentiment = None
                    sentiment_cols = [
                        "Sentiment Score", "sentiment_score", "overall_sentiment_score", "score"]

                    for col in sentiment_cols:
                        if col in result.columns:
                            sentiment = float(result[col].mean())
                            break
                    # Build a simple news summary
                    news_summary = {
                        "headlines": headlines if headlines else ["No headlines available"],
                        "count": len(result),
                        "average_sentiment": sentiment,
                        "sources": result["Source"].tolist()[:5] if "Source" in result.columns else []
                    }
                    return news_summary
                return {"headlines": [], "count": 0, "message": "No news data available"}

            elif tool_name == "fetch_alpha_vantage_news":
                # Process Alpha Vantage news+sentiment
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Extract key information
                    ticker = tool_args.get("symbol", "")

                    # If sentiment scores are available, summarize them
                    if "sentiment_score" in result.columns:
                        avg_sentiment = float(result["sentiment_score"].mean())
                        sentiment_counts = result["sentiment"].value_counts(
                        ).to_dict()
                    else:
                        avg_sentiment = None
                        sentiment_counts = {}

                    # Extract headlines or titles
                    headlines = []
                    for col in ["title", "headline"]:
                        if col in result.columns:
                            headlines = result[col].tolist()[:5]
                            break

                    # Build summary
                    news_summary = {
                        "ticker": ticker,
                        "headlines": headlines if headlines else ["No headlines available"],
                        "count": len(result),
                        "average_sentiment_score": avg_sentiment,
                        "sentiment_distribution": sentiment_counts
                    }

                    return news_summary
                return {"ticker": tool_args.get("symbol", ""), "count": 0, "message": "No news data available"}

            elif tool_name == "search_sec_filings":
                # Process SEC filing search results
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Extract key information
                    ticker = tool_args.get("ticker", "")
                    search_terms = tool_args.get("search_terms", [])

                    # Build search result summary
                    search_summary = {
                        "ticker": ticker,
                        "search_terms": search_terms,
                        "total_matches": len(result),
                        "filing_dates": sorted(result["filing_date"].astype(str).unique().tolist()),
                        "sections_with_matches": sorted(result["section"].unique().tolist()),
                        "sample_contexts": []
                    }

                    # Add a sample of contexts for each search term
                    for term in search_terms:
                        term_matches = result[result["search_term"] == term]
                        if not term_matches.empty:
                            # Get up to 2 contexts per term
                            contexts = term_matches["context"].tolist()[:2]
                            for context in contexts:
                                search_summary["sample_contexts"].append({
                                    "term": term,
                                    "context": context
                                })

                    return search_summary

                return {
                    "ticker": tool_args.get("ticker", ""),
                    "search_terms": tool_args.get("search_terms", []),
                    "total_matches": 0,
                    "message": "No matches found in SEC filings"
                }

            # Handle the unified news tool specifically
            if tool_name == "fetch_all_news":
                # This is the unified news tool result, with built-in fields
                if isinstance(result, dict) and "articles" in result:
                    # Extract search guidance and add notes on relevance filtering
                    search_guidance = result.get("search_guidance", "")
                    
                    # Add note about filtering by relevance if we have relevance scores
                    articles = result["articles"]
                    filtered_articles = []
                    low_relevance_count = 0
                    
                    # Filter articles if relevance_score exists
                    if articles and len(articles) > 0 and "relevance_score" in articles[0]:
                        for article in articles:
                            if article.get("relevance_score", 0) >= 0.5:
                                filtered_articles.append(article)
                            else:
                                low_relevance_count += 1
                    else:
                        filtered_articles = articles
                    
                    # Process the filtered articles
                    if filtered_articles:
                        # Extract headlines
                        headlines = []
                        for article in filtered_articles[:5]:
                            headline = article.get("title", "No headline available")
                            score = article.get("relevance_score", "N/A")
                            headlines.append(f"{headline} (relevance: {score})")
                        
                        # Calculate average sentiment if available
                        sentiment_scores = [article.get("sentiment_score", None) for article in filtered_articles 
                                          if article.get("sentiment_score") is not None]
                        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None
                        
                        # Count sources
                        sources = set()
                        for article in filtered_articles:
                            if "source_id" in article:
                                sources.add(article["source_id"])
                        
                        # Build a summary with relevance information
                        summary = {
                            "headlines": headlines,
                            "count": len(filtered_articles),
                            "original_count": len(articles),
                            "low_relevance_filtered": low_relevance_count,
                            "average_sentiment": avg_sentiment,
                            "sources": list(sources),
                            "search_guidance": search_guidance,
                            "search_terms": {
                                "ticker": result.get("ticker", None),
                                "keywords": result.get("keywords", None),
                                "date_range": result.get("date_range", None)
                            }
                        }
                        
                        # Add guidance for follow-up searches if needed
                        if low_relevance_count > 0 and len(filtered_articles) < 3:
                            summary["search_recommendation"] = "Consider trying a more specific search with better keywords"
                        
                        return summary
                    else:
                        return {
                            "count": 0,
                            "message": "No relevant articles found. Try different search terms.",
                            "search_guidance": search_guidance,
                            "original_count": len(articles),
                            "search_terms": {
                                "ticker": result.get("ticker", None),
                                "keywords": result.get("keywords", None)
                            }
                        }
                    
                # Return the result as is if it doesn't match our expected structure
                return result
                
            # Handle other cases - ensure result is simple and serializable
            if isinstance(result, pd.DataFrame):
                # Generic DataFrame handling - convert to simple dict with limited rows
                if not result.empty:
                    return {
                        "summary": f"DataFrame with {len(result)} rows and columns: {', '.join(list(result.columns))}",
                        "sample_data": result.head(3).to_dict(orient="records")
                    }
                return {"summary": "Empty DataFrame"}
            # Return the result as is if it's already serializable
            return result
        except Exception as e:
            traceback.print_exc()
            print(f"Error in process_tool_result: {str(e)}")
            return {"error": f"Failed to process result: {str(e)}"}

    def generate_reply(self, messages, context=None):
        """
        Primary entry point for generating replies to user messages.
        Let's the LLM decide which tools to call based on the query.

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

        # Add guidance to use multiple tools
        system_prompt += "\n\nIMPORTANT: For comprehensive analysis, you should use MULTIPLE relevant tools rather than just one. Use multiple data sources for cross-validation and deeper insights."

        # Add guidance about using the unified news tool with relevance scoring
        system_prompt += "\n\nNEWS RELEVANCE SCORING:"
        system_prompt += "\n- The fetch_all_news tool sorts articles by relevance to your query"
        system_prompt += "\n- Pay attention to the 'relevance_score' field - higher means more relevant"
        system_prompt += "\n- IGNORE articles with relevance_score < 0.5 as they are likely not relevant"
        system_prompt += "\n- Check the 'search_guidance' field which gives feedback on result quality"
        system_prompt += "\n- If search_guidance indicates poor results, try a different search with more specific keywords"

        # Add specific guidance based on extracted entities
        if query_details.get("ticker"):
            ticker = query_details["ticker"]
            system_prompt += f"\n\nThis query mentions the stock ticker {ticker}. For comprehensive analysis, use these tools:"
            system_prompt += f"\n1. fetch_all_news(ticker=\"{ticker}\", keywords=\"earnings,performance,news\") - For relevant news with smart filtering"
            system_prompt += f"\n2. fetch_market_data(ticker=\"{ticker}\", start_date=\"{query_details.get('start_date')}\") - For price and volume data"
            system_prompt += f"\n3. fetch_finnhub_news(tickers=['{ticker}']) - For additional financial news"

        if query_details.get("topic"):
            topic = query_details["topic"]
            system_prompt += f"\n\nThis query mentions the topic '{topic}'. Use these news sources for comprehensive coverage:"
            system_prompt += f"\n1. fetch_all_news(keywords=\"{topic}\", count=10) - For relevant news with smart filtering"
            system_prompt += f"\n2. fetch_finnhub_financial_headlines() - For financial market headlines that may relate to {topic}"
            system_prompt += f"\n3. fetch_finnhub_economic_headlines() - For economic news that may impact {topic}"

        # Add guidance for SEC filings search if appropriate
        if query_details.get("ticker") and any(term in last_message.lower() for term in ["risk", "sec", "filing", "10-k", "10k", "report", "risk", "earnings", "er"]):
            ticker = query_details["ticker"]
            system_prompt += f"\n\nThis query appears to be asking about SEC filings or earnings. Include regulatory information with:"
            system_prompt += f"\n1. search_sec_filings(ticker=\"{ticker}\", search_terms=[\"risk\", \"earnings\"], form_type=\"10-K\") - For risk disclosures"

        # Let the LLM generate a response with tool usage
        # process_with_tools may return a coroutine if in an async context
        return self.process_with_tools(last_message, system_prompt)
