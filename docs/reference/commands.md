# Command Reference

## Environment Setup

- **Python version**: 3.10+
- **Conda environment**: `conda activate RH2MAS`
- **Install dependencies**: `pip install -e .`

## Current Development Commands

### Voting Strategy Testing (Validated System) ✅

```bash
# Core validation experiments  
python tests/experiment_293_macd_vs_voting.py       # Voting vs single MACD comparison
python tests/experiment_extended_period_voting.py  # 2024-2025 bull vs volatile analysis
python tests/experiment_voting_optimized.py        # Fibonacci MACD optimization test

# Parameter optimization
python tests/experiment_macd_optimization.py       # Multi-ticker parameter optimization

# Individual component tests
python tests/experiment_ichimoku_standalone.py     # Ichimoku solo vs voting comparison
```

### Fibonacci Regime Development (In Progress) 🔄

```bash
# Phase 1: Core Fibonacci Module (Issue #298)
python tests/fibonacci_regime/test_phase_1.py      # 34 EMA filtering validation

# Phase 2: CCI Integration (Issue #299) 
python tests/fibonacci_regime/test_cci_integration.py

# Phase 3: Symmetry Break Detection (Issue #300)
python tests/fibonacci_regime/test_symmetry_breaks.py

# Phase 4: Full Integration (Issue #301)
python tests/fibonacci_regime/test_full_integration.py
```

### Code Quality & Validation

```bash
# Lint and format code
ruff check src/ scripts/ tests/
black src/ scripts/ tests/

# Type checking (if available)
mypy src/ --ignore-missing-imports

# Run unit tests
python -m unittest discover tests
```

## Configuration Commands

### Market Data Cache
```bash
# Check cache status
ls -la .cache/market_data/

# Verify data availability for 2024-2025 testing
ls .cache/market_data/*2024* .cache/market_data/*2025*
```

### API Configuration
```bash
# Create config file
mkdir -p config
cat > config/config.json << EOF
{
  "POLYGON_API_KEY": "your_key_here",
  "ALPHA_VANTAGE_KEY": "your_key_here"
}
EOF
```

## Results Analysis Commands

### Active Results (Current Development)
```bash
# View voting strategy validation
cat reports/active/voting_strategy/experiment_293_validation/293_voting_validation_report.md

# Check MACD optimization results  
cat reports/active/voting_strategy/macd_optimization/optimization_report.md

# Review extended period analysis
cat reports/active/voting_strategy/extended_period_analysis/results.json

# Monitor Fibonacci regime development
ls reports/active/fibonacci_regime/
```

### Historical Analysis (Archived)
```bash
# View archived V0-V4 results
cat reports/archived/v0_v4_deprecated/analysis/V0-V4_Framework_Results.md

# Check legacy backtest data
ls reports/archived/v0_v4_deprecated/continuous_backtests/
```

## Development Workflow Commands

### GitHub Issue Management
```bash
# View active Fibonacci regime issues
gh issue list --repo iAmGiG/RH2MAS --label "fibonacci-regime"

# Check phase development status
gh issue view 298 --repo iAmGiG/RH2MAS  # Phase 1
gh issue view 299 --repo iAmGiG/RH2MAS  # Phase 2
gh issue view 300 --repo iAmGiG/RH2MAS  # Phase 3
gh issue view 301 --repo iAmGiG/RH2MAS  # Phase 4
```

### Documentation Updates
```bash
# View current documentation structure
tree docs/ -I "__pycache__"

# Check documentation status
cat docs/README.md
cat docs/voting_strategy/validation_results.md
cat docs/fibonacci_regime/README.md
```

## Legacy Commands (Deprecated)

### V0-V4 Sentiment Framework ❌
```bash
# These commands are deprecated - system moved to archived
python scripts/runs/backtest.py --version V0 --symbol AAPL --year 2024
python scripts/runs/backtest.py --all-versions --symbol AAPL --year 2024
python scripts/analysis/generate_results_summary.py --advanced
```

**Note**: V0-V4 framework deprecated in favor of validated voting + Fibonacci regime approach.

## Troubleshooting Commands

### Common Issues
```bash
# Check Python environment
python --version
conda info --envs

# Verify imports work
python -c "from src.core.agents.simple_voting_orchestrator import SimpleVotingOrchestrator; print('Import successful')"

# Test data loading
python -c "import json; data = json.load(open('.cache/market_data/AAPL_2024-01-01_2024-12-31_polygon_consolidated.json')); print(f'Loaded {len(data.get(\"data\", []))} records')"

# Check disk space for cache
du -sh .cache/
```

### Performance Monitoring
```bash
# Monitor test execution time
time python tests/experiment_293_macd_vs_voting.py

# Check memory usage during backtests
/usr/bin/time -v python tests/experiment_extended_period_voting.py
```

---

*Commands updated for validated voting system + Fibonacci regime development*

*Current Focus: Phase 1 implementation (Issue #298) - Core Fibonacci Module*