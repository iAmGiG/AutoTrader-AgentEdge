# CLAUDE.md

This file provides essential guidance to Claude when working with this repository.

## Project Overview

RH2MAS (Reflective Hybrid Head Multi-Agent System) is a research framework for studying **gradual LLM introduction** in financial trading decisions through a **5-phase sentiment analysis comparison** (V0-V4). The system demonstrates the progressive value of AI through increasingly sophisticated sentiment approaches while maintaining consistent MACD-based trading strategy.

**For detailed terminology and acronyms**: See [docs/reference/terminology.md](docs/reference/terminology.md)  
**For project structure details**: See [docs/architecture/project_structure.md](docs/architecture/project_structure.md)  
**For commands and setup**: See [docs/reference/commands.md](docs/reference/commands.md)  
**For troubleshooting**: See [docs/reference/troubleshooting.md](docs/reference/troubleshooting.md)

## Quick Reference

### Essential Commands ✨

```bash
# Install dependencies
pip install -e .

# Simple continuous backtesting (recommended)
python scripts/runs/simple_continuous_backtest.py --all-versions
python scripts/runs/simple_continuous_backtest.py --status

# V4 date obfuscation testing
python scripts/obfuscation_test.py
```

### Current Development Status (2025-08-20)

**Status**: 🎯 V1 RE-RUN READY WITH CLEAN MONTHLY CACHE

**Completed**:
- ✅ **V0**: +9.00% return, 24 trades (pure MACD baseline)
- ✅ **V2**: +2.33% return, 16 trades (VXX volatility market fear)
- ✅ **Monthly News Cache**: 49 clean files, 81.5% deduplication, 260 unique articles
- ✅ **Architecture**: 4 core agents with clean tool separation
- ✅ **Infrastructure**: Polygon.io + Alpha Vantage + Google Search + VXX tools ready

**Next Priorities**:
- 🔄 **V1 Re-run**: Clean monthly cache with smart sampling
- ⏳ **V3**: Heuristic combination (V1 + V2) after V1 completion
- ⏳ **V4**: LLM intelligent reasoning after V0-V3 validation

## Key Architecture Patterns

### 1. Agent Pattern

- Agents inherit from `BaseAgent` (`src/agents/base_agent.py`)
- Each agent has specific data sources and processing capabilities  
- Agents expose a `generate_reply` method as their primary interface

### 2. Tools Pattern (Clean Architecture)

- **V0 Sentiment**: No tools (fixed sentiment = 1.0)
- **V1 Sentiment**: Google Search API only (news-based VADER analysis) + smart sampling
- **V2 Sentiment**: VXX volatility tool only (market fear)
- **V3 Sentiment**: Google Search + VXX tools (heuristic combination) + smart sampling
- **Tech Agent**: Polygon.io primary (5/min) + Alpha Vantage fallback (25/day)
- **Strategy Agent**: No direct tools (pure aggregation pattern)
- **Tool Access Control**: SENTIMENT_TOOLS vs TECH_TOOLS separation enforced
- **Dynamic Symbols**: No hardcoded defaults, context-driven

### 3. V0-V4 Sentiment Analysis Framework

**Research Objective**: Demonstrate gradual LLM introduction value through 5 sentiment approaches:

- **V0**: Fixed Baseline (sentiment = 1.0) - Pure MACD strategy
- **V1**: NLP Analysis (VADER + Google Search news)
- **V2**: Market Fear (VXX/VIX volatility-based sentiment)
- **V3**: Heuristic Combination (V1 + V2 with adaptive weighting)
- **V4**: Intelligent LLM Reasoning (market psychology understanding + News/VXX/SPY-QQQ + smart sampling)

**Key Principle**: Only V4 uses LLM for decision-making; V0-V3 are purely mechanical

## Working with API Keys

API keys stored in `config/config.json` (**NOT IN REPO** - create locally):

- **Polygon.io**: Primary market data source (5 calls/min, 1-year history)
- **Alpha Vantage**: Fallback market data (25 calls/day limit)
- **Google Custom Search**: News analysis (100 calls/day) ✅ **QUOTA OPTIMIZED** - Smart sampling reduces usage by 80-90%
- **OpenAI**: LLM processing for agent analysis

## Critical Implementation Notes

### ✅ Smart News Sampling (NewsGovernor)

**NewsGovernor Implementation**: Intelligent quota management with 80-90% reduction:
- **Weekly sampling strategy**: 3 API calls vs 22 traditional (86.4% cache hit rate)
- **Configurable cache windows**: 1-2 days (conservative) to 2 weeks (aggressive)
- **Cross-agent benefits**: V1, V3, and V4 all use smart sampling automatically
- **Sustainable testing**: Multiple quarterly tests within daily 100-call quota
- **Flexible configuration**: Balanced, conservative, aggressive, and strict modes

### AutoGen 0.7.x Tool Calling

- Tools implemented using `FunctionTool` from `autogen_core.tools`
- Type annotations and docstrings crucial for schema generation
- Handle both sync and async functions with proper cancellation tokens
- Convert DataFrames: `df.to_dict(orient='records')` then `json.dumps()`

### Data Validation & Integrity

- **ObfuscationValidator**: Tests LLM decisions with/without obfuscated data
- **Polygon.io Cache**: Historical market data with rate limiting protection
- **News Source**: Google Custom Search API (premium sources: WSJ, Bloomberg, Barrons)
- **Monthly News Cache**: ✅ 49 clean monthly files, 81.5% deduplication rate, 260 unique articles
- **Date Filtering**: Cache prevents future spill - returns only articles up to requested date
- **Title-Only Analysis**: Prevents date smuggling, mimics realistic trader headline scanning

### V4 LLM Context Recognition (Pragmatic Limitation)

**Known Limitation**: V4 can potentially recognize companies from headlines (e.g., "Apple", "iPhone", "Tim Cook")

**Why This Is Actually Defensible**:
- **Realistic Scenario**: Real traders know what they're trading - company recognition is natural
- **Stateless API Calls**: Each GPT call is independent - recognition is probabilistic, not deterministic  
- **Information Bottleneck**: Title-only analysis limits how much context the LLM can exploit
- **Noisy Real Data**: Google Search returns mosaic of tangentially-related results, adding realistic variability
- **Professional Parallel**: Traders naturally see company names but lack the emotional biases humans have

**Enhancement Proposed** (Issue #208): Hierarchical adaptive news system with SPY/QQQ market context for even more realistic professional trader information consumption patterns.

### V0-V4 Testing Framework

**Quarterly Testing Strategy**:
- **Test Periods**: AAPL 2024 Q1-Q4, 2025 Q1 (5 quarters)
- **Base Strategy**: Consistent MACD crossover signals across all versions
- **Variable Factor**: Sentiment approach (V0 → V1 → V2 → V3 → V4)
- **Comparison Metrics**: Returns, Sharpe ratio, max drawdown, trade frequency

**Implementation**:
- **Development**: Create 5 sentiment agent classes (Issues #181-185)
- **Testing**: Quarterly comparison framework (Issue #187)
- **Analysis**: Statistical significance testing between versions

## Code Style Guidelines

- **Imports**: Standard library → third-party → local modules
- **Type hints**: Always use typing annotations
- **Naming**: CamelCase for classes, snake_case for methods/functions  
- **Docstrings**: Triple-quotes with parameter documentation
- **Error handling**: Specific exception types with try/except
- **No Claude signatures**: Academic project requires proper authorship

## File Locations Reference

### Essential Files

- `scripts/runs/simple_continuous_backtest.py` - Primary testing interface
- `scripts/obfuscation_test.py` - V4 date validation
- `src/tools/news_governor.py` - Smart news sampling system
- `src/tools/data_sources/news/google_search_api.py` - News with monthly cache
- `src/tools/data_sources/market/vxx_volatility_tool.py` - VXX market fear tool
- `src/agents/sentiment_v1.py` - V1 VADER + Google Search agent
- `src/agents/sentiment_v4.py` - V4 LLM reasoning agent

### Cache Structure

- `.cache/news_monthly/` - 49 monthly files organized by ticker/month
- `.cache/market_data/` - Polygon.io historical market data cache
- `.cache/backtests/runs/` - Backtest results storage

### Documentation

- `docs/architecture/V0-V4_ARCHITECTURE.md` - Framework architecture
- `docs/implementation/tools/newsgovernor_smart_sampling.md` - Smart sampling guide
- `docs/reference/commands.md` - Complete command reference

---

*Historical development details archived in `.claude_archive/`*