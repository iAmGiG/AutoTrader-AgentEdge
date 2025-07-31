# Project Structure Guide

## Core Directories

### `src/` - Source Code

- `agents/` - Agent implementations (SentimentAgent, QuantitativeAgent, LLMStrategyAgent, etc.)
- `core/` - Core system components (orchestration, memory, decision engine)
- `tools/` - Data sources and tool implementations
  - `data_sources/` - API tools for different providers
    - `market/` - Market data (AlphaVantageMarketTool, YahooFinanceTool, MarketDataTool)
    - `news/` - News sources (AlphaVantageNewsTool, FinnHubTool, UnifiedNewsTool)
    - `government/` - Government data (SECEdgarTool, FREDDataTool)
  - `processors/` - Data processing utilities
    - `data_normalizer.py` - Standardizes data from different sources
    - `sentiment_analyzer.py` - Analyzes text sentiment
    - `indicator_library.py` - Technical indicator calculations
  - `cache/` - Caching system for market data
  - `memory/` - Memory system components
  - `tools.py` - Central tool registry and FunctionTool wrappers
- `utils/` - General-purpose utilities
  - `date_utils.py` - Date handling and timezone utilities
  - `agent_utils.py` - Agent-related helper functions
  - `output_manager.py` - Organized output and report generation
- `validation/` - Validation and testing frameworks
- `test/` - Integration tests

### `scripts/` - Executable Scripts

- `backtesting/` - Core backtesting functionality
  - `backtest_mas.py` - Main MAS backtesting engine
  - `run_backtest_suite.py` - Batch runner
  - `backtest_configs.yaml` - Test configurations
- `strategies/` - Strategy implementations
  - `mechanical/` - Rule-based strategies
  - `llm/` - LLM-based strategies
- `validation/` - Validation and analysis tools
- `utils/` - Utility scripts
- `services/` - Background services

### `reports/` - Documentation and Results

- `validation/` - LLM validation and obfuscation test results
- `analysis/` - Market and strategy analysis reports
- `sessions/` - Work session summaries (organized by year)
- `technical/` - Technical implementation reports

### `tests/` - Unit Tests

- Component-specific tests (all files begin with `test_`)

### `.cache/` - Cached Data

- `backtests/` - Backtest results and progress tracking
- `market_data/` - Cached market data from APIs

### `config/` - Configuration (Not in Repo)

- `config.json` - API keys and settings (gitignored for security)

### `docs/` - Reference Documentation

- `autogen_core_reference/` - AutoGen 0.6.x class interfaces and patterns
- Project-specific documentation files
