# RH2MAS Backtesting Suite

## Overview

The RH2MAS backtesting system has been consolidated into a unified, configuration-driven suite that replaces multiple redundant scripts. The new system provides:

- **Configuration-based test definitions** using YAML
- **Multiple test suites** (quick, comprehensive, extended, all)
- **Parallel execution** support for faster testing
- **Progress tracking** and state management
- **Resume capability** for interrupted runs
- **Automatic result aggregation**

## Quick Start

```bash
# Run quick tests (for development/debugging)
python scripts/run_backtest_suite.py quick

# Run comprehensive tests in parallel (market stress periods)
python scripts/run_backtest_suite.py comprehensive --parallel

# Run extended tests for specific symbols
python scripts/run_backtest_suite.py extended --symbols AAPL,MSFT,NVDA

# List available test suites
python scripts/run_backtest_suite.py --list

# Resume an interrupted run
python scripts/run_backtest_suite.py --resume
```

## Core Components

### 1. Primary Scripts (Keep These)

- **`backtest_mas.py`** - Core backtesting engine
  - Implements MACD crossover strategy with sentiment filtering
  - Integrates with multi-agent system
  - Saves results to CSV files
  - Usage: `python backtest_mas.py SYMBOL START END`

- **`aggregate_results.py`** - Results analyzer
  - Loads all CSV files from cache directory
  - Calculates aggregate statistics
  - Generates comprehensive reports
  - Automatically run after test suites

- **`run_backtest_suite.py`** - Unified batch runner (NEW)
  - Replaces all other batch runners
  - Configuration-driven test execution
  - Parallel processing support
  - State management and resume capability

### 2. Configuration File

**`backtest_configs.yaml`** defines all test scenarios:

```yaml
# Test definitions organized by category
quick_tests:
  - name: "Test Name"
    symbol: "AAPL"
    start: "2025-06-20"
    end: "2025-06-25"
    description: "Test description"

# Test suite configurations
test_suites:
  quick:
    tests: ["quick_tests"]
    timeout_minutes: 2
    parallel: false
    description: "Quick validation tests"
```

### 3. Deprecated Scripts (To Be Removed)

The following scripts are now redundant and should be removed:

- `batch_backtest.py` - Basic batch runner → Use `run_backtest_suite.py`
- `run_comprehensive_backtest.py` - Volatile period tests → Use `comprehensive` suite
- `run_extended_backtest.py` - Long duration tests → Use `extended` suite
- `test_single_backtest.py` - Single test runner → Use `backtest_mas.py` directly
- `create_sample_extended_results.py` - Demo data generator → Not needed

## Test Suites

### Quick Suite

- **Purpose**: Fast validation and debugging
- **Duration**: ~2 minutes per test
- **Use When**: Testing code changes, debugging issues

### Comprehensive Suite

- **Purpose**: Test strategy during market stress periods
- **Includes**: COVID crash, 2018 corrections, 2022 bear market, etc.
- **Duration**: ~5 minutes per test
- **Use When**: Validating strategy performance in volatile conditions

### Extended Suite

- **Purpose**: Long-duration backtests
- **Includes**: Full year and 6-month periods
- **Duration**: ~10 minutes per test
- **Use When**: Analyzing strategy over extended timeframes

### All Suite

- **Purpose**: Complete system validation
- **Includes**: All tests from all suites
- **Use When**: Final validation before deployment

## Advanced Features

### Parallel Execution

```bash
# Enable parallel execution with custom worker count
python run_backtest_suite.py comprehensive --parallel --workers 8
```

### Symbol Filtering

```bash
# Run tests only for specific symbols
python run_backtest_suite.py extended --symbols AAPL,MSFT,GOOGL
```

### Resume Interrupted Runs

```bash
# If a run is interrupted (Ctrl+C), resume from where it left off
python run_backtest_suite.py --resume

# Clear saved state and start fresh
python run_backtest_suite.py --clear-state
```

### Custom Configuration

```bash
# Use a custom configuration file
python run_backtest_suite.py quick --config my_tests.yaml
```

## Output Structure

All results are saved to `.cache/backtests/`:

```
.cache/backtests/
├── SYMBOL_trades_START_END.csv      # Individual trade records
├── SYMBOL_equity_START_END.csv      # Equity curve data
├── SYMBOL_metrics_START_END.csv     # Performance metrics
├── suite_summary_*.json             # Test suite execution summary
├── aggregate_summary.md             # Comprehensive analysis report
└── aggregate_summary.json           # Machine-readable aggregate data
```

## Adding New Tests

1. Edit `backtest_configs.yaml`
2. Add test definitions to appropriate section
3. Update test suite configurations if needed

Example:

```yaml
comprehensive_tests:
  - name: "New Market Event"
    symbol: "SPY"
    start: "2024-07-01"
    end: "2024-09-30"
    description: "Testing new market conditions"
```

## Migration Guide

To migrate from old scripts:

1. **Instead of `python batch_backtest.py`**
   → Use `python run_backtest_suite.py quick`

2. **Instead of `python run_comprehensive_backtest.py`**
   → Use `python run_backtest_suite.py comprehensive --parallel`

3. **Instead of `python run_extended_backtest.py`**
   → Use `python run_backtest_suite.py extended --parallel`

4. **Instead of hardcoding test configs in scripts**po
   → Add them to `backtest_configs.yaml`

## Troubleshooting

- **Tests timing out**: Increase `timeout_minutes` in config
- **API rate limits**: Reduce parallel workers or add delays
- **Memory issues**: Disable parallel execution
- **Interrupted runs**: Use `--resume` to continue

## Future Enhancements

- Real-time progress dashboard
- Integration with visualization tools
- Parameter optimization support
- Cloud execution support
- Performance comparison across strategies
