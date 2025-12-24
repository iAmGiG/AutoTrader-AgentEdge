# Methodology Validation Summary

Research completed: 2025-12-22

Issues: #495, #498, #502

---

> **⚠️ PROBLEMATIC RESULTS - LOOK-AHEAD BIAS DETECTED**
>
> All backtesting results below are **optimistically biased**. A look-ahead bias was discovered where signals calculated at close(t) were executed at the same close(t). This is unrealistic - real execution requires t+1.
>
> **Fix applied**: `signals = signals.shift(1).fillna(0)`
>
> **Experiments must be rerun** - see issue #523
>
> Results below are preserved for reference but should NOT be used for production decisions.

---

## Overview

This document summarizes research into backtesting methodology validation, including walk-forward testing, multiple testing corrections, and formula comparisons.

---

## #495: Walk-Forward Validation & P-Hacking Mitigation

### Framework

- **Train Period**: 2020-01-01 to 2022-12-31 (3 years)
- **Test Period**: 2023-01-01 to 2024-12-31 (2 years)
- **Validation Criteria**:
  - OOS Sharpe > 0.3
  - Degradation < 50%

### Multiple Testing Corrections

Applied Benjamini-Hochberg FDR correction to control false discovery rate when testing multiple strategies.

### Key Findings

| Strategy | IS Sharpe | OOS Sharpe | Degradation | Status |
|----------|-----------|------------|-------------|--------|
| MACD_RSI_QQQ | 1.353 | 0.468 | 65.4% | FAIL |
| MACD_RSI_IWM | 1.751 | 0.118 | 93.2% | FAIL |
| TSMOM_QQQ | 0.000 | 0.477 | N/A | PASS |

**Critical Finding**: MACD+RSI shows 65-93% performance degradation from in-sample to out-of-sample. This suggests potential overfitting in previous validation work.

### Causal Mechanism Framework

Documented WHO-WHOM-WHAT for validated patterns:

- **Gamma Pinning**: Market makers → Options sellers → Price gravitates to max gamma strike
- **Momentum Effect**: CTAs/momentum funds → All participants → Slow information diffusion creates persistent trends
- **MACD Crossover**: Technical traders → Other technicals → Self-fulfilling prophecy (medium confidence)

---

## #498: Multi-Asset TSMOM Research

### Methodology

Time-Series Momentum based on Moskowitz, Ooi, Pedersen (2012):

- Lookback periods: 63, 126, 252 days
- Volatility scaling: target 40% annualized vol

### Results by Asset Class

| Asset Class | Avg OOS Sharpe | Best Performer |
|-------------|----------------|----------------|
| Equity Index | 0.847 | QQQ (1.097) |
| Volatility | 1.082 | UVXY |
| Leveraged | -0.249 | TQQQ (0.819) |

### Lookback Period Comparison

| Lookback | Avg OOS Sharpe | Pass Rate |
|----------|----------------|-----------|
| 63 days | -0.121 | 25% |
| 126 days | 0.244 | 50% |
| 252 days | 0.254 | 57% |

**Recommendation**: 12-month (252-day) lookback is optimal, consistent with academic literature.

---

## #502: S-Squared GEX Scaling (Negative Result)

### Formulas Compared

- **Current**: `weighted_gamma = gamma * open_interest`
- **Academic**: `GEX = OI * Gamma * S^2 * 0.01 * 100`

### Results

| Metric | Current | S-Squared |
|--------|---------|-----------|
| Win Rate | 71% | 29% |
| Avg CV | 0.532 | 0.735 |
| Avg Sharpe Improvement | - | -0.047 |

**Conclusion**: S-squared scaling does NOT improve trading signals. Current formula is more stable and performs better for single-asset analysis.

---

## Files Created

- `scripts/research/walk_forward_validation.py`
- `scripts/research/multi_asset_tsmom.py`
- `scripts/research/s_squared_gex_scaling.py`
- `docs/08_research/03_strategy_research/walk_forward_results.yaml`
- `docs/08_research/03_strategy_research/tsmom_multi_asset_results.yaml`
- `docs/08_research/02_gex_research/s_squared_scaling_results.yaml`

## Branch

`research/b-chat-methodology-495-498-502`
