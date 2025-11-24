# AutoTrader Terminology & Acronyms

## AutoGen Agent Architecture

- **VoterAgent** = Production-ready MACD+RSI voting agent (0.856 Sharpe validated)
- **ScannerAgent** = Market scanning and opportunity identification (in development)
- **RiskAgent** = Risk management and position sizing (in development)
- **ExecutorAgent** = Trade execution and order management (minimal implementation)
- **TradingOrchestrator** = Multi-agent coordination and workflow management
- **BaseAgent** = Parent class for all AutoGen trading agents with tool integration

## Legacy Agent Acronyms (Deprecated V0-V4 System)

- **TA** = Technical Agent (analyzes price patterns, volume, technical indicators)
- **SA** = Sentiment Agent (analyzes news sentiment and market psychology)
- **RA** = Risk Agent (evaluates portfolio risk and position sizing)
- **Strategy Agent** = Makes final trading decisions based on inputs from other agents
- **MAS** = Multi-Agent System (the overall system architecture)

## Stock & Market Terms

- **MAG7** = Magnificent Seven stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA)
- **MACD Histogram** = Difference between MACD line and signal line
- **Signal Strength** = Normalized score (0-1) indicating entry quality
- **Market Heat** = Composite score of market conditions (VXX, SPY momentum, sector rotation)

## System Architecture Terms

### AutoGen Framework

- **AutoGen** = Microsoft's multi-agent conversation framework
- **AssistantAgent** = AutoGen's base agent class for conversational agents
- **FunctionTool** = AutoGen wrapper for external functions/APIs
- **BaseAgent** = Custom parent class for all trading agents with tool integration

### Trading Infrastructure

- **Voting Consensus** = MACD+RSI agreement system for signal generation
- **Signal Strength** = Normalized score (0-1) indicating entry quality based on consensus
- **Position Tracker** = System for monitoring open positions and portfolio state
- **Risk Calculator** = Position sizing and risk management calculations
- **Market Data Fetcher** = Unified data sourcing with caching (90% performance improvement)

### Legacy Components (Deprecated)

- **DataObfuscator** = Tool for validating LLM decisions without training data leakage
- **ParallelStrategyTester** = Framework for comparing Buy & Hold vs Mechanical vs LLM strategies
- **V0-V4 Sentiment Framework** = Complex sentiment analysis system (moved to deprecated)

## File Extensions & Formats

### Current Directory Structure

- **`src/autogen_agents/`** = AutoGen-based trading agents (production system)
- **`src/deprecated/v0_v4_agents/`** = Legacy sentiment-based agent system
- **`src/trading_tools/`** = Core trading utilities (indicators, data fetching, risk management)
- **`config_defaults/`** = Default configuration files and parameter management
- **`scripts/experiments/experiment_293_validation/`** = Current validation testing framework

### Cache and Data Formats

- **`.cache/backtests/`** = Directory for backtest results and cached data
- **`.cache/market_data/`** = Cached market data from various APIs (90% performance improvement)
- **`_yy_mm_dd.md`** = Standard naming convention for reports (e.g., `validation_25_07_29.md`)

### Agent Development Status

- **✅ PRODUCTION READY** = VoterAgent (0.856 Sharpe validated)
- **🚧 IN DEVELOPMENT** = Scanner, Risk, Executor, Trading Orchestrator agents
- **❌ DEPRECATED** = V0-V4 sentiment framework (complex, unproven ROI)
