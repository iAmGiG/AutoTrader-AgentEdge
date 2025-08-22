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
- **Data Source**: Google Custom Search API (single-tier: direct company news only)
- **News Search**: `GoogleSearchNewsTool` - Direct company news (`AAPL` articles)
- **Processing**: 
  - Fetches company-specific news articles only
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
- **Approach**: Adaptive weighted blend of V1 (news) + V2 (market fear) using combiner agent pattern
- **Data Sources**: Google Search news + VXX volatility data (inherits from both V1 and V2)
- **Architecture**: Combiner agent that calls V1 + V2 internally, no sentiment logic duplication
- **Processing**:
  - Calls V1 agent internally for news sentiment (VADER + Google Search)
  - Calls V2 agent internally for market fear sentiment (VXX volatility)
  - Applies mechanical adaptive weighting algorithm (no LLM decisions)
  - Default weights: 60% news sentiment (V1), 40% market fear (V2)
  - Dynamic adjustments based on confidence levels and VXX volatility context
- **Adaptive Weighting Algorithm**:
  ```python
  # Base weights favor news sentiment
  v1_weight = 0.6  # News sentiment (primary)  
  v2_weight = 0.4  # Market fear (secondary)
  
  # Market condition adjustments
  if vxx_level > 40:  # High fear
      v2_weight = min(0.7, v2_weight * 1.3)  # Emphasize market fear
  elif vxx_level < 25:  # Low fear  
      v1_weight = min(0.7, v1_weight * 1.3)  # Emphasize news sentiment
  ```
- **Benefits**: Automatic inheritance of V1/V2 improvements, balanced sentiment fusion
- **Output**: Combined sentiment score with adaptive market-aware weighting

### V4: LLM Analysis
- **Approach**: GPT-4o-mini reasoning with full market context
- **Data Sources**: 3-tier hierarchical news system + market context
- **News Search**: `HierarchicalNewsTool` - Multi-tier professional trader pattern:
  - **Tier 1 (Direct)**: Company-specific news (`AAPL` articles) - 5-8 items
  - **Tier 2 (Sector)**: ETF sector news (`QQQ`, `XLK` for tech) - 2-4 items  
  - **Tier 3 (Market)**: Broad market news (`SPY`) - 1-3 items
- **Processing**:
  - Provides comprehensive news + market context to LLM
  - LLM reasons about sentiment implications across all tiers
  - Returns structured sentiment decision with reasoning
- **Output**: LLM-derived sentiment with comprehensive market reasoning

## News Search Strategy Comparison

### Single-Tier News Search (V1, V3)
```python
# V1 and V3 use standard direct news only
news_tool = GoogleSearchNewsTool()
news_data = news_tool.search_historical_news('AAPL', '2024-10-15', '2024-10-15')
# Returns: Direct AAPL company news only
# Sources: Bloomberg, CNBC, Reuters, Business Wire (.cache/news_filtered/)
```

### Multi-Tier Hierarchical News Search (V4 Only)
```python  
# V4 uses comprehensive hierarchical approach
hierarchical_tool = HierarchicalNewsTool()
news_data = hierarchical_tool.fetch_hierarchical_news('AAPL', datetime(2024, 10, 15))
# Returns: {
#   'direct': [AAPL company news],    # 5-8 articles
#   'sector': [QQQ, XLK ETF news],    # 2-4 articles  
#   'market': [SPY broad market news] # 1-3 articles
# }
```

### Why Different News Strategies?

- **V1 & V3**: Test value of basic news sentiment vs mechanical approaches
- **V4**: Demonstrate maximum LLM value with professional trader information consumption pattern
- **Research Goal**: Show progressive sophistication V1→V3→V4 in news utilization

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