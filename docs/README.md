# RH2MAS Documentation

This directory contains comprehensive documentation for RH2MAS - a simplified trading platform focused on proven MACD+RSI voting strategy.

## Documentation Structure

### 🎯 **Current Focus: Simplified Trading System** (September 7, 2025)
- **Reality Check Complete**: Closed 16 complexity trap issues (#272, #278-286, #291, #297-301)
- **Performance Validation**: Simple MACD+RSI voting = 0.856 Sharpe, 51.4% win rate
- **Complex Systems Failed**: Percentile exits = 17.7% win rate, -1.260 Sharpe (TERRIBLE)
- **Fibonacci Abandoned**: All Fibonacci levels (38.2%, 61.8%, 161.8%) proven ineffective
- **Path Forward**: MACD(13/34/8) + RSI voting + fixed percentage exits ONLY

### ✅ **Validated Systems Documentation**

#### **[voting_strategy/](voting_strategy/)** - Simple Proven System (KEEP THIS)
- **[validation_results.md](voting_strategy/validation_results.md)** - Experiment #293 validation proof
- **Configuration**: MACD (13/34/8) + RSI (14/30/70), 2-way consensus voting
- **Performance**: 0.856 Sharpe, 12.62% return, 51.4% win rate, -10.10% max drawdown
- **Exit Strategy**: Fixed percentages (+8% take profit, -5% stop loss) or momentum reversals

#### **[architecture/](architecture/)** - System Design  
- **[modular_agent_system.md](architecture/modular_agent_system.md)** - Component-based enhancement architecture
- **[cache_system.md](architecture/cache_system.md)** - Market data caching (90% performance boost)
- **[phase_based_development.md](architecture/phase_based_development.md)** - Incremental enhancement methodology

### 📊 **Performance Documentation**
- **Simple System Performance**: 0.856 Sharpe, -10.10% max drawdown, 51.4% win rate
- **Reality Check Results**: Complex systems FAILED (17.7% win rate vs 51.4% simple)
- **Parameters**: MACD (13/34/8) + RSI (14/30/70) voting consensus
- **Exit Rules**: Fixed +8%/-5% targets OR momentum reversal signals only

### 🗂️ **Archived Documentation**

#### **[archived/v0_v4_deprecated/](archived/v0_v4_deprecated/)** - Legacy System Documentation
- **V0-V4 Sentiment Framework**: Original research direction (deprecated for complexity)
- **Migration Guide**: How V0-V4 insights informed current voting system
- **Historical Results**: Complete performance analysis of sentiment-based approach

#### **Complexity Traps Archived (September 7, 2025)**
- **Fibonacci Regime Detection**: Issues #297-301 closed (docs removed)
- **Percentile Exit Systems**: Issues #291 archived - performed terribly
- **Multi-Indicator Ensembles**: Issues #278-286 closed - unnecessary complexity
- **Elliott Wave Patterns**: Issue #272 closed - more Fibonacci nonsense
- **Scripts Archived**: `scripts/validation/archived_complexity_traps/`
- **Code Archived**: `src/trading/archived_complexity_traps/`

### 📚 **Reference Documentation**

#### **[reference/](reference/)** - Quick Reference
- **[commands.md](reference/commands.md)** - Simple system commands and testing
- **[terminology.md](reference/terminology.md)** - Simplified trading terminology (NO Fibonacci)
- **[troubleshooting.md](reference/troubleshooting.md)** - Common issues and solutions
- **[configuration.md](reference/configuration.md)** - Validated parameter settings

## Quick Navigation

### 🚀 **Getting Started**
1. **[validation_results.md](voting_strategy/validation_results.md)** - Understand proven voting system
2. **[fibonacci_regime/phase_1_guide.md](fibonacci_regime/phase_1_guide.md)** - Current development focus
3. **[reference/commands.md](reference/commands.md)** - Run experiments and tests

### 📈 **Key Results**
- **Voting Validation**: `docs/voting_strategy/validation_results.md`
- **Fibonacci Parameters**: `docs/voting_strategy/fibonacci_macd_optimization.md`  
- **Market Regime Analysis**: `docs/voting_strategy/market_regime_insights.md`
- **Current Development**: `docs/fibonacci_regime/README.md`

### 🛠️ **Development Guide**
- **Architecture Overview**: `docs/architecture/modular_agent_system.md`
- **Phase Development**: `docs/architecture/phase_based_development.md`
- **Testing Protocols**: `docs/reference/testing_guide.md`

## Current Status

### ✅ **Completed & Validated**
- **Voting Strategy**: MACD + RSI consensus outperforms single indicators
- **Parameter Optimization**: Fibonacci 13/34/8 MACD proven across multiple tickers
- **Market Regime Research**: Identified voting's volatile market advantage
- **Modular Architecture**: Foundation ready for Fibonacci enhancements

### 🔄 **Active Development**  
- **Phase 1**: Core Fibonacci Module (34 EMA filtering)
- **Goal**: Reduce bull market gap from -25.8% to <-15%
- **Approach**: Modular enhancements without disrupting validated foundation

### 📋 **Documentation Maintenance**
- **Active**: All files in main directories reflect current development
- **Archived**: Historical V0-V4 research preserved in `/archived/`
- **Updated**: Command references, terminology, and troubleshooting current

---

*Documentation reflects the strategic shift from sentiment complexity to validated voting + Fibonacci regime enhancement*

*Last Updated: September 5, 2025 - Post-validation, Pre-Fibonacci Phase 1*