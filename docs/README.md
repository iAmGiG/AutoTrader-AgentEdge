# RH2MAS Documentation

This directory contains comprehensive documentation for RH2MAS - a practical trading platform with powerful backtesting capabilities and multi-agent architecture.

## Documentation Structure

### 🎯 [backtesting/](backtesting/) - Enhanced Backtesting Laboratory
- **[README.md](backtesting/README.md)** - Backtesting framework overview
- **[practical_filters.md](backtesting/practical_filters.md)** - Volume, spread, event-based filters
- **[execution_reality.md](backtesting/execution_reality.md)** - Slippage, commissions, market impact
- **[leverage_testing.md](backtesting/leverage_testing.md)** - 2x/3x ETF comparison framework *(coming soon)*
- **[monte_carlo_framework.md](backtesting/monte_carlo_framework.md)** - Confidence intervals and robustness *(coming soon)*
- **[parameter_optimization.md](backtesting/parameter_optimization.md)** - Grid search and genetic algorithms *(coming soon)*

### [architecture/](architecture/) - System Design
- **[V0-V4_ARCHITECTURE.md](architecture/V0-V4_ARCHITECTURE.md)** - Complete framework architecture
- **[project_structure.md](architecture/project_structure.md)** - Repository organization
- **[cache_system.md](architecture/cache_system.md)** - ✅ **Cache system architecture (overhauled 2025-08-26)**

### [analysis/](analysis/) - Advanced Metrics System
- **[advanced_metrics_system.md](analysis/advanced_metrics_system.md)** - ✅ **Complete advanced metrics implementation (2025-08-26)**

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

### Project Reports
- **[project_rebuild_summary.md](project_rebuild_summary.md)** - ✅ **Complete MAG7 + benchmarks data infrastructure rebuild (2025-08-26)**

## Quick Start

### Current Capabilities
- **V0-V4 Testing**: `python scripts/runs/backtest.py --all-versions`
- **Advanced Metrics**: `python scripts/analysis/generate_results_summary.py --advanced`
- **Single Strategy**: `python scripts/runs/backtest.py --version V4 --symbol AAPL`

### Coming Soon (Enhanced Backtesting)
- **Leverage ETFs**: `python scripts/runs/backtest.py --leverage-comparison QQQ`
- **Trading Filters**: `python scripts/runs/backtest.py --filters enabled`
- **Execution Costs**: `python scripts/runs/backtest.py --slippage realistic`
- **Optimization**: `python scripts/runs/backtest.py --optimize-params`

## Development Focus

The project has pivoted from academic research to building a **powerful personal backtesting laboratory** without constraints. Current priorities:

1. **Phase 1**: Practical trading filters and execution reality (#264, #267)
2. **Phase 2**: Leverage ETF testing and technical variations (#265, #266)
3. **Phase 3**: Monte Carlo and parameter optimization (#268, #269)
4. **Phase 4**: Production trading capabilities (#258-263)