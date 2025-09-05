# Fibonacci Regime Detection Development

**Status**: 🔄 **IN DEVELOPMENT** - Phase-based implementation (Issues #297-#301)

## Overview

Enhancing validated voting strategy with Fibonacci-based regime detection to address bull market underperformance while maintaining volatile market advantages.

**Goal**: Reduce bull market gap from -25.8% to <-15% while maintaining -14.6% volatile market gap.

## Phase Development Plan

### Phase 1: Core Fibonacci Module (Issue #298) ⚠️ BLOCKED
**Goal**: Add 34 EMA filtering without disrupting proven voting system

**🚨 CRITICAL BLOCKING ISSUE DISCOVERED**:
- Baseline trading simulation generates **ZERO trades** across all symbols/periods
- Signals generated but not converting to actual portfolio transactions
- Optimization meaningless until trade execution logic is fixed

**Implementation** - Components Ready:
- ✅ `FibonacciRegimeModule` class with periods [8, 13, 21, 34, 55, 89, 144, 233]
- ✅ 34 EMA filter: Price > EMA34 for buys, < EMA34 for sells
- ✅ Integration with existing MACD (13/34/8) + RSI voting
- ❌ **BLOCKED**: Must fix baseline trade execution first

**Success Target**: -25.8% → -20% bull market gap reduction (pending baseline fix)

### Phase 2: CCI Filter Integration (Issue #299) ⏸️
**Goal**: Add Commodity Channel Index per Borden methodology

**Implementation**:
- CCI calculation: (Typical Price - SMA) / (0.015 * Mean Deviation)  
- 14-period CCI > 0 for buys, < 0 for sells
- 50-period CCI > 0 for buys, < 0 for sells

**Success Target**: Win rate >55% (vs current 51.4%)

### Phase 3: Symmetry Break Detection (Issue #300) ⏸️
**Goal**: Trend change prediction via symmetry analysis

**Key Insight**: *"Important trend changes will most often be preceded by a break in symmetry"* - Borden

**Implementation**:
- Swing identification over 55-period lookback
- Symmetry break: swing_ratio outside 0.8-1.2 range
- Apply to stop-loss tightening and position sizing

### Phase 4: Full Integration (Issue #301) ⏸️
**Goal**: Complete modular system with regime-adaptive position sizing

**Regime-Adaptive Rules**:
- **STRONG_BULL**: 120% position size, RSI oversold = 35
- **STRONG_BEAR**: 60% position size, RSI oversold = 25
- **TRANSITIONAL**: Standard parameters

**Final Targets**:
- Bull market gap: <-15%
- Volatile market: Maintain -14.6% gap  
- Sharpe ratio: >0.9
- Max drawdown: <-15%

## Modular Architecture

```python
class TradingAgentSystem:
    modules = {
        'voting': VotingModule(),           # ✅ Validated baseline
        'fibonacci': FibonacciRegimeModule(), # 🔄 Phase 1
        'cci_filter': CCIFilterModule(),      # ⏸️ Phase 2  
        'symmetry': SymmetryAnalyzer(),       # ⏸️ Phase 3
    }
    
    # Start minimal, add incrementally
    active_modules = ['voting']  # Expand as phases complete
```

## Results Storage

Each phase will store results in respective subdirectories:
- `phase_1_results/` - 34 EMA filtering results
- `phase_2_results/` - CCI integration comparisons
- `phase_3_results/` - Symmetry detection validation
- `phase_4_results/` - Full system integration tests

## Success Criteria

Each phase must:
1. **Improve or maintain** current voting metrics
2. **Be easily reversible** if performance degrades
3. **Follow A/B testing** protocol vs baseline
4. **Document clear benefit** before next phase

---
*Phase planning completed September 5, 2025*