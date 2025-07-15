# Scripts Directory

This directory contains executable scripts for running backtests, generating reports, and analyzing results.

## Directory Structure

```bash
scripts/
├── backtest_service/     # Intelligent backtest service with rate limit management
│   ├── backtest_service.py
│   ├── start_backtest_service.py
│   └── run_backtest_service.sh
├── backtest_mas.py       # Main multi-agent system backtesting script
├── run_backtest_suite.py # Batch runner for multiple backtests
├── backtest_configs.yaml # Configuration for test suites
└── aggregate_results.py  # Results aggregation and analysis
```

## Main Scripts

### Core Backtesting

- `backtest_mas.py` - Main multi-agent system backtesting script
- `run_backtest_suite.py` - Run multiple backtests with different configurations
- `backtest_configs.yaml` - Define test suites and parameters
- `aggregate_results.py` - Aggregate and analyze backtest results

### Backtest Service

- `backtest_service/` - Intelligent service for managing long-running backtests with rate limit handling
- See `backtest_service/README.md` for detailed documentation

## Usage Examples

### Single Backtest

```bash
python scripts/backtest_mas.py AAPL 2024-01-01 2024-12-31
```

### Batch Backtesting

```bash
python scripts/run_backtest_suite.py comprehensive --parallel
```

### Start Backtest Service

```bash
python scripts/backtest_service/start_backtest_service.py
```

### Aggregate Results

```bash
python scripts/aggregate_results.py
```

## Notes

- Test scripts have been moved to the `tests/` directory
- Template files have been moved to `docs/templates/`
- Old CLI test files have been removed
