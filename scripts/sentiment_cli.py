#!/usr/bin/env python3
"""
Simplified interactive CLI for the Sentiment Agent using AutoGen 0.5.x.
"""

import sys
import os
import json
import asyncio
import traceback
from typing import Dict, Any
from src.agents.sentiment_agent import SentimentAgent
from config.config_loader import ConfigLoader

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath('.'))

# Import configuration

# Import the SentimentAgent class

# Import tools and tool dictionary


async def execute_tool_async(tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """Execute a tool asynchronously."""
    from src.tools.tools import ALL_TOOLS_DICT, market_data_tool, fetch_market_data
    from autogen_core._cancellation_token import CancellationToken

    # Special handling for market_data tool which might be called with either name
    if tool_name == "fetch_market_data":
        # Map to the correct tool
        tool = market_data_tool
    else:
        # Get the tool from the global dictionary
        tool = ALL_TOOLS_DICT.get(tool_name)

    if not tool:
        raise ValueError(f"Tool '{tool_name}' not found.")

    print(f"Executing tool: {tool_name}")

    # Create a cancellation token for methods that require it
    cancellation_token = CancellationToken()

    # Define helper to execute functions based on their async nature
    async def call_exec_fn(exec_fn, *args, **kwargs):
        if asyncio.iscoroutinefunction(exec_fn):
            return await exec_fn(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: exec_fn(*args, **kwargs))

    # Special handling for common parameter issues
    if tool_name == "fetch_market_data":
        # Rename 'symbol' parameter to 'ticker' if needed
        if 'symbol' in tool_args and 'ticker' not in tool_args:
            tool_args['ticker'] = tool_args.pop('symbol')

        return await call_exec_fn(fetch_market_data, **tool_args)

    # Special handling for search_sec_filings
    elif tool_name == "search_sec_filings":
        # Handle parameter issues in search_sec_filings
        from src.tools.data_sources.government.sec_edgar_tool import SECEdgarTool

        # Extract parameters in the correct order
        ticker = tool_args.get('ticker')
        search_terms = tool_args.get('search_terms', [])
        form_type = tool_args.get('form_type', '10-K')
        section = tool_args.get('section', None)
        num_filings = tool_args.get('num_filings', 3)

        print(
            f"Executing search_sec_filings with fixed parameters: ticker={ticker}, search_terms={search_terms}")

        # Create SEC tool instance and call search_filings method
        sec_tool = SECEdgarTool(use_temp_dir=True)
        return await call_exec_fn(sec_tool.search_filings, ticker, search_terms, form_type, section, num_filings)

    # Try different methods to call the tool
    if hasattr(tool, 'func'):
        return await call_exec_fn(tool.func, **tool_args)

    if callable(tool):
        return await call_exec_fn(tool, **tool_args)

    if hasattr(tool, 'run'):
        return await call_exec_fn(tool.run, tool_args, cancellation_token)

    # Check global function map as a fallback
    from src.tools.tools import TOOL_FUNCTION_MAP
    if tool_name in TOOL_FUNCTION_MAP:
        return await call_exec_fn(TOOL_FUNCTION_MAP[tool_name], **tool_args)

    raise ValueError(f"Could not determine how to execute tool: {tool_name}")


async def process_with_llm_function_calling(prompt: str, system_prompt: str = None):
    """Process a prompt with LLM function calling."""
    try:
        # Load configuration
        loader = ConfigLoader()
        openai_key = loader.get("open_ai_key")
        model_name = loader.get("open_model") or "gpt-4o"

        # Import OpenAI
        import openai
        client = openai.OpenAI(api_key=openai_key)

        # Import tool definitions for schema generation
        from src.tools.tools import get_tools_for_agent, SENTIMENT_AGENT
        sentiment_tools = get_tools_for_agent(SENTIMENT_AGENT)

        # Instead of hardcoding tool definitions, use the actual tools from tools.py
        tools = []
        for tool in sentiment_tools:
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description
                }
            }

            # Extract parameters from the tool schema
            if hasattr(tool, 'schema') and tool.schema:
                if 'parameters' in tool.schema:
                    tool_schema["function"]["parameters"] = tool.schema["parameters"]

            tools.append(tool_schema)

        # Add market_data tool for stock price information
        tools.append({
            "type": "function",
            "function": {
                "name": "fetch_market_data",
                "description": "Fetch market data from the specified source for a given ticker and date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol/ticker to fetch data for"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start of date range (YYYY-MM-DD or relative like '-30d')"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End of date range (YYYY-MM-DD or 'today')"
                        },
                        "source": {
                            "type": "string",
                            "description": "Data source to use ('alpha_vantage', 'yahoo')"
                        }
                    },
                    "required": ["symbol"]
                }
            }
        })

        # Build the initial messages
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
        print("Calling LLM to analyze query...")
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.3
        )

        response = completion.choices[0].message
        messages.append(response)

        # Check if there are tool calls to execute
        if not response.tool_calls:
            return response.content

        print(f"LLM requested {len(response.tool_calls)} tool calls")

        # Process each tool call
        for tool_call in response.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            tool_id = tool_call.id

            print(f"Executing {function_name}")

            try:
                # Execute the tool using async executor
                result = await execute_tool_async(function_name, function_args)

                # Format the result for OpenAI
                result_str = json.dumps(result) if isinstance(
                    result, (dict, list)) else str(result)

                # Add the result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": function_name,
                    "content": result_str
                })

            except Exception as e:
                error_message = f"Error executing {function_name}: {str(e)}"

                # Add error message to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": function_name,
                    "content": error_message
                })

        # Final call to get response after tool execution
        print("Generating final response...")
        final_completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.3
        )

        return final_completion.choices[0].message.content

    except Exception as e:
        return f"Error: {str(e)}"


async def process_with_agent(prompt: str, agent: SentimentAgent):
    """Process a prompt using the actual SentimentAgent."""
    try:
        # If generate_reply returns a coroutine (from process_with_tools_async), await it
        result = agent.generate_reply([prompt])
        if asyncio.iscoroutine(result):
            response = await result
            return response
        else:
            return result
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error in process_with_agent: {error_details}")
        return f"Error: {str(e)}"


async def interactive_mode():
    """Run an interactive CLI with the Sentiment Agent."""
    print("\nSentiment Agent CLI")
    print("Type 'exit' or 'quit' to close the program.")
    print("Type 'help' to see example queries.")
    print("Type 'direct' to switch modes.")

    # System prompt for the LLM
    system_prompt = """
    You are a financial analyst assistant that helps analyze market data and news.
    
    IMPORTANT INSTRUCTIONS:
    
    1. ALWAYS use MULTIPLE tools (at least 3) for a comprehensive analysis.
    
    2. UNDERSTAND FINANCIAL ABBREVIATIONS:
       - "ER" means "Earnings Report" - not a ticker symbol
       - When asked about upcoming "ER" or "earnings", this refers to the next earnings report date
       - Understand that queries like "ZIM ER" mean "ZIM's upcoming earnings report"
    
    3. FOR COMPANY/STOCK ANALYSIS, ALWAYS USE THESE TOOLS TOGETHER:
       - fetch_all_news(ticker="TICKER", keywords="relevant terms") - Unified news tool with relevance sorting
       - fetch_market_data(symbol="TICKER") - For price data to see trends
       - fetch_finnhub_news(tickers=["TICKER"]) - For additional financial news specific to the company
       - fetch_finnhub_financial_headlines() - For broader market context
    
    4. FOR QUERIES ABOUT TARIFFS OR POLICY IMPACTS:
       - fetch_finnhub_economic_headlines() - For economic policy news
       - fetch_all_news(keywords="tariffs, policy, impact") - For relevant news filtered by importance
    
    5. FOR QUERIES ABOUT EARNINGS OR FINANCIAL REPORTS:
       - search_sec_filings(ticker="TICKER", search_terms=["earnings"]) - For official filings
    
    6. NEWS RELEVANCE SCORING:
       - The fetch_all_news tool sorts articles by relevance to your query
       - Pay attention to the 'relevance_score' field - higher means more relevant
       - IGNORE articles with relevance_score < 0.5 as they are likely not relevant
       - Check the 'search_guidance' field which gives feedback on result quality
       - If search_guidance indicates poor results, try a different search with more specific keywords
    
    Available tools:
    1. fetch_all_news - PREFERRED NEWS TOOL with smart relevance scoring, sentiment, and search guidance
    2. fetch_news - Backup for general news articles on a topic
    3. fetch_alpha_vantage_news - For stock-specific news and sentiment
    4. fetch_finnhub_news - For financial news from Finnhub about specific tickers
    5. fetch_finnhub_financial_headlines - For diverse financial headlines (use for broader market context)
    6. fetch_finnhub_economic_headlines - For economic news headlines (use for policy impacts, tariffs, etc.)
    7. search_sec_filings - For searching SEC documents (official company filings)
    8. fetch_market_data - For price data on stocks and ETFs
    
    Approach every query by using at least 3 complementary tools. NEVER rely on just one data source.
    
    Provide clear, concise analysis focusing on sentiment, key findings, earnings dates if relevant, and actionable insights.
    """

    # Mode flag and agent initialization
    use_direct_agent = False
    agent = None

    while True:
        # Get user input
        try:
            mode_label = "direct agent" if use_direct_agent else "function calling"
            user_input = input(f"\nQuery ({mode_label} mode): ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting")
            break

        # Handle exit commands
        if user_input.lower() in ['exit', 'quit']:
            print("Exiting")
            break

        # Handle help command
        if user_input.lower() in ['help', '?']:
            print("\nExample queries:")
            print("- What's the sentiment on Apple stock?")
            print("- Get headlines about technology sector")
            print("- Risk factors for Tesla in SEC filings?")
            print("- How is Microsoft performing?")
            print("- Latest news on inflation")
            continue

        # Handle mode switch
        if user_input.lower() == 'direct':
            use_direct_agent = not use_direct_agent
            print(f"Switched to {mode_label} mode")
            continue

        print("Processing...")

        if use_direct_agent:
            # Process using SentimentAgent
            if agent is None:
                print("Initializing SentimentAgent...")
                agent = SentimentAgent()
                print("SentimentAgent initialized")

            response = await process_with_agent(user_input, agent)
        else:
            # Process using function calling
            response = await process_with_llm_function_calling(user_input, system_prompt)

        print("\nResponse:")
        print("=" * 70)
        print(response)
        print("=" * 70)


def main():
    """Main entry point for the CLI."""
    print("Starting Sentiment Agent CLI...")
    asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
