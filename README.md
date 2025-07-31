# RH2MAS: Reflective Hybrid-Head Multi-Agent System

## Overview

RH2MAS is a financial analysis research project exploring multi-agent architectures using [AutoGen](https://github.com/microsoft/autogen) 0.7.x. The system demonstrates how LLM-powered and rule-based agents can work together for trading strategy analysis.

## Research Focus

This project implements a three-way strategy comparison framework:

- **Buy & Hold**: Baseline reference strategy
- **Mechanical**: MACD histogram crossover with sentiment >= 0 threshold
- **LLM**: AI-powered decision making with structured explanations

The system is designed to validate whether LLM-enhanced trading strategies provide advantages over traditional approaches.

## Architecture

### Agent Implementation Status

#### LLM-Powered Agents (Use GPT-4o-mini)

1. **SentimentAgent**: Analyzes news sentiment using LLM, falls back to VXX volatility when no news
2. **TechAgent**: Interprets pre-calculated technical indicators using LLM
3. **LLMStrategyAgent**: Makes trading decisions with structured explanations

#### Experimental/Future Features

- **MarketIntelligenceAgent**: Ranks multiple stocks based on market conditions (not used in core comparison)

#### Rule-Based Agents (No LLM Required)

1. **StrategyAgent**: MACD histogram crossover with sentiment >= 0 threshold
2. **BuyHoldStrategy**: Simple baseline for comparison
3. **CoordinatorAgent**: Orchestrates other agents (no direct LLM usage)

#### Placeholder

1. **RiskAgent**: Not implemented (TODO comment only)

### Core Features

- **Multi-Source News**: Fetches from [Alpha Vantage](https://www.alphavantage.co/), [Finnhub](https://finnhub.io/), [NewsAPI](https://newsapi.org/) (with fallbacks)
- **Sentiment Sources**: News analysis when available, VXX volatility index as primary fallback (frequently used)
- **Technical Analysis**: Uses MACD histogram (12/26 EMA difference minus signal line) for trading signals. Additional indicators available: RSI, Bollinger Bands, Fibonacci retracements
- **Price Data**: Uses only closing prices for all trading decisions
- **Backtesting Framework**: Historical strategy performance evaluation on cached data
- **Data Caching**: Automatic caching to reduce API calls (freemium tier friendly)

## Installation

```bash
# Python 3.10+ required
conda create -n RH2MAS python=3.10
conda activate RH2MAS

# Install dependencies
pip install -e .
```

## Configuration

Create `config/config.json` with required API keys:

```json
{
  "openai_api_key": "sk-...",
  "alpha_vantage_key": "...",
  "newsapi_key": "...",
  "finnhub_key": "..."
}
```

Note: This file is excluded from version control for security.

## Usage

### Single Backtest

```bash
python scripts/backtest.py SYMBOL START_DATE END_DATE
# Example: python scripts/backtest.py AAPL 2023-01-01 2023-12-31
```

### Automated Backtest Service

```bash
python scripts/run_experiments.py
```

### Three-Way Strategy Analysis

```bash
python scripts/analyze_results.py
```

### Parallel Strategy Comparison Demo

```bash
python scripts/agents/demo_parallel.py SYMBOL START END
```

## Project Structure

```bash
RH2MAS/
├── src/
│   ├── agents/           # Agent implementations
│   ├── tools/            # Data sources and processing tools
│   ├── utils/            # Utilities including ParallelStrategyTester
│   └── validation/       # Validation tools (ObfuscationValidator)
├── scripts/
│   ├── backtest.py       # Primary backtesting script
│   ├── analyze_results.py # Results analysis
│   ├── run_experiments.py # Batch experiments
│   ├── agents/           # Agent operation scripts
│   └── tools/            # Data and validation tools
├── docs/                 # Documentation
├── config/               # Configuration directory (create locally)
└── reports/              # Analysis reports and guides
```

## Documentation

- [Terminology](docs/terminology.md) - Complete terminology and acronym reference
- [Project Structure](docs/project_structure.md) - Detailed directory structure
- [Commands](docs/commands.md) - All commands and setup instructions
- [Troubleshooting](docs/troubleshooting.md) - Common issues and solutions

## API Services

- [Alpha Vantage](https://www.alphavantage.co/documentation/) - News and market data (freemium)
- [Finnhub](https://finnhub.io/docs/api) - Financial data (freemium)
- [NewsAPI](https://newsapi.org/docs) - General news (freemium)
- [OpenAI](https://platform.openai.com/docs/api-reference) - LLM services (usage-based)

The system implements caching to work efficiently with freemium API tiers.

## Academic Context

This is an academic research project exploring multi-agent systems for financial analysis. The focus is on validating whether LLM-enhanced decision-making provides advantages over traditional rule-based approaches.

## License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
