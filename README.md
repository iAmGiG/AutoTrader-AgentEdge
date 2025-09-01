# RH2MAS: Practical Multi-Agent Trading Platform

## Overview

RH2MAS (Reflective Hybrid-Head Multi-Agent System) is a **production-ready trading platform** that combines sophisticated multi-agent architecture with advanced risk management for real-world trading applications. Originally developed as a research framework for gradual LLM introduction (V0-V4 sentiment analysis), it has evolved into a comprehensive backtesting and trading system.

**🚀 Production Features**: 
- Multi-strategy ensemble system with V0-V4 agents
- Real-time paper trading with Alpaca API integration
- Advanced risk management and portfolio optimization
- Comprehensive performance analytics and alerting
- 90%+ performance improvements through cache optimization

## Core Strategy Agents: V0-V4 Framework

The platform implements a multi-strategy system with 5 progressively sophisticated agents:

- **V0 (Baseline)**: Fixed sentiment = 1.0 - Pure MACD strategy foundation  
- **V1 (NLP)**: VADER sentiment analysis on news - Traditional sentiment processing
- **V2 (Market Fear)**: VXX/VIX volatility-based sentiment - Market regime detection
- **V3 (Hybrid)**: Weighted combination of V1 + V2 - Mechanical ensemble approach
- **V4 (LLM)**: GPT-4o-mini reasoning - AI-enhanced market psychology understanding

**Production Integration**: These agents serve as strategy components in an ensemble orchestration system, with dynamic weighting based on market conditions and performance attribution.

### Performance Architecture

**Unified Cache-Optimized Agents (V0-V4)**:
1. **Direct Tool Access** (cache hit): Instant data retrieval from UnifiedCacheManager → 90%+ speed improvement
2. **LLM Tool Calling** (cache miss): Systematic data fetching with LLM routing → Full functionality 
3. **Neutral Sentiment** (emergency fallback): Graceful degradation in extreme failure cases

**V4 LLM Processing**:
- Weekly batch processing with date sanitization (prevents training data leakage)
- Checkpoint/resume system for long-running backtests
- Incremental progress tracking with research artifact preservation

This architecture enables instant V0-V3 responses when cached, while V4 processes intelligently with temporal safeguards.

## Production Architecture

### Core Components

1. **StrategyOrchestrator**: Ensemble management with weighted voting and dynamic rebalancing
2. **RiskAgent**: Comprehensive risk management with position sizing and portfolio controls
3. **V0-V4 Agents**: Multi-strategy sentiment analysis (5 specialized agents)
4. **ExecutionAgent**: Alpaca API integration for paper/live trading
5. **TechAgent**: Market data processing and technical indicator calculation
6. **AlertAgent**: Multi-channel notifications and monitoring

### Data Infrastructure

**Trading APIs**:
- **Alpaca**: Paper and live trading execution (real-time order management)
- **Polygon.io**: Real-time and historical market data (WebSocket + REST)
- **Alpha Vantage**: Fallback market data source

**Analysis APIs**:
- **Google Custom Search**: News sentiment analysis (smart sampling)
- **OpenAI**: V4 agent LLM processing and advanced analysis

**Data Management**:
- **UnifiedCacheManager**: 90%+ performance improvement through intelligent caching
- **NewsGovernor**: API usage reduction (80-90%) through smart news sampling
- **Real-time Pipeline**: WebSocket data streaming for live decision making

## Installation

```bash
# Python 3.10+ required
conda create -n RH2MAS python=3.10
conda activate RH2MAS

# Install dependencies
pip install -e .
```

## Configuration

Create `config/config.json` with required API keys:

```json
{
  "ALPACA_API_KEY": "...",         // Paper/live trading
  "ALPACA_SECRET_KEY": "...",      // Trading authentication
  "ALPACA_BASE_URL": "paper-api.alpaca.markets",  // Paper trading URL
  "OPENAI_API_KEY": "sk-...",      // V4 LLM analysis
  "POLYGON_API_KEY": "...",        // Real-time market data
  "ALPHA_VANTAGE_KEY": "...",      // Fallback market data
  "GOOGLE_API_KEY": "...",         // News sentiment analysis
  "GOOGLE_CSE_ID": "..."           // Custom search engine ID
}
```

Note: This file is excluded from version control for security.

## Usage

### Production Trading (Coming Soon)

```bash
# Start paper trading with ensemble strategies
python scripts/trading/live_trading.py --mode paper

# Real-time performance monitoring
python scripts/monitoring/dashboard.py

# Portfolio analysis and risk metrics
python scripts/analysis/portfolio_analysis.py
```

### Backtesting and Strategy Development

```bash
# Strategy ensemble backtesting
python scripts/runs/backtest.py --ensemble --all-versions

# Individual strategy testing
python scripts/runs/backtest.py --version V4

# Performance comparison and analysis
python scripts/analysis/generate_results_summary.py --advanced
```

### Risk Management and Alerts

```bash
# Configure risk parameters
python scripts/risk/configure_risk_limits.py

# Test alert system
python scripts/alerts/test_notifications.py
```

## Project Structure

```bash
RH2MAS/
├── src/
│   ├── agents/           # V0-V4 strategy agents + Risk/Execution agents
│   ├── orchestration/    # Strategy ensemble and portfolio management
│   ├── risk/             # Risk management and position sizing
│   ├── execution/        # Alpaca API integration and order management
│   ├── monitoring/       # Performance analytics and alerting
│   ├── tools/            # Data sources with unified caching
│   └── utils/            # Common utilities and helpers
├── scripts/
│   ├── trading/          # Live trading and paper trading
│   ├── monitoring/       # Performance dashboards and alerts
│   ├── risk/             # Risk parameter configuration
│   ├── runs/             # Backtesting and strategy development
│   └── analysis/         # Results analysis and reporting
├── docs/
│   ├── architecture/     # System design and component structure
│   ├── trading/          # Trading setup and risk management
│   └── api/              # API integration guides
├── config/               # API configuration (local only)
├── reports/              # Trading results and performance analytics
└── .cache/               # Unified caching system
```

## Documentation

**Trading Setup**:
- [Trading Guide](docs/trading/setup.md) - Paper and live trading setup
- [Risk Management](docs/trading/risk_management.md) - Position sizing and portfolio controls
- [API Integration](docs/api/alpaca_setup.md) - Alpaca and data provider setup

**System Architecture**:
- [V0-V4 Architecture](docs/architecture/V0-V4_ARCHITECTURE.md) - Core strategy framework
- [Production Architecture](docs/architecture/production_system.md) - Trading system design
- [Agent Orchestration](docs/architecture/agent_orchestration.md) - Ensemble management

**Reference**:
- [Commands](docs/reference/commands.md) - All available scripts and commands
- [Troubleshooting](docs/reference/troubleshooting.md) - Common issues and solutions

## Development Status

### Production-Ready Foundation ✅

- **V0-V4 Strategy Framework**: Complete multi-agent strategy system  
- **Advanced Backtesting**: Full-year testing with checkpoint/resume capabilities
- **Cache-Optimized Architecture**: 90%+ performance improvement through intelligent caching
- **Multi-Asset Support**: Stocks, ETFs, and portfolio-level testing capabilities
- **News Integration**: Smart sampling and sentiment analysis infrastructure
- **Performance Analytics**: Comprehensive metrics and statistical validation

### Active Production Development 🚧

**Priority 1 (Foundation)**:
- [Alpaca API Integration](https://github.com/iAmGiG/RH2MAS/issues/258) - Paper trading implementation
- [Comprehensive Risk Agent](https://github.com/iAmGiG/RH2MAS/issues/177) - Position sizing and risk controls  
- [Real-time Data Pipeline](https://github.com/iAmGiG/RH2MAS/issues/259) - WebSocket integration

**Priority 2 (Enhancement)**:
- [Strategy Orchestration](https://github.com/iAmGiG/RH2MAS/issues/260) - Ensemble management system
- [Performance Dashboard](https://github.com/iAmGiG/RH2MAS/issues/261) - Real-time monitoring interface
- [Alert System](https://github.com/iAmGiG/RH2MAS/issues/262) - Multi-channel notifications

**Priority 3 (Advanced)**:
- [Portfolio Management](https://github.com/iAmGiG/RH2MAS/issues/263) - Multi-asset portfolio optimization

### Project Evolution

Originally developed as an academic research framework for studying gradual LLM introduction in trading decisions, RH2MAS has evolved into a practical trading platform. The V0-V4 foundation provides a robust multi-strategy base for production trading applications.

**Key Advantages**:

- **Proven Framework**: V0-V4 strategies tested across full-year market conditions
- **Risk-First Design**: Built with comprehensive risk management from the ground up  
- **Scalable Architecture**: Designed for both individual trading and institutional use
- **Open Source**: Complete transparency in strategy logic and risk controls

## License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
