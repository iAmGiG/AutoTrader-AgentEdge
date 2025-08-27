# CLAUDE.md

This file provides essential guidance to Claude when working with this repository.

## Project Overview

RH2MAS (Reflective Hybrid Head Multi-Agent System) is a research framework for studying **gradual LLM introduction** in financial trading decisions through a **5-phase sentiment analysis comparison** (V0-V4). The system demonstrates the progressive value of AI through increasingly sophisticated sentiment approaches while maintaining consistent MACD-based trading strategy.

**For detailed documentation**: See [docs/](docs/) directory structure

## Quick Reference

### Essential Commands ✨

```bash
# Install dependencies
pip install -e .

# Simple continuous backtesting (primary testing interface)
python scripts/runs/backtest.py --status                    # Check all V0-V4 progress
python scripts/runs/backtest.py --all-versions              # Run all versions (full year)
python scripts/runs/backtest.py --all-versions --month 1    # January 2024 testing
python scripts/runs/backtest.py --version V4                # Single version test

# V4 date obfuscation testing
python scripts/validation/obfuscation_test.py

# Analysis and results
python scripts/analysis/generate_results_summary.py --advanced                 # Advanced metrics analysis
```

### Current Development Status

**Status**: Framework ready - Active development and testing

**Infrastructure Complete**:

- ✅ V0-V4 sentiment framework with gradual LLM introduction
- ✅ Multi-asset testing capability (stocks and ETFs)  
- ✅ Sentiment-based position sizing (30%-100% scaling)
- ✅ Cache-optimized agents (90%+ performance improvement - unified implementation)
- ✅ Checkpoint/resume system for long-running tests
- ✅ Smart news sampling with NewsGovernor
- ✅ Advanced metrics capture and analysis system

**Active Issues**: See GitHub Issues for current priorities

## V0-V4 Sentiment Framework

**Research Objective**: Demonstrate gradual LLM introduction value through 5 sentiment approaches:

- **V0**: Fixed Baseline (sentiment = 1.0) - Pure MACD strategy
- **V1**: NLP Analysis (VADER + Google Search news)
- **V2**: Market Fear (VXX/VIX volatility-based sentiment)
- **V3**: Heuristic Combination (V1 + V2 with adaptive weighting)
- **V4**: Intelligent LLM Reasoning (market psychology understanding + News/VXX/SPY-QQQ + date sanitization)

**Key Principle**: Only V4 uses LLM for decision-making; V0-V3 are purely mechanical

**Performance Architecture**: All agents (V1-V4) use cache-first optimization with 3-tier fallback:

1. **Direct Tool Access** (cached data) → 90%+ speed improvement
2. **LLM Tool Calling** (systematic fallback) → Full functionality
3. **Neutral Sentiment** (emergency fallback) → Graceful degradation

## Working with API Keys

API keys stored in `config/config.json` (**NOT IN REPO** - create locally):

- **Polygon.io**: Primary market data source (5 calls/min, 1-year history)
- **Alpha Vantage**: Fallback market data (25 calls/day limit)
- **Google Custom Search**: News analysis (100 calls/day) - Smart sampling reduces usage by 80-90%
- **OpenAI**: LLM processing for agent analysis

## Key File Locations

### Primary Scripts

- `scripts/runs/backtest.py` - Primary testing interface
- `scripts/validation/obfuscation_test.py` - V4 date validation
- `scripts/analysis/generate_results_summary.py` - Results analysis with advanced metrics

### Core Components

- `src/agents/sentiment_v[0-4].py` - V0-V4 sentiment agents
- `src/tools/news_governor.py` - Smart news sampling system
- `src/tools/data_sources/` - Market and news data tools
- `src/utils/date_sanitizer.py` - V4 date sanitization utility

### Cache Structure

- `.cache/news_filtered/` - URL-filtered reliable sources (Bloomberg/CNBC/Reuters/BusinessWire)
- `.cache/market_data/` - Polygon.io historical market data cache
- `reports/` - Backtest results and analysis reports

### Documentation

- `docs/architecture/` - System architecture documentation
- `docs/reference/` - Commands, terminology, and troubleshooting
- `docs/implementation/` - Implementation guides and details

---

*Detailed historical information archived in `.claude_archive/`*
