# Sentiment Agent CLI

This CLI provides an interface to the Sentiment Agent, which analyzes market data and news sentiment.

## Features

- Interactive mode with command history
- Direct execution mode for one-off queries
- Ability to switch between:
  - Direct SentimentAgent mode (using the full AutoGen agent with all tools)
  - Function calling mode (simplified implementation with OpenAI function calling)
- Real-time data fetching from:
  - Yahoo Finance for market data
  - NewsAPI for news headlines and sentiment

## Usage

### Interactive Mode

Run the CLI in interactive mode:

```bash
python sentiment_agent_cli.py -i
```

This starts an interactive session where you can enter queries and get responses. You can:

- Type `help` to see example queries
- Type `direct` to toggle between direct SentimentAgent mode and function calling mode
- Type `exit` or `quit` to close the program

### Query Mode

Run the CLI with a specific query:

```bash
python sentiment_agent_cli.py -q "How is Apple stock performing?"
```

To use the direct SentimentAgent implementation (with AutoGen):

```bash
python sentiment_agent_cli.py -q "How is Apple stock performing?" -d
```

## Example Queries

- "How is Apple stock performing lately?"
- "What's the sentiment around NVIDIA?"
- "Tell me about Tesla stock and recent news"
- "Analyze the technology sector"
- "What's happening with SPY ETF?"

## Requirements

- Python 3.10+
- AutoGen 0.5.1 (conda environment recommended)
- OpenAI API key (configured in config/config.json)
- NewsAPI key (configured in config/config.json)

## Technical Notes

This CLI consolidates functionality that was previously split across multiple test files:

- `sentiment_agent_cli.py`: The original CLI with function calling
- `test_sentiment_agent.py`: Testing the SentimentAgent directly
- `sentiment_agent_simple.py`: A simplified PoC for data fetching

All functionality is now available through a single unified interface.
