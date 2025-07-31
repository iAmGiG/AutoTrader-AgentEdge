# Command Reference

## Environment Setup

- **Python version**: 3.10.16
- **Conda environment**: `conda activate AutoGen`
- **Install dependencies**: `pip install -e .`

## Core Commands

### Single Backtesting

```bash
# Single backtest for specific symbol/dates
python scripts/backtest_mas.py SYMBOL START END
# Example: python scripts/backtest_mas.py AAPL 2024-01-01 2024-01-31
```

### Automated Backtesting Service

```bash
# Start intelligent backtest service (recommended for multiple tests)
python scripts/start_backtest_service.py

# Market conditions report
python scripts/generate_market_conditions_report.py --resume --parallel

# Skip backtests, generate report from existing data
python scripts/generate_market_conditions_report.py --skip-backtests
```

### Testing

```bash
# Run all unit tests
python -m unittest discover tests

# Run specific test
python -m pytest tests/test_market_data_tool.py
```

### Analysis Tools

```bash
# Three-way strategy comparison
python scripts/validation/analyze_cached_performance.py

# Build FMP data cache
python scripts/utils/build_fmp_cache.py

# Run obfuscation validation
python scripts/validation/run_obfuscation_validation.py
```

### Interactive Tools

```bash
# Sentiment agent CLI
python sentiment_cli.py
```

## Service Management

### Screen (Recommended for Remote)

```bash
# Start service in screen
python scripts/start_backtest_service.py
# Choose option 1 (screen)

# Reconnect to view
screen -r backtest_service

# Detach (keep running): Ctrl+A, then D
```

### Nohup (Alternative)

```bash
# Start with nohup
python scripts/start_backtest_service.py
# Choose option 3 (nohup)

# View logs
tail -f .cache/backtests/nohup.out
```

## Legacy Commands (Deprecated)

```bash
# Old batch runner (use backtest service instead)
python scripts/run_backtest_suite.py comprehensive --parallel
```
