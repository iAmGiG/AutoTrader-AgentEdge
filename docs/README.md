# AutoTrader-AgentEdge Documentation

Professional documentation for AutoTrader-AgentEdge - a Microsoft AutoGen-based trading platform with proven MACD+RSI voting strategy and comprehensive multi-agent architecture.

## Documentation Structure

### 📋 **01 - Overview** (Start Here)

- **[01. System Overview](01_overview/01_system_overview.md)** - What the system is and what it does
- **[02. Phases of Operation](01_overview/02_phases_of_operation.md)** - How it works (5 sequential phases)
- **[03. System Context](01_overview/03_system_context.md)** - Why it was built and design philosophy

### 🏗️ **02 - Architecture** (Technical Design)

- **[01. Core Architecture](02_architecture/01_core_architecture.md)** - Layer separation, directory structure, design principles
- **[02. Agent Ensemble](02_architecture/02_agent_ensemble.md)** - Multi-agent system with VoterAgent, Scanner, Risk, Executor
- **[03. Voting System](02_architecture/03_voting_system.md)** - Multi-indicator voting structure and implementation
- **[04. Cache System](02_architecture/04_cache_system.md)** - SQLite-based caching (8-10x performance improvement)
- **[05. Integration APIs](02_architecture/05_integration_apis.md)** - Alpaca market data and order management

### 📚 **03 - Reference** (Lookup & Details)

- **[01. Validation Results](03_reference/01_validation_results.md)** - Proven performance metrics and experiment results
- **[02. Terminology](03_reference/02_terminology.md)** - Glossary of terms and concepts
- **[03. Commands](03_reference/03_commands.md)** - CLI commands and scripts reference
- **[04. Troubleshooting](03_reference/04_troubleshooting.md)** - Common issues and solutions
- **[05. Known Issues](03_reference/05_known_issues.md)** - Current known limitations and workarounds
- **[06. Naming Conventions](03_reference/05_naming_conventions.md)** - Code and file naming standards
- **[07. News Limitations](03_reference/06_news_limitations.md)** - API constraints and considerations

### 📂 **04 - Development** (For Contributors)

- **[01. Codebase Structure](04_development/01_codebase_structure.md)** - File organization and component layout
- **[02. Project Status](04_development/02_project_status.md)** - Current development status, roadmap, and priorities

## Key Features

### ✅ **AutoGen Multi-Agent System**

- **VoterAgent**: Production-ready MACD+RSI voting with 0.856 Sharpe ratio performance
- **Agent Architecture**: Microsoft AutoGen framework for agent coordination
- **Multi-Agent Trading**: Scanner, Risk, Executor, and Orchestrator agents (in development)
- **Tool Integration**: Market data and trading tools accessible to all agents

### ✅ **Professional Architecture**

- **Agent Communication**: Structured message passing between AutoGen agents
- **Unified Tools**: Single source of truth accessible to all agents
- **Error Handling**: Comprehensive error recovery and logging
- **State Management**: Persistent trade state across restarts and agent coordination

### ✅ **Production Ready**

- **Paper Trading**: Safe testing environment
- **Live Trading**: Production-ready execution
- **Fill Monitoring**: Automatic order fill detection
- **Market Hours**: Smart handling of market open/close

## Quick Navigation

### 🚀 **Getting Started**

1. Read [System Overview](01_overview/01_system_overview.md) to understand what the system does
2. Review [Phases of Operation](01_overview/02_phases_of_operation.md) to see how it works
3. Check [System Context](01_overview/03_system_context.md) for design philosophy

### 🔧 **Developers & Technical**

1. Study [Core Architecture](02_architecture/01_core_architecture.md) for system design
2. Understand [Agent Ensemble](02_architecture/02_agent_ensemble.md) for multi-agent coordination
3. Review [Voting System](02_architecture/03_voting_system.md) for trading logic

### 📊 **Performance & Validation**

1. See [Validation Results](03_reference/01_validation_results.md) for proven performance (0.856 Sharpe)
2. Review [Research Papers](research_papers.md) for academic foundation
3. Check [Troubleshooting](03_reference/04_troubleshooting.md) for common issues

## Current Status

### ✅ **Production Components**

- **VoterAgent**: Production-ready AutoGen agent with validated MACD+RSI voting (0.856 Sharpe)
- **CLI Trade Assistant** (#308): Human-in-loop interactive trading interface ✅ NEW
  - Natural language parsing with OpenAI (gpt-4o-mini + o4-mini)
  - Real MACD+RSI analysis with market data fetching
  - Portfolio % risk management and position sizing
  - Interactive REPL with confirm/auto autonomy modes
  - Usage: `python main.py trade-assist`
- **Position Manager**: Unified position and account tracking accessible to agents
- **Order Manager**: Complete order placement and monitoring via AutoGen tools
- **Trading Cycle**: Comprehensive position monitoring and stop management

### ✅ **Integration Complete**

- **Alpaca Markets**: Full paper and live trading support
- **Market Data**: Real-time and historical data feeds (Alpaca, Polygon, Alpha Vantage)
- **Order Types**: Market, limit, stop, and bracket orders
- **Fill Monitoring**: Automatic state transitions
- **OpenAI API**: Natural language parsing and tool calling ✅ NEW

### 📊 **Validated Performance**

- **Sharpe Ratio**: 0.856 (validated backtesting)
- **Win Rate**: 51.4% (realistic expectations)
- **Max Drawdown**: -10.10% (controlled risk)
- **System Uptime**: 99.9% (robust error handling)

---

## Research Foundation

For academic research and citations informing the system architecture:

- **[Research Papers](research_papers.md)** - Academic foundation with abstract, introduction, and citations
- **[Agent Ensemble](02_architecture/02_agent_ensemble.md)** - Evolution from V0-V4 to current multi-agent system
- **[Voting System](02_architecture/03_voting_system.md)** - Multi-indicator voting architecture
- **[Validation Results](03_reference/01_validation_results.md)** - Experiment #293 proving voting superiority (0.856 Sharpe)

---

*Documentation follows professional standards with clear organization, consistent naming, and comprehensive coverage of all AutoGen agents and system components.*

*Last Updated: November 2025 - Production-Ready AutoGen Multi-Agent Trading System*
