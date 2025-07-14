# RH2MAS: Reflective Hybrid-Head Multi-Agent System

## Overview

RH2MAS is a financial analysis system using a multi-agent architecture with AutoGen 0.6.x. The system employs specialized agents working together to analyze market sentiment, technical indicators, and make trading decisions.

## Key Features

> NOTE: not all features have been implemented yet, as further testing is required.

- **Multi-Agent Architecture**: Sentiment, Technical, Strategy, and Coordinator agents
- **Enhanced Sentiment Analysis**: News aggregation with VXX volatility fallback
- **Technical Analysis**: MACD, RSI, Bollinger Bands, and pattern recognition
- **Smart Caching**: Reduces API calls with market data and news caching
- **Comprehensive Backtesting**: Organized output with LLM reasoning capture

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run a single backtest
python scripts/backtest_mas.py AAPL 2024-01-01 2024-01-31

# Run test suite
python scripts/run_backtest_suite.py quick
```

## Project Structure

```bash
RH2MAS/
├── src/
│   ├── agents/         # Agent implementations
│   ├── core/          # Core system components
│   ├── tools/         # Data sources and tools
│   └── utils/         # Utilities and helpers
├── scripts/           # Executable scripts
├── docs/              # Documentation
├── config/            # Configuration files
└── .cache/           # Cached data and results
```

## Current Agents

1. **SentimentAgent**: Analyzes news sentiment with VXX fallback
2. **TechAgent**: Performs technical analysis (MACD fix implemented)
3. **StrategyAgent**: Makes trading decisions (sentiment >= 0)
4. **CoordinatorAgent**: Orchestrates multi-agent collaboration

## Recent Updates (2025-07-11)

- ✅ Fixed MACD calculation (now uses MACD line, not histogram)
- ✅ Added news caching with relevance filtering
- ✅ Consolidated documentation
- ✅ Enhanced strategy with VXX fallback

## Documentation

- [System Architecture](docs/CURRENT_ARCHITECTURE.md) - Current system design
- [Agent Documentation](docs/implementation/agents/) - Individual agent guides
- [AutoGen Reference](docs/autogen_core_reference/) - Framework documentation
- [API Documentation](docs/implementation/tools/) - Tool and API references

## Configuration

API keys must be stored in `config/config.json` (not included in repo for security):

1. Create the config directory: `mkdir -p config`
2. Create `config/config.json` with your API keys:

```json
{
  "openai_api_key": "sk-...",
  "alpha_vantage_api_key": "...",
  "newsapi_key": "...",
  "finnhub_api_key": "..."
}
```

**Important**:

- `config/config.json` is in `.gitignore` and should NEVER be committed
- Keep your API keys secure and private
- The system uses `ConfigLoader` to load keys at runtime

## Environment Setup

```bash
# Python 3.10+ required
conda create -n RH2MAS python=3.10
conda activate RH2MAS

# Install requirements
pip install -e .
```

## API Limitations

- **Alpha Vantage**: 25 calls/day (free tier)
- **Yahoo Finance**: Rate limited, but primary source
- **Solution**: Aggressive caching (24hr market data, 7-day news)

## Performance

Example backtest results:

- Processing: ~80 seconds per symbol/month
- Cache hit rate: >90% after initial run
- LLM calls: 2-3 per trading day

## Contributing

This is an active research project. Key areas for contribution:

- Additional data sources
- Risk agent implementation
- Real-time trading capabilities
- Performance optimizations

## License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
