# RH2MAS Documentation

This directory contains comprehensive documentation for RH2MAS - a validated trading platform with Fibonacci-based regime detection and proven voting strategies.

## Documentation Structure

### 🎯 **Current Focus: Fibonacci Regime Detection** (Issues #297-#301)
- **[fibonacci_regime/](fibonacci_regime/)** - Phase-based Fibonacci regime implementation guide
- **[architecture/voting_system_validated.md](architecture/voting_system_validated.md)** - Validated 2-way voting architecture
- **Phase 1**: Core Fibonacci Module with 34 EMA filtering (Issue #298)
- **Phase 2**: CCI Filter Integration per Borden methodology (Issue #299) 
- **Phase 3**: Symmetry Break Detection for trend changes (Issue #300)
- **Phase 4**: Full modular integration with regime-adaptive sizing (Issue #301)

### ✅ **Validated Systems Documentation**

#### **[voting_strategy/](voting_strategy/)** - Proven Voting System
- **[validation_results.md](voting_strategy/validation_results.md)** - Experiment #293 validation proof
- **[fibonacci_macd_optimization.md](voting_strategy/fibonacci_macd_optimization.md)** - 13/34/8 parameter validation
- **[market_regime_insights.md](voting_strategy/market_regime_insights.md)** - Bull vs volatile market performance
- **Configuration**: MACD (13/34/8) + RSI (14/30/70), 2-way consensus voting

#### **[architecture/](architecture/)** - System Design  
- **[modular_agent_system.md](architecture/modular_agent_system.md)** - Component-based enhancement architecture
- **[cache_system.md](architecture/cache_system.md)** - Market data caching (90% performance boost)
- **[phase_based_development.md](architecture/phase_based_development.md)** - Incremental enhancement methodology

### 📊 **Performance Documentation**
- **[results_analysis/](results_analysis/)** - Key findings and performance metrics
- **Validated Performance**: 0.856 Sharpe, -10.10% max drawdown, 51.4% win rate
- **Market Regime Insight**: Better performance in volatile (-14.6% gap) vs bull (-25.8% gap) markets
- **Fibonacci Parameters**: 13/34/8 MACD optimal across 7 tech stocks

### 🗂️ **Archived Documentation**

#### **[archived/v0_v4_deprecated/](archived/v0_v4_deprecated/)** - Legacy System Documentation
- **V0-V4 Sentiment Framework**: Original research direction (deprecated for complexity)
- **Migration Guide**: How V0-V4 insights informed current voting system
- **Historical Results**: Complete performance analysis of sentiment-based approach

### 📚 **Reference Documentation**

#### **[reference/](reference/)** - Quick Reference
- **[commands.md](reference/commands.md)** - Updated command reference for voting + Fibonacci system
- **[terminology.md](reference/terminology.md)** - Glossary including Fibonacci regime terms
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