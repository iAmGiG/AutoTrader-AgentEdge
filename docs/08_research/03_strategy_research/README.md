# Strategy Research

Research documents and experimental results for trading strategy validation.

## Research Documents

| Document | Issue | Description | Status |
|----------|-------|-------------|--------|
| [biggunz_research.md](biggunz_research.md) | #461 | BIGGUNZ Triple-Consensus Signal | Completed |
| [raf_research.md](raf_research.md) | #460 | Ready-Aim-Fire Multi-Stochastic | Completed |
| [weekly_kama_research.md](weekly_kama_research.md) | #467 | Weekly KAMA MA Crossover | Completed |
| [methodology_validation_summary.md](methodology_validation_summary.md) | #523, #495 | Methodology fixes and validation | Completed |

## Results

Experimental results are stored as YAML files in the [results/](results/) folder:

| Results File | Issue | Description |
|--------------|-------|-------------|
| [macd_stability_results.yaml](results/macd_stability_results.yaml) | #518 | MACD parameter stability across assets |
| [transaction_cost_results.yaml](results/transaction_cost_results.yaml) | #519 | Transaction cost impact analysis |
| [tsmom_gex_hybrid_results.yaml](results/tsmom_gex_hybrid_results.yaml) | #516 | TSMOM + GEX hybrid strategy |
| [tsmom_multi_asset_results.yaml](results/tsmom_multi_asset_results.yaml) | #498 | Multi-asset TSMOM backtest |
| [walk_forward_results.yaml](results/walk_forward_results.yaml) | #523 | Walk-forward validation |
| [weekly_kama_results.yaml](results/weekly_kama_results.yaml) | #467 | Weekly KAMA crossover results |
| [biggunz_results.yaml](results/biggunz_results.yaml) | #461 | BIGGUNZ signal results |
| [raf_results.yaml](results/raf_results.yaml) | #460 | RAF signal results |

## Key Findings (Dec 2025)

From methodology fixes (#523):

1. **MACD Stability** (#518): Parameters stable across tech stocks
2. **Transaction Costs** (#519): ~2bp slippage impact on Sharpe
3. **TSMOM+GEX Hybrid** (#516): GEX improves TSMOM in positive regimes
4. **Weekly KAMA** (#467): Outperforms weekly MACD (avg Sharpe ~0.75)

See [02_project_status.md](../../04_development/02_project_status.md) for integration roadmap.
