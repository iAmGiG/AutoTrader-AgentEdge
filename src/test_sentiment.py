import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.sentiment_agent import SentimentAgent

if __name__ == "__main__":
    agent = SentimentAgent()
    response = agent.handle_message("Fetch news on Musk")
    print(f"SentimentAgent Response: {response}")
