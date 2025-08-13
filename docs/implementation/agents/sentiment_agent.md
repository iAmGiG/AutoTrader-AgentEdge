# Sentiment Agent Documentation (V0-V4 Framework)

**Last Updated**: 2025-08-13

## Overview

The Sentiment Agent implements 5 different sentiment approaches (V0-V4) for the framework's gradual LLM introduction study. Each version provides a sentiment score that modulates the base MACD trading strategy.

## V0-V4 Implementations

### V0: Fixed Baseline
- **Approach**: Always returns sentiment = 1.0 (bullish)
- **Purpose**: Pure MACD strategy baseline
- **Data Sources**: None
- **Implementation**: Simple constant return

### V1: NLP Analysis
- **Approach**: VADER sentiment analysis on news
- **Data Source**: Google Custom Search API
- **Processing**: 
  - Fetches relevant news articles
  - Applies VADER with financial lexicon
  - Averages sentiment scores
- **Output**: Score between -1.0 and 1.0

### V2: Market Fear Gauge
- **Approach**: VXX/VIX volatility-based sentiment
- **Data Source**: Polygon.io or Alpha Vantage
- **Processing**:
  - Fetches VXX price movements
  - Converts volatility to fear score
  - Inverts to sentiment (high VXX = negative sentiment)
- **Output**: Fear-adjusted sentiment score

### V3: Heuristic Combination
- **Approach**: Weighted blend of V1 + V2
- **Processing**:
  - Gets V1 news sentiment
  - Gets V2 volatility sentiment
  - Applies adaptive weighting based on market conditions
- **Output**: Combined sentiment score

### V4: LLM Analysis
- **Approach**: GPT-4o-mini reasoning
- **Data Sources**: Google Search news + market context
- **Processing**:
  - Provides news and market data to LLM
  - LLM reasons about sentiment implications
  - Returns structured sentiment decision
- **Output**: LLM-derived sentiment with reasoning

## Implementation Details

### Base Class
All sentiment agents inherit from `BaseAgent` and implement:
```python
def generate_reply(self, messages: List[Dict]) -> Dict:
    # Returns sentiment score and reasoning
```

### Caching Strategy
- News cached for 7 days to reduce API calls
- Market data cached with appropriate TTL
- V4 implements date obfuscation for validation

## Usage in V0-V4 Framework

The StrategyAgent selects which sentiment version to use:
```python
sentiment_agent = SentimentAgentV0()  # or V1, V2, V3, V4
sentiment = sentiment_agent.generate_reply(context)
# Combine with MACD signals for trading decision
```