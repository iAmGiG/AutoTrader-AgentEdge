from src.agents.sentiment_agent import SentimentAgent


def test_sentiment_agent():
    agent = SentimentAgent()
    response = agent.handle_message("Fetch news on Technology")
    print(f"The current tech news is: {response}")


if __name__ == "__main__":
    test_sentiment_agent()
