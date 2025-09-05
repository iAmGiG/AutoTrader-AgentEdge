# Fibonacci Regime Detection System

**Status**: 🔄 **IN DEVELOPMENT** - Phase-based implementation to enhance validated voting strategy

## Overview

The Fibonacci Regime Detection System enhances our proven voting strategy with market regime awareness, addressing the bull market underperformance while maintaining volatile market advantages.

**Goal**: Reduce bull market gap from -25.8% to <-15% while preserving -14.6% volatile market performance.

## Background & Motivation

### Validated Foundation ✅
Our voting strategy (MACD + RSI) has been proven effective:
- **0.856 Sharpe ratio** (beats single indicators)
- **Better risk management** (-10.10% vs -10.58% max drawdown)
- **Market regime insight**: Performs relatively better in volatile markets

### The Challenge 🎯
While voting excels at risk management, it significantly underperforms in strong bull markets:
- **2024 Bull**: -25.8% gap vs buy-and-hold  
- **2025 Volatile**: -14.6% gap vs buy-and-hold (11.2% better!)

### The Solution 🔬
Implement Fibonacci-based regime detection to adapt strategy based on market conditions, inspired by Carolyn Borden's methodology and our proven Fibonacci MACD parameters (13/34/8).

## Phase-Based Development Plan

### Phase 1: Core Fibonacci Module (Issue #298) ⏳
**Status**: Ready for implementation

**Goal**: Add 34 EMA filtering without disrupting proven voting system

**Components**:
```python
class FibonacciRegimeModule:
    FIB_PERIODS = [8, 13, 21, 34, 55, 89, 144, 233]
    
    def generate_entry_signal(self, data):
        price = data['close'][-1]
        ema_34 = data['close'].ewm(span=34).mean()[-1]
        
        # Filter existing voting signals
        if price > ema_34:
            return 'ALLOW_BUY'  # Enable buy signals
        elif price < ema_34:  
            return 'ALLOW_SELL'  # Enable sell signals
        return 'NEUTRAL'
```

**Success Target**: Bull market gap reduction (-25.8% → -20%)

### Phase 2: CCI Filter Integration (Issue #299) ⏸️
**Goal**: Add Commodity Channel Index filters per Borden methodology

**Borden's CCI Criteria**:
- **14-period CCI** > 0 for buys, < 0 for sells
- **50-period CCI** > 0 for buys, < 0 for sells  
- **Combined with 34 EMA** for multi-timeframe confirmation

**Implementation**:
```python
def calculate_cci(data, period):
    # CCI = (Typical Price - SMA) / (0.015 * Mean Deviation)
    typical_price = (data['high'] + data['low'] + data['close']) / 3
    sma = typical_price.rolling(period).mean()
    mad = typical_price.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
    return (typical_price - sma) / (0.015 * mad)
```

**Success Target**: Win rate >55% (vs current 51.4%)

### Phase 3: Symmetry Break Detection (Issue #300) ⏸️  
**Goal**: Implement trend change prediction via symmetry analysis

**Borden's Key Insight**: 
> "Important trend changes will most often be preceded by a break in symmetry"

**Implementation**:
```python
def check_symmetry_break(self, data, lookback=55):
    recent_swings = self.identify_swings(data, lookback)
    
    if len(recent_swings) >= 2:
        swing_ratio = recent_swings[-1] / recent_swings[-2]
        # Symmetry break if ratio outside 0.8-1.2 range
        if swing_ratio < 0.8 or swing_ratio > 1.2:
            return 'SYMMETRY_BREAK'
    return 'SYMMETRIC'
```

**Applications**:
- Stop-loss tightening when symmetry breaks
- Position size reduction before trend changes
- Early warning for major market shifts

### Phase 4: Full Integration & Testing (Issue #301) ⏸️
**Goal**: Complete modular system with regime-adaptive position sizing

**Modular Architecture**:
```python
class TradingAgentSystem:
    def __init__(self):
        self.modules = {
            'voting': VotingModule(),           # ✅ Validated baseline
            'fibonacci': FibonacciRegimeModule(), # Phase 1
            'cci_filter': CCIFilterModule(),      # Phase 2  
            'symmetry': SymmetryAnalyzer(),       # Phase 3
        }
        self.active_modules = ['voting']  # Expand incrementally
```

**Regime-Adaptive Position Sizing**:
```python
def adjust_thresholds(self, base_signal, regime):
    if regime == 'STRONG_BULL':
        return {
            'rsi_oversold': 35,  # vs 30 baseline (less restrictive)
            'position_size': 1.2  # 120% sizing (more aggressive)
        }
    elif regime in ['STRONG_BEAR', 'SYMMETRY_BREAK']:
        return {
            'rsi_oversold': 25,  # vs 30 baseline (more restrictive)  
            'position_size': 0.6  # 60% sizing (more conservative)
        }
    return base_signal  # TRANSITIONAL: use standard parameters
```

## Fibonacci Framework Foundation

### Core Fibonacci Relationships
**Primary Periods**: 8, 13, 21, 34, 55, 89, 144, 233
**Key Ratios**: 0.382, 0.618, 1.618, 2.618  
**Time Projections**: 55 + 89 = 144, 89 + 144 = 233

### Validated Parameters ✅
Our existing system already uses Fibonacci-based MACD:
- **Fast EMA**: 13 periods (Fibonacci)
- **Slow EMA**: 34 periods (Fibonacci)  
- **Signal EMA**: 8 periods (Fibonacci)

This provides the foundation for expanding Fibonacci-based analysis.

### Hybrid MA Strategy
**Regime Detection**: Use SMA for stability (55, 89 periods)
**Signal Generation**: Use EMA for responsiveness (34 period)

## Implementation Principles

### 1. **Modular Design** 🧩
Each phase adds independent components that can be easily enabled/disabled for testing.

### 2. **Preserve Foundation** 🛡️
The validated voting system remains untouched. All enhancements are additive.

### 3. **Incremental Enhancement** 📈
Each phase must demonstrate improvement before proceeding to the next.

### 4. **A/B Testing** 🔬
Compare each enhancement against the baseline to ensure genuine improvement.

## Success Metrics

### Phase-by-Phase Targets:
- **Phase 1**: -25.8% → -20% bull market gap reduction
- **Phase 2**: >55% win rate (vs 51.4% baseline)  
- **Phase 3**: Improved drawdown control during trend reversals
- **Phase 4**: Bull market gap <-15%, Sharpe >0.9, Max drawdown <-15%

### Overall Success Criteria:
1. **Bull Market Performance**: Gap reduction to <-15%
2. **Volatile Market Maintenance**: Preserve -14.6% gap or better
3. **Risk Metrics**: Maintain or improve Sharpe ratio and drawdown
4. **Practical Implementation**: System remains operationally stable

## Development Resources

### Implementation Files (To Be Created):
- `src/core/agents/fibonacci_regime_module.py` - Phase 1 core module
- `src/core/indicators/cci_filter.py` - Phase 2 CCI calculations  
- `src/core/analysis/symmetry_analyzer.py` - Phase 3 break detection
- `src/core/orchestrators/modular_agent_system.py` - Phase 4 integration

### Testing Files:
- `tests/fibonacci_regime/test_phase_1.py` - 34 EMA filtering validation
- `tests/fibonacci_regime/test_cci_integration.py` - Phase 2 validation
- `tests/fibonacci_regime/test_symmetry_breaks.py` - Phase 3 validation  
- `tests/fibonacci_regime/test_full_integration.py` - Phase 4 validation

### Results Storage:
- `reports/active/fibonacci_regime/phase_1_results/` - Implementation results by phase
- `reports/active/fibonacci_regime/phase_2_results/`
- `reports/active/fibonacci_regime/phase_3_results/`  
- `reports/active/fibonacci_regime/phase_4_results/`

---

*Ready to begin Phase 1 implementation - Core Fibonacci Module with 34 EMA filtering*

**Next Action**: Implement `FibonacciRegimeModule` class and integration with validated voting system.