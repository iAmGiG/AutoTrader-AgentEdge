# RH2MAS Documentation

This directory contains comprehensive documentation for RH2MAS - a practical trading platform with powerful backtesting capabilities and multi-agent architecture.

## Documentation Structure

### 🗳️ Multi-Indicator Voting System (New Implementation)
- **[research_papers.md](research_papers.md)** - Academic research foundation (90% accuracy with ensembles)
- **[issue_relationship_map.md](issue_relationship_map.md)** - Dependencies, integration points, and development workflow
- **Multi-Indicator Architecture**: MACD + RSI + Bollinger Bands + Volume + V0-V4 Sentiment
- **Phase 1** - Basic voting foundation (Issues #250, #277-280)
- **Phase 2** - Weighted confidence voting (Issues #281-283)
- **Phase 3** - Market regime adaptation (Issues #284-286)
- **Phase 4** - Production readiness (Issues #287-289)

### [architecture/](architecture/) - System Design
- **[agent_transformation_guide.md](architecture/agent_transformation_guide.md)** - **🎯 V0-V4 to Multi-Indicator Evolution (NEW)**
- **[new_voting_system_structure.md](architecture/new_voting_system_structure.md)** - Multi-indicator voting architecture (NEW)
- **[cache_system.md](architecture/cache_system.md)** - ✅ **Cache system architecture (overhauled 2025-08-26)**

### [New System Documentation] (In Development)
- **Multi-Indicator Implementation Guides** - Coming with Issue #250+ development
- **Ensemble Voting Patterns** - Voting architecture documentation  
- **Production Integration Guides** - Order management, risk controls
- **Advanced Analytics** - Ensemble metrics and performance tracking

### [reference/](reference/) - Quick Reference
- **[commands.md](reference/commands.md)** - Command reference and setup
- **[terminology.md](reference/terminology.md)** - Glossary of terms and acronyms
- **[troubleshooting.md](reference/troubleshooting.md)** - Common issues and solutions
- **[news_limitations.md](reference/news_limitations.md)** - News data constraints

### 📚 Deprecated Documentation (Reference Only)
- **[deprecated/README.md](deprecated/README.md)** - Overview of deprecated V0-V4 system  
- **[deprecated/V0-V4_ARCHITECTURE.md](deprecated/V0-V4_ARCHITECTURE.md)** - Complete original system architecture
- **[deprecated/project_structure.md](deprecated/project_structure.md)** - V0-V4 repository organization
- **[deprecated/sentiment_agent_v0_v4.md](deprecated/sentiment_agent_v0_v4.md)** - V0-V4 sentiment implementations
- **[deprecated/advanced_metrics_system.md](deprecated/advanced_metrics_system.md)** - V0-V4 metrics analysis
- **[deprecated/project_rebuild_summary.md](deprecated/project_rebuild_summary.md)** - V0-V4 data infrastructure rebuild
- **[deprecated/backtesting_v0_v4/](deprecated/backtesting_v0_v4/)** - V0-V4 backtesting enhancements  
- **[deprecated/implementation_v0_v4/](deprecated/implementation_v0_v4/)** - Complete V0-V4 implementation docs
- **Note**: These files are preserved for reference but replaced by multi-indicator voting system

## Quick Start

### Current Capabilities (Deprecated V0-V4 System)
- **V0-V4 Testing**: `python scripts/runs/backtest.py --all-versions`
- **Advanced Metrics**: `python scripts/analysis/generate_results_summary.py --advanced`
- **Single Strategy**: `python scripts/runs/backtest.py --version V4 --symbol AAPL`

### New Multi-Indicator Voting System (In Development)
- **Basic Ensemble**: Start with Issue #250 (Core Voting Architecture)
- **RSI Integration**: Issue #277 (15% win rate improvement target)
- **Weighted Voting**: Issue #281 (Sharpe ratio 0.71 → 1.43 target)
- **Production Ready**: Issues #287-289 (Order management, risk controls)

### Enhanced Backtesting (Future Development)
- **Leverage ETFs**: Issue #265 - 2x/3x ETF comparison framework
- **Trading Filters**: Issue #264 - Volume, spread, event-based filters  
- **Execution Costs**: Issue #267 - Slippage, commissions, market impact
- **Optimization**: Issue #269 - Grid search, genetic algorithms

## Development Focus

The project has pivoted from academic V0-V4 research to building a **production-ready multi-indicator ensemble trading system** targeting 90% accuracy. Current priorities:

1. **Phase 1A**: Multi-indicator voting system (Issues #250, #277-289) - **PRIORITY 1**
2. **Phase 1B**: Enhanced backtesting improvements (#264, #267, #265) - Parallel development  
3. **Phase 2**: Advanced analytics and optimization (#268, #269)
4. **Phase 3**: Production trading capabilities (#258-263)

**Research Target**: Transform single MACD (~60% accuracy) to ensemble voting system (90% accuracy based on academic studies)