# CLAUDE.md

This file provides essential guidance to Claude when working with this repository.

## Project Overview

RH2MAS (Reflective Hybrid Head Multi-Agent System) is a **practical trading platform** that combines multi-agent architecture with sophisticated risk management for real-world trading applications. Originally developed as a research framework for gradual LLM introduction (V0-V4 sentiment analysis), it has evolved into a production-ready backtesting and trading system.

**For detailed documentation**: See [docs/](docs/) directory structure

## Quick Reference

### Essential Commands ✨

```bash
# Install dependencies
pip install -e .

# Multi-Indicator Voting System (NEW)
python examples/basic_voting_demo.py                        # Demo Issue #250 implementation
python scripts/lint_check.py src/voting/                   # Enhanced code quality checks
python scripts/lint_check.py                                # Full project linting

# Enhanced Backtesting (Coming Soon - Issues #264-267)
python scripts/runs/backtest.py --leverage-etfs             # Test 2x/3x ETFs vs base assets
python scripts/runs/backtest.py --filters enabled           # Apply practical trading filters
python scripts/runs/backtest.py --slippage realistic        # Include execution costs
python scripts/runs/backtest.py --optimize-params           # Parameter optimization
python scripts/runs/backtest.py --tournament                # Run strategy tournament

# Analysis Tools
python scripts/analysis/generate_results_summary.py --advanced      # Advanced metrics
python scripts/analysis/monte_carlo.py --confidence 95              # Monte Carlo simulation
python scripts/analysis/walk_forward.py --period quarterly          # Walk-forward analysis
python scripts/analysis/execution_impact.py                        # Transaction cost analysis

# Development Workflow
python -m ruff check --fix src/voting/                     # Auto-fix linting issues
python -m ruff check examples/                             # Validate example code
```

### Current Development Status

**Status**: AutoGen Architecture + Alpaca Market Data Integration Complete (September 9, 2025)

**Core System Validated + AutoGen Restructure Complete**:

- **Baseline**: MACD(13/34/8) + RSI Voting = 0.856 Sharpe ratio ✅ (Issue #293 validated)
- **AutoGen Framework**: ✅ Proper autogen-agentchat implementation with BaseAgent inheritance
- **VoterAgent**: ✅ MACD+RSI voting agent with validated 0.856 Sharpe logic
- **Alpaca Market Data**: ✅ Production-ready SDK integration with intelligent caching (Issue #312)
- **Focus**: Simple voting entries + fixed percentage exits ONLY

**AutoGen Implementation Status (September 9, 2025)**:

**✅ Completed and Validated**:
- Issue #307: AutoGen restructure complete with proper base_agent.py
- Issue #309: Testing framework and validation approach corrected
- Issue #293/294: VoterAgent validation complete - MACD+RSI voting working
- **Issue #312**: ✅ **Alpaca Market Data Integration COMPLETE**
  - Official `alpaca-py` SDK implementation (production-ready)
  - Real-time bars/quotes/trades/snapshots retrieval
  - Intelligent caching reduces API calls by >90%
  - Data normalization across Alpaca, Polygon, Alpha Vantage
  - AutoGen tool wrappers ready for all agents
  - Paper account compatibility with IEX feed
  - All tests passing (3/3) - Ready for agent integration
- **VoterAgent**: ✅ Fully implemented and tested
  - MACD(13/34/8) + RSI(14/30/70) voting logic validated
  - Generated real trading signal: SELL (65% confidence)
  - Configuration system integration complete
  - Parameter variations working (A/B testing capable)
  - AutoGen BaseAgent inheritance functional
  - Ready for production integration
- Configuration system: Issue #303 parameter management
- Pure functions: trading_tools/ extracted and organized

**🔄 Next Phase: Complete Remaining Agents (Issue #310)**:
**Foundation Ready**: Issue #312 (Alpaca Market Data) provides production-ready data layer
- Scanner Agent: Multi-ticker scanning with MACD+RSI signals (now has data source)
- Risk Agent: Position sizing and portfolio risk management (can access account data)
- Executor Agent: Paper trading execution and position tracking (ready for order integration)
- Human Interface: CLI and decision formatting components

**Unblocked Issues**: #313 (Order Management), #314 (Account Management), #315 (Paper Trading), #317 (Data Format)

**Current Priority: Core System Validation (September 8, 2025)**:

**Simple System Architecture**:

- ✅ **#293 Validated**: MACD(13/34/8) + RSI voting beats single indicator (0.856 vs 0.841 Sharpe)
- 🎯 **Entry Detection**: Use proven MACD+RSI voting for entry signals only
- 🎯 **Simple Exits**: Fixed percentage targets (+8%/-5%) OR momentum reversal signals
- 🎯 **NO Complexity**: No Fibonacci, no percentiles, no ensembles, no adaptive weights
- 🎯 **Test Reality**: Validate on 2024-2025 data with simple rules

**Simplification Results & Validation (September 7, 2025)**:

- ✅ **Simple System Works**: MACD+RSI voting = 51.4% win rate, 0.856 Sharpe  
- ✅ **Balanced Exits Optimal**: 8% TP / 5% SL = 27.48% annual return, 1.288 Sharpe
- ❌ **Conservative Exits Failed**: 6% TP / 8% SL has negative EV at realistic win rates
- ❌ **Complex Systems Failed**: Percentile exits = 17.7% win rate, -1.260 Sharpe
- 🎯 **Issue #303 Created**: Configuration system for parameter management

**Future Enhancements (Only If Simple System Fails)**:

- **Different Exit Methods**: Trailing stops, momentum reversals
- **Parameter Tuning**: Different MACD/RSI settings
- **NEVER ADD**: Fibonacci levels, percentile calculations, multi-indicator ensembles

**Development Documentation**:

- See [TODO.md](TODO.md) for detailed phase-by-phase development roadmap and milestones
- See [docs/deprecated/](docs/deprecated/) for complete V0-V4 reference documentation

## Backtesting-First Development Approach

**Philosophy**: Build a powerful personal backtesting laboratory without academic constraints. Test what actually works in real trading, not what's "novel" for papers.

### Key Enhancements in Progress

**Practical Reality Checks**:

- Volume, spread, and gap filters for realistic conditions
- FOMC, earnings, and options expiry event awareness
- Slippage and commission modeling (real execution costs)
- Market impact for different position sizes

**Strategy Expansion** (Future - Only if simple system proves insufficient):

- Leverage ETF testing (QQQ/QLD/TQQQ, SPY/SSO/UPRO)
- Technical indicator variations (MACD parameters, RSI, Bollinger)
- Configuration-based parameter optimization (Issue #303)
- Strategy tournament system for automatic winner identification
- **NO Fibonacci levels** - proven ineffective

**Advanced Analytics**:

- Monte Carlo simulations for confidence intervals
- Walk-forward analysis for robustness testing
- Parameter optimization (grid search, genetic algorithms)
- Professional risk metrics (VaR, Sharpe, Sortino, Calmar)

### Implementation Priority

1. **Immediate (Phase 1)**: Filters + Execution Reality (#264, #267)
2. **Near-term (Phase 2)**: Leverage ETFs + Technical Variations (#265, #266)
3. **Advanced (Phase 3)**: Monte Carlo + Optimization (#268, #269)
4. **Future (Phase 4)**: Production Trading (#258-263)

## Working with API Keys

API keys stored in `config/config.json` (**NOT IN REPO** - create locally):

**Trading APIs**:

- **Alpaca Markets**: ✅ **PRODUCTION-READY** - Paper and live trading with market data (Issue #312 complete)
  - Official `alpaca-py` SDK integration with intelligent caching
  - Real-time bars/quotes/trades/snapshots via IEX feed
  - Paper account compatible, >90% API call reduction
  - AutoGen tool wrappers ready for all agents
- **Polygon.io**: Real-time and historical market data (5 calls/min, 1-year history)
- **Alpha Vantage**: Fallback market data (25 calls/day limit)

**Analysis APIs**:

- **Google Custom Search**: News analysis (100 calls/day) - Smart sampling reduces usage by 80-90%
- **OpenAI**: LLM processing for V4 agent and analysis

## Key File Locations

### Primary Scripts

- `scripts/runs/backtest.py` - Primary testing interface
- `scripts/validation/obfuscation_test.py` - V4 date validation
- `scripts/analysis/generate_results_summary.py` - Results analysis with advanced metrics

### Core Components

- `src/agents/sentiment_v[0-4].py` - V0-V4 sentiment agents
- `src/agents/autogen/voter_agent.py` - MACD+RSI voting agent (Issue #293/294 validated)
- `src/data_sources/sources/market/alpaca_market_data.py` - **NEW**: Production Alpaca SDK integration
- `src/tools/news_governor.py` - Smart news sampling system
- `src/tools/data_sources/` - Market and news data tools
- `src/utils/date_sanitizer.py` - V4 date sanitization utility

### Cache Structure

- `.cache/news_filtered/` - URL-filtered reliable sources (Bloomberg/CNBC/Reuters/BusinessWire)
- `.cache/market_data/` - Multi-provider historical market data cache (Polygon.io + **Alpaca**)
- `reports/` - Backtest results and analysis reports

### Testing

- `tests/test_alpaca_basic.py` - **NEW**: Essential Alpaca SDK functionality tests (3/3 passing)
- `tests/test_alpaca_connection.py` - Alpaca API authentication verification

### Documentation

- `docs/architecture/` - System architecture documentation
- `docs/reference/` - Commands, terminology, and troubleshooting
- `docs/implementation/` - Implementation guides and details
- `docs/alpaca_market_data_integration.md` - **NEW**: Comprehensive Alpaca SDK integration guide

---

*Detailed historical information archived in `.claude_archive/`*
