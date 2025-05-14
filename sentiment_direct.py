"""
Direct mode only - Sentiment Agent online.
"""
import asyncio
from src.agents.sentiment_agent import SentimentAgent


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


def main():
    """Main entry point for the CLI."""
    print("Starting Sentiment Agent CLI...")
    agent = SentimentAgent()

    while True:
        try:
            user_input = input()
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

        print("Processing...")
        response = asyncio.run(process_with_agent(user_input, agent))

        print("\nResponse:")
        print("=" * 70)
        print(response)
        print("=" * 70)
