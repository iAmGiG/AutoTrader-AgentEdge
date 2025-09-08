# Scripts Directory

The scripts directory contains V0-V4 sentiment analysis validation and production runs.

## Directory Structure

```bash
scripts/
├── README.md
├── analysis/                # General analysis utilities (experiment-agnostic)
├── data/                   # Data collection scripts
├── experiments/            # Organized experiment files (NEW)
│   ├── experiment_293_validation/    # MACD+RSI voting validation
│   ├── exit_strategy_analysis/      # Exit strategy performance analysis
│   └── configuration_system/        # Configuration system demonstration
├── runs/                   # V0-V4 sentiment framework runs
│   ├── validation/         # Production validation scripts
│   ├── analysis/          # Performance analysis scripts  
│   └── comparison/        # Cross-version comparison runs
└── validation/            # General validation scripts (V4 obfuscation, etc.)
```

## Experiment-Specific Scripts

### Experiments Directory (`experiments/`)

**NEW**: Organized experiment files grouped by specific research areas.

#### `experiment_293_validation/`
- **Purpose**: MACD+RSI voting system validation vs single indicators
- **Key Finding**: Voting achieves 0.856 Sharpe vs 0.841 MACD-only
- **Scripts**: `experiment_293_retest.py`, `experiment_294_vote_thresholds.py`

#### `exit_strategy_analysis/`  
- **Purpose**: Exit strategy performance and expected value analysis
- **Critical Discovery**: Conservative exits (6%/8%) have negative expected value!
- **Recommendation**: Use Balanced exits (8%/5%) for 27.48% annual return
- **Scripts**: `performance_clarification.py`, `expected_value_analysis.py`

#### `configuration_system/`
- **Purpose**: Flexible parameter management demonstration
- **Benefit**: Change trading parameters without code modifications
- **Related Issue**: #303
- **Scripts**: `config_usage_demo.py`

## General-Purpose Scripts

### Analysis Tools (`analysis/`)

**General analysis and reporting scripts (experiment-agnostic):**

- `generate_results_summary.py` - Generate V0-V4 results summary with basic and advanced metrics
  - `--basic`: Simple performance summary (default)
  - `--advanced`: Comprehensive metrics with sentiment effectiveness analysis

### V0-V4 Framework (`runs/`)

#### Analysis (`runs/analysis/`)
**V0-V4 sentiment analysis frameworks:**
- `comprehensive_2024_v0_v4_analysis.py` - Full V0-V4 comparison framework
- `run_2024_full_analysis.py` - Complete yearly analysis
- `simple_2024_analysis.py` - Streamlined analysis framework
- `v0_v4_comparison_summary.py` - Performance comparison utilities

#### Validation (`runs/validation/`)
**V0-V4 validation scripts:**
- `run_v0_pipeline_validation.py` - V0 baseline validation  
- `run_v4_data_leakage_detection.py` - V4 obfuscation testing

### General Validation (`validation/`)

**General validation tools (not experiment-specific):**
- `obfuscation_test.py` - V4 date obfuscation validation

## Archived Tools

**One-off debugging and development tools moved to `deprecated/scripts/`:**

- Debug utilities (cache debugging, async troubleshooting)
- Maintenance scripts (cache fixes, data refreshing)
- Quick test scripts (exploratory testing)
- Development analysis scripts (one-time investigations)

## V0-V4 Research Framework

**Objective**: Demonstrate incremental value of LLM introduction.

- **V0**: Fixed Baseline (sentiment = 1.0) - Pure MACD strategy
- **V1**: NLP Analysis (VADER + Google Search news)  
- **V2**: Market Fear (VXX/VIX volatility-based sentiment)
- **V3**: Heuristic Combination (V1 + V2 with adaptive weighting)
- **V4**: Enhanced LLM Analysis (GPT-4o-mini + SPY/QQQ market context)

**Current Status**: ✅ All V0-V4 agents operational with enhanced market context integration
