# Project Structure Guide (V0-V4 Framework)

## Core Directories

### `src/` - Source Code

- **`agents/`** - Agent implementations for V0-V4 framework
  - `base_agent.py` - Base class for all agents
  - `sentiment_agent.py` - V0-V4 sentiment implementations
  - `tech_agent.py` - Technical analysis agent (MACD)
  - `strategy_agent.py` - Orchestrator combining tech + sentiment

- **`tools/`** - Data sources and processing
  - **`data_sources/`** - API integrations
    - `market/` - Market data tools
      - `polygon_market.py` - Primary market data (5 calls/min)
      - `alpha_vantage_market.py` - Fallback data (25 calls/day)
    - `news/` - News sources
      - `google_search_simple.py` - Main news interface
      - `google_search_api.py` - Google Custom Search implementation
  - **`processors/`** - Data processing utilities
    - `data_normalizer.py` - Standardizes data formats
    - `sentiment_analyzer.py` - VADER sentiment analysis
    - `indicator_library.py` - MACD and technical indicators
  - **`cache/`** - Caching system
    - `market_data_cache.py` - Market data caching
    - `news_cache.py` - News article caching
  - `tools.py` - Tool registry for AutoGen 0.7.x

- **`utils/`** - Utilities
  - `date_utils.py` - Date handling and timezone utilities
  - `agent_utils.py` - Agent helper functions

- **`validation/`** - V4 validation
  - `obfuscation_validator.py` - Date obfuscation for V4 testing

### `scripts/` - Executable Scripts

- `obfuscation_test.py` - V4 date obfuscation testing
- Future: `backtest_v0_v4.py` - Quarterly backtesting runner

### `reports/` - Analysis Results

- `README.md` - V0-V4 report organization
- `TEMPLATE.md` - Report template
- Future: Quarterly V0-V4 comparison reports

### `tests/` - Test Suite

- **`unit/`** - Unit tests for V0-V4 components
  - `agents/` - Agent tests
  - `tools/` - Tool and cache tests
  - `utils/` - Utility tests
- **`integration/`** - Integration tests
  - Polygon.io integration tests
  - Google Search integration tests
- **`tools/`** - Tool-specific tests
  - `data_quality/` - MACD verification tests

### `config/` - Configuration

- `config.json` - API keys (not in repo)
- `pyproject.toml` - Project configuration
- `requirements.txt` - Python dependencies (AutoGen 0.7.x)

### `docs/` - Documentation

- `V0-V4_ARCHITECTURE.md` - Framework architecture
- `implementation/` - Component documentation
- `commands.md` - Setup and commands
- `terminology.md` - Glossary
- `troubleshooting.md` - Common issues

### `.cache/` - Data Cache (not in repo)

- `market_data/` - Cached market data files
- `news/` - Cached news articles
- `backtests/` - Historical backtest results

## Deprecated Code

All deprecated code from the original multi-agent system has been moved to the untracked `deprecated/` folder, preserving it for reference while keeping the main codebase clean and focused on V0-V4.