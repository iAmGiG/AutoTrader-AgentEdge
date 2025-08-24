# RH2MAS: V0-V4 Sentiment Analysis Framework

## Overview

RH2MAS (Reflective Hybrid-Head Multi-Agent System) is a research framework demonstrating the **gradual introduction of LLM capabilities** in financial trading through a 5-phase sentiment analysis comparison study (V0-V4). Built on [AutoGen](https://github.com/microsoft/autogen) 0.7.x, the system measures the incremental value of increasingly sophisticated sentiment approaches applied to a consistent MACD-based trading strategy.

**🚀 Performance Optimized**: V1-V3 agents now feature 90%+ performance improvements through direct tool access with systematic LLM fallback, enabling full-year continuous backtesting that previously timed out.

## Research Focus: V0-V4 Framework

This project implements a systematic comparison of 5 sentiment approaches:

- **V0 (Baseline)**: Fixed sentiment = 1.0 - Pure MACD strategy
- **V1 (NLP)**: VADER sentiment analysis on news - Mechanical text processing
- **V2 (Market Fear)**: VXX/VIX volatility-based sentiment - Fear gauge approach
- **V3 (Hybrid)**: Weighted combination of V1 + V2 - Heuristic blending
- **V4 (LLM)**: GPT-4o-mini reasoning - Only version using LLM for decisions

All versions use identical MACD crossover signals with AAPL as the test symbol across 5 quarters (2024 Q1-Q4, 2025 Q1).

### Performance Architecture

**Optimized Agent Design (V1-V3)**:
1. **Direct Tool Access** (fast path): Bypass LLM routing when data is cached → 90%+ speed improvement
2. **LLM Tool Calling** (systematic fallback): Use LLM to fetch data when cache is empty → Full functionality 
3. **Neutral Sentiment** (emergency fallback): Graceful degradation in extreme failure cases

This 3-tier approach enables blazing fast performance when cached, while maintaining systematic functionality without cache dependency.

## Simplified Architecture

### Core Agents

1. **StrategyAgent**: Orchestrator combining TechAgent + SentimentAgent[V0-V4]
2. **TechAgent**: Fetches market data and calculates MACD indicators
3. **SentimentAgent**: Implements V0-V4 sentiment approaches (5 versions)
4. **BaseAgent**: Common interface for all agents

### Data Sources (V0-V4 Infrastructure)

- **Market Data**:
  - Primary: [Polygon.io](https://polygon.io) API (5 calls/min, 1-year history)
  - Fallback: [Alpha Vantage](https://www.alphavantage.co/) API (25 calls/day)
- **News Data**:
  - [Google Custom Search](https://developers.google.com/custom-search) API (100 calls/day)
  - Premium sources: WSJ, Bloomberg, Barrons, Reuters

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
  "OPENAI_API_KEY": "sk-...",      // For V4 LLM analysis
  "POLYGON_API_KEY": "...",        // Primary market data
  "ALPHA_VANTAGE_KEY": "...",      // Fallback market data
  "GOOGLE_API_KEY": "...",         // News data
  "GOOGLE_CSE_ID": "..."           // Custom search engine ID
}
```

Note: This file is excluded from version control for security.

## Usage

### V4 Date Obfuscation Testing

```bash
python scripts/obfuscation_test.py
```

### Future: V0-V4 Quarterly Backtesting

```bash
# To be implemented (Issue #187)
python scripts/backtest_v0_v4.py AAPL 2024-01-01 2024-03-31  # Q1 2024
```

## Project Structure

```bash
RH2MAS/
├── src/
│   ├── agents/           # V0-V4 agent implementations
│   ├── tools/            # Data sources (Polygon, Google Search)
│   └── validation/       # V4 obfuscation validator
├── scripts/
│   └── obfuscation_test.py  # V4 validation script
├── docs/
│   ├── architecture/     # V0-V4 framework design
│   ├── implementation/   # Component details
│   └── reference/        # Commands, terminology
├── tests/                # V0-V4 component tests
├── config/               # API configuration (local only)
└── reports/              # V0-V4 analysis results
```

## Documentation

- [V0-V4 Architecture](docs/architecture/V0-V4_ARCHITECTURE.md) - Framework design
- [Project Structure](docs/architecture/project_structure.md) - Repository organization
- [Commands](docs/reference/commands.md) - Setup and usage
- [Terminology](docs/reference/terminology.md) - Glossary
- [Troubleshooting](docs/reference/troubleshooting.md) - Common issues

## Development Status

### Completed ✅

- Repository cleanup (Issues #186, #190-193)
- Simplified multi-agent architecture
- V0-V4 framework design
- Data infrastructure (Polygon.io + Google Search)

### In Progress 🚧

- V0-V4 sentiment agent implementations (Issues #181-185)
- Quarterly testing framework (Issue #187)
- Statistical comparison analysis

### Repository Cleanup Note

All deprecated code from the original complex multi-agent system has been moved to an untracked `deprecated/` folder, preserving it for reference while keeping the main codebase focused on the V0-V4 framework.

## Academic Context

This is an academic research project exploring the gradual introduction of LLM capabilities in financial trading decisions. The V0-V4 framework provides measurable evidence of the incremental value each approach adds to a consistent base strategy.

## License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
