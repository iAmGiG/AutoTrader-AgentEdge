# Research Documentation

Research documents, experimental results, and validation studies for AutoTrader strategies.

This companion repository tests practitioner hypotheses and documents what works (and doesn't) to help the main project narrow scope.

## Contents

| Path | Description |
|------|-------------|
| [01_broker_api_comparison_2025.md](01_broker_api_comparison_2025.md) | Broker API feature comparison and evaluation |
| [02_gex_research/](02_gex_research/) | Gamma Exposure (GEX) research and experiments |
| [03_strategy_research/](03_strategy_research/) | Trading strategy validation and backtests |
| [99_archived/](99_archived/) | Completed and deprecated experiments |

---

## Research Summary (Dec 2025)

### Scope Narrowing

Hypotheses tested and found **not actionable** - saves the main project from pursuing dead ends.

| Hypothesis | Issue | Result | Evidence |
|------------|-------|--------|----------|
| GEX regime filtering improves TSMOM | #516 | **Invalidated** | Median improvement -2.9% (makes it worse) |
| MACD parameters can be optimized for robustness | #518 | **No robust edge** | Best OOS Sharpe -0.223 ("least unprofitable") |
| Academic TSMOM (12-mo return) is tradeable | #519 | **Poor after costs** | 19% pass rate, -0.259 avg net Sharpe |
| Inverse GEX regime weighting (full in negative gamma) | #516 | **Invalidated** | Hybrid strategy underperforms pure TSMOM |

**Key Insight**: Most parameter optimization shows IS→OOS decay (overfitting). The data does not support GEX as a signal filter for momentum strategies.

### High Value Leads

Hypotheses that show **promise** and warrant further investigation.

| Finding | Issue | Result | Next Step |
|---------|-------|--------|-----------|
| MACD+RSI voting more robust than TSMOM | #519 | **44% pass rate** (vs 19% for TSMOM) | Already in VoterAgent |
| Weekly KAMA outperforms weekly MACD | #467 | **~0.75 avg Sharpe** | Consider TrendFilterAgent |
| Path-dependent simulation reveals wick risk | #528 | **Framework created** | Apply to all strategies |
| VoterAgent validated | Exp 293 | **0.856 Sharpe** | Production ready |

### Critical Research Gaps

Issues that must be addressed before production deployment.

| Gap | Impact | Resolution |
|-----|--------|------------|
| **Wick Risk** | Vectorized backtests overestimate Sharpe | Path-dependent simulation (#528) |
| **Strategy Definitions** | Multiple TSMOM/MACD definitions across scripts | Canonical implementations needed |
| **Portfolio Correlation** | Symbols analyzed in isolation | Portfolio-level simulation |
| **Data Granularity** | Some scripts estimate High/Low | Use actual OHLC data |

### Research Contradiction (Resolved)

| Script | Momentum Definition | GEX Finding |
|--------|---------------------|-------------|
| `tsmom_vs_gex_analysis.py` (#421) | MACD+RSI (short-term) | Better in POSITIVE_GAMMA |
| `tsmom_gex_hybrid.py` (#516) | 12-month return (academic) | Tested NEGATIVE_GAMMA (failed) |

**Resolution**: These are different strategies. The contradiction arose from inconsistent terminology ("TSMOM" used for both). The #421 finding for MACD+RSI may still hold but requires re-validation with corrected methodology.

---

## Methodology Standards

All research scripts now follow these standards:

1. **Look-ahead prevention**: `signals.shift(1)`, `regimes.shift(1)` for t+1 execution
2. **Transaction costs**: Turnover-proportional (not fixed deduction)
3. **Div-by-zero protection**: EPSILON = 1e-9
4. **Reporting**: Median alongside mean for outlier-robust metrics
5. **YAML serialization**: Explicit `float()`, `int()` casts to avoid numpy types

---

## Quick Links

- **Strategy Results**: [03_strategy_research/results/](03_strategy_research/results/)
- **GEX Research**: [02_gex_research/](02_gex_research/)
- **Archived Experiments**: [99_archived/](99_archived/)
