# RH2MAS Development TODO

**NOW TRACKED IN REPO** - Shared across environments for consistent development

## 🎯 SINGLE FOCUS: One Working Voting Strategy

**Goal**: Prove the voting concept with ONE strategy that works on 2024 data.

### Success Criteria
- ✅ **Positive returns** over 2024 (+12.6% achieved)
- ❌ **Better Sharpe ratio** than buy-and-hold (12.6% vs 34.9% buy-hold)
- ✅ **At least 10 trades** executed (140 trades executed)
- ✅ **Documented configuration** that worked
- ✅ **AutoGen framework integration** complete

**RESULT**: Voting strategy operational but needs tuning to beat buy-and-hold.

---

## Current Sprint: Minimal Voting Implementation

### 🚀 Implementation Tasks

#### 1. Create Minimal Voting Strategy ✅ COMPLETE
- ✅ Use existing `src/strategies/basic_voting_strategy.py` as foundation
- ✅ Integrate with `TechAgent` (MACD) as single voter
- ✅ Add simple RSI as second voter (basic implementation, uses indicator_library.rsi())
- ✅ 2-indicator voting: MACD + RSI

#### 2. Create Voting Orchestrator ✅ COMPLETE
- ✅ Simple coordinator that collects 2 signals (`SimpleVotingOrchestrator`)
- ✅ Basic decision logic: both agree = strong signal, one agrees = weak signal
- ✅ Position sizing: strong signal = full position, weak = half position

#### 3. AutoGen Framework Integration ✅ COMPLETE
- ✅ Import dependencies resolved (conditional imports for missing nltk)
- ✅ Cache system compatibility (backward compatible with existing data)
- ✅ Full AutoGen tooling operational for scalability

#### 4. Validation ✅ COMPLETE
- ✅ Compare against buy-and-hold AAPL 2024 (12.6% vs 34.9%)
- ✅ Ensure at least 10 trades executed (140 trades)
- ✅ Measure actual performance vs baseline (documented)

---

## Technical Architecture (Minimal)

### What We Built ✅
- **SimpleVotingOrchestrator**: MACD + RSI voting coordinator
- **SimpleRSI**: 14-period RSI using efficient indicator_library.rsi()
- **AutoGen Integration**: Full framework compatibility achieved
- **UnifiedCache**: Backward compatible with existing market data

### What We're NOT Building
- No complex multi-indicator systems
- No sentiment agents (V0-V4 deprecated)
- No market regime detection
- No weighted confidence scoring
- No LLM orchestration

### File Structure ✅ REORGANIZED
```
src/
├── core/                               # 🆕 Core trading components
│   ├── agents/
│   │   ├── simple_voting_orchestrator.py # ✅ MACD + RSI voting coordinator
│   │   ├── tech_agent.py                 # ✅ MACD signals  
│   │   └── base_agent.py                 # ✅ Common agent interface
│   ├── indicators/                       # 🆕 All indicators consolidated
│   │   ├── indicator_library.py          # ✅ Efficient calculations (MACD, RSI, etc.)
│   │   ├── simple_rsi.py                 # ✅ RSI with IndicatorSignal interface
│   │   └── base_indicator.py             # ✅ IndicatorSignal interface
│   └── strategies/
│       └── base_voting_strategy.py       # ✅ Voting strategy framework
├── data/                               # 🆕 Flattened data access layer
│   ├── cache/                            # ✅ Cache implementations
│   ├── sources/market/                   # ✅ Market data sources (flattened)
│   ├── sources/news/                     # ✅ News data sources
│   └── processors/                       # ✅ Data processing utilities
└── analysis/
    └── optimization/                     # ✅ MACD parameter optimization
```

**✅ Benefits**: Eliminated duplication, clearer separation of concerns, cross-platform compatibility

---

## Development Environment

**Requirements**:
- Python 3.10+ with conda environment  
- Existing RH2MAS dependencies
- 2024 AAPL data (should exist in cache)

**Testing Commands**:
```bash
# Isolated test (bypasses complex dependencies)
python tests/test_voting_isolated.py

# Full AutoGen framework test (with reorganized imports)
python tests/test_voting_autogen.py
```

**Import Pattern** (post-reorganization):
```python
# New clean import structure
from src.core.agents.simple_voting_orchestrator import SimpleVotingOrchestrator
from src.core.indicators.simple_rsi import SimpleRSI
from src.data.cache.unified_cache import UnifiedCacheManager
```

**Actual Results**:
- Total return: +12.6% ✅
- Trades executed: 140 ✅  
- Buy-hold comparison: 12.6% vs 34.9% ❌
- AutoGen integration: Fully operational ✅

---

## Success Definition

**ACTUAL RESULTS** from implemented voting strategy:
```
=== VOTING STRATEGY RESULTS ===
Symbol: AAPL
Period: 2024-01-01 to 2024-12-31
Strategy Return: +12.6% ✅
Buy-Hold Return: +34.9% ❌
Total Trades: 140 ✅
Trading Activity: 57.1%
AutoGen Framework: Fully Operational ✅

🟡 PARTIAL SUCCESS: Strategy works, needs tuning to beat buy-and-hold
```

**Configuration Documented ✅**:
- MACD: 12/26/9 with ±0.1 histogram thresholds
- RSI: 14-period, 30/70 oversold/overbought thresholds  
- Voting: Strong signal (both agree) = 1.0 size, Weak signal = 0.5 size
- Cache: polygon_consolidated source, backward compatible format
- Framework: Full AutoGen 0.7.x integration with resolved dependencies

---

## Experiment Queue (Next Phase)

**Current Status**: ✅ Voting strategy operational with AutoGen framework + Clean reorganized codebase
**Performance Gap**: Strategy +12.6% vs Buy-Hold +34.9% (22.3% gap)

**Systematic Experiments** (GitHub Issues Created):
1. **🔬 [#293](https://github.com/iAmGiG/RH2MAS/issues/293)**: Voting vs Single Indicator (HIGH priority)
2. **🔬 [#294](https://github.com/iAmGiG/RH2MAS/issues/294)**: Optimal vote thresholds (2/4 vs 3/4 vs 4/4)
3. **🔬 [#295](https://github.com/iAmGiG/RH2MAS/issues/295)**: Confidence weighting vs equal votes
4. **🔬 [#296](https://github.com/iAmGiG/RH2MAS/issues/296)**: Market regime detection & adaptation

**Infrastructure Complete**: 
- AutoGen scaling ready for production deployment
- Reorganized codebase eliminates duplication
- Cross-platform Linux/Windows compatibility

---

*This TODO is now tracked in repo for cross-environment consistency*
*Last Updated: September 4, 2025 - Voting Strategy Implementation Complete*