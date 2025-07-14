# Sentiment Agent Documentation

**Last Updated**: 2025-07-11

## Overview

The Sentiment Agent is responsible for analyzing market sentiment through news articles and providing sentiment scores for trading decisions. It features an enhanced VXX fallback mechanism to ensure reliable sentiment signals even when news data is unavailable.

## Key Features

### 1. Multi-Source News Analysis

- **Data Sources**: Alpha Vantage News, NewsAPI, Finnhub
- **Unified News Tool**: Aggregates news from multiple sources
- **Relevance Scoring**: Filters news by relevance (threshold ≥ 0.5)
- **Sentiment Analysis**: Uses LLM to analyze article sentiment

### 2. VXX Fallback Mechanism

When news is unavailable, the agent:

1. Fetches VXX (volatility index) data
2. Analyzes VXX movement patterns
3. Converts volatility signals to sentiment scores
4. Ensures trading strategy always has sentiment input

### 3. News Caching System (NEW)

- **Implementation**: NewsCache class with 7-day expiry
- **Filtering**: Only caches relevant news (score ≥ 0.5)
- **Benefits**: Reduces API calls, speeds up backtesting
- **Location**: `.cache/news/` directory

## Architecture

### Data Flow

```
User Query
    ↓
SentimentAgent
    ├── Check News Cache
    ├── Fetch News (if not cached)
    │   ├── Alpha Vantage News API
    │   ├── NewsAPI
    │   └── Finnhub
    ├── Relevance Filtering
    ├── Sentiment Analysis (LLM)
    └── VXX Fallback (if no news)
         ↓
    Sentiment Score (0-1)
```

### Key Components

1. **BaseAgent Integration**
   - Inherits from `BaseAgent` for tool management
   - Uses AutoGen 0.6.x function calling
   - Handles async/sync tool execution

2. **Tool Management**

   ```python
   # Tools available to sentiment agent
   - fetch_all_news: Unified news fetching
   - fetch_market_data: Market data for VXX
   - analyze_sentiment: LLM-based analysis
   ```

3. **Caching Override**

   ```python
   async def _execute_tool(self, tool_name, tool_args):
       if tool_name == "fetch_all_news":
           # Check cache first
           cached = self.news_cache.get(...)
           if cached:
               return cached
           # Fetch and cache if not found
   ```

## Implementation Details

### News Fetching and Analysis

1. **Unified News Tool**
   - Fetches from multiple sources in parallel
   - Standardizes output format
   - Deduplicates similar articles
   - Provides search guidance for poor results

2. **Relevance Scoring**

   ```python
   # Scoring factors:
   - Ticker match in title: 3x weight
   - Keyword match in title: 2x weight
   - Content matches: 1x weight
   # Articles with score < 0.5 are filtered
   ```

3. **Sentiment Analysis Process**
   - Extract key themes from articles
   - Analyze tone and market implications
   - Generate confidence score
   - Provide narrative explanation

### VXX Fallback Logic

When no relevant news is found:

```python
# Fetch VXX data for the date
vxx_data = self.market_data_tool.fetch_market_data(
    symbol="VXX",
    start_date=date,
    end_date=date
)

# Analyze VXX movement
if vxx_change > 5%:
    sentiment = 0.2  # High volatility = negative
elif vxx_change < -5%:
    sentiment = 0.8  # Low volatility = positive
else:
    sentiment = 0.5  # Neutral
```

## Configuration

### LLM Settings

```python
SENTIMENT_LLM_CONFIG = {
    "temperature": 0.3,  # Balanced for analysis
    "max_tokens": 4096,  # Sufficient for complex responses
    "model": "gpt-4"
}
```

### System Prompt

The agent uses a detailed system prompt that guides it to:

- Analyze news sentiment objectively
- Consider market context
- Provide numerical scores with explanations
- Use VXX as a fallback indicator

## Usage Examples

### Basic Usage

```python
# Initialize agent
agent = SentimentAgent()

# Get sentiment for a date
result = agent.generate_reply(
    messages=[{
        "role": "user",
        "content": "What's the sentiment for AAPL on 2024-01-15?"
    }]
)
```

### Response Format

```json
{
    "score": 0.7,
    "analysis": "Positive sentiment based on product launch news",
    "confidence": 0.8,
    "key_themes": ["innovation", "market expansion"],
    "data_source": "news"  // or "vxx_fallback"
}
```

## Testing and Validation

### Unit Tests

- News fetching with mock data
- Sentiment scoring accuracy
- VXX fallback triggering
- Cache hit/miss scenarios

### Integration Tests

- Multi-agent coordination
- API failure handling
- Cache persistence
- Performance benchmarks

## Recent Improvements (2025-07-11)

1. **News Caching**: Added NewsCache integration
2. **Relevance Filtering**: Only cache/use relevant news
3. **Enhanced VXX Fallback**: More sophisticated analysis
4. **Better Error Handling**: Graceful degradation

## Known Limitations

1. **API Rate Limits**:
   - Alpha Vantage: 25 calls/day
   - Solution: Aggressive caching

2. **News Quality**:
   - Not all news is relevant
   - Solution: Relevance scoring

3. **Historical Data**:
   - Limited news for old dates
   - Solution: VXX fallback

## Future Enhancements

1. **Additional Sources**: Reuters, Bloomberg APIs
2. **NLP Improvements**: Fine-tuned sentiment models
3. **Real-time Analysis**: Streaming news integration
4. **Sector Analysis**: Industry-specific sentiment
