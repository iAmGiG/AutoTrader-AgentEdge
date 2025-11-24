# AutoTrader-AgentEdge Overview

**Status**: Production-Ready Multi-Agent Trading Platform
**Foundation**: Microsoft AutoGen Framework
**Validated Performance**: 0.856 Sharpe Ratio, 51.4% Win Rate

## What Is This System?

AutoTrader-AgentEdge is a professional algorithmic trading platform built on Microsoft's AutoGen multi-agent framework. The system employs ensemble voting methodologies backed by academic research to achieve superior risk-adjusted returns compared to single-indicator strategies.

### Core Purpose

This is a **human-guided trade management system**, not an autonomous trading bot:

- **Human decides**: External trade signals and opportunities from trader network
- **System provides**: Entry timing via MACD+RSI voting, risk management, execution
- **System manages**: Position monitoring, stop management, exit strategies
- **Goal**: Beat savings account returns (2-5% APY) with controlled risk

### Performance Benchmark

- **Comparison**: Savings account rates (2-5% APY), NOT buy-and-hold
- **Target**: 8-12% annual return = SUCCESS
- **Focus**: Risk-adjusted returns over raw returns

## System Capabilities

### ✅ Production Components

**VoterAgent** - Production-ready MACD+RSI voting with proven performance:

- Validated Sharpe Ratio: 0.856
- Win Rate: 51.4%
- Max Drawdown: -10.10%
- Configuration: Fibonacci MACD (13/34/8) + RSI(14)

**Position Manager** - Unified position and account tracking:

- Real-time account monitoring
- Position state management
- Integration with all agents via tools

**Order Manager** - Complete order placement and monitoring:

- Order types: Market, limit, stop, trailing, bracket
- Risk management: Market hours, daily limits, position validation
- Fill monitoring with automatic state transitions

**Trading Cycle** - Comprehensive position monitoring:

- Entry signal detection
- Position tracking during hold
- Stop management and exit execution

### ✅ Integration Complete

**Alpaca Markets**:

- Full paper and live trading support
- Real-time and historical market data
- Order execution and monitoring
- Account and position management

**Market Data**:

- Real-time data via Alpaca SDK
- Intelligent caching (>90% API call reduction)
- Multi-provider normalization (Polygon, Alpha Vantage fallbacks)
- AutoGen tool wrappers for agent access

**Order Types**:

- Market orders (immediate execution)
- Limit orders (price-specific)
- Stop orders (risk management)
- Trailing stops (profit protection)
- Bracket orders (OCO with stops)

### 🔄 In Development

**Multi-Agent Ecosystem** (Issue #310):

1. **Scanner Agent**: Multi-ticker market scanning
2. **Risk Agent**: Portfolio risk management
3. **Executor Agent**: Trade execution coordination
4. **Human Interface**: Decision presentation and CLI

## Architecture Highlights

### Multi-Agent Framework

The system leverages Microsoft AutoGen for agent coordination:

- **Agent Communication**: Structured message passing between agents
- **Unified Tools**: Single source of truth accessible to all agents
- **Error Handling**: Comprehensive error recovery and logging
- **State Management**: Persistent trade state across restarts

### Layer Separation

Clean architectural boundaries:

1. **Integration Layer** (`src/trading/`): External service integrations, stateful operations
2. **Business Logic Layer** (`src/trading_tools/`): Pure functions, calculations, utilities
3. **AutoGen Agent Layer** (`src/autogen_agents/`): Multi-agent trading coordination
4. **Data Layer** (`src/data_sources/`): Market data acquisition and normalization

### Key Design Principles

1. **Separation of Concerns**: Integration ≠ Business Logic ≠ Decisions
2. **Unified Architecture**: Single codebase for paper and live trading
3. **Production Safety**: Multi-level confirmations, comprehensive validation
4. **Agent-Ready Design**: AutoGen tool wrappers for all functionality

## Validated Performance

### Experiment #293 Results

The 2-way voting strategy (MACD + RSI) validated as superior to single indicators:

| Metric | MACD-Only | Voting (MACD+RSI) | Winner |
|--------|-----------|-------------------|--------|
| **Sharpe Ratio** | 0.841 | **0.856** | **Voting** |
| **Max Drawdown** | -10.58% | **-10.10%** | **Voting** |
| **Win Rate** | 31.9% | **51.4%** | **Voting** |
| **Volatility** | 16.58% | **15.30%** | **Voting** |

### Extended Period Performance (2024-2025)

- **Period**: 417 trading days
- **Sharpe Ratio**: 0.771
- **Total Return**: +36.6%
- **Key Finding**: Voting performs relatively better in volatile markets (11.2% improvement vs bull markets)

### System Reliability

- **Test Coverage**: 35/35 tests passing
- **System Uptime**: 99.9% (robust error handling)
- **Cache Performance**: >90% API call reduction
- **Error Recovery**: Comprehensive validation and recovery

## Research Foundation

The system architecture is grounded in peer-reviewed research:

1. **Ensemble Methods**: 70-90% accuracy potential (vs 45-65% single indicators)
2. **Multi-Indicator Integration**: 15% win rate improvement through signal confirmation
3. **Regime Adaptation**: 32% drawdown reduction via dynamic strategy adjustment
4. **LLM Trading Behavior**: Bias mitigation through regime-aware approaches

**Academic Support**:

- Machine Learning Ensemble Methods for Stock Market Forecasting (2020)
- Enhanced Trading Performance through Multi-Indicator Signal Integration (2024)
- Hierarchical Multi-Agent Trading with Dynamic Strategy Selection (2023)
- FINSABER: LLM Trading Behavior Analysis (2024)

See [research_foundation.md](../presentations/research_foundation.md) for detailed citations and implementation impact.

## Technology Stack

**Core Framework**:

- Microsoft AutoGen (multi-agent coordination)
- Python 3.8+ (primary language)

**Trading Integration**:

- Alpaca Markets API (broker integration)
- alpaca-py SDK (official Python SDK)

**Data & Analysis**:

- pandas (data manipulation)
- NumPy (numerical computations)
- TA-Lib / custom indicators (technical analysis)

**Caching & Performance**:

- TradingCacheManager (SQLite: 8-10x performance, 90%+ hit rate)
- ACID transactions with thread-safe concurrent access
- Smart expiration: Historical data (10 year TTL), Recent data (24 hour TTL)

## Current Development Status

### Phase 1-2: Complete ✅

- Core voting architecture implemented
- MACD+RSI validation successful
- Production-ready single-agent system

### Phase 3: In Progress 🚧

- Expanded ensemble with additional indicators (RSI, Bollinger Bands, Volume)
- Multi-agent coordination framework
- Scanner and Risk agents

### Phase 4-5: Planned 📋

- Weighted voting and confidence scoring
- Market regime detection and adaptation
- Production deployment with live trading

## Next Steps

For detailed information about specific aspects of the system:

- **How It Works**: See `02_phases_of_operation.md` for operational flow
- **Why It Exists**: See `03_system_context.md` for development philosophy
- **Technical Design**: See `../02_architecture/` for detailed architecture
- **Proven Results**: See `../03_reference/01_validation_results.md` for performance data

---

*Production-ready AutoGen multi-agent trading platform with research-validated ensemble voting methodology and comprehensive safety controls.*
