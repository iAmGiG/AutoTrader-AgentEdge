# V0-V4 Sentiment Framework Architecture

## Overview

RH2MAS implements a 5-phase sentiment analysis study demonstrating the gradual introduction of LLM capabilities in financial trading decisions. Each version (V0-V4) uses the same MACD-based trading strategy with different sentiment approaches.

**Status (August 2025)**: V0-V3 complete with full 2024 backtesting results. V4 implementation ready with weekly batch processing architecture.

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
  - Reliable sources: Bloomberg, CNBC, Reuters, Business Wire
  - Smart sampling reduces usage by 80-90%

### 3. V0-V4 Sentiment Approaches

#### V0: Fixed Baseline ✅ Complete

- **Result**: +9.00% return, 24 trades (2024)
- Sentiment = 1.0 (always bullish)
- Pure MACD strategy baseline for comparison

#### V1: NLP Analysis ✅ Complete  

- **Result**: +9.61% return, 6 trades (2024) - Best performance
- VADER sentiment analysis on Google Search news
- **News Search**: Direct company news (`AAPL` articles)
- Mechanical sentiment scoring with smart sampling

#### V2: Market Fear ✅ Complete

- **Result**: -3.53% return, 6 trades (2024) - Conservative/defensive
- VXX/VIX volatility-based sentiment with percentile-primary logic
- Fear gauge from market indicators (Issue #211 corrected)
- **News Search**: None (volatility-only approach)

#### V3: Heuristic Combination ✅ Complete

- **Result**: +1.04% return, 6 trades (2024) - Risk management
- Adaptive weighted blend of V1 (news) + V2 (market fear)
- **News Search**: Direct company news (inherits V1 approach)  
- Combiner agent pattern with mechanical weighting algorithm

#### V4: LLM Analysis 🚧 Implementation Ready

- **Architecture**: Weekly batch processing with date sanitization
- GPT-4o-mini reasoning for sentiment decisions
- **News Search**: 3-tier hierarchical system (Direct/Sector/Market news)
- **Market Context**: SPY/QQQ integration for macro awareness
- Only version using LLM for decision-making
- **Date Obfuscation**: Prevents temporal contamination in LLM analysis

## Data Flow

```
Market Data (Polygon.io) → TechAgent → MACD Signals
                                          ↓
News Data Paths:
- V0: None → SentimentAgent → Fixed Sentiment (1.0) ✅ +9.00%
- V1: Direct News → SentimentAgent → VADER Sentiment ✅ +9.61%
- V2: VXX Data → SentimentAgent → Fear-based Sentiment ✅ -3.53%
- V3: Direct News + VXX → SentimentAgent → Combined Sentiment ✅ +1.04%
- V4: Hierarchical News (3-tier) + Market Context → SentimentAgent → LLM Sentiment 🚧
                                          ↓
                            StrategyAgent → Trading Decision
```

## Key Design Principles

1. **Consistent Base Strategy**: MACD crossover signals remain constant across V0-V4
2. **Variable Sentiment**: Only sentiment approach changes between versions
3. **Clean Separation**: Each agent has single responsibility and data source
4. **Incremental Complexity**: V0→V1→V2→V3→V4 shows gradual sophistication
5. **Measurable Impact**: Quarterly backtesting shows value of each approach

## Testing Framework & Results

### Completed Testing (V0-V3)

- **Test Symbol**: AAPL (consistent across all tests)  
- **Test Period**: Full year 2024 (Jan 1 - Dec 31)
- **Results Summary**:
  - **V1 Best**: +9.61% return (news sentiment captured bull market)
  - **V0 Baseline**: +9.00% return (solid MACD foundation)
  - **V3 Conservative**: +1.04% return (risk management blend)
  - **V2 Defensive**: -3.53% return (contrarian in bull market)

### V4 Implementation Status

- **Architecture**: Weekly batch processing ready
- **Data Sources**: Hierarchical news + market context integrated
- **Date Sanitization**: Temporal obfuscation system implemented
- **Blocking Issue**: #212 (LLM tool calling efficiency optimization)

### Research Validation

- **Framework Proven**: V0-V3 demonstrate incremental sentiment value
- **Infrastructure**: Caching, APIs, and agents all validated
- **Academic Rigor**: Date filtering prevents contamination
- **Next Phase**: V4 completion for full LLM comparison
