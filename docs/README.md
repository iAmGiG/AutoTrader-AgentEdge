# OptionsCommander Documentation

Documentation for OptionsCommander (formerly RH2MAS; GitHub repository `iAmGiG/AutoTrader-AgentEdge`), a Microsoft AutoGen-based trading platform with a MACD+RSI voting strategy and a multi-agent architecture.

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

- **[01. Validation Results](03_reference/01_validation_results.md)** - Experiment #293 results (in-sample, superseded by the [live-rules baseline](08_research/03_strategy_research/live_rules_baseline.md))
- **[02. Terminology](03_reference/02_terminology.md)** - Glossary of terms and concepts
- **[03. Commands](03_reference/03_commands.md)** - CLI commands and scripts reference
- **[04. Troubleshooting](03_reference/04_troubleshooting.md)** - Common issues and solutions
- **[05. Known Issues](03_reference/05_known_issues.md)** - Current known limitations and workarounds
- **[06. Naming Conventions](03_reference/06_naming_conventions.md)** - Code and file naming standards
- **[07. News Limitations](03_reference/07_news_limitations.md)** - API constraints and considerations

### 📂 **04 - Development** (For Contributors)

- **[01. Codebase Structure](04_development/01_codebase_structure.md)** - File organization and component layout
- **[02. Project Status](04_development/02_project_status.md)** - Current development status, roadmap, and priorities
- **[All development guides](04_development/README.md)**

### 🧭 **05 - Decisions**

- **[Architecture Decision Records](05_decisions/README.md)** - Code organization, error handling, caching, agent patterns

### 🧰 **06 - Features** (User Manual)

- **[Feature Documentation](06_features/README.md)** - Position alerts, daily scheduler, scheduler CLI, order display

### 🧪 **07 - Testing**

- **[Testing Documentation](07_testing/README.md)** - Test layout, test safety, forward testing protocol

### 🔬 **08 - Research**

- **[Research Documentation](08_research/README.md)** - GEX and strategy research, with STOP/DONE/CONTINUE status

### 🔭 **09 - Future**

- **[Future Reference Library](09_future/README.md)** - Ideas and papers for later phases

## Key Features

### ✅ **AutoGen Multi-Agent System**

- **VoterAgent**: MACD+RSI voting, the live CLI's signal (no backtested edge over buy-and-hold; see the [live-rules baseline](08_research/03_strategy_research/live_rules_baseline.md))
- **Agent Architecture**: Microsoft AutoGen framework for agent coordination
- **Multi-Agent Trading**: Scanner, Risk, Executor, and Orchestrator agents (in development)
- **Tool Integration**: Market data and trading tools accessible to all agents

### ✅ **Professional Architecture**

- **Agent Communication**: Structured message passing between AutoGen agents
- **Unified Tools**: Single source of truth accessible to all agents
- **Error Handling**: Comprehensive error recovery and logging
- **State Management**: Persistent trade state across restarts and agent coordination

### ✅ **Trading Infrastructure**

- **Paper Trading**: Safe testing environment (the scheduler runs on a paper account)
- **Live Trading**: Alpaca live accounts are supported
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

1. See the [live-rules baseline](08_research/03_strategy_research/live_rules_baseline.md) for backtested performance (experiment 293's 0.856 Sharpe is superseded)
2. Review the [research summary](08_research/README.md) for what was tested and stopped, and the archived [research foundation](archived/presentations/research_foundation.md) for the academic background
3. Check [Troubleshooting](03_reference/04_troubleshooting.md) for common issues

## Current Status

### ✅ **Components in Use**

- **VoterAgent**: AutoGen agent with MACD+RSI voting
- **CLI Trade Assistant** (#308): Human-in-loop interactive trading interface ✅ NEW
  - Natural language parsing with OpenAI (gpt-4o-mini + o4-mini)
  - Real MACD+RSI analysis with market data fetching
  - Portfolio % risk management and position sizing
  - Interactive REPL with confirm/auto autonomy modes
  - Usage: `python main.py`
- **Position Manager**: Unified position and account tracking accessible to agents
- **Order Manager**: Complete order placement and monitoring via AutoGen tools
- **Trading Cycle**: Comprehensive position monitoring and stop management
- **Daily Scheduler**: Morning and evening routines run from cron ([quick start](06_features/02_gtc_scheduler_quickstart.md))

### ✅ **Integration Complete**

- **Alpaca Markets**: Full paper and live trading support
- **Market Data**: Real-time and historical data feeds (Alpaca, Alpha Vantage; Polygon removed in Oct 2026, #607)
- **Order Types**: Market, limit, stop, and bracket orders
- **Fill Monitoring**: Automatic state transitions
- **OpenAI API**: Natural language parsing and tool calling ✅ NEW

### 📊 **Backtested Performance (#574 stage A)**

- **Sharpe Ratio**: 0.69 at 5 bps a side, 2009 to 2026-10-09, live rules and timing ([live-rules baseline](08_research/03_strategy_research/live_rules_baseline.md))
- **Alpha vs buy-and-hold of the same symbols**: +0.11% a year (t = 0.19), so no edge
- **Win Rate**: 44.2%; **Max Drawdown**: -6.9% (positions average about 11% of equity)

---

## Research Foundation

For academic research and citations informing the system architecture:

- **[Research Foundation](archived/presentations/research_foundation.md)** (archived) - Academic foundation with abstract, introduction, and citations
- **[Research Documentation](08_research/README.md)** - Research status, methods and results
- **[Agent Ensemble](02_architecture/02_agent_ensemble.md)** - Evolution from V0-V4 to current multi-agent system
- **[Voting System](02_architecture/03_voting_system.md)** - Multi-indicator voting architecture
- **[Validation Results](03_reference/01_validation_results.md)** - Experiment #293 (in-sample, superseded by the [live-rules baseline](08_research/03_strategy_research/live_rules_baseline.md))

---

*Documentation follows professional standards with clear organization, consistent naming, and comprehensive coverage of all AutoGen agents and system components.*

Last updated: October 2026 (performance figures from #574; scheduler, naming and links corrected).
