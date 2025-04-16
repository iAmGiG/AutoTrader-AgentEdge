#!/usr/bin/env python3
"""
Simplified CLI for interacting with the Sentiment Agent.

This script demonstrates how to use function calling with AutoGen 0.5.x
"""

import sys
import os
import argparse
import asyncio
import json
import pandas as pd
import traceback

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath('.'))

# Import configuration
from config.config_loader import ConfigLoader

# Import the data fetching functions directly
from src.tools.data_sources.yahoo_finance_tool import YahooFinanceTool
from src.tools.data_sources.news_headline_tool import NewsHeadlineTool

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

def fetch_stock_data(symbol="AAPL", start_date="-7d", end_date=None):
    """
    Fetch stock data using Yahoo Finance.
    """
    try:
        tool = YahooFinanceTool()
        data = tool.fetch_stock_data(symbol, start_date, end_date)
        
        if data is None or data.empty:
            return {
                "error": f"No data available for {symbol}",
                "status": "error"
            }
            
        # Convert to a simpler format for OpenAI response
        result = {
            "status": "success",
            "ticker": symbol,
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
            "error": f"Error fetching data: {str(e)}",
            "status": "error"
        }

def fetch_news_data(keyword="market", count=5):
    """
    Fetch news headlines for a topic or ticker.
    """
    # For the demo, we'll use mock data to avoid API calls
    mock_news = pd.DataFrame({
        'headline': [
            f"{keyword} reports strong quarterly results", 
            f"Analysts upgrade {keyword} to Buy",
            f"New product line announced by {keyword}",
            f"{keyword} sees increased competition",
            f"{keyword} expands international presence"
        ],
        'source': ['CNBC', 'Bloomberg', 'Reuters', 'WSJ', 'MarketWatch'],
        'date': pd.date_range(end=pd.Timestamp.now(), periods=5, freq='D'),
        'sentiment': [0.6, 0.8, 0.7, -0.2, 0.5]
    })
    
    result = {
        "status": "success",
        "keyword": keyword,
        "article_count": count,
        "headlines": mock_news.head(count)[['headline', 'source', 'sentiment']].to_dict(orient='records'),
        "avg_sentiment": round(mock_news.head(count)['sentiment'].mean(), 2)
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
                    "name": "fetch_stock_data",
                    "description": "Fetches historical stock market data for a given symbol and date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
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
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_news_data",
                    "description": "Fetches news headlines related to a keyword or ticker symbol.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "The keyword or ticker to search for (e.g., 'AAPL' or 'technology')"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of news articles to retrieve (default: 5)"
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
            
            # Execute the function
            if function_name == "fetch_stock_data":
                result = fetch_stock_data(
                    symbol=function_args.get("symbol", "AAPL"),
                    start_date=function_args.get("start_date", "-7d"),
                    end_date=function_args.get("end_date")
                )
            elif function_name == "fetch_news_data":
                result = fetch_news_data(
                    keyword=function_args.get("keyword", "market"),
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
    print("\nSentiment Agent CLI")
    print("Type 'exit' or 'quit' to close the program.")
    print("Type 'help' to see example queries.")
    
    # Default system prompt
    system_prompt = """
    You are a financial analyst assistant that helps analyze market data and news.
    Your goal is to provide insightful analysis based on the data available.
    
    When analyzing stock data:
    1. Comment on the overall trend (bullish, bearish, or neutral)
    2. Note significant price movements or patterns
    3. Interpret the volume data
    4. If news is available, consider how it might impact the stock
    
    Be concise but informative, focusing on the most relevant insights.
    """
    
    while True:
        # Get user input
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
            continue
        
        print("\nProcessing...")
        print()
        
        # Process using function calling
        response = process_with_function_calling(user_input, system_prompt)
        
        print("\nResponse:")
        print("=" * 80)
        print(response)
        print("=" * 80)
    
def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Simplified Sentiment Agent CLI")
    parser.add_argument('--query', '-q', type=str, help='Query to process')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
        
    print("Initializing Sentiment Agent...")
    
    # Interactive mode
    if args.interactive:
        interactive_mode()
    # Single query mode
    elif args.query:
        print("Processing query:", args.query)
        print("-" * 80)
        
        response = process_with_function_calling(args.query)
        
        print("\nResponse:")
        print("=" * 80)
        print(response)
        print("=" * 80)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()