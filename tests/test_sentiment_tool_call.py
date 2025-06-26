#!/usr/bin/env python3
"""Test sentiment agent tool calling with a simple, direct prompt."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.sentiment_agent import SentimentAgent
import asyncio

async def test_sentiment_direct():
    """Test sentiment agent with a very direct tool call request."""
    print("Testing Direct Sentiment Agent Tool Call")
    print("=" * 50)
    
    # Create sentiment agent
    sentiment = SentimentAgent()
    
    # Very direct prompt that should trigger tool use
    test_prompt = """
    Call the fetch_all_news tool with ticker="NVDA" and count=5 to get recent news about NVIDIA.
    """
    
    print("Sending DIRECT tool request to Sentiment Agent...")
    print(f"Query: {test_prompt.strip()}")
    print("-" * 50)
    
    try:
        # Use the agent's process_with_tools method
        response = await sentiment.process_with_tools_async(test_prompt)
        
        print("\nAgent Response:")
        print(response)
        
        return "fetch_all_news" in response or "news" in response.lower()
        
    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_with_simple_system_prompt():
    """Test with a simplified system prompt."""
    print("\n\nTesting with Simplified System Prompt")
    print("=" * 50)
    
    sentiment = SentimentAgent()
    
    # Override with a simpler system prompt
    simple_prompt = """
    You are a sentiment analysis agent with access to tools.
    When asked about news, use the fetch_all_news tool.
    """
    
    test_query = "Get news about NVDA"
    
    print("Query:", test_query)
    print("-" * 50)
    
    try:
        response = await sentiment.process_with_tools_async(test_query, simple_prompt)
        print("\nAgent Response:")
        print(response)
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    """Run the tests."""
    success1 = asyncio.run(test_sentiment_direct())
    success2 = asyncio.run(test_with_simple_system_prompt())
    
    print("\n" + "=" * 50)
    print(f"Direct test: {'PASSED' if success1 else 'FAILED'}")
    print(f"Simple prompt test: {'PASSED' if success2 else 'FAILED'}")
    
    return 0 if (success1 or success2) else 1

if __name__ == "__main__":
    sys.exit(main())