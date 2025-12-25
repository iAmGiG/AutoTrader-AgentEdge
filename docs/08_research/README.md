# Research Documentation

Research documents, experimental results, and validation studies for AutoTrader strategies.

## Contents

| Path | Description |
|------|-------------|
| [01_broker_api_comparison_2025.md](01_broker_api_comparison_2025.md) | Broker API feature comparison and evaluation |
| [02_gex_research/](02_gex_research/) | Gamma Exposure (GEX) research and experiments |
| [03_strategy_research/](03_strategy_research/) | Trading strategy validation and backtests |
| [99_archived/](99_archived/) | Completed and deprecated experiments |

## Quick Links

### Active Research

- **GEX Integration**: See [02_gex_research/README.md](02_gex_research/README.md)
- **Strategy Validation**: See [03_strategy_research/README.md](03_strategy_research/README.md)

### Key Findings (Dec 2025)

From [03_strategy_research/methodology_validation_summary.md](03_strategy_research/methodology_validation_summary.md):

1. **MACD Stability** (#518): Parameters stable across tech stocks
2. **Transaction Costs** (#519): ~2bp slippage impact on Sharpe
3. **TSMOM+GEX Hybrid** (#516): GEX improves TSMOM in positive regimes
4. **Weekly KAMA** (#467): Outperforms weekly MACD (avg Sharpe ~0.75)

### Archived Experiments

Completed validation studies in [99_archived/](99_archived/):

- Experiment 293: VoterAgent validation (0.856 Sharpe)
- Extended period analysis (2024-2025)
- MACD optimization studies
