# Sentiment Agent CLI

This CLI provides an interface to the Sentiment Agent, which analyzes market data and news sentiment.

## Features

- Interactive mode with command history
- Ability to switch between:
  - Direct SentimentAgent mode (using the full AutoGen agent with all tools)
  - Function calling mode (simplified implementation with OpenAI function calling)
- Real-time data fetching from multiple sources:
  - Yahoo Finance for market data
  - Alpha Vantage for market data and financial news
  - NewsAPI for general news headlines
  - Unified market data interface with source selection
- Full access to all tools defined in tools.py through function calling

## Implementation Modes

The CLI supports two different implementation approaches:

1. **Function Calling Mode (Default)**
   - Uses OpenAI API directly with function calling
   - Simplified tool schemas defined directly in the CLI
   - Easier to understand for new developers

2. **AutoGen Framework Mode**
   - Uses the full SentimentAgent class with proper AutoGen integration
   - Access to all tools defined for the sentiment agent
   - Follows the project's architectural patterns

Switch between modes by typing `direct` at the CLI prompt.

## Usage

### Interactive Mode

Run the CLI:

```bash
python sentiment_agent_cli_improved.py
```

This starts an interactive session where you can enter queries and get responses. You can:

- Type `help` to see example queries
- Type `direct` to toggle between direct SentimentAgent mode and function calling mode
- Type `exit` or `quit` to close the program

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

- `fetch_yahoo_data`: Fetches stock data from Yahoo Finance
- `fetch_alpha_vantage_data`: Fetches stock data from Alpha Vantage API
- `fetch_market_data`: Unified interface to fetch from different sources

### News Data Tools

- `fetch_news`: Fetches general news from NewsAPI (best for non-financial topics)
- `fetch_alpha_vantage_news`: Fetches news with financial sentiment from Alpha Vantage (best for stock-specific news)
- `fetch_finnhub_news`: Fetches financial news from Finnhub
- `fetch_finnhub_financial_headlines`: Fetches combined financial headlines from multiple categories
- `fetch_finnhub_economic_headlines`: Fetches headlines specifically from the 'economic' category

### SEC Data Tools

- `search_sec_filings`: Search SEC filings for specific terms to get context

## Requirements

- Python 3.10+
- AutoGen 0.5.6 (conda environment recommended)
- OpenAI API key
- NewsAPI key
- Alpha Vantage API key
- Finnhub API key

Environment variables are now used instead of `config/config.json`. Secrets can
be managed with the [Codex](https://github.com/openai/codex) CLI by storing them
and setting `envKey` fields to match the lowercase variable names below:

- `open_ai_key`
- `newsapi_key`
- `alpha_vantage_key`
- `finnhub_key`

> NOTE: API KEYS ARE NOT PRESENT AT THE REPO LEVEL SEE LOCAL SYSTEM. if **missing** API KEYS, SELF PROCUREMENT ***WILL*** BE REQUIRED.

## Technical Notes

This CLI consolidates functionality that was previously split across multiple test files.
All functionality is now available through a single unified interface with access to the full range of tools defined in tools.py.

## Documentation

For detailed information about the Sentiment Agent's architecture, implementation, and development, see the complete [Sentiment Agent Documentation](./sentiment_agent.md).
