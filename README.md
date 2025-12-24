# AutoTrader: Multi-Agent Trading System

**Copyright (C) 2024-2025 Chris R. (iAmGiG)** | Licensed under [AGPL-3.0](LICENSE) | See [NOTICE](NOTICE)

## Powered by AgentEdge - Autonomous AI agents seeking trading edge

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![AutoGen](https://img.shields.io/badge/AutoGen-0.7.x-green.svg)](https://github.com/microsoft/autogen)
[![Alpaca](https://img.shields.io/badge/Broker-Alpaca-yellow.svg)](https://github.com/alpacahq/alpaca-py)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)

---

## Disclaimer

**THIS SOFTWARE IS FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY.**

- **Not Financial Advice**: This system does not provide financial, investment, or trading advice
- **Use at Your Own Risk**: Trading involves substantial risk of loss
- **No Warranties**: Provided "as-is" without guarantees of accuracy or profitability
- **Past Performance**: Walk-forward validated results do not guarantee future performance

---

## Overview

**AutoTrader** is a research-driven trading platform featuring a multi-agent AI architecture powered by Microsoft AutoGen. The system implements walk-forward validated strategies with rigorous statistical testing and human oversight for paper/live trading via Alpaca Markets.

**Core Philosophy**: Validated momentum + regime filtering + human decision making > curve-fit technical indicators

### Key Research Findings (Dec 2025)

Recent walk-forward validation experiments have yielded several key insights:

- **GEX is a Powerful Regime Filter**: Standalone strategies like TSMOM see a dramatic performance improvement when filtered by the GEX (Gamma Exposure) regime. For example, TSMOM's Sharpe ratio improves from -0.456 to **1.282** when only trading during positive gamma periods.
- **New Validated Strategies**: Weekly KAMA has been validated as a robust, low-frequency trend filter, outperforming a weekly MACD baseline.
- **S² Scaling for GEX**: The academic S² scaling for GEX provides more stable, comparable values across assets and is recommended for adoption.

### Validated Strategy Performance

Out-of-sample (OOS) results from the [walk-forward validation framework](docs/08_research/03_strategy_research/walk_forward_results.yaml):

| Strategy         | Out-of-Sample Sharpe | Period    | Validation Status              |
|------------------|----------------------|-----------|--------------------------------|
| TSMOM-12M (Avg)  | 0.85+                | 2023-2024 | ✅ Passed                      |
| Weekly KAMA (Avg)| ~0.75                | 2016-2024 | ✅ Passed                      |
| MACD+RSI (QQQ)   | 0.468                | 2021-2024 | ❌ Failed (65% degradation)    |

**Methodology**: Walk-forward split with out-of-sample testing. Benjamini-Hochberg FDR correction applied to control for p-hacking.

**Note**: Past performance does not guarantee future results. All strategies validated using out-of-sample testing to minimize overfitting risk.

### Production Status

| Component | Status |
|-----------|--------|
| VoterAgent | Production Ready |
| CLI Trade Assistant | Complete |
| Alpaca Integration | Operational |
| Position Management | Complete |
| Trading Cycle | Complete |
| ScannerAgent | In Development |
| RiskAgent | In Development |
| ExecutorAgent | In Development |

---

## Core Agents

### VoterAgent (Production Ready)

Location: `src/autogen_agents/voter_agent.py`

- **MACD Signal Generation**: Optimized 13/34/8 Fibonacci parameters
- **RSI Momentum Analysis**: 14-period with 30/70 thresholds
- **Consensus Voting**: Strong signals when both indicators agree
- **Validated Performance**: 0.856 Sharpe ratio over 2024-2025

### Agents in Development

- **ScannerAgent**: Market opportunity identification
- **RiskAgent**: Position sizing and risk management
- **ExecutorAgent**: Trade execution via Alpaca API
- **TradingOrchestrator**: Multi-agent coordination

---

## Installation

```bash
# Python 3.12+ required
conda create -n AutoTrader python=3.12
conda activate AutoTrader
pip install -e .
```

## Configuration

Create `config/config.yaml` with API credentials:

```yaml
POLYGON_IO: "your_key"           # Required: Market data
ALPHA_VANTAGE_KEY: "your_key"    # Required: Fallback data
ALPACA_PAPER_API_KEY: "your_key" # Required: Paper trading
ALPACA_PAPER_SECRET: "your_key"  # Required: Paper trading
ALPACA_ENDPOINT: "https://paper-api.alpaca.markets/v2"

# Optional - VoterAgent uses pure math, no LLM required
OPEN_AI_KEY: "sk-..."
```

---

## Quick Start

### Interactive CLI

```bash
python main.py

# Example session:
> buy 10 AAPL              # Execute trade
> show portfolio           # View positions
> check my alerts          # Position alerts
> /schedule                # Scheduler management
> /help                    # All commands
```

### Daemon Mode

```bash
python main.py --daemon

# Runs twice daily:
# - Morning: 9:20 AM ET (reconciliation)
# - Evening: 3:50 PM ET (review)
```

---

## CLI Commands

### Trading

| Command | Description |
|---------|-------------|
| `buy SYMBOL QTY` | Place buy order |
| `sell SYMBOL QTY` | Place sell order |
| `cancel ORDER_ID` | Cancel order |

### Information

| Command | Description |
|---------|-------------|
| `show portfolio` | Portfolio summary |
| `show positions` | Open positions with P&L |
| `show orders` | Order history |
| `show account` | Account details |

### Configuration

| Command | Description |
|---------|-------------|
| `show timeframe` | Current timeframe |
| `set timeframe 1d` | Change timeframe |
| `show config-file` | View YAML config |
| `show watchlist` | Scanner symbols |

### Workflow

| Command | Description |
|---------|-------------|
| `morning-routine` | Morning scan and analysis |
| `evening-summary` | End-of-day report |
| `monitor` | Watch positions for exits |
| `forward-test start NAME` | Start validation test |

---

## Project Structure

```text
AutoTrader-AgentEdge/
├── src/
│   ├── autogen_agents/     # AI agents (AutoGen framework)
│   │   ├── voter_agent.py  # Production MACD+RSI voting
│   │   ├── base_agent.py   # Base agent class
│   │   └── ...             # Other agents (in development)
│   ├── trading/            # Trading infrastructure
│   │   ├── broker/         # Alpaca integration
│   │   ├── orders/         # Order management
│   │   ├── positions/      # Position tracking
│   │   └── scheduling/     # Daily routines
│   ├── data_sources/       # Market data
│   └── cli/                # CLI tools
├── config/                 # API credentials (local only)
├── config_defaults/        # Default YAML configs
├── docs/                   # Documentation
├── reports/                # Trading reports
└── tests/                  # Test suite
```

---

## Documentation

| Topic | Location |
|-------|----------|
| Architecture | [docs/02_architecture/](docs/02_architecture/) |
| Development | [docs/04_development/](docs/04_development/) |
| Design Decisions | [docs/05_decisions/](docs/05_decisions/) |
| Features | [docs/06_features/](docs/06_features/) |
| Testing | [docs/07_testing/](docs/07_testing/) |

---

## Development

### Testing

```bash
# Unit tests
python -m pytest tests/ -v

# Code quality
ruff check src/
black --check src/

# VoterAgent validation
python -c "from src.autogen_agents.voter_agent import VoterAgent; print('OK')"
```

### Contributing

1. Pick an issue from [GitHub Issues](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues)
2. Create a feature branch
3. Make changes following [docs/05_decisions/](docs/05_decisions/)
4. Submit PR to `development` branch

---

## License

AGPL-3.0 - See LICENSE file for details.
