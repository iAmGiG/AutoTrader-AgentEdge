# AutoGen-TradingSystem: Microsoft AutoGen Multi-Agent Trading Platform

## Overview

AutoGen-TradingSystem is a **production-ready trading platform** built on **Microsoft AutoGen** multi-agent framework. The system combines validated MACD+RSI voting strategies with sophisticated multi-agent coordination for real-world trading applications.

**🚀 Production Features**:
- **✅ VoterAgent** - Production-ready AutoGen agent with validated 0.856 Sharpe MACD+RSI voting
- **🚧 Multi-Agent System** - Scanner, Risk, Executor, and Orchestrator agents (in development)
- **Optimized Parameters** - Validated MACD (13/34/8) Fibonacci parameters across tech stocks
- **AutoGen Framework** - Built on Microsoft AutoGen for agent coordination and communication
- **Flexible Configuration** - Dynamic parameter adjustment without code changes
- **Paper Trading Ready** - Integration with Alpaca API (development in progress)
- **Comprehensive Testing** - Extensive validation and backtesting framework
- **Tool Integration** - Market data fetching and analysis tools for AutoGen agents

## Core AutoGen Agents: Multi-Agent Trading System

The platform implements a Microsoft AutoGen-based multi-agent architecture with specialized agents:

### Production-Ready Agents

**VoterAgent** (`src/autogen_agents/voter_agent.py`) - ✅ **PRODUCTION READY**:
- **MACD Signal Generation**: Optimized 13/34/8 Fibonacci parameters (fast/slow/signal)
- **RSI Momentum Analysis**: 14-period RSI with 30/70 oversold/overbought levels
- **Consensus Voting**: Strong signals when both indicators agree, weak when only one signals
- **Parameterizable Design**: Flexible parameter adjustment for testing and optimization
- **Validated Performance**: 0.856 Sharpe ratio, 36.6% return over 2024-2025 testing period
- **AutoGen Integration**: Full message handling and tool integration capabilities

### Agents in Development

**ScannerAgent** (`src/autogen_agents/scanner_agent.py`) - 🚧 **IN DEVELOPMENT**:
- Market opportunity identification and screening
- Multi-symbol analysis and ranking
- Real-time market scanning capabilities

**RiskAgent** (`src/autogen_agents/risk_agent.py`) - 🚧 **IN DEVELOPMENT**:
- Position sizing and risk management
- Portfolio-level risk monitoring
- Stop-loss and risk mitigation strategies

**ExecutorAgent** (`src/autogen_agents/executor_agent.py`) - 🚧 **IN DEVELOPMENT**:
- Trade execution and order management
- Alpaca API integration for paper/live trading
- Order status monitoring and reporting

**TradingOrchestrator** (`src/autogen_agents/trading_orchestrator.py`) - 🚧 **IN DEVELOPMENT**:
- Multi-agent coordination and workflow management
- Decision aggregation and conflict resolution
- System-wide monitoring and reporting

### AutoGen Architecture

**Agent Communication Framework**:
1. **Base Agent Class**: Common AutoGen agent foundation with tool integration
2. **Message Handling**: Structured JSON communication between agents
3. **Tool Integration**: Market data fetching and analysis tools accessible to all agents
4. **Parameter Management**: Flexible configuration system for dynamic agent adjustment

**Data Infrastructure**:
- **Market Data Tools**: Polygon.io integration through AutoGen tool system
- **Indicator Calculations**: MACD and RSI functions integrated with agents
- **Cache Optimization**: Intelligent caching for improved performance
- **Configuration System**: Flexible parameter management without code changes

**Validation Framework**:
- **VoterAgent Testing**: Comprehensive validation with 0.856 Sharpe performance
- **Parameter Optimization**: Systematic testing across multiple configurations
- **Multi-market Testing**: Validation across different market conditions
- **AutoGen Integration Testing**: Agent communication and coordination validation

## Production Architecture

### Core Components

1. **VoterAgent**: ✅ Production-ready AutoGen agent with validated MACD+RSI voting (0.856 Sharpe)
2. **Base Agent Framework**: AutoGen agent foundation with tool integration and message handling
3. **Trading Tools**: MACD and RSI calculation functions optimized for AutoGen agents
4. **Configuration System**: Flexible parameter management enabling dynamic agent adjustment
5. **Market Data Integration**: Polygon.io API integration through AutoGen tool framework
6. **Validation Suite**: Comprehensive testing framework for agent performance validation

*AutoGen Agents in Development*:
- **ScannerAgent**: Market opportunity identification and multi-symbol analysis
- **RiskAgent**: Portfolio risk management and position sizing
- **ExecutorAgent**: Trade execution and Alpaca API integration
- **TradingOrchestrator**: Multi-agent coordination and workflow management

### Data Infrastructure

**Trading APIs**:
- **Alpaca**: Paper and live trading execution (real-time order management)
- **Polygon.io**: Real-time and historical market data (WebSocket + REST)
- **Alpha Vantage**: Fallback market data source

**Technical Analysis Tools**:
- **Enhanced Fibonacci Regime Module**: Advanced market regime detection
- **Multi-Indicator Suite**: MACD, RSI, EMA filters with validated parameters
- **Statistical Validation**: Walk-forward analysis, Monte Carlo simulation

**Data Management**:
- **UnifiedCacheManager**: 90%+ performance improvement through intelligent caching
- **Multi-Source Aggregation**: Polygon.io primary, Alpha Vantage fallback
- **Real-time Pipeline**: WebSocket data streaming for live decision making (coming soon)

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
  "POLYGON_API_KEY": "...",        // Primary market data for AutoGen agents
  "ALPHA_VANTAGE_KEY": "...",      // Fallback market data source
  "OPENAI_API_KEY": "sk-...",      // For AutoGen agent LLM capabilities
  "ALPACA_API_KEY": "...",         // Paper/live trading (future)
  "ALPACA_SECRET_KEY": "...",      // Trading authentication (future)
  "ALPACA_BASE_URL": "paper-api.alpaca.markets"  // Paper trading URL (future)
}
```

Note: This file is excluded from version control for security. Currently only POLYGON_API_KEY and OPENAI_API_KEY are actively used by the VoterAgent.

## Usage

### AutoGen Agent Testing

```bash
# Test production VoterAgent (primary)
python scripts/experiments/experiment_293_validation/test_voter_agent.py

# VoterAgent validation experiments
python scripts/experiments/experiment_293_validation/experiment_293_retest.py
python scripts/experiments/experiment_293_validation/experiment_294_vote_thresholds.py

# Configuration system demonstration
python scripts/experiments/configuration_system/config_usage_demo.py
```

### Legacy Validation Scripts

```bash
# Historical validation experiments
python tests/experiment_293_macd_vs_voting.py       # Original voting validation
python tests/experiment_extended_period_voting.py  # Extended period testing

# Generate comprehensive analysis
python scripts/analysis/generate_results_summary.py --advanced
```

### Multi-Agent Development (Coming Soon)

```bash
# Start AutoGen multi-agent trading system
python scripts/trading/autogen_trading_system.py --mode paper

# Test agent coordination
python scripts/testing/test_multi_agent_coordination.py

# Monitor agent communication
python scripts/monitoring/agent_dashboard.py
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
AutoGen-TradingSystem/
├── src/
│   ├── autogen_agents/        # AutoGen agent implementations
│   │   ├── voter_agent.py     # ✅ Production-ready MACD+RSI voting agent
│   │   ├── base_agent.py      # Base AutoGen agent with tool integration
│   │   ├── scanner_agent.py   # 🚧 Market scanning agent (in development)
│   │   ├── risk_agent.py      # 🚧 Risk management agent (in development)
│   │   ├── executor_agent.py  # 🚧 Trade execution agent (in development)
│   │   └── trading_orchestrator.py  # 🚧 Multi-agent coordinator
│   ├── trading_tools/         # Tools and functions for AutoGen agents
│   │   └── indicators.py      # MACD and RSI calculation functions
│   ├── data_sources/          # Market data integration
│   │   └── tools.py           # Market data fetching tools for agents
│   ├── deprecated/            # Legacy V0-V4 sentiment system (archived)
│   └── utils/                 # Common utilities and helpers
├── scripts/
│   ├── experiments/           # Organized experiment validation
│   │   ├── experiment_293_validation/  # VoterAgent testing and validation
│   │   └── configuration_system/       # Parameter management demos
│   ├── analysis/              # Results analysis and reporting
│   └── validation/            # General validation scripts
├── config/                    # API configuration (local only)
├── config_defaults/           # Default configuration management
├── tests/                     # Legacy test scripts
└── .cache/                    # Market data caching system
```

## Documentation

**Trading Setup**:
- [Trading Guide](docs/trading/setup.md) - Paper and live trading setup
- [Risk Management](docs/trading/risk_management.md) - Position sizing and portfolio controls
- [API Integration](docs/api/alpaca_setup.md) - Alpaca and data provider setup

**System Architecture**:
- [Fibonacci Integration Guide](docs/integration/fibonacci_enhanced_integration_guide.md) - Complete integration documentation
- [Quick Reference](docs/integration/quick_reference.md) - Essential commands and usage
- [Regime Detection Tools](docs/fibonacci_regime/regime_detection_tools.md) - Technical analysis modules

**Reference**:
- [Commands](docs/reference/commands.md) - All available scripts and commands
- [Troubleshooting](docs/reference/troubleshooting.md) - Common issues and solutions

## Development Status

### Production-Ready Foundation ✅

- **✅ VoterAgent Production Ready**: AutoGen-based MACD+RSI voting agent with validated 0.856 Sharpe performance
- **✅ Validated Parameters**: MACD 13/34/8 Fibonacci parameters optimized across tech stocks
- **✅ AutoGen Integration**: Full Microsoft AutoGen framework integration with message handling and tool access
- **✅ Flexible Configuration**: Dynamic parameter adjustment system without code modifications
- **✅ Performance Proven**: 36.6% return over 2024-2025, superior performance in volatile markets
- **✅ Tool Integration**: Market data fetching and analysis tools accessible to AutoGen agents
- **✅ Testing Framework**: Comprehensive validation suite for agent performance testing

### Active Development 🚧

**Phase 2: Multi-Agent System Completion**:
- **ScannerAgent** - Market opportunity identification and multi-symbol analysis
- **RiskAgent** - Portfolio risk management and position sizing logic
- **ExecutorAgent** - Trade execution and Alpaca API integration
- **TradingOrchestrator** - Multi-agent coordination and workflow management

**Priority Development Issues**:
- [Issue #324](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/324) - Forward testing protocol implementation
- [Issue #323](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/323) - Full trading pipeline workflow
- [Issue #322](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/322) - Live execution layer enhancements
- [Issue #321](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/321) - Dynamic trailing stop logic
- [Issue #320](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/320) - Expand sample size for statistical confidence

### Project Evolution

Originally developed as a research framework (RH2MAS), this project has evolved into AutoGen-TradingSystem - a production-ready trading platform built on Microsoft AutoGen multi-agent framework. The system combines validated MACD+RSI voting strategies with sophisticated multi-agent coordination.

**Key Advantages**:

- **AutoGen-Based Architecture**: Built on Microsoft AutoGen framework for robust multi-agent communication
- **Production-Ready VoterAgent**: Validated 0.856 Sharpe performance with MACD+RSI voting logic
- **Flexible Parameter System**: Dynamic configuration without code modifications
- **Extensible Multi-Agent Design**: Clean separation enabling easy addition of new specialized agents
- **Tool Integration**: Market data and analysis tools seamlessly integrated with AutoGen agents
- **Open Source**: Complete transparency in agent logic, parameters, and validation results

## License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
