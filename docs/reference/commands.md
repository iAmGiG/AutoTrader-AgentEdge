# Command Reference

## Environment Setup

- **Python version**: 3.10.16
- **Conda environment**: `conda activate AutoGen`
- **Install dependencies**: `pip install -e .`

## Core Commands

### Continuous Backtesting (V0-V4 Framework)

```bash
# Simple continuous backtest with checkpoint/resume
python scripts/runs/simple_continuous_backtest.py --version V0 --symbol AAPL --year 2024

# Run all versions for a symbol
python scripts/runs/simple_continuous_backtest.py --all-versions --symbol AAPL --year 2024

# Single month testing
python scripts/runs/simple_continuous_backtest.py --version V2 --symbol AAPL --month 1

# Check status of all versions
python scripts/runs/simple_continuous_backtest.py --status

# V4 date obfuscation testing
python scripts/obfuscation_test.py
```

### Single Backtesting (Legacy)

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
# V0-V4 Results Summary (basic)
python scripts/analysis/generate_results_summary.py

# Advanced Metrics Analysis 
python scripts/analysis/generate_results_summary.py --advanced

# Three-way strategy comparison (legacy)
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

## Advanced Metrics Analysis

```bash
# Generate comprehensive analysis of all V0-V4 results
python scripts/analysis/generate_results_summary.py --advanced

# Outputs generated:
# - reports/backtest_analysis_2024.json (comprehensive analysis)
# - reports/strategy_comparison_2024.csv (comparative metrics)
# - reports/continuation_states_2025/ (40 continuation state files)
```

## Recent Performance Results (2024)

### AAPL
- **V0** (Fixed baseline): +8.73% return (24 trades)
- **V1** (News sentiment): -3.83% return
- **V2** (VXX volatility): +5.49% return
- **V3** (Combined heuristic): +2.73% return
- **V4** (LLM reasoning): ~50-60 mins processing time

### AMZN
- **V0**: +22.98% return
- **V1**: +13.24% return
- **V2**: +6.09% return
- **V3**: +11.46% return

### SPY
- **V0**: +6.86% return
- **V1**: +2.70% return
- **V2**: +1.89% return
- **V3**: +1.55% return

## Cache Management

```bash
# Check cache directory structure
ls -la .cache/market_data/

# Consolidated cache files should be named:
# SYMBOL_YYYY-MM-DD_YYYY-MM-DD_source_consolidated.json
# Example: AAPL_2024-01-01_2024-12-31_polygon_consolidated.json

# Clear old checkpoints after cache fixes
rm reports/continuous_backtests/V*/*.json
```

## Legacy Commands (Deprecated)

```bash
# Old batch runner (use backtest service instead)
python scripts/run_backtest_suite.py comprehensive --parallel
```
