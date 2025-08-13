# Scripts Directory

The scripts directory is organized into 3 clear layers matching the system architecture:

## Layer 1: Experiment Entry Points

**Main scripts for running experiments and analysis:**

### `backtest.py` - Primary Backtesting

```bash
python backtest.py SYMBOL START_DATE END_DATE
# Example: python backtest.py AAPL 2023-01-01 2023-12-31
```

Single stock backtesting with full LLM reasoning capture.

### `analyze_results.py` - Results Analysis  

```bash
python analyze_results.py
```

Analyzes cached backtest data and generates performance reports.

### `run_experiments.py` - Batch Experiments

```bash
python run_experiments.py
```

Automated batch processing with rate limiting and resume capability.

## Layer 2: Agent Operations (`agents/`)

**Scripts for working directly with agents:**

### `compare_strategies.py` - Strategy Comparison

Three-way comparison demo: Buy & Hold vs Mechanical vs LLM

### `demo_parallel.py` - Parallel Strategy Demo

Real-time parallel execution of multiple strategies

### `test_agents.py` - Agent Testing

Validation and testing of agent functionality

## Layer 3: Tools & Utilities (`tools/`)

**Supporting tools and utilities:**

### Data Tools (`tools/data/`)

- `build_cache.py` - Build market data cache
- `collect_data.py` - Collect fresh market data

### Validation Tools (`tools/validation/`)

- `obfuscation_test.py` - Data integrity validation

### General Utils (`tools/utils/`)

- `examine_cached_results.py` - Analyze Google Search news cache contents
- `organize_news_cache.py` - Organize news cache by publication date
- Other maintenance and utility scripts

## Quick Start

1. **Run a single backtest:**

   ```bash
   python backtest.py NVDA 2023-01-01 2023-12-31
   ```

2. **Analyze results:**

   ```bash
   python analyze_results.py
   ```

3. **Compare strategies:**

   ```bash
   python agents/compare_strategies.py
   ```

## Architecture Notes

- **Layer 1**: What users interact with directly
- **Layer 2**: Agent-specific operations and demos  
- **Layer 3**: Supporting infrastructure

This structure mirrors the system architecture: experiment entry points → agent operations → underlying tools and utilities.

## Legacy Scripts

The old directory structure (`backtesting/`, `analysis/`, `strategies/`, etc.) is preserved for reference but the new 3-layer structure provides clearer entry points.
