# Strategy Research

Research documents and experimental results for trading strategy validation.

See [../README.md](../README.md) for consolidated research status (STOP/DONE/CONTINUE).

---

## Research Status Summary (Dec 2025)

| Research | Issue | Status | Finding |
| -------- | ----- | ------ | ------- |
| TSMOM+GEX Hybrid | #516 | 🛑 STOP | Median -2.9% (worse than pure TSMOM) |
| MACD Parameter Optimization | #518 | 🛑 STOP | No robust edge, IS→OOS decay |
| Academic TSMOM (12-mo) | #519 | 🛑 STOP | 19% pass rate, -0.259 avg net Sharpe |
| Weekly KAMA | #467 | 🔄 CONTINUE | Avg Sharpe ~0.75, outperforms weekly MACD |
| MACD+RSI Voting | #519 | ✅ DONE | 44% pass rate, integrated in VoterAgent |
| Ready-Aim-Fire (RAF) | #460 | 🔄 CONTINUE | Outperforms VoterAgent (0.553 Sharpe), 80% win rate |
| Live-rules baseline (Oct 2026) | #574 | 🛑 STOP | Live rules at live timing: Sharpe 0.69 at 5 bps, no alpha over buy-and-hold of the same symbols |

---

## Research Documents

| Document | Issue | Description | Status |
| -------- | ----- | ----------- | ------ |
| [biggunz_research.md](biggunz_research.md) | #461 | BIGGUNZ Triple-Consensus Signal | Completed |
| [raf_research.md](raf_research.md) | #460 | Ready-Aim-Fire Multi-Stochastic | 🔄 CONTINUE |
| [weekly_kama_research.md](weekly_kama_research.md) | #467 | Weekly KAMA MA Crossover | 🔄 CONTINUE |
| [methodology_validation_summary.md](methodology_validation_summary.md) | #523, #495 | Methodology fixes and validation | ✅ DONE |
| [live_rules_baseline.md](live_rules_baseline.md) | #574 | Baseline of the live CLI rules for paper validation | ✅ Complete |

## Results

Experimental results are stored as YAML files in the [results/](results/) folder:

| Results File | Issue | Status | Description |
| ------------ | ----- | ------ | ----------- |
| [macd_stability_results.yaml](results/macd_stability_results.yaml) | #518 | 🛑 STOP | MACD parameter stability - no robust edge |
| [transaction_cost_results.yaml](results/transaction_cost_results.yaml) | #519 | ✅ DONE | Transaction cost methodology validated |
| [tsmom_gex_hybrid_results.yaml](results/tsmom_gex_hybrid_results.yaml) | #516 | 🛑 STOP | TSMOM + GEX hybrid - hypothesis invalidated |
| [tsmom_multi_asset_results.yaml](results/tsmom_multi_asset_results.yaml) | #498 | 🛑 STOP | Multi-asset TSMOM - poor after costs |
| [walk_forward_results.yaml](results/walk_forward_results.yaml) | #523 | ✅ DONE | Walk-forward validation methodology |
| [weekly_kama_results.yaml](results/weekly_kama_results.yaml) | #467 | 🔄 CONTINUE | Weekly KAMA - promising results |
| [biggunz_results.yaml](results/biggunz_results.yaml) | #461 | Archived | BIGGUNZ signal results |
| [raf_results.yaml](results/raf_results.yaml) | #460 | 🔄 CONTINUE | RAF signal results - Outperforms VoterAgent |
| [live_rules_baseline.yaml](results/live_rules_baseline.yaml) | #574 | 🛑 STOP | Live CLI rules, 2009 to 2026-10-09, two modes, three cost levels |

## Key Findings (Dec 2025)

### What Works (DONE/CONTINUE)

1. **MACD+RSI Voting** (#519): 44% pass rate vs 19% for TSMOM - ✅ Integrated in VoterAgent
2. **Weekly KAMA** (#467): Outperforms weekly MACD (avg Sharpe ~0.75) - 🔄 Consider TrendFilterAgent
3. **Ready-Aim-Fire (RAF)** (#460): Multi-stochastic strategy outperformed VoterAgent (0.553 vs 0.481 Sharpe). Robust on Daily timeframe despite practitioner intraday origins.
4. **Methodology Standards**: Look-ahead prevention, turnover-proportional costs - ✅ Applied

### What Doesn't Work (STOP)

1. **TSMOM+GEX Hybrid** (#516): Median -2.9% improvement (makes it worse)
2. **MACD Optimization** (#518): Best OOS Sharpe -0.223 ("least unprofitable")
3. **Academic TSMOM** (#519): Poor after realistic transaction costs

See [02_project_status.md](../../04_development/02_project_status.md) for integration roadmap.
