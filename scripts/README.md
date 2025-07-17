# Scripts Directory

This directory contains executable scripts for running backtests, generating reports, and analyzing results.

## Directory Structure

```bash
scripts/
├── analysis/                    # Analysis and reporting tools
│   ├── analyze_cache.py        # Analyzes cached market data coverage
│   ├── analyze_scan_performance.py  # Evaluates scan results
│   └── aggregate_results.py    # Aggregates backtest results
├── backtest_service/           # Intelligent backtest service
│   ├── backtest_service.py
│   ├── start_backtest_service.py
│   └── run_backtest_service.sh
├── backtest_mas.py            # Main multi-agent system backtesting
├── run_backtest_suite.py      # Batch runner for multiple backtests
├── run_daily_scan.py          # Daily mechanical strategy scanner
├── run_multi_timeframe_scan.py # Multi-date scanner
└── backtest_configs.yaml      # Configuration for test suites
```

## Main Scripts

### Mechanical Strategy (Option 1)

- `run_daily_scan.py` - Daily portfolio scanner with TA + Market Heat filtering
- `run_multi_timeframe_scan.py` - Multi-date scanner for historical analysis

### Core Backtesting

- `backtest_mas.py` - Main multi-agent system backtesting script
- `run_backtest_suite.py` - Run multiple backtests with different configurations
- `backtest_configs.yaml` - Define test suites and parameters

### Analysis Tools

- `analysis/analyze_cache.py` - Check cached market data coverage
- `analysis/analyze_scan_performance.py` - Evaluate mechanical strategy performance
- `analysis/aggregate_results.py` - Aggregate and analyze backtest results

### Backtest Service

- `backtest_service/` - Intelligent service for managing long-running backtests with rate limit handling
- See `backtest_service/README.md` for detailed documentation

## Usage Examples

### Mechanical Strategy Scanning

```bash
# Single day scan
python scripts/run_daily_scan.py --date 2025-07-10 --heat-threshold -0.5

# Multi-day scan
python scripts/run_multi_timeframe_scan.py --start 2025-07-01 --end 2025-07-10
```

### Backtesting

```bash
# Single backtest
python scripts/backtest_mas.py AAPL 2024-01-01 2024-12-31

# Batch backtesting
python scripts/run_backtest_suite.py comprehensive --parallel

# Start backtest service
python scripts/backtest_service/start_backtest_service.py
```

### Analysis

```bash
# Check data availability
python scripts/analysis/analyze_cache.py

# Analyze scan performance
python scripts/analysis/analyze_scan_performance.py

# Aggregate backtest results
python scripts/analysis/aggregate_results.py
```

## Notes

- Test scripts have been moved to the `tests/` directory
- Template files have been moved to `docs/templates/`
- Old CLI test files have been removed
