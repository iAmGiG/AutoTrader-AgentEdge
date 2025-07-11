# RH2MAS Current Architecture

**Last Updated**: 2025-07-11

## Overview

RH2MAS (Reflective Hybrid Head Multi-Agent System) uses a streamlined multi-agent architecture for financial analysis and trading decisions.

## Core Agents

### 1. SentimentAgent (`src/agents/sentiment_agent.py`)

- **Enhanced Features**:
  - News sentiment analysis using multiple sources
  - VXX fallback mechanism for missing news data
  - News caching with relevance filtering (≥ 0.5 score)
  - Always provides reliable sentiment signal (0-1 scale)
- **Data Sources**: Alpha Vantage News, NewsAPI, Finnhub
- **Caching**: 7-day news cache to reduce API calls

### 2. TechAgent (`src/agents/tech_agent.py`)

- **Technical Analysis**:
  - MACD calculation (fixed: uses MACD line, not histogram)
  - RSI, Bollinger Bands, EMA/SMA indicators
  - Pattern recognition via LLM
- **Key Fix**: MACD = MACD_line (EMA12 - EMA26) for correct signals
- **Data Sources**: Yahoo Finance, Alpha Vantage, FMP

### 3. StrategyAgent (`src/agents/strategy_agent.py`)

- **Trading Strategy**:
  - Enhanced strategy: sentiment >= 0 requirement
  - MACD-based entry/exit signals
  - Risk management with position sizing
- **Decision Logic**: Combines sentiment + technical signals

### 4. CoordinatorAgent (`src/agents/coordinator_agent.py`)

- **Orchestration**:
  - Manages agent communication
  - Aggregates signals from all agents
  - Provides unified trading recommendations
- **Output**: Structured signals with reasoning

## System Architecture

```
User Request
    ↓
CoordinatorAgent
    ├── SentimentAgent → News Analysis + VXX Fallback
    ├── TechAgent → Technical Indicators + MACD
    └── StrategyAgent → Trading Decision
         ↓
    Trading Signal
```

## Key Infrastructure

### Caching System

- **Market Data Cache**: 24-hour expiry, reduces API calls
- **News Cache**: 7-day expiry, filters relevant news only
- **Location**: `.cache/` directory

### Data Sources

- **Market Data**: Yahoo (primary), Alpha Vantage, FMP
- **News**: Alpha Vantage News, NewsAPI, Finnhub
- **Economic**: FRED, SEC Edgar (future)

### Output Organization

Backtests create organized output:

```
.cache/backtests/runs/SYMBOL_START_END_TIMESTAMP/
├── data/          # CSV files (trades, equity, metrics)
├── analysis/      # LLM reasoning and agent responses
├── reports/       # Executive summaries
└── metadata.json  # Run configuration
```

## Running the System

### Single Backtest

```bash
python scripts/backtest_mas.py SYMBOL START END

# Example
python scripts/backtest_mas.py AAPL 2024-01-01 2024-01-31
```

### Batch Testing

```bash
# Quick tests (2-3 minutes)
python scripts/run_backtest_suite.py quick

# Comprehensive tests (market stress periods)
python scripts/run_backtest_suite.py comprehensive --parallel

# Extended tests for specific symbols
python scripts/run_backtest_suite.py extended --symbols AAPL,MSFT
```

## Recent Changes (2025-07-11)

1. **MACD Fix**: Technical agent now uses MACD line instead of histogram
2. **News Caching**: Sentiment agent caches relevant news (score ≥ 0.5)
3. **Test Cleanup**: Tests moved to rapid iteration mode
4. **Documentation**: Consolidated agent docs, added technical agent guide

## API Limitations

- **Alpha Vantage**: 25 calls/day (free tier)
- **Yahoo Finance**: Rate limited but primary source
- **Solution**: Aggressive caching strategy

## Future Enhancements

- Risk agent implementation
- Quantitative agent for advanced analytics
- Memory system integration
- Real-time trading capabilities
