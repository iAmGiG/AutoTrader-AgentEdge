# RH2MAS: V0-V4 Sentiment Analysis Framework

## Overview

RH2MAS (Reflective Hybrid-Head Multi-Agent System) is a research framework demonstrating the **gradual introduction of LLM capabilities** in financial trading through a 5-phase sentiment analysis comparison study (V0-V4). Built on [AutoGen](https://github.com/microsoft/autogen) 0.7.x, the system measures the incremental value of increasingly sophisticated sentiment approaches applied to a consistent MACD-based trading strategy.

**🚀 Production Ready**: Unified cache-optimized agent system with 90%+ performance improvements. Complete continuous backtesting framework with checkpoint/resume capabilities for V4 LLM processing.

## Research Focus: V0-V4 Framework

This project implements a systematic comparison of 5 sentiment approaches:

- **V0 (Baseline)**: Fixed sentiment = 1.0 - Pure MACD strategy
- **V1 (NLP)**: VADER sentiment analysis on news - Mechanical text processing
- **V2 (Market Fear)**: VXX/VIX volatility-based sentiment - Fear gauge approach
- **V3 (Hybrid)**: Weighted combination of V1 + V2 - Heuristic blending
- **V4 (LLM)**: GPT-4o-mini reasoning - Only version using LLM for decisions

All versions use identical MACD crossover signals across multiple symbols (AAPL, SPY, QQQ, AMZN, etc.) with full-year 2024 backtesting capability.

### Performance Architecture

**Unified Cache-Optimized Agents (V0-V4)**:
1. **Direct Tool Access** (cache hit): Instant data retrieval from UnifiedCacheManager → 90%+ speed improvement
2. **LLM Tool Calling** (cache miss): Systematic data fetching with LLM routing → Full functionality 
3. **Neutral Sentiment** (emergency fallback): Graceful degradation in extreme failure cases

**V4 LLM Processing**:
- Weekly batch processing with date sanitization (prevents training data leakage)
- Checkpoint/resume system for long-running backtests
- Incremental progress tracking with research artifact preservation

This architecture enables instant V0-V3 responses when cached, while V4 processes intelligently with temporal safeguards.

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
  - **UnifiedCacheManager**: Smart caching with automatic source routing
- **News Data**:
  - [Google Custom Search](https://developers.google.com/custom-search) API (100 calls/day)
  - Premium sources: WSJ, Bloomberg, Barrons, Reuters
  - **NewsGovernor**: Smart sampling reduces API usage 80-90%

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

### Continuous Backtesting (Primary Interface)

```bash
# Check status of all V0-V4 backtests
python scripts/runs/backtest.py --status

# Run all versions for full-year 2024
python scripts/runs/backtest.py --all-versions

# Test specific version
python scripts/runs/backtest.py --version V4

# Monthly testing
python scripts/runs/backtest.py --all-versions --month 1  # January 2024
```

### V4 Date Obfuscation Testing

```bash
python scripts/validation/obfuscation_test.py
```

### Advanced Analysis

```bash
# Generate comprehensive metrics report
python scripts/analysis/generate_results_summary.py --advanced
```

## Project Structure

```bash
RH2MAS/
├── src/
│   ├── agents/           # Unified V0-V4 agent implementations
│   ├── tools/            # Data sources with unified caching
│   │   ├── cache/        # UnifiedCacheManager system
│   │   └── data_sources/ # Market data and news tools
│   └── utils/            # Date sanitizer, metrics system
├── scripts/
│   ├── runs/             # Primary testing interface
│   ├── analysis/         # Results analysis and reporting
│   └── validation/       # V4 obfuscation testing
├── docs/
│   ├── architecture/     # V0-V4 framework design
│   ├── implementation/   # Component details
│   └── reference/        # Commands, terminology
├── reports/
│   └── continuous_backtests/  # V0-V4 results and checkpoints
├── config/               # API configuration (local only)
└── .cache/               # Unified caching system
```

## Documentation

- [V0-V4 Architecture](docs/architecture/V0-V4_ARCHITECTURE.md) - Framework design
- [Project Structure](docs/architecture/project_structure.md) - Repository organization
- [Commands](docs/reference/commands.md) - Setup and usage
- [Terminology](docs/reference/terminology.md) - Glossary
- [Troubleshooting](docs/reference/troubleshooting.md) - Common issues

## Development Status

### Completed ✅

- **V0-V4 Framework**: Complete sentiment analysis comparison system
- **Unified Agent System**: Cache-optimized agents with 90%+ performance improvement
- **Continuous Backtesting**: Full-year testing capability with checkpoint/resume
- **Advanced Metrics**: Comprehensive performance analysis with statistical validation
- **Cache Unification**: UnifiedCacheManager with smart source routing
- **Date Sanitization**: V4 temporal knowledge leakage prevention
- **Multi-Symbol Testing**: AAPL, SPY, QQQ, AMZN validation complete

### Active Development 🚧

- V4 Performance optimization (Issue #221) - Reduce LLM processing time
- Portfolio-level statistics enhancements (Issue #162)
- Executive reporting tools (Issue #130)

### Repository Cleanup Note

All deprecated code from the original complex multi-agent system has been moved to an untracked `deprecated/` folder, preserving it for reference while keeping the main codebase focused on the V0-V4 framework.

## Academic Context

This is an academic research project exploring the gradual introduction of LLM capabilities in financial trading decisions. The V0-V4 framework provides measurable evidence of the incremental value each approach adds to a consistent base strategy.

## License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
