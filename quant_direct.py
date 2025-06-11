"""
Direct mode only - Quantitative Agent online.
"""

import asyncio
import os
import traceback
from src.agents.quantitative_agent import QuantitativeAgent


async def process_with_agent(prompt: str, agent: QuantitativeAgent):
    """
    Send a single prompt to the QuantitativeAgent and return the response.
    Handles both synchronous and coroutine returns (process_with_tools_async).
    """
    try:
        # generate_reply expects a list of message dicts similar to
        # AutoGen's conversation format. Provide the prompt as a single
        # user message.
        messages = [{"role": "user", "content": prompt}]
        result = agent.generate_reply(messages)
        if asyncio.iscoroutine(result):
            response = await result
            return response
        return result
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error in process_with_agent: {error_details}")
        return f"Error: {str(e)}"


def main():
    """Console entry-point for quick, ad-hoc testing."""
    if not os.environ.get("OPEN_AI_KEY"):
        raise RuntimeError("OPEN_AI_KEY environment variable not set")

    print("Starting Quantitative Agent CLI...")
    agent = QuantitativeAgent()

    while True:
        try:
            user_input = input("Agent is ready:\n")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Exiting")
            break

        if user_input.lower() in {"help", "?"}:
            print(
                "\nExample queries:"
                "\n- Hourly Go/NoGo for AAPL with avwap"
                "\n- Show RSI14 and Supertrend for TSLA"
                "\n- Fetch 4-hour data on ETH and compute EMA50"
                "\n- What is the 10Y–3M yield-curve spread today?"
            )
            continue

        print("Processing…")
        response = asyncio.run(process_with_agent(user_input, agent))

        print("\nResponse:")
        print("=" * 70)
        print(response)
        print("=" * 70)


if __name__ == "__main__":
    main()
