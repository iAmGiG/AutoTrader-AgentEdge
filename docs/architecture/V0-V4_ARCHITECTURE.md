# V0-V4 Sentiment Framework Architecture

## Overview
RH2MAS implements a 5-phase sentiment analysis study demonstrating the gradual introduction of LLM capabilities in financial trading decisions. Each version (V0-V4) uses the same MACD-based trading strategy with different sentiment approaches.

## Core Components

### 1. Agent Architecture (Simplified)
- **StrategyAgent**: Orchestrator that combines TechAgent + SentimentAgent outputs
- **TechAgent**: Fetches market data and calculates MACD indicators
- **SentimentAgent**: Implements V0-V4 sentiment approaches (5 different versions)
- **BaseAgent**: Common interface for all agents

### 2. Data Sources
- **Market Data**: 
  - Primary: Polygon.io API (5 calls/min, 1-year history)
  - Fallback: Alpha Vantage API (25 calls/day)
- **News Data**: 
  - Google Custom Search API (100 calls/day)
  - Premium sources: WSJ, Bloomberg, Barrons, Reuters

### 3. V0-V4 Sentiment Approaches

#### V0: Fixed Baseline
- Sentiment = 1.0 (always bullish)
- Pure MACD strategy baseline

#### V1: NLP Analysis  
- VADER sentiment analysis on Google Search news
- Mechanical sentiment scoring

#### V2: Market Fear
- VXX/VIX volatility-based sentiment
- Fear gauge from market indicators

#### V3: Heuristic Combination
- Weighted blend of V1 + V2
- Adaptive weighting based on market conditions

#### V4: LLM Analysis
- GPT-4o-mini reasoning for sentiment decisions
- Only version using LLM for decision-making

## Data Flow

```
Market Data (Polygon.io) → TechAgent → MACD Signals
                                          ↓
News Data (Google Search) → SentimentAgent[V0-V4] → Sentiment Score
                                          ↓
                            StrategyAgent → Trading Decision
```

## Key Design Principles

1. **Consistent Base Strategy**: MACD crossover signals remain constant across V0-V4
2. **Variable Sentiment**: Only sentiment approach changes between versions
3. **Clean Separation**: Each agent has single responsibility and data source
4. **Incremental Complexity**: V0→V1→V2→V3→V4 shows gradual sophistication
5. **Measurable Impact**: Quarterly backtesting shows value of each approach

## Testing Framework

- **Test Symbol**: AAPL (consistent across all tests)
- **Test Periods**: 2024 Q1-Q4, 2025 Q1 (5 quarters)
- **Metrics**: Returns, Sharpe ratio, max drawdown, trade frequency
- **Validation**: Statistical significance testing between versions