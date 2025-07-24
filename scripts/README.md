# Scripts Directory

This directory contains executable scripts organized by functionality for running backtests, analyzing results, and demonstrating strategies.

## Directory Structure

```bash
scripts/
├── backtesting/                 # Core backtesting functionality
│   ├── backtest_mas.py         # Main multi-agent system backtesting engine
│   ├── run_backtest_suite.py   # Batch runner for multiple backtests  
│   └── backtest_configs.yaml   # Configuration for test suites
│
├── strategies/                  # Strategy implementations and demos
│   ├── mechanical/             # Mechanical/rule-based strategies
│   │   ├── run_daily_scan.py   # Daily portfolio scanner with TA + Market Heat
│   │   └── run_multi_timeframe_scan.py  # Historical multi-date analysis
│   │
│   └── llm/                    # LLM-based strategies
│       ├── demo_parallel_strategies.py    # Mechanical vs LLM comparison
│       └── demo_three_way_comparison.py   # Buy & Hold vs Mechanical vs LLM
│
├── analysis/                    # Analysis and reporting tools
│   ├── analyze_cache.py        # Analyzes cached market data coverage
│   ├── analyze_scan_performance.py  # Evaluates scan results
│   ├── aggregate_results.py    # Aggregates backtest results
│   └── README_ANALYSIS_TOOLS.md # Analysis tools documentation
│
├── services/                    # Background services and automation
│   ├── backtest_service.py     # Intelligent backtest service with rate limiting
│   ├── start_backtest_service.py  # User-friendly service launcher
│   ├── run_backtest_service.sh # Shell wrapper with auto-restart
│   └── README.md               # Service documentation
│
├── demos/                       # Quick demonstration scripts (future)
│
└── utils/                       # Utility scripts (future)
```

## Quick Start Guide

### 1. Running a Single Backtest

```bash
python scripts/backtesting/backtest_mas.py AAPL 2024-01-01 2024-12-31
```

### 2. Comparing Strategies

**Two-way comparison (Mechanical vs LLM):**
```bash
python scripts/strategies/llm/demo_parallel_strategies.py NVDA 2024-01-01 2024-01-31
```

**Three-way comparison (Buy & Hold vs Mechanical vs LLM):**
```bash
python scripts/strategies/llm/demo_three_way_comparison.py MSFT 2024-01-01 2024-01-31
```

### 3. Running Mechanical Strategy Scans

**Daily scan across portfolios:**
```bash
python scripts/strategies/mechanical/run_daily_scan.py
```

**Historical analysis:**
```bash
python scripts/strategies/mechanical/run_multi_timeframe_scan.py
```

### 4. Batch Backtesting

**Run comprehensive test suite:**
```bash
python scripts/backtesting/run_backtest_suite.py comprehensive --parallel
```

**Start intelligent backtest service:**
```bash
python scripts/services/start_backtest_service.py
```

### 5. Analyzing Results

**Aggregate backtest results:**
```bash
python scripts/analysis/aggregate_results.py
```

**Analyze cache coverage:**
```bash
python scripts/analysis/analyze_cache.py
```

## Key Script Categories

### Backtesting Scripts

- **backtest_mas.py**: Core engine that runs the multi-agent system on historical data
- **run_backtest_suite.py**: Batch runner for multiple symbols/periods with parallel support
- **backtest_configs.yaml**: Defines test suites (quick, comprehensive, extended)

### Strategy Scripts

#### Mechanical Strategies
- **run_daily_scan.py**: Scans portfolios using TA signals + market heat filtering
- **run_multi_timeframe_scan.py**: Tests mechanical strategy across date ranges

#### LLM Strategies
- **demo_parallel_strategies.py**: Demonstrates LLM vs Mechanical decision differences
- **demo_three_way_comparison.py**: Proves strategy progression (B&H → Mechanical → LLM)

### Analysis Scripts

- **analyze_cache.py**: Shows what market data is cached to avoid API limits
- **analyze_scan_performance.py**: Evaluates mechanical strategy scan results
- **aggregate_results.py**: Combines results from multiple backtests for comparison

### Service Scripts

- **backtest_service.py**: Core service with intelligent rate limiting and resume
- **start_backtest_service.py**: User interface for launching the service
- **run_backtest_service.sh**: Shell script for production deployment

## Common Use Cases

### Research & Development

1. Test new strategy ideas using backtest_mas.py
2. Compare strategies with demo scripts
3. Analyze results with aggregation tools

### Production Backtesting

1. Use backtest service for large-scale tests
2. Configure test suites in backtest_configs.yaml
3. Monitor progress and handle API limits automatically

### Strategy Evaluation

1. Run three-way comparison to prove LLM superiority
2. Analyze agreement/disagreement patterns
3. Generate reports for advisors/stakeholders

## Notes

- All scripts handle relative imports correctly after reorganization
- Scripts automatically add project root to Python path
- Cache data in `.cache/` to minimize API calls
- Use `--help` flag on any script for detailed options