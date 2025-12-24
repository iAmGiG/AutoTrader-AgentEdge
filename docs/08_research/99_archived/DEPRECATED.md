# ARCHIVED - Voting Validation Results

> **Status**: DEPRECATED - Results superseded by walk-forward validation (#495)

## Why Archived

These results from experiment #293 showed **0.856 Sharpe ratio** for MACD+RSI voting, but walk-forward validation (#495) revealed:

- **65-93% performance degradation** from in-sample to out-of-sample
- Fibonacci MACD parameters (13/34/8) were likely curve-fit to 2016-2020 bull market
- Results do not generalize to 2023-2024 test period

## Current Recommendations

See [methodology_validation_summary.md](../03_strategy_research/methodology_validation_summary.md) for validated strategies:

- **TSMOM-12M**: 1.097 OOS Sharpe (QQQ) - VALIDATED
- **MACD+RSI**: 0.468 OOS Sharpe - FAILED (65% degradation)

## Files in This Archive

- `experiment_293_validation/` - Original VoterAgent validation
- `extended_period_analysis/` - Extended period backtests
- `indicator_comparisons/` - Ichimoku, optimized voting tests
- `macd_optimization/` - Fibonacci parameter optimization (overfit)

## Related Issues

- #495 - Walk-forward validation framework
- #518 - MACD parameter stability analysis (in progress)
