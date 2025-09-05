# RH2MAS Development TODO

**NOW TRACKED IN REPO** - Shared across environments for consistent development

## 🎯 CURRENT FOCUS: Fibonacci-Based Regime Detection System

**Status**: ✅ Voting strategy VALIDATED - Moving to enhancement phase

### Voting Strategy Results ✅ COMPLETE

- ✅ **Voting validated**: 0.856 Sharpe beats single MACD (0.841)
- ✅ **Risk management**: -10.10% drawdown beats MACD (-10.58%)  
- ✅ **Extended testing**: 36.6% return over 2024-2025 period
- ✅ **Market regime insight**: Performs better in volatile (-14.6% gap) vs bull markets (-25.8% gap)
- ✅ **Fibonacci MACD**: 13/34/8 parameters optimized across 7 tech stocks

**RESULT**: Foundation proven, now implementing Fibonacci regime enhancement from main chat collaboration (Issue #297)

---

## 🔬 Phase-Based Implementation Roadmap

### Phase 1: Core Fibonacci Module ⚠️ CRITICAL ISSUE DISCOVERED

**GitHub Issue**: [#298](https://github.com/iAmGiG/RH2MAS/issues/298)  
**Goal**: Add 34 EMA filter without disrupting proven voting system

#### ⚠️ CRITICAL BLOCKING ISSUE

**Problem**: Baseline trading simulation generates **ZERO trades** across all symbols/periods
- Portfolio value remains constant at $10,000 (0% returns)
- Signals generated but not converting to actual trades
- Makes optimization meaningless until trade execution is fixed

#### Tasks - BLOCKED

- ✅ Create `FibonacciRegimeModule` class with Fibonacci periods [8, 13, 21, 34, 55, 89, 144, 233]
- ✅ Implement 34 EMA filter: Price > EMA34 for buys, < EMA34 for sells  
- ✅ Test integration with existing MACD (13/34/8) + RSI voting
- ❌ **BLOCKED**: Fix baseline trade execution before optimization

#### Success Target

- Reduce bull market gap from -25.8% to -20%
- Maintain volatile market performance (-14.6% gap)

### Phase 2: CCI Filter Integration ⏸️ PENDING  

**GitHub Issue**: [#299](https://github.com/iAmGiG/RH2MAS/issues/299)
**Goal**: Add Commodity Channel Index filters per Borden methodology

#### Tasks

- ⏸️ Implement CCI calculation: (Typical Price - SMA) / (0.015 * Mean Deviation)
- ⏸️ Create `CCIFilterModule` with 14 & 50-period filters
- ⏸️ Integration: 14-period CCI > 0 for buys, < 0 for sells
- ⏸️ Integration: 50-period CCI > 0 for buys, < 0 for sells

#### Success Target

- Higher win rate: >55% (vs current 51.4%)
- More strong consensus signals, fewer weak trades

### Phase 3: Symmetry Break Detection ⏸️ PENDING

**GitHub Issue**: [#300](https://github.com/iAmGiG/RH2MAS/issues/300)  
**Goal**: Implement trend change prediction via symmetry analysis

#### Key Insight
>
> "Important trend changes will most often be preceded by a break in symmetry" - Borden

#### Tasks

- ⏸️ Swing identification over 55-period lookback (Fibonacci)
- ⏸️ Symmetry break detection: swing_ratio outside 0.8-1.2 range
- ⏸️ Apply to stop-loss tightening and position sizing

#### Success Target

- Improved drawdown control during trend reversals
- Early warning for major market shifts

### Phase 4: Full Integration & Testing ⏸️ PENDING

**GitHub Issue**: [#301](https://github.com/iAmGiG/RH2MAS/issues/301)
**Goal**: Complete modular system with regime-adaptive position sizing

#### Modular Architecture

- `VotingModule` (existing MACD/RSI) ✅
- `FibonacciRegimeModule` (34 EMA filtering)
- `CCIFilterModule` (14/50 period filters)  
- `SymmetryAnalyzer` (break detection)

#### Regime-Adaptive Sizing

- **STRONG_BULL**: 120% position size, RSI oversold = 35
- **STRONG_BEAR**: 60% position size, RSI oversold = 25
- **TRANSITIONAL**: Standard parameters

#### Final Success Targets

- **Bull market gap**: < -15% (vs current -25.8%)
- **Volatile market**: Maintain -14.6% gap or better  
- **Sharpe ratio**: > 0.9 (vs current 0.771)
- **Max drawdown**: < -15% (vs current -23.4%)

---

## 📊 Experiment Results Archive

### ✅ Completed Experiments

1. **Experiment #293**: MACD vs Voting comparison → **Voting validated** (reports/voting_experiments/experiment_293_report.md)
2. **MACD Optimization**: Found universal Fibonacci parameters 13/34/8 (reports/voting_experiments/macd_optimization/)
3. **Ichimoku Testing**: Confirmed visual indicator only, adds noise to voting (reports/voting_experiments/ichimoku/)
4. **Extended Period**: 2024-2025 testing revealed regime-dependent performance (reports/voting_experiments/extended_period/)

### 🔄 Active Development - BLOCKED

- **Fibonacci Regime System** (Issue #297): **BLOCKED** - Must fix trade execution first
- **Modular Architecture**: Components ready but baseline broken
- **NEW PRIORITY**: Issue #302 - Multi-threaded HPCC optimization infrastructure 
- **CRITICAL**: Debug why baseline generates 0 trades (signals exist but no execution)

---

## 🛠️ Technical Architecture

### Current Proven Stack

- **Indicators**: MACD (13/34/8) + RSI (14/30/70)
- **Voting Logic**: 2-way consensus (strong/weak/hold)
- **Position Sizing**: Dynamic based on signal strength
- **Cache System**: UnifiedCacheManager with 90% performance boost
- **Framework**: Full AutoGen integration for scalability

### Proposed Enhancements

- **Fibonacci Regime Detection**: EMA + CCI filters
- **Modular Agents**: Easy component addition/removal
- **Adaptive Sizing**: Regime-aware position management
- **Symmetry Analysis**: Trend change prediction

---

## 📋 Development Workflow

### Current Phase (1)

1. **Implement** `FibonacciRegimeModule` class
2. **Test** 34 EMA filtering on existing data
3. **Compare** baseline vs Fib-enhanced performance
4. **Document** results before Phase 2

### Cross-Platform Support

- ✅ Windows/Linux compatibility maintained
- ✅ Relative imports for portability  
- ✅ Cache system cross-platform paths

### Quality Gates

- All phases must improve or maintain current metrics
- Modular design allows easy rollback if phase fails
- A/B testing required for each component addition

---

*This TODO reflects the strategic shift from "prove voting works" to "enhance proven voting with Fibonacci regime detection"*

*Last Updated: September 5, 2025 - Post-main chat collaboration*
