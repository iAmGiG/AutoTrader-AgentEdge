# Coordinator Agent Documentation

**Last Updated**: 2025-07-11

## Overview

The Coordinator Agent is the orchestrator of the multi-agent system, responsible for managing communication between agents, aggregating their signals, and providing unified analysis for trading decisions.

## Core Responsibilities

### 1. Agent Orchestration

- Manages parallel agent execution
- Handles agent communication
- Aggregates responses from multiple agents
- Ensures data consistency

### 2. Signal Aggregation

- Collects sentiment analysis from SentimentAgent
- Gathers technical indicators from TechAgent
- Combines signals into structured format
- Validates signal completeness

### 3. Error Handling

- Manages agent failures gracefully
- Provides fallback mechanisms
- Logs issues for debugging
- Ensures system resilience

## Architecture

### Communication Flow

```
Coordinator Agent
    ├── Parallel Execution
    │   ├── SentimentAgent.analyze(date, symbol)
    │   └── TechAgent.analyze(date, symbol)
    ├── Response Collection
    │   ├── Parse Sentiment Data
    │   └── Parse Technical Data
    └── Signal Aggregation
        └── Return Unified Signal
```

### Key Methods

#### `get_signals(date, symbol)`

Primary method for obtaining trading signals:

```python
async def get_signals(self, date: str, symbol: str) -> Dict:
    """
    Orchestrate agents to get trading signals.
    
    Returns:
        {
            'ok': bool,
            'sentiment': {...},
            'technical': {...},
            'risk': {...},  # Future
            'error': str    # If failed
        }
    """
```

#### `get_signals_with_reasoning(date, symbol)`

Enhanced method that captures LLM reasoning:

```python
async def get_signals_with_reasoning(self, date: str, symbol: str):
    """
    Get signals plus raw LLM responses for analysis.
    
    Returns:
        (signals_dict, raw_responses_dict)
    """
```

## Signal Structure

### Unified Output Format

```python
{
    'ok': True,
    'sentiment': {
        'score': 0.7,           # 0-1 scale
        'analysis': '...',      # Text explanation
        'confidence': 0.8,      # Confidence level
        'key_themes': [...]     # Main topics
    },
    'technical': {
        'macd_today': -0.5,     # Current MACD
        'macd_yest': -0.8,      # Previous MACD
        'analysis': {...},      # Detailed analysis
        'pattern': '...',       # Identified patterns
        'signal_strength': 0.6  # Signal confidence
    }
}
```

### Raw Response Capture

For backtesting analysis:

```python
raw_responses = {
    'sentiment': {
        'raw_response': '...',      # Full LLM output
        'parsed_data': {...},       # Extracted data
        'tools_called': [...],      # Which tools used
        'timestamp': '...'
    },
    'technical': {
        'raw_response': '...',
        'parsed_data': {...},
        'indicators_calculated': [...]
    }
}
```

## Implementation Details

### 1. Parallel Agent Execution

```python
# Execute agents concurrently for efficiency
tasks = [
    self.sentiment_agent.analyze(date, symbol),
    self.tech_agent.analyze(date, symbol)
]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 2. Response Parsing

The coordinator uses specialized parsing for each agent:

- **Sentiment**: Extracts score, themes, confidence
- **Technical**: Extracts MACD values, patterns
- **Validation**: Ensures required fields present

### 3. Error Recovery

```python
# Graceful degradation
if sentiment_failed:
    # Use neutral sentiment
    signals['sentiment'] = {'score': 0.5, 'analysis': 'Data unavailable'}
    
if technical_failed:
    # Mark as invalid
    signals['ok'] = False
    signals['error'] = 'Technical analysis failed'
```

## Integration Points

### 1. With Backtesting System

```python
# In backtest_mas.py
coord = CoordinatorAgent()
for date in trading_days:
    signals = await coord.get_signals_with_reasoning(date, symbol)
    # Save reasoning for analysis
    output_manager.save_llm_reasoning(date, signals)
```

### 2. With Strategy Agent

```python
# Strategy uses coordinator's unified signals
signals = coordinator.get_signals(date, symbol)
decision = strategy.decide_trade(signals, price, date)
```

### 3. With Output Manager

Coordinator signals are saved for post-analysis:

- Daily reasoning files
- Agent response tracking
- Performance attribution

## Configuration

### Agent Initialization

```python
class CoordinatorAgent:
    def __init__(self):
        self.sentiment_agent = SentimentAgent()
        self.tech_agent = TechAgent()
        # Future: self.risk_agent = RiskAgent()
```

### Timeout Settings

- Agent timeout: 30 seconds per agent
- Total timeout: 60 seconds
- Retry attempts: 1

## Recent Improvements (2025-07-11)

1. **Enhanced Reasoning Capture**: Now returns raw LLM responses
2. **Better Error Messages**: More descriptive failure reasons
3. **Parallel Execution**: Faster signal generation
4. **Structured Parsing**: Reliable data extraction

## Usage Example

```python
# Initialize coordinator
coordinator = CoordinatorAgent()

# Get signals for a specific date
signals = await coordinator.get_signals("2024-01-15", "AAPL")

if signals['ok']:
    print(f"Sentiment: {signals['sentiment']['score']}")
    print(f"MACD: {signals['technical']['macd_today']}")
else:
    print(f"Error: {signals['error']}")

# Get signals with full reasoning
signals, reasoning = await coordinator.get_signals_with_reasoning(
    "2024-01-15", "AAPL"
)
# Save reasoning for analysis
save_llm_reasoning(reasoning)
```

## Error Handling

### Common Issues

1. **Agent Timeout**: Returns partial signals
2. **API Failures**: Uses cached data when possible
3. **Parse Errors**: Falls back to default values
4. **Network Issues**: Implements retry logic

### Debugging

- Check agent logs for detailed errors
- Review raw_responses for parsing issues
- Verify API credentials and limits
- Monitor cache hit rates

## Future Enhancements

1. **Additional Agents**:
   - Risk Agent integration
   - Quantitative Agent support
   - Custom agent plugins

2. **Advanced Features**:
   - Agent priority/weighting
   - Consensus mechanisms
   - Conflict resolution

3. **Performance**:
   - Result caching
   - Batch processing
   - Stream processing

4. **Monitoring**:
   - Agent health checks
   - Performance metrics
   - Alert systems
