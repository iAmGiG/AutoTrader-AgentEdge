# AutoGen-TradingSystem: Human-in-Loop Multi-Agent Trading Platform

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![AutoGen](https://img.shields.io/badge/AutoGen-0.7.x-green.svg)](https://github.com/microsoft/autogen)
[![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Sharpe Ratio](https://img.shields.io/badge/Sharpe-0.856-brightgreen.svg)](docs/validation/)
[![Total Return](https://img.shields.io/badge/Return-36.6%25-brightgreen.svg)](docs/validation/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[![Alpaca Markets](https://img.shields.io/badge/Broker-Alpaca-yellow.svg)](https://alpaca.markets/)
[![Polygon.io](https://img.shields.io/badge/Data-Polygon.io-purple.svg)](https://polygon.io/)
[![OpenAI](https://img.shields.io/badge/LLM-OpenAI-412991.svg)](https://openai.com/)
[![Paper Trading](https://img.shields.io/badge/Trading-Paper%20%26%20Live-orange.svg)](#quick-start)

[![Async/Await](https://img.shields.io/badge/Async-asyncio-blue.svg)](https://docs.python.org/3/library/asyncio.html)
[![YAML](https://img.shields.io/badge/Config-YAML-red.svg)](https://yaml.org/)
[![Interactive CLI](https://img.shields.io/badge/Interface-Interactive%20CLI-green.svg)](#quick-start)

## Overview

AutoGen-TradingSystem is a **production-ready trading platform** built on **Microsoft AutoGen 0.7.x** framework. The system combines validated pure-math MACD+RSI strategies with human oversight for paper/live trading via Alpaca Markets.

**💡 Core Philosophy**: Pure mathematical indicators + human decision making > complex LLM sentiment analysis

**🚀 Production Status** (Updated 2025-11-11):

- **✅ VoterAgent** - Production-ready with validated 0.856 Sharpe ratio, 36.6% return
- **✅ main.py Runner** - Fully functional CLI for paper trading operations
- **✅ Alpaca Integration** - Paper trading validated and operational
- **✅ Position Management** - Real-time tracking with broker-as-truth reconciliation
- **✅ Trading Cycle** - Cost-efficient daily routines (90% fewer API calls)
- **✅ Scheduler CLI** - Interactive management interface with daemon detection
- **✅ YAML Configuration** - All configs migrated to readable YAML format
- **✅ Human-in-Loop CLI** - Trade approval interface (Issue #308 - COMPLETED)
- **🚧 Multi-Agent System** - Scanner, Risk, Executor agents (planned)

**Key Metrics**:

- **Sharpe Ratio**: 0.856 (excellent risk-adjusted returns)
- **Total Return**: 36.6% (2024-2025 validation period)
- **Win Rate**: 51.4%
- **Max Drawdown**: -10.10%
- **Strategy**: Pure MACD(13/34/8) + RSI(14/30/70) voting - NO LLM calls

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

**NEW**: Configuration files now use YAML format for better readability. JSON format still supported for backward compatibility.

All API credentials in `config/config.yaml` (or `config/config.json`):

```json
{
  "POLYGON_IO": "your_key_here",              // ✅ Required: Primary market data
  "ALPHA_VANTAGE_KEY": "your_key_here",       // ✅ Required: Fallback market data
  "ALPACA_PAPER_API_KEY": "your_key_here",    // ✅ Required: Paper trading
  "ALPACA_PAPER_SECRET": "your_key_here",     // ✅ Required: Paper trading secret
  "ALPACA_ENDPOINT": "https://paper-api.alpaca.markets/v2",  // ✅ Paper trading URL

  "OPEN_AI_KEY": "sk-...",                    // Optional: For future LLM-based agents
  "OPENAI_TOOL_MODEL": "gpt-4o-mini",         // Optional: Tool calling model
  "OPENAI_PROMPT_MODEL": "o3-mini",           // Optional: Reasoning model

  "GOOGLE_SEARCH_API_KEY": "...",             // Legacy: Deprecated sentiment system
  "NEWSAPI_KEY": "...",                       // Legacy: Deprecated sentiment system
  "FINNHUB_KEY": "..."                        // Legacy: Deprecated sentiment system
}
```

**Note**:

- VoterAgent uses **pure math calculations** (MACD+RSI) - OpenAI keys NOT required for trading
- LLM sentiment analysis was tested and deprecated as ineffective vs. technical indicators
- This file is excluded from version control for security

## Quick Start

### Unified Interactive CLI (✅ NEW - Priority #1)

**Default: Interactive Trading Assistant**

```bash
# Launch unified interactive CLI (default)
python main.py

# Interactive session with all features:
> buy 10 AAPL              # Execute trades
> check my alerts          # Position alerts
> show portfolio           # Account status
> /schedule                # Enter scheduler management CLI
> /help                    # Show all commands
> /exit                    # Exit
```

**Daemon Mode: Background Scheduler**

```bash
# Run daily scheduler in background
python main.py --daemon

# Executes twice daily:
#   - Morning: 9:20 AM ET (position reconciliation + alerts)
#   - Evening: 3:50 PM ET (performance review)
```

**Legacy Commands (Deprecated)**

```bash
# Legacy one-shot commands (will be removed)
python main.py --legacy test-voter
python main.py --legacy check-positions
python main.py --legacy paper-trade SPY
```

**Example Interactive Session**:

```
🚀 Launching Interactive Trading Assistant...

======================================================================
   AutoGen Trading Assistant - Unified Interactive CLI
======================================================================

> buy 10 AAPL
⏳ Analyzing trade...
📊 AAPL @ $185.50
✅ BUY SUGGESTED
   Confidence: 65.0%
   Entry:  $185.50
   Stop:   $176.23 (-5.0%)
   Target: $200.34 (+8.0%)

Continue? [yes/no]: yes
✅ ORDER PLACED SUCCESSFULLY

> check my alerts
📊 Checking Position Alerts...
🔔 1 Alert(s) Generated:
   ⚠️  TQQQ: approaching_take_profit
      Current: $53.85
      distance_pct: 1.85%

> show portfolio
💼 Portfolio Status...
💰 Account:
   Equity: $102,450.00
   Buying Power: $52,000.00
📊 Positions (3):
   🟢 AAPL: 10 shares @ $185.50
      P/L: +$85.00 (+4.58%)
```

### Validation & Backtesting

```bash
# VoterAgent validation experiments
python scripts/experiments/experiment_293_validation/test_voter_agent.py
python scripts/experiments/experiment_293_validation/experiment_293_retest.py

# Generate comprehensive analysis with advanced metrics
python scripts/analysis/generate_results_summary.py --advanced
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

**Scheduler & Automation**:

- [Scheduler CLI Reference](docs/features/scheduler_cli_reference.md) - Interactive scheduler management
- [GTC Scheduler Technical](docs/features/03_gtc_scheduler_technical.md) - Daily execution system details
- [Background Service Design](docs/architecture/scheduler_background_service.md) - Future service architecture
- [Quick Start Guide](docs/features/QUICKSTART_ISSUE_287.md) - Getting started with automation

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

### Active Production Development 🚧

**Phase 2: Multi-Agent System Completion**:

- **ScannerAgent** - Market opportunity identification and multi-symbol analysis
- **RiskAgent** - Portfolio risk management and position sizing logic
- **ExecutorAgent** - Trade execution and Alpaca API integration
- **TradingOrchestrator** - Multi-agent coordination and workflow management

**Priority Development Issues**:

- [Issue #327](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/327) - ✅ Make main.py functional (COMPLETED 2025-10-23)
- [Issue #287](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/287) - ✅ GTC Daily Execution System (COMPLETED 2025-11-11)
- [Issue #308](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/308) - ✅ CLI human-in-loop interface (COMPLETED 2025-11-11)
- [Issue #349](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/349) - ✅ Entry price display fix (COMPLETED 2025-11-11)
- [Issue #350](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/350) - 🚧 Background scheduler service (planned)
- [Issue #328](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/328) - JSON→YAML token optimization (future)
- [Issue #310](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/310) - Complete remaining AutoGen agents
- [Issue #316](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/316) - Event bus for agent communication
- [Issue #324](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/324) - Forward testing protocol
- [Issue #321](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/321) - Dynamic trailing stop logic

### Project Evolution

Originally developed as a research framework (RH2MAS), this project has evolved into AutoGen-TradingSystem - a production-ready trading platform built on Microsoft AutoGen multi-agent framework. The system combines validated MACD+RSI voting strategies with sophisticated multi-agent coordination.

**Key Advantages**:

- **AutoGen-Based Architecture**: Built on Microsoft AutoGen framework for robust multi-agent communication
- **Production-Ready VoterAgent**: Validated 0.856 Sharpe performance with MACD+RSI voting logic
- **Flexible Parameter System**: Dynamic configuration without code modifications
- **Extensible Multi-Agent Design**: Clean separation enabling easy addition of new specialized agents
- **Tool Integration**: Market data and analysis tools seamlessly integrated with AutoGen agents
- **Open Source**: Complete transparency in agent logic, parameters, and validation results

## Recent Updates

### November 2025 - Enhanced Scheduler CLI & YAML Configuration Migration

**✅ Completed**:

- **Dedicated Scheduler Management CLI** with `/schedule` command
- **Interactive Configuration Editor** - No manual file editing required
- **Real-time Daemon Status Detection** - Clear distinction between config vs service state
- **YAML Configuration Migration** - All configs now in readable YAML format
- **CLI Message Configuration System** - Centralized UI text management
- **Entry Price Display Fix** (Issue #349) - Accurate position tracking
- **Complete Documentation** - Scheduler CLI reference and background service design

**🚀 Key Features**:

- **Scheduler CLI Commands**:
  - `status` - Show config state and daemon status with next run times
  - `config` - View all scheduler settings
  - `edit` - Interactive editor with input validation
  - `enable/disable` - Toggle automated trading
  - `test morning/evening` - Run routines immediately for testing
  - `history` - View execution history with success/failure tracking
  - `next` - See upcoming scheduled runs

- **UX Improvements**:
  - Fixed "enabled" confusion - now shows both "Config: ENABLED" and "Service: RUNNING" separately
  - Clear instructions when daemon not running but config enabled
  - Real-time daemon process detection using psutil
  - Input validation prevents configuration errors

- **YAML Migration Benefits**:
  - Better readability for all configuration files
  - Backward compatible with existing JSON configs
  - `config_defaults/` now contains: `trading_config.yaml`, `scheduler_config.yaml`, `agent_prompts.yaml`
  - Template file `config.example.yaml` for easy API key setup

**Quick Start - Scheduler Management**:

```bash
# Enter scheduler management from main CLI
python main.py
> /schedule

# Check status (shows if daemon actually running)
Scheduler> status

🟢 Config: ENABLED
❌ Service: NOT RUNNING (no automatic execution)

💡 Config is enabled but daemon is not running.
   To start automatic execution:
   1. Exit this CLI
   2. Run: python main.py --daemon

# Edit configuration interactively
Scheduler> edit

# Test a routine immediately (don't wait for scheduled time)
Scheduler> test morning

# View execution history
Scheduler> history
```

**Documentation**:

- [Scheduler CLI Reference](docs/features/scheduler_cli_reference.md) - Complete command guide
- [Background Service Design](docs/architecture/scheduler_background_service.md) - Future self-terminating service architecture

**See Issues**:

- [Issue #349](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/349) - Entry price display fix
- [Issue #350](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/350) - Background service feature (planned)

### November 11, 2025 - GTC Daily Execution System (Issue #287)

**✅ Completed**:

- Automated "set it and forget it" daily trading system
- Morning (9:20 AM ET) and evening (3:50 PM ET) routines
- Comprehensive retry logic with exponential backoff
- Robust error handling and crash recovery
- systemd service and crontab deployment options
- 90% API call reduction through GTC orders

**🚀 Key Features**:

- **Daily Scheduling**: Automated position reconciliation and stop adjustments
- **Retry Logic**: Exponential backoff (60s, 120s, 240s) with 10% jitter
- **Error Handling**: Task, execution, and system-level exception management
- **Monitoring**: Detailed execution logs and status reports
- **Cost-Efficient**: 6-10 API calls per day vs. 1,000+ with traditional polling

**Quick Start**:

```bash
# Test the scheduler
python src/trading/daily_scheduler.py --mode once --task morning_routine

# Install as service (systemd)
sudo scripts/deployment/install_scheduler.sh

# Or setup cron jobs
./scripts/deployment/setup_cron.sh
```

**See**:

- [Issue #287](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/287) for requirements
- [Quick Start Guide](docs/features/QUICKSTART_ISSUE_287.md) for setup
- [Full Documentation](docs/features/issue_287_gtc_daily_execution.md) for details

### October 23, 2025 - main.py Production Ready

**✅ Completed**:

- Fixed all import errors and function signature issues in main.py
- Validated Alpaca paper trading integration (14 shares SPY @ $657.60, +2.2% P&L)
- Implemented dual OpenAI model configuration (4o-mini for tools, o3-mini for reasoning)
- Updated documentation to clarify pure-math approach (no LLM sentiment)

**🎯 Key Insights**:

- VoterAgent uses pure MACD+RSI calculations (no LLM calls) - faster, cheaper, validated
- LLM sentiment analysis was tested extensively and deprecated as ineffective
- Human-in-loop design: System assists humans, doesn't trade autonomously
- Cost-efficient: 90% fewer API calls through intelligent batching and GTC orders

**See**: [Issue #327](https://github.com/iAmGiG/AutoGen-TradingSystem/issues/327) for complete details

---

## License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
