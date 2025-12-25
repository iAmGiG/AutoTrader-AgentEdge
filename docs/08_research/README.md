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
| GEX overnight swing filter (Close→Close+1) | #516 | 🛑 STOP | Median improvement -2.9% (makes it worse) |
| MACD parameters can be optimized for robustness | #518 | 🛑 STOP | Best OOS Sharpe -0.223 ("least unprofitable") |
| Academic TSMOM (12-mo return) is tradeable | #519 | 🛑 STOP | 19% pass rate, -0.259 avg net Sharpe |
| GEX + TSMOM hybrid (overnight hold) | #516 | 🛑 STOP | Hybrid underperforms pure strategies |

**Key Insight**: Most parameter optimization shows IS→OOS decay (overfitting). GEX as overnight/swing filter does not work.

**Important Caveat**: The intraday GEX use case (Open→Close, practitioner approach) was **never tested** - see #530.

### Critique of TSMOM Scope (Why it failed here vs Academia)

Similar to GEX, the "Academic TSMOM" tests (#519) may have failed due to implementation gaps relative to the literature (Moskowitz et al., 2012).

| Feature | Academic TSMOM | AutoTrader Implementation |
| :--- | :--- | :--- |
| **Universe** | 58 instruments (Commodities, Bonds, FX, Equities) | Mostly Equity ETFs (SPY, QQQ) |
| **Sizing** | **Volatility Scaled** (Target 40% Ann. Vol) | Capital Allocation (Equal Weight) |
| **Mechanism** | Diversification across uncorrelated trends | Single-asset directional prediction |

**The Gap**: TSMOM is primarily a *portfolio construction technique*, not a *stock picking signal*. It relies on the fact that *something* is usually trending somewhere (e.g., Long Oil, Short Bonds). Testing it on SPY alone removes the diversification benefit and exposes the strategy to single-asset whipsaws.

**Status**: 🛑 STOP remains correct for *this project's current scope* (single-asset equity trading), but the strategy itself is likely valid for multi-asset portfolios.

---

### High Value Leads — ✅ DONE / 🔄 CONTINUE

Findings that show **promise**. Some integrated into production, others warrant further investigation.

| Finding | Issue | Status | Action |
| --------- | ------- | -------- | -------- |
| MACD+RSI voting more robust than TSMOM | #519 | ✅ DONE | Integrated in VoterAgent (0.856 Sharpe) |
| VoterAgent validated | Exp 293 | ✅ DONE | Production ready, no changes needed |
| Ready-Aim-Fire (RAF) outperforms VoterAgent | #460, #532 | 🔄 CONTINUE | 0.553 Sharpe, 80% win rate - integration planned |
| Weekly KAMA outperforms weekly MACD | #467 | 🔄 CONTINUE | Consider TrendFilterAgent implementation |
| Path-dependent simulation reveals wick risk | #528 | 🔄 CONTINUE | Apply framework to all strategies |
| MACD+RSI in positive gamma (short-term) | #531 | 🔄 CONTINUE | Re-validate with corrected methodology |

**Conclusion**: VoterAgent work is complete. RAF is the best practitioner strategy tested - consider integration as 3rd voter.

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

- GEX as overnight/swing filter (Close→Close+1)
- Academic TSMOM (12-month lookback)
- MACD parameter optimization for Sharpe
- GEX + momentum hybrid strategies (overnight holds)

### Continue Working On

- **Ready-Aim-Fire (RAF) integration** (#532) - best practitioner strategy, 0.553 Sharpe
- Weekly KAMA TrendFilterAgent (#529, research in #467)
- Path-dependent wick simulation (#528)
- MACD+RSI in positive gamma re-validation (#531)
- Portfolio-level correlation analysis

### Untested (Optional Future Research)

- Intraday GEX (Open→Close) - practitioner use case (#530)

### Already Complete

- VoterAgent validation (Exp 293)
- MACD+RSI voting integration (#519)
- Methodology corrections (look-ahead, costs)

---

## Quick Links

- **Strategy Results**: [03_strategy_research/results/](03_strategy_research/results/)
- **GEX Research**: [02_gex_research/](02_gex_research/)
- **Archived Experiments**: [99_archived/](99_archived/)
