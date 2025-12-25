# Research Documentation

Research documents, experimental results, and validation studies for AutoTrader strategies.

This companion repository tests practitioner hypotheses and documents what works (and doesn't) to help the main project narrow scope.

## Contents

| Path | Description |
| ------ | ------------- |
| [01_broker_api_comparison_2025.md](01_broker_api_comparison_2025.md) | Broker API feature comparison and evaluation |
| [02_gex_research/](02_gex_research/) | Gamma Exposure (GEX) research and experiments |
| [03_strategy_research/](03_strategy_research/) | Trading strategy validation and backtests |
| [99_archived/](99_archived/) | Completed and deprecated experiments |

---

## Research Status Legend

| Status | Meaning | Action |
| -------- | --------- | -------- |
| 🛑 **STOP** | Hypothesis invalidated, research concluded | Do not pursue further |
| ✅ **DONE** | Findings validated and integrated | No further work needed |
| 🔄 **CONTINUE** | Promising results, worth pursuing | Allocate resources |
| ⚠️ **GAP** | Critical issue blocking production | Must address before launch |

---

## Research Summary (Dec 2025)

### Scope Narrowing — 🛑 STOP

Hypotheses tested and found **not actionable**. Saves the main project from pursuing dead ends.

| Hypothesis | Issue | Status | Evidence |
| ------------ | ------- | -------- | ---------- |
| GEX regime filtering improves TSMOM | #516 | 🛑 STOP | Median improvement -2.9% (makes it worse) |
| MACD parameters can be optimized for robustness | #518 | 🛑 STOP | Best OOS Sharpe -0.223 ("least unprofitable") |
| Academic TSMOM (12-mo return) is tradeable | #519 | 🛑 STOP | 19% pass rate, -0.259 avg net Sharpe |
| Inverse GEX regime weighting (full in negative gamma) | #516 | 🛑 STOP | Hybrid strategy underperforms pure TSMOM |

**Key Insight**: Most parameter optimization shows IS→OOS decay (overfitting). The data does not support GEX as a signal filter for momentum strategies.

**Conclusion**: These hypotheses have been thoroughly tested. Further work on GEX+momentum combinations or TSMOM parameter tuning is **not recommended**.

---

### High Value Leads — ✅ DONE / 🔄 CONTINUE

Findings that show **promise**. Some integrated into production, others warrant further investigation.

| Finding | Issue | Status | Action |
| --------- | ------- | -------- | -------- |
| MACD+RSI voting more robust than TSMOM | #519 | ✅ DONE | Integrated in VoterAgent (0.856 Sharpe) |
| VoterAgent validated | Exp 293 | ✅ DONE | Production ready, no changes needed |
| Weekly KAMA outperforms weekly MACD | #467 | 🔄 CONTINUE | Consider TrendFilterAgent implementation |
| Path-dependent simulation reveals wick risk | #528 | 🔄 CONTINUE | Apply framework to all strategies |
| MACD+RSI in positive gamma (short-term) | #421 | 🔄 CONTINUE | Re-validate with corrected methodology |

**Conclusion**: VoterAgent work is complete. Focus new resources on KAMA exploration and wick risk simulation.

---

### Critical Research Gaps — ⚠️ GAP

Issues that **must be addressed** before production deployment.

| Gap | Impact | Status | Resolution |
| ----- | -------- | -------- | ------------ |
| Wick Risk | Vectorized backtests overestimate Sharpe | ⚠️ GAP | Path-dependent simulation (#528) |
| Strategy Definitions | Multiple TSMOM/MACD definitions across scripts | ⚠️ GAP | Canonical implementations needed |
| Portfolio Correlation | Symbols analyzed in isolation | ⚠️ GAP | Portfolio-level simulation |
| Data Granularity | Some scripts estimate High/Low | ⚠️ GAP | Use actual OHLC data |

**Conclusion**: These gaps affect result reliability. Address before trusting backtest numbers for production sizing.

---

### Research Contradiction (Resolved)

| Script | Momentum Definition | GEX Finding |
| -------- | --------------------- | ------------- |
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

## Quick Reference: What to Work On

### Stop Working On

- GEX as a momentum signal filter
- Academic TSMOM (12-month lookback)
- MACD parameter optimization for Sharpe
- Inverse regime weighting strategies

### Continue Working On

- Weekly KAMA TrendFilterAgent (#529, research in #467)
- Path-dependent wick simulation (#528)
- MACD+RSI in positive gamma re-validation (#421)
- Portfolio-level correlation analysis

### Already Complete

- VoterAgent validation (Exp 293)
- MACD+RSI voting integration (#519)
- Methodology corrections (look-ahead, costs)

---

## Quick Links

- **Strategy Results**: [03_strategy_research/results/](03_strategy_research/results/)
- **GEX Research**: [02_gex_research/](02_gex_research/)
- **Archived Experiments**: [99_archived/](99_archived/)
