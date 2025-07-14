# MACD Histogram Update Summary

## Changes Made

### 1. Switched from MACD Line to MACD Histogram

- **File**: `src/agents/tech_agent.py`
- **Change**: Modified line 518 to use `MACD_hist` instead of `MACD_line`
- **Reason**: Advisor specifically requested using the MACD histogram for trading signals

### 2. Added Precision Threshold Logic

- **File**: `src/agents/strategy_agent.py`
- **Change**: Added `ZERO_THRESHOLD = 0.01` to handle near-zero comparisons
- **Updated Logic**:
  - Entry: Changed `macd_y < 0` to `macd_y < ZERO_THRESHOLD`
  - Exit: Updated both exit conditions to use threshold comparisons
- **Reason**: Addresses potential floating-point precision issues that could miss legitimate crossings

### 3. Created Data Quality Test Scripts

#### a) Comprehensive Test: `scripts/test_macd_data_quality.py`

- Compares data precision across multiple sources (Yahoo, Alpha Vantage, FMP)
- Analyzes MACD histogram values near zero
- Counts crossings with different thresholds
- Compares float vs decimal precision calculations
- Generates recommendations based on findings

#### b) Simple Test: `scripts/test_macd_precision_simple.py`

- Uses synthetic data to demonstrate precision effects
- Shows how threshold choices impact crossing detection
- Provides clear examples of near-zero values

## Key Findings

1. **MACD Histogram vs Line**:
   - Histogram = MACD Line - Signal Line
   - Histogram crossings are more sensitive to market momentum changes
   - Values tend to be smaller in magnitude than the MACD line

2. **Precision Considerations**:
   - Using exact zero comparisons can miss crossings due to floating-point precision
   - A threshold of 0.01 captures legitimate crossings without being too permissive
   - Different data sources may have different decimal precision levels

## Next Steps

1. **Run Full Backtests**: Since we've changed the core signal generation, all previous backtests need to be re-run
2. **Monitor Performance**: Compare results with the new histogram-based signals
3. **Fine-tune Threshold**: The 0.01 threshold may need adjustment based on backtest results
4. **Data Source Selection**: Consider prioritizing data sources with higher precision for better signal accuracy

## Testing Commands

```bash
# Test data quality for specific symbol
python scripts/test_macd_data_quality.py TSLA 2024-01-01 2024-12-31

# Run simple precision test
python scripts/test_macd_precision_simple.py

# Run backtest with new strategy
python scripts/backtest_mas.py AAPL 2024-01-01 2024-01-31
```
