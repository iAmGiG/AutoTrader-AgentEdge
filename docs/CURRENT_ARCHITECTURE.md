# RH2MAS Current Architecture

## Simplified Agent System

The system now uses a streamlined architecture with enhanced agents:

### Core Agents

1. **SentimentAgent** (`src/agents/sentiment_agent.py`)
   - Enhanced with VXX fallback mechanism
   - Uses news sentiment when available
   - Falls back to VXX volatility indicator when news unavailable
   - Always provides reliable sentiment signal

2. **TechAgent** (`src/agents/tech_agent.py`)
   - Performs technical analysis
   - Calculates MACD and other indicators
   - Provides market timing signals

3. **StrategyAgent** (`src/agents/strategy_agent.py`)
   - Uses sentiment >= 0 requirement (allows neutral sentiment)
   - Combines sentiment and technical signals
   - Makes trading decisions based on MACD conditions

4. **CoordinatorAgent** (`src/agents/coordinator_agent.py`)
   - Orchestrates multi-agent collaboration
   - Aggregates signals from all agents
   - Provides unified trading recommendations

### Key Features

- **VXX Fallback**: Ensures sentiment analysis works even without news data
- **Market Data Caching**: Reduces API calls and speeds up backtesting
- **Unified Strategy**: Single strategy implementation (sentiment >= 0)
- **Simplified Testing**: Focused test suite for core functionality

### Running Backtests

```bash
# Single backtest
python scripts/backtest_mas.py SYMBOL START END

# Example
python scripts/backtest_mas.py AAPL 2024-01-01 2024-03-31

# Run test suite
python scripts/run_backtest_suite.py quick
```

### Deprecated Components

Old agent versions have been moved to `src/agents/deprecated/` and are excluded from the repository.