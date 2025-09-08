# Experiments Directory

This directory contains organized experiment files grouped by specific research areas.

## Structure

```
experiments/
├── README.md                           # This file
├── experiment_293_validation/          # MACD+RSI voting validation
├── exit_strategy_analysis/             # Exit strategy performance analysis
└── configuration_system/               # Configuration system demonstration
```

## Experiment Categories

### `experiment_293_validation/`
**Purpose**: Validate MACD+RSI voting system performance vs single indicators
**Key Finding**: Voting system achieves 0.856 Sharpe vs 0.841 for MACD-only
**Related Issue**: #293

### `exit_strategy_analysis/`
**Purpose**: Analyze different exit strategies and their expected values
**Key Finding**: Balanced exits (8% TP / 5% SL) optimal with 27.48% annual return
**Critical Discovery**: Conservative exits (6% TP / 8% SL) have negative expected value

### `configuration_system/`
**Purpose**: Demonstrate flexible configuration management for trading parameters
**Key Benefit**: Enables parameter tuning without code changes
**Related Issue**: #303

## Organization Principles

1. **Experiment-Specific**: Each directory contains scripts for a specific research question
2. **Self-Contained**: Each experiment directory includes all necessary files
3. **Documented**: Each experiment has clear purpose and findings
4. **Reproducible**: Scripts can be re-run to validate results

## Usage

Navigate to specific experiment directories to run related scripts:

```bash
# Run MACD+RSI validation
cd scripts/experiments/experiment_293_validation/
python experiment_293_retest.py

# Analyze exit strategies  
cd scripts/experiments/exit_strategy_analysis/
python performance_clarification.py

# Demo configuration system
cd scripts/experiments/configuration_system/
python config_usage_demo.py
```

## General Tools

For experiment-agnostic tools (data collection, analysis utilities, validation frameworks), see parent directories:
- `scripts/analysis/` - General analysis tools
- `scripts/validation/` - General validation scripts (V4 obfuscation testing)
- `scripts/runs/` - V0-V4 sentiment framework runs