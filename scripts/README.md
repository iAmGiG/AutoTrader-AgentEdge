# Scripts Directory

The scripts directory contains V0-V4 sentiment analysis validation and production runs.

## Directory Structure

```bash
scripts/
├── README.md
├── analysis/                # SPY/QQQ analysis utilities  
├── data/                   # Data collection scripts
└── runs/                   # V0-V4 sentiment framework runs
    ├── validation/         # Production validation scripts
    ├── analysis/          # Performance analysis scripts  
    └── comparison/        # Cross-version comparison runs
```

## Production Scripts

### Analysis (`runs/analysis/`)

**Reusable analysis frameworks:**

- `comprehensive_2024_v0_v4_analysis.py` - Full V0-V4 comparison framework
- `run_2024_full_analysis.py` - Complete yearly analysis
- `simple_2024_analysis.py` - Streamlined analysis framework
- `v0_v4_comparison_summary.py` - Performance comparison utilities

### Validation (`runs/validation/`)

**Core validation scripts:**

- `run_v0_pipeline_validation.py` - V0 baseline validation  
- `run_v4_data_leakage_detection.py` - V4 obfuscation testing

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
