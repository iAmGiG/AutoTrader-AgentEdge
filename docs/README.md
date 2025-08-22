# RH2MAS Documentation (V0-V4 Framework)

This directory contains documentation for the V0-V4 sentiment analysis framework - a research study demonstrating the gradual introduction of LLM capabilities in financial trading decisions.

## V0-V4 Framework Overview

The project implements 5 sentiment approaches (V0-V4) applied to a consistent MACD-based trading strategy, measuring the incremental value of each approach through quarterly backtesting on AAPL.

## Documentation Structure

### [architecture/](architecture/) - System Design
- **[V0-V4_ARCHITECTURE.md](architecture/V0-V4_ARCHITECTURE.md)** - Complete framework architecture
- **[project_structure.md](architecture/project_structure.md)** - Repository organization

### [implementation/](implementation/) - Component Details
- **[agents/](implementation/agents/)** - Agent documentation
  - `sentiment_agent.md` - V0-V4 sentiment implementations
  - `strategy_agent.md` - Orchestrator pattern
  - `technical_agent.md` - Market data and MACD
- **[tools/](implementation/tools/)** - Tool documentation
  - `indicator_library.md` - MACD and technical indicators
  - `google_search_historical_news.md` - News data source
  - `news_cache_organization.md` - Caching strategy
  - `newsgovernor_smart_sampling.md` - Intelligent quota management
  - `news_source_reliability_analysis.md` - ✅ **URL pattern implementation & source filtering**
- **[macd_analysis/](implementation/macd_analysis/)** - MACD verification scripts

### [reference/](reference/) - Quick Reference
- **[commands.md](reference/commands.md)** - Command reference and setup
- **[terminology.md](reference/terminology.md)** - Glossary of terms and acronyms
- **[troubleshooting.md](reference/troubleshooting.md)** - Common issues and solutions
- **[news_limitations.md](reference/news_limitations.md)** - News data constraints

## Quick Links

- **V0-V4 Testing**: Quarterly backtesting framework (Issues #181-187)
- **Data Sources**: Polygon.io (market), Google Search (news)
- **Base Strategy**: MACD crossover signals (consistent across V0-V4)