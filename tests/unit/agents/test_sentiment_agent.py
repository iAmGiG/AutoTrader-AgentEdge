"""
Test script for the enhanced SentimentAgent with LLM function calling capabilities
"""

import logging
import os
import sys

# Handle import path for both running from root and from within src directory
try:
    # Use V0 agent instead of legacy SentimentAgent
    from src.agents.sentiment_v0 import V0SentimentAgent as SentimentAgent
except ImportError:
    # If that fails, adjust path and try again
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from src.agents.sentiment_v0 import V0SentimentAgent as SentimentAgent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_sentiment_agent_basic():
    """Test the SentimentAgent with various message types - basic functionality"""

    print("\n" + "=" * 70)
    print("PART 1: TESTING BASIC SENTIMENT AGENT FUNCTIONALITY WITH DATA RETRIEVAL")
    print("=" * 70)

    # Create the agent
    agent = SentimentAgent()

    # Test messages to try
    test_messages = [
        "Get stock data for AMD",
        "Get news for inflation",
        "Get stock data for TSM since -3d",
        "Get stock data for FNGB for the last week",
        # "Invalid command",
    ]

    # Process each test message
    for message in test_messages:
        print(f"\n===== Testing: '{message}' =====")
        try:
            response = agent.handle_message(message)
            print(response)
        except Exception as e:
            print(f"Error: {str(e)}")

    return True


def test_enhanced_narrative():
    """Test the enhanced narrative generation capabilities"""

    print("\n" + "=" * 70)
    print("PART 2: TESTING ENHANCED NARRATIVE GENERATION WITH MISSESIAN ECONOMICS")
    print("=" * 70)

    # Create the agent
    agent = SentimentAgent()

    # Test messages focusing on narrative generation
    test_messages = [
        "What's the market sentiment on chips?",
        "Get stock data for NVDA for the last month",
        "Tell me about QQQ sentiment",
        "What's the news sentiment on tarrifs?",
    ]

    # Process each test message
    for message in test_messages:
        print(f"\n===== Testing Narrative: '{message}' =====")
        try:
            response = agent.handle_message(message)
            print(response)
        except Exception as e:
            print(f"Error: {str(e)}")

    return True


def test_direct_llm_processing():
    """Test the direct LLM processing capability"""

    print("\n" + "=" * 70)
    print("PART 3: TESTING DIRECT LLM PROCESSING CAPABILITY")
    print("=" * 70)

    # Create the agent
    agent = SentimentAgent()

    # Get the system prompt
    system_prompt = agent.build_system_prompt()

    # Sample data to process
    sample_data = {
        "ticker": "NVDA",
        "sentiment_score": 0.45,
        "headlines": [
            "Apple announces new AI features for iPhone",
            "AAPL stock hits new high after earnings beat",
            "Analysts bullish on Apple's services growth",
        ],
        "article_count": 24,
    }

    # Create a prompt for the LLM to interpret
    prompt = f"""
    Please analyze this financial data and provide a missesian interpretation:

    Ticker: {sample_data['ticker']}
    Sentiment Score: {sample_data['sentiment_score']}
    Number of Articles: {sample_data['article_count']}
    Sample Headlines:
    - {sample_data['headlines'][0]}
    - {sample_data['headlines'][1]}
    - {sample_data['headlines'][2]}
    """

    print("Sending the following prompt to the LLM:")
    print("-" * 60)
    print(prompt)
    print("-" * 60)

    # Process with the LLM
    try:
        response = agent.process_with_llm(prompt, system_prompt)
        print("\nLLM Response:")
        print("-" * 60)
        print(response)
    except Exception as e:
        print(f"\nError during LLM processing: {str(e)}")


if __name__ == "__main__":
    print("Testing Enhanced SentimentAgent with LLM Function Calling...")

    try:
        # Run the basic tests
        test_sentiment_agent_basic()

        # Prompt to continue
        input("\nPress Enter to continue to enhanced narrative tests...")

        # Test enhanced narrative generation
        test_enhanced_narrative()

        # Prompt to continue
        input("\nPress Enter to continue to direct LLM processing test...")

        # Test direct LLM processing
        test_direct_llm_processing()

        print("\nAll tests completed successfully!")
    except Exception as e:
        print(f"\nError during testing: {str(e)}")
