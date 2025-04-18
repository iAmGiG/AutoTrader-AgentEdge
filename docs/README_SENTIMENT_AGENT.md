# Sentiment Agent CLI

This CLI provides an interface to the Sentiment Agent, which analyzes market data and news sentiment.

## Features

- Interactive mode with command history
- Direct execution mode for one-off queries
- Ability to switch between:
  - Direct SentimentAgent mode (using the full AutoGen agent with all tools)
  - Function calling mode (simplified implementation with OpenAI function calling)
- Real-time data fetching from multiple sources:
  - Yahoo Finance for market data
  - Alpha Vantage for market data and financial news
  - NewsAPI for general news headlines
  - Unified market data interface with source selection
- Full access to all tools defined in tools.py through function calling

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
- "Compare Alpha Vantage and Yahoo Finance data for MSFT"
- "Get financial news about Amazon from Alpha Vantage"
- "Combine news from multiple sources about NVIDIA"
- "Get comprehensive market and news data for Microsoft"

## Available Tools

The CLI exposes several tools for data retrieval:

### Market Data Tools

- `fetch_yahoo_stock_data`: Fetches stock data from Yahoo Finance
- `fetch_alpha_vantage_stock_data`: Fetches stock data from Alpha Vantage API
- `fetch_market_data_unified`: Unified interface to fetch from different sources

### News Data Tools

- `fetch_news_data`: Fetches general news from NewsAPI (best for non-financial topics)
- `fetch_alpha_vantage_news_data`: Fetches news with financial sentiment from Alpha Vantage (best for stock-specific news)
- `fetch_combined_news`: Fetches from both sources, combining results for comprehensive analysis (recommended for financial queries)

## Requirements

- Python 3.10+
- AutoGen 0.5.1 (conda environment recommended)
- OpenAI API key (configured in config/config.json)
- NewsAPI key (configured in config/config.json)
- Alpha Vantage API key (configured in config/config.json)

> NOTE: API KEYS ARE NOTE PRESENT AT THE REPO LEVEL SEE LOCAL SYSTEM. if **missing** API KEYS, SELF PROCUREMENT ***WILL*** BE REQURIED.

## Technical Notes

This CLI consolidates functionality that was previously split across multiple test files.
All functionality is now available through a single unified interface with access to the full range of tools defined in tools.py.
