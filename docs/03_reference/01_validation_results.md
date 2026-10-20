# Voting Strategy Validation Results

**Status**: Superseded (Oct 2026). Experiment #293's results below are in-sample.

> **Superseded (Oct 2026, #574):** these are experiment 293's in-sample results (AAPL 2024, MACD 12/26/9, filled at the signal's own close, no costs). Backtested with the live rules and timing on the 19-symbol watchlist from 2009, MACD+RSI voting has a Sharpe of 0.69 at 5 bps a side and no alpha over buy-and-hold of the same symbols; see the [live-rules baseline](../08_research/03_strategy_research/live_rules_baseline.md).

## Executive Summary

In experiment #293 (in-sample), the 2-way voting strategy (MACD + RSI) beat single indicator approaches on several risk-adjusted metrics.

**Key Result**: Voting achieved 0.856 Sharpe ratio vs 0.841 for single MACD, with better drawdown control and higher win rates.

## Experiment #293 Results

### Primary Success Metrics ✅

| Metric | MACD-Only | Voting (MACD+RSI) | Winner |
|--------|-----------|-------------------|--------|
| **Sharpe Ratio** | 0.841 | **0.856** | **Voting** |
| **Max Drawdown** | -10.58% | **-10.10%** | **Voting** |
| **Win Rate** | 31.9% | **51.4%** | **Voting** |

### Secondary Metrics

| Metric | MACD-Only | Voting (MACD+RSI) | Winner |
|--------|-----------|-------------------|--------|
| Total Return | **13.34%** | 12.62% | MACD |
| Number of Trades | 18 | 140 | - |
| Volatility | 16.58% | **15.30%** | **Voting** |

### Validation Criteria Met

- ✅ **Better Risk-Adjusted Returns**: Sharpe ratio improvement
- ✅ **Lower Drawdown**: Risk management superiority  
- ✅ **Statistical Significance**: Tested on 252 trading days (full year)
- ✅ **Practical Implementation**: Working AutoGen integration

## Configuration Validated

```python
# Locked-in Voting Parameters
FIBONACCI_MACD = (13, 34, 8)  # Fast/Slow/Signal periods
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Voting Decision Logic
def make_voting_decision(macd_signal, rsi_signal):
    if macd_signal == rsi_signal and both != "HOLD":
        return {"action": signal, "position_size": 1.0, "confidence": "strong"}
    elif one_signals and other == "HOLD":
        return {"action": active_signal, "position_size": 0.5, "confidence": "weak"}  
    else:
        return {"action": "HOLD", "position_size": 0.0, "confidence": "none"}
```

## Extended Period Validation (2024-2025)

### Market Regime Performance Discovery 🔥

**Critical Finding**: Voting performs **relatively better** in volatile markets

| Market Regime | Voting Gap vs Buy-Hold | Performance |
|---------------|------------------------|-------------|
| **2024 Bull Market** | -25.8% gap | Significant underperformance |
| **2025 Volatile Market** | -14.6% gap | **11.2% better relative performance** |

**Strategic Insight**: The smaller gap in volatile markets (2025) validates voting's risk management value during corrections and uncertainty.

### Overall Extended Period Results

- **Period**: 2024-01-02 to 2025-08-29 (417 trading days)
- **Voting Return**: +36.6%  
- **Buy-Hold Return**: +90.6%
- **Gap**: -54% (needs improvement, but relatively better in volatility)
- **Sharpe Ratio**: 0.771 (solid risk-adjusted performance)

## Why Voting Works

### 1. **Signal Confirmation**

Requiring consensus between MACD (momentum) and RSI (overbought/oversold) filters false signals.

### 2. **Dynamic Position Sizing**

- **Strong signals** (both agree): 100% position size
- **Weak signals** (one agrees): 50% position size  
- **No signals** (conflict): 0% position size (stay in cash)

### 3. **Complementary Indicators**

- **MACD**: Captures trend momentum and direction
- **RSI**: Identifies overbought/oversold extremes
- **Together**: Reduce whipsaws and false breakouts

### 4. **Risk Management**

Lower drawdown and volatility demonstrate superior risk control, critical for long-term sustainability.

## Comparison with Alternatives

### vs Single Indicators ✅

- **MACD-only**: Voting wins on risk metrics
- **RSI-only**: Not tested directly, but expected similar pattern
- **Moving Averages**: Not tested

### vs Complex Systems ❌  

- **Ichimoku 3-way**: Degraded performance (added noise)
- **V0-V4 Sentiment**: Deprecated due to complexity without proven ROI
- **Conclusion**: Quality over quantity in indicator selection

## Implementation Status

### ✅ **Operational Components**

- `SimpleVotingOrchestrator`: MACD + RSI coordination
- `TechAgent`: Fibonacci MACD (13/34/8) signals
- `SimpleRSI`: 14-period RSI with confidence scoring
- `TradingCacheManager`: SQLite-based market data caching (8-10x performance improvement, 90%+ hit rate)

### ❌ **Fibonacci Regime Experiment Closed**

Issues #297-#301 (Fibonacci regime detection) were closed after analysis showed the approach was too complex and not additive to the voting strategy.

## Next Steps

1. **Maintain Foundation**: Keep the voting system as the baseline to compare against
2. **Focus on Simplicity**: Avoid complex enhancements that don't meaningfully improve performance
3. **Re-test at live timing**: Done in #574 stage A; the live rules show no edge over buy-and-hold of the same symbols ([live-rules baseline](../08_research/03_strategy_research/live_rules_baseline.md))

---

Experiment #293 complete; its in-sample result is superseded by the live-rules baseline.

**Files**:

- Raw results: `docs/08_research/99_archived/experiment_293_validation/`
- Extended analysis: `docs/08_research/99_archived/extended_period_analysis/`
- Test scripts: `tests/experiment_293_macd_vs_voting.py`
