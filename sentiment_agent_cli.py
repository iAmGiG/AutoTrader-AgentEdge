#!/usr/bin/env python3
"""
Consolidated CLI for interacting with the Sentiment Agent.

This script provides both a direct CLI for testing the SentimentAgent class
and a simplified interactive mode using function calling with AutoGen 0.5.x
"""

import sys
import os
import argparse
import json
import pandas as pd
import traceback

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath('.'))

# Import configuration
from config.config_loader import ConfigLoader

# Import the SentimentAgent class
from src.agents.sentiment_agent import SentimentAgent

# Import the data fetching functions directly
from src.tools.data_sources.yahoo_finance_tool import YahooFinanceTool
from src.tools.data_sources.news_headline_tool import NewsHeadlineTool
from src.tools.data_sources.alpha_vantage_tool import AlphaVantageTool
from src.tools.data_sources.market_data_tool import MarketDataTool

# Import all tools from tools.py
from src.tools.tools import (
    fetch_market_data, 
    fetch_news, 
    fetch_yahoo_data, 
    fetch_alpha_vantage_data, 
    fetch_alpha_vantage_news
)

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import openai
        import yfinance
        
        # Test AutoGen core imports
        try:
            import autogen_core
            import autogen_agentchat
            import autogen_ext
            print("✅ autogen_ext found successfully")
            print("✅ autogen_agentchat found successfully")
            return True
        except ImportError:
            print("❌ AutoGen 0.5.x packages not found.")
            print("Make sure you're using the correct conda environment.")
            print("Try: conda activate AutoGen")
            return False
            
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Try: pip install openai yfinance")
        return False

def fetch_yahoo_stock_data(ticker="AAPL", start_date="-7d", end_date=None):
    """
    Fetch stock data using Yahoo Finance.
    """
    try:
        tool = YahooFinanceTool()
        data = tool.fetch_stock_data(ticker, start_date, end_date)
        
        if data is None or data.empty:
            return {
                "error": f"No data available for {ticker}",
                "status": "error"
            }
            
        # Convert to a simpler format for OpenAI response
        result = {
            "status": "success",
            "source": "Yahoo Finance",
            "ticker": ticker,
            "days": len(data),
            "start_date": data.index[0].strftime("%Y-%m-%d"),
            "end_date": data.index[-1].strftime("%Y-%m-%d"),
            "data_sample": data.head(3).to_dict(orient="records"),
            "summary": {
                "first_close": round(data['Close'].iloc[0], 2),
                "last_close": round(data['Close'].iloc[-1], 2),
                "change_pct": round(((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0]) * 100, 2),
                "avg_volume": int(data['Volume'].mean())
            }
        }
        return result
    except Exception as e:
        traceback.print_exc()
        return {
            "error": f"Error fetching Yahoo Finance data: {str(e)}",
            "status": "error"
        }

def fetch_alpha_vantage_stock_data(symbol="AAPL", start_date="-30d", end_date="today"):
    """
    Fetch stock data from Alpha Vantage.
    """
    try:
        data = fetch_alpha_vantage_data(symbol=symbol, start_date=start_date, end_date=end_date)
        
        if data is None or data.empty:
            return {
                "error": f"No Alpha Vantage data available for {symbol}",
                "status": "error"
            }

        # Normalize column names if needed
        close_col = 'Close' if 'Close' in data.columns else 'close'
        volume_col = 'Volume' if 'Volume' in data.columns else 'volume'
            
        # Convert to a simpler format for OpenAI response
        result = {
            "status": "success",
            "source": "Alpha Vantage",
            "ticker": symbol,
            "days": len(data),
            "start_date": data.index[0].strftime("%Y-%m-%d") if hasattr(data.index[0], 'strftime') else str(data.index[0]),
            "end_date": data.index[-1].strftime("%Y-%m-%d") if hasattr(data.index[-1], 'strftime') else str(data.index[-1]),
            "data_sample": data.head(3).to_dict(orient="records"),
            "summary": {
                "first_close": round(float(data[close_col].iloc[0]), 2),
                "last_close": round(float(data[close_col].iloc[-1]), 2),
                "change_pct": round(((float(data[close_col].iloc[-1]) - float(data[close_col].iloc[0])) / float(data[close_col].iloc[0])) * 100, 2),
                "avg_volume": int(data[volume_col].mean()) if volume_col in data.columns else 0
            }
        }
        return result
    except Exception as e:
        traceback.print_exc()
        return {
            "error": f"Error fetching Alpha Vantage data: {str(e)}",
            "status": "error"
        }

def fetch_market_data_unified(symbol="AAPL", start_date="-30d", end_date="today", source="yahoo"):
    """
    Fetch market data using the unified MarketDataTool.
    """
    try:
        tool = MarketDataTool({"data_source": source})
        data = tool.fetch_market_data(symbol, start_date, end_date)
        
        if data is None or data.empty:
            return {
                "error": f"No market data available for {symbol} from {source}",
                "status": "error"
            }
            
        # Normalize column names if needed
        close_col = 'Close' if 'Close' in data.columns else 'close'
        volume_col = 'Volume' if 'Volume' in data.columns else 'volume'
            
        # Convert to a simpler format for OpenAI response
        result = {
            "status": "success",
            "source": source,
            "ticker": symbol,
            "days": len(data),
            "start_date": data.index[0].strftime("%Y-%m-%d") if hasattr(data.index[0], 'strftime') else str(data.index[0]),
            "end_date": data.index[-1].strftime("%Y-%m-%d") if hasattr(data.index[-1], 'strftime') else str(data.index[-1]),
            "data_sample": data.head(3).to_dict(orient="records"),
            "summary": {
                "first_close": round(float(data[close_col].iloc[0]), 2),
                "last_close": round(float(data[close_col].iloc[-1]), 2),
                "change_pct": round(((float(data[close_col].iloc[-1]) - float(data[close_col].iloc[0])) / float(data[close_col].iloc[0])) * 100, 2),
                "avg_volume": int(data[volume_col].mean()) if volume_col in data.columns else 0
            }
        }
        return result
    except Exception as e:
        traceback.print_exc()
        return {
            "error": f"Error fetching unified market data: {str(e)}",
            "status": "error"
        }

def fetch_news_data(keyword="market", count=5):
    """
    Fetch news headlines for a topic or ticker using NewsHeadlineTool.
    """
    try:
        tool = NewsHeadlineTool()
        news_df = tool.fetch_data(keyword=keyword, count=count)
        
        if news_df is None or news_df.empty:
            return {
                "error": f"No news available for {keyword}",
                "status": "error"
            }
            
        result = {
            "status": "success",
            "keyword": keyword,
            "article_count": len(news_df),
            "headlines": news_df[['Headline', 'Source', 'Sentiment Score']].to_dict(orient='records'),
            "avg_sentiment": round(news_df['Sentiment Score'].mean(), 2) if 'Sentiment Score' in news_df.columns else 0
        }
        
        return result
    except Exception as e:
        traceback.print_exc()
        return {
            "error": f"Error fetching news: {str(e)}",
            "status": "error"
        }

def fetch_alpha_vantage_news_data(symbol="AAPL", topics=None, count=5):
    """
    Fetch news and sentiment data from Alpha Vantage API.
    """
    try:
        print(f"🔍 Fetching Alpha Vantage news for symbol: {symbol}, topics: {topics}")
        
        # Now call through the function tool
        print("🔍 Calling fetch_alpha_vantage_news function tool")
        news_df = fetch_alpha_vantage_news(symbol=symbol, topics=topics)
        
        # Debug info about the news dataframe
        if news_df is not None:
            print(f"🔍 Alpha Vantage news dataframe: {news_df.shape}, columns: {list(news_df.columns)}")
            if len(news_df) > 0:
                print(f"🔍 Sample data: {news_df.iloc[0].to_dict()}")
        else:
            print("🔍 Alpha Vantage news dataframe is None")
            
        if news_df is None or news_df.empty:
            return {
                "error": f"No Alpha Vantage news available for {symbol}",
                "status": "error"
            }
        
        # Identify title/headline column
        title_col = None
        for col in ['title', 'Title', 'headline', 'Headline']:
            if col in news_df.columns:
                title_col = col
                break
                
        # Identify source column
        source_col = None
        for col in ['source', 'Source', 'provider', 'Provider']:
            if col in news_df.columns:
                source_col = col
                break
                
        # Identify sentiment column
        sentiment_col = None
        for col in ['sentiment_score', 'Sentiment Score', 'overall_sentiment_score', 'score']:
            if col in news_df.columns:
                sentiment_col = col
                break
        
        # If the required columns are found, create the result
        if title_col and source_col:
            headlines = []
            for _, row in news_df.head(count).iterrows():
                headline_item = {
                    "headline": row[title_col],
                    "source": row[source_col]
                }
                if sentiment_col:
                    headline_item["sentiment_score"] = float(row[sentiment_col]) if pd.notnull(row[sentiment_col]) else 0.0
                headlines.append(headline_item)
                
            result = {
                "status": "success",
                "source": "Alpha Vantage",
                "symbol": symbol,
                "article_count": len(news_df),
                "headlines": headlines
            }
            
            if sentiment_col:
                result["avg_sentiment"] = float(news_df[sentiment_col].mean()) if not news_df[sentiment_col].empty else 0.0
                
            return result
        else:
            return {
                "error": "Could not identify required columns in Alpha Vantage news data",
                "status": "error"
            }
    except Exception as e:
        traceback.print_exc()
        return {
            "error": f"Error fetching Alpha Vantage news: {str(e)}",
            "status": "error"
        }

def fetch_combined_news(keyword: str, symbol: str = None, count: int = 5):
    """
    Fetch news from both NewsAPI and Alpha Vantage, combining the results.
    
    Args:
        keyword: General topic or search term for NewsAPI
        symbol: Stock symbol for Alpha Vantage (optional)
        count: Number of articles to retrieve from each source
        
    Returns:
        Combined news data from both sources
    """
    print(f"🔄 Fetching combined news - keyword: {keyword}, symbol: {symbol}")
    
    # Initialize results
    news_api_headlines = []
    alpha_vantage_headlines = []
    total_count = 0
    avg_sentiment = 0
    sentiment_values = []
    
    # First get general news
    try:
        news_result = fetch_news_data(keyword=keyword, count=count)
        if news_result and news_result.get("status") == "success":
            news_api_headlines = news_result.get("headlines", [])
            # Mark the source
            for headline in news_api_headlines:
                headline["news_source"] = "NewsAPI"
                if "sentiment_score" in headline:
                    sentiment_values.append(headline["sentiment_score"])
            total_count += len(news_api_headlines)
            print(f"✅ NewsAPI returned {len(news_api_headlines)} articles")
        else:
            print(f"⚠️ NewsAPI returned no articles: {news_result}")
    except Exception as e:
        print(f"⚠️ Error fetching from NewsAPI: {str(e)}")
    
    # Then get Alpha Vantage news if a symbol is provided
    if symbol:
        try:
            av_result = fetch_alpha_vantage_news_data(symbol=symbol, count=count)
            if av_result and av_result.get("status") == "success":
                alpha_vantage_headlines = av_result.get("headlines", [])
                # Mark the source
                for headline in alpha_vantage_headlines:
                    headline["news_source"] = "Alpha Vantage"
                    if "sentiment_score" in headline:
                        sentiment_values.append(headline["sentiment_score"])
                total_count += len(alpha_vantage_headlines)
                print(f"✅ Alpha Vantage returned {len(alpha_vantage_headlines)} articles")
            else:
                print(f"⚠️ Alpha Vantage returned no articles: {av_result}")
        except Exception as e:
            print(f"⚠️ Error fetching from Alpha Vantage: {str(e)}")
    
    # Combine headlines and calculate average sentiment
    combined_headlines = news_api_headlines + alpha_vantage_headlines
    
    if sentiment_values:
        avg_sentiment = sum(sentiment_values) / len(sentiment_values)
    
    result = {
        "status": "success",
        "keyword": keyword,
        "symbol": symbol,
        "article_count": total_count,
        "headlines": combined_headlines,
        "avg_sentiment": round(avg_sentiment, 2) if sentiment_values else None,
        "sources_used": ["NewsAPI"] + (["Alpha Vantage"] if symbol else [])
    }
    
    return result

def process_with_llm(prompt, system_prompt=None):
    """
    Process a prompt with OpenAI directly (no tool calling).
    """
    try:
        # Load configuration
        loader = ConfigLoader()
        openai_key = loader.get("open_ai_key")
        model_name = loader.get("open_model") or "gpt-4o"
        
        # Import OpenAI
        import openai
        client = openai.OpenAI(api_key=openai_key)
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Call OpenAI API
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        traceback.print_exc()
        return f"Error processing with LLM: {str(e)}"

def process_with_function_calling(prompt, system_prompt=None):
    """
    Process a prompt with OpenAI's function calling.
    """
    try:
        # Load configuration
        loader = ConfigLoader()
        openai_key = loader.get("open_ai_key")
        model_name = loader.get("open_model") or "gpt-4o"
        
        # Import OpenAI
        import openai
        client = openai.OpenAI(api_key=openai_key)
        
        # Define the tools schemas
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "fetch_yahoo_stock_data",
                    "description": "Fetches historical stock market data from Yahoo Finance for a given ticker symbol and date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "The ticker symbol of the stock (e.g., 'AAPL')"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date for data retrieval, can be YYYY-MM-DD format or relative like '-7d'"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date for data retrieval (optional)"
                            }
                        },
                        "required": ["ticker"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_alpha_vantage_stock_data",
                    "description": "Fetches historical stock market data from Alpha Vantage API for a given symbol and date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "The ticker symbol of the stock (e.g., 'AAPL')"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date for data retrieval, can be YYYY-MM-DD format or relative like '-30d'"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date for data retrieval (default: 'today')"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_market_data_unified",
                    "description": "Fetches historical market data from a specified source (alpha_vantage, yahoo, csv) for a given symbol and date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "The ticker symbol of the stock (e.g., 'AAPL')"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date for data retrieval, can be YYYY-MM-DD format or relative like '-30d'"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date for data retrieval (default: 'today')"
                            },
                            "source": {
                                "type": "string",
                                "description": "Data source to use (alpha_vantage, yahoo, csv)",
                                "enum": ["alpha_vantage", "yahoo", "csv"]
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_news_data",
                    "description": "Fetches general news headlines related to a keyword using NewsAPI (best for general topics, not financial-specific news).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "The keyword or topic to search for (e.g., 'technology', 'climate')"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of news articles to retrieve (default: 5)"
                            }
                        },
                        "required": ["keyword"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_alpha_vantage_news_data",
                    "description": "Fetches financial news and sentiment data related to a stock symbol from Alpha Vantage API (best for financial sentiment analysis).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "The ticker symbol to search for (e.g., 'AAPL')"
                            },
                            "topics": {
                                "type": "string",
                                "description": "Optional topics to filter by (comma separated)"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of news articles to retrieve (default: 5)"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_combined_news",
                    "description": "Fetches news from both NewsAPI and Alpha Vantage, combining the results for the most comprehensive view (RECOMMENDED for financial queries).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "General topic keyword for NewsAPI (e.g., 'market', 'technology')"
                            },
                            "symbol": {
                                "type": "string",
                                "description": "Stock symbol for Alpha Vantage financial news (e.g., 'AAPL', 'MSFT')"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of news articles to retrieve from each source (default: 5)"
                            }
                        },
                        "required": ["keyword"]
                    }
                }
            }
        ]
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # First call to get tool requests
        print("- Calling LLM to analyze the query...")
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.3
        )
        
        response = completion.choices[0].message
        messages.append(response)
        
        # Check if there are tool calls
        if not response.tool_calls:
            return response.content
            
        print(f"- LLM requested {len(response.tool_calls)} tool calls")
        
        # Process each tool call
        for tool_call in response.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"- Executing {function_name} with args: {function_args}")
            
            # For debugging purposes, log all available tool calls
            if function_name != "fetch_alpha_vantage_news_data" and ("AAPL" in str(function_args) or "aapl" in str(function_args).lower() or 
                                                                    "MSFT" in str(function_args) or "msft" in str(function_args).lower() or
                                                                    "AMZN" in str(function_args) or "amazon" in str(function_args).lower()):
                # This is a stock-related query but not using Alpha Vantage news
                print("⚠️ WARNING: Stock-related query but not using fetch_alpha_vantage_news_data!")
            
            # Execute the function
            if function_name == "fetch_yahoo_stock_data":
                result = fetch_yahoo_stock_data(
                    ticker=function_args.get("ticker", "AAPL"),
                    start_date=function_args.get("start_date", "-7d"),
                    end_date=function_args.get("end_date")
                )
            elif function_name == "fetch_alpha_vantage_stock_data":
                result = fetch_alpha_vantage_stock_data(
                    symbol=function_args.get("symbol", "AAPL"),
                    start_date=function_args.get("start_date", "-30d"),
                    end_date=function_args.get("end_date", "today")
                )
            elif function_name == "fetch_market_data_unified":
                result = fetch_market_data_unified(
                    symbol=function_args.get("symbol", "AAPL"),
                    start_date=function_args.get("start_date", "-30d"),
                    end_date=function_args.get("end_date", "today"),
                    source=function_args.get("source", "yahoo")
                )
            elif function_name == "fetch_news_data":
                result = fetch_news_data(
                    keyword=function_args.get("keyword", "market"),
                    count=function_args.get("count", 5)
                )
            elif function_name == "fetch_alpha_vantage_news_data":
                result = fetch_alpha_vantage_news_data(
                    symbol=function_args.get("symbol", "AAPL"),
                    topics=function_args.get("topics"),
                    count=function_args.get("count", 5)
                )
            elif function_name == "fetch_combined_news":
                result = fetch_combined_news(
                    keyword=function_args.get("keyword", "market"),
                    symbol=function_args.get("symbol"),
                    count=function_args.get("count", 5)
                )
            else:
                result = {"error": f"Unknown function: {function_name}"}
                
            # Convert result to string (important!)
            result_str = json.dumps(result)
            
            # Add the result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": result_str
            })
        
        # Final call to get response
        print("- Calling LLM to generate final response with tool results...")
        final_completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.3
        )
        
        return final_completion.choices[0].message.content
        
    except Exception as e:
        traceback.print_exc()
        return f"Error processing with function calling: {str(e)}"

def interactive_mode():
    """
    Run an interactive CLI with the Sentiment Agent.
    """
    print("\nSentiment Agent CLI - Interactive Mode")
    print("Type 'exit' or 'quit' to close the program.")
    print("Type 'help' to see example queries.")
    print("Type 'direct' to switch to direct SentimentAgent mode.")
    
    # Default system prompt
    system_prompt = """
    You are a financial analyst assistant that helps analyze market data and news.
    Your goal is to provide insightful analysis based on the data available.
    
    IMPORTANT NEWS SOURCES:
    
    1. fetch_combined_news - PREFERRED FOR ALL FINANCIAL QUERIES
       Parameters:
       - keyword: General topic keyword (e.g., "market", "technology")
       - symbol: Stock ticker for financial sentiment (e.g., "AAPL", "MSFT")
       - count: Number of articles from each source
       
       This tool fetches from BOTH news sources for the most comprehensive view.
    
    2. fetch_alpha_vantage_news_data - FOR FINANCIAL SENTIMENT ANALYSIS
       Parameters:
       - symbol (required): The stock ticker symbol (e.g., "AAPL", "MSFT")
       - topics (optional): Filter topics
       - count (optional): Number of articles
    
    3. fetch_news_data - FOR GENERAL NON-FINANCIAL TOPICS ONLY
       Parameters:
       - keyword: Search term
       - count: Number of articles
    
    WHEN TO USE EACH NEWS SOURCE:
    - For MOST queries, use fetch_combined_news with both keyword and symbol
    - For purely financial queries, use fetch_combined_news or fetch_alpha_vantage_news_data
    - For non-financial topics only, use fetch_news_data
    
    MARKET DATA SOURCES (use with news data for complete analysis):
    - fetch_yahoo_stock_data: Fetch stock data from Yahoo Finance
    - fetch_alpha_vantage_stock_data: Fetch stock data from Alpha Vantage API
    - fetch_market_data_unified: Unified interface to fetch from either source
    
    EXAMPLE QUERIES AND OPTIMAL TOOL USAGE:
    1. "How is Apple stock doing?" → fetch_yahoo_stock_data + fetch_combined_news(keyword="apple", symbol="AAPL")
    2. "Tell me about MSFT" → fetch_market_data_unified + fetch_combined_news(keyword="microsoft", symbol="MSFT")
    3. "What's the market sentiment on Tesla?" → fetch_alpha_vantage_stock_data + fetch_combined_news(keyword="tesla", symbol="TSLA")
    4. "What's happening with climate change?" → fetch_news_data(keyword="climate change")
    
    REMEMBER: When the user wants deep financial sentiment context, always use fetch_combined_news with both 
    a keyword for general news and a symbol for financial sentiment. This ensures the most comprehensive view.
    
    When analyzing stock data:
    1. Comment on the overall trend (bullish, bearish, or neutral)
    2. Note significant price movements or patterns
    3. Interpret the volume data
    4. If news is available, consider how it might impact the stock
    
    Be concise but informative, focusing on the most relevant insights.
    """
    
    # Mode flag
    use_direct_agent = False
    agent = None
    
    while True:
        # Get user input
        if use_direct_agent:
            user_input = input("\nEnter your query (direct mode): ")
        else:
            user_input = input("\nEnter your query: ")
        
        # Handle exit commands
        if user_input.lower() in ['exit', 'quit']:
            print("Exiting Sentiment Agent CLI.")
            break
            
        # Handle help command
        if user_input.lower() in ['help', '?']:
            print("\nExample queries:")
            print("- How is Apple stock performing?")
            print("- What's the latest on MSFT?")
            print("- Show me news about Tesla")
            print("- Analyze NVDA stock for the past week")
            print("- Tell me about the technology sector")
            continue
            
        # Handle mode switch
        if user_input.lower() == 'direct':
            use_direct_agent = not use_direct_agent
            print(f"\nSwitched to {'direct SentimentAgent' if use_direct_agent else 'function calling'} mode")
            if use_direct_agent and agent is None:
                print("Initializing SentimentAgent...")
                agent = SentimentAgent()
                print("✅ SentimentAgent initialized")
            continue
        
        print("\nProcessing...")
        print()
        
        if use_direct_agent:
            # Process using the actual SentimentAgent
            if agent is None:
                print("Initializing SentimentAgent...")
                agent = SentimentAgent()
                print("✅ SentimentAgent initialized")
            
            response = agent.generate_reply([user_input])
        else:
            # Process using function calling
            response = process_with_function_calling(user_input, system_prompt)
        
        print("\nResponse:")
        print("=" * 80)
        print(response)
        print("=" * 80)
    
def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Sentiment Agent CLI")
    parser.add_argument('--query', '-q', type=str, help='Query to process')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')
    parser.add_argument('--direct', '-d', action='store_true', help='Use the SentimentAgent class directly')
    parser.add_argument('--test-alpha-vantage', '-tav', action='store_true', help='Run Alpha Vantage news API test')
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Run Alpha Vantage news test if requested
    if args.test_alpha_vantage:
        test_alpha_vantage_news()
        return
        
    print("Initializing Sentiment Agent CLI...")
    
    # Interactive mode
    if args.interactive:
        interactive_mode()
    # Single query mode
    elif args.query:
        print("Processing query:", args.query)
        print("-" * 80)
        
        if args.direct:
            # Process using the actual SentimentAgent
            agent = SentimentAgent()
            response = agent.generate_reply([args.query])
        else:
            # Process using function calling
            response = process_with_function_calling(args.query)
        
        print("\nResponse:")
        print("=" * 80)
        print(response)
        print("=" * 80)
    else:
        parser.print_help()

def test_alpha_vantage_news():
    """Test function to verify the Alpha Vantage news function works correctly."""
    print("\n===== Testing Alpha Vantage News API =====")
    
    # First, test direct call
    print("\n1. Testing direct call to AlphaVantageTool.fetch_news_sentiment:")
    try:
        from src.tools.data_sources.alpha_vantage_tool import AlphaVantageTool
        alpha_tool = AlphaVantageTool()
        direct_news_df = alpha_tool.fetch_news_sentiment("AAPL")
        if direct_news_df is not None and not direct_news_df.empty:
            print(f"✅ Direct call successful! Shape: {direct_news_df.shape}")
            print(f"   Columns: {list(direct_news_df.columns)}")
            print(f"   First row: {direct_news_df.iloc[0].to_dict()}")
        else:
            print("❌ Direct call returned empty dataframe")
    except Exception as e:
        print(f"❌ Direct call error: {str(e)}")
    
    # Then, test via function tool
    print("\n2. Testing via fetch_alpha_vantage_news function:")
    try:
        from src.tools.tools import fetch_alpha_vantage_news
        tool_news_df = fetch_alpha_vantage_news("MSFT")
        if tool_news_df is not None and not tool_news_df.empty:
            print(f"✅ Function tool call successful! Shape: {tool_news_df.shape}")
            print(f"   Columns: {list(tool_news_df.columns)}")
            print(f"   First row: {tool_news_df.iloc[0].to_dict()}")
        else:
            print("❌ Function tool call returned empty dataframe")
    except Exception as e:
        print(f"❌ Function tool call error: {str(e)}")
    
    # Finally, test via our CLI wrapper function
    print("\n3. Testing via CLI wrapper function fetch_alpha_vantage_news_data:")
    try:
        result = fetch_alpha_vantage_news_data("AMZN")
        print(f"✅ CLI wrapper returned: {result}")
    except Exception as e:
        print(f"❌ CLI wrapper error: {str(e)}")
    
    print("\n===== Alpha Vantage News Test Complete =====\n")

if __name__ == "__main__":
    # Uncomment to run test function
    # test_alpha_vantage_news()
    main()