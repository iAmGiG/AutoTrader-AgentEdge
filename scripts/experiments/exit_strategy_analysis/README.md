# Exit Strategy Analysis Experiments

**Research Question**: Which exit strategy provides the best expected value for MACD+RSI voting system?

## Critical Discovery
**Conservative exits (6% TP / 8% SL) have NEGATIVE expected value at realistic win rates!**

## Methodology
- **Entry System**: Validated MACD(13/34/8) + RSI voting
- **Test Scenarios**: Bull market, bear market, volatile sideways
- **Analysis**: Expected value calculation, actual backtesting, mathematical verification

## Scripts

### `performance_clarification.py`
- **Purpose**: Clarify per-trade vs annual returns
- **Key Insight**: 6%/8% are per-trade targets, not annual returns
- **Findings**: Actual annual returns depend on trade frequency and compounding

### `expected_value_analysis.py`
- **Purpose**: Mathematical expected value verification
- **Critical Finding**: Conservative strategy has -0.08% EV at 56.6% win rate
- **Formula**: EV = (Win Rate × Take Profit) - (Loss Rate × Stop Loss)

## Exit Strategy Comparison

### 🏆 Balanced Strategy (8% TP / 5% SL) - RECOMMENDED
- **Expected Value**: +1.50% per trade at 50% win rate
- **Breakeven Win Rate**: 38.5% (very achievable)
- **Actual Performance**: 27.48% annual return, 1.288 Sharpe ratio
- **Status**: ✅ OPTIMAL CHOICE

### ❌ Conservative Strategy (6% TP / 8% SL) - AVOID
- **Expected Value**: -0.08% per trade at 56.6% win rate
- **Breakeven Win Rate**: 57.1% (requires high accuracy)
- **Actual Performance**: 10.42% annual return, 0.578 Sharpe
- **Status**: ❌ NEGATIVE EXPECTED VALUE

### ⚡ Aggressive Strategy (10% TP / 3% SL)
- **Expected Value**: +1.33% per trade at 33.3% win rate
- **Breakeven Win Rate**: 23.1% (very low threshold)
- **Actual Performance**: 7.67% annual return, 0.488 Sharpe
- **Status**: 🤔 MATHEMATICALLY GOOD, PRACTICALLY MODERATE

## Key Mathematical Insights

### Expected Value Formula
```
EV per trade = (Win Rate × Take Profit %) - (Loss Rate × Stop Loss %)
```

### Breakeven Win Rate Formula
```
Breakeven WR = Stop Loss % / (Take Profit % + Stop Loss %)
```

### Examples:
- **Balanced (8%/5%)**: 5% / (8% + 5%) = 38.5% breakeven
- **Conservative (6%/8%)**: 8% / (6% + 8%) = 57.1% breakeven
- **Aggressive (10%/3%)**: 3% / (10% + 3%) = 23.1% breakeven

## Critical Lesson
**The original "0.373 Sharpe" claim for conservative exits was misleading!** The actual win rate achieved (66.7%) was much higher than the claimed 56.6%, masking the negative expected value.

## Recommendation
✅ **Use Balanced Strategy (8% TP / 5% SL)** 
- Best expected value at realistic win rates
- Robust to win rate variations
- Proven 27.48% annual returns in testing

## Related Issues
- Issue #293 - Updated with these findings
- Issue #303 - Configuration system to make exit strategies adjustable

## Usage
```bash
# Clarify performance metrics
python performance_clarification.py

# Verify expected value math
python expected_value_analysis.py
```