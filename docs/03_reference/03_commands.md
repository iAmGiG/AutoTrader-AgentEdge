# Command Reference

## Environment Setup

- **Python version**: 3.10+
- **Conda environment**: `conda activate RH2MAS`
- **Install dependencies**: `pip install -e .`

## Current Development Commands

### AutoGen Agent Testing (Production System) ✅

```bash
# VoterAgent (production-ready with 0.856 Sharpe validation)
python -c "from src.autogen_agents.voter_agent import VoterAgent; print('VoterAgent: Production Ready')"

# Multi-agent development testing
python -c "from src.autogen_agents.scanner_agent import ScannerAgent; print('ScannerAgent: In Development')"
python -c "from src.autogen_agents.risk_agent import RiskAgent; print('RiskAgent: In Development')"
python -c "from src.autogen_agents.executor_agent import ExecutorAgent; print('ExecutorAgent: In Development')"

# Trading orchestrator coordination
python -c "from src.autogen_agents.trading_orchestrator import TradingOrchestrator; print('Orchestrator: In Development')"

# All unit tests
python -m unittest discover tests
```

### Archived Validation Results ✅

```bash
# Validation complete - results archived in docs/archived/experiments/experiment_293_validation/
# Key findings: MACD+RSI voting (0.856 Sharpe) > single MACD (0.841 Sharpe)
# VoterAgent now production-ready based on validated results
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

### Market Data Cache (SQLite)

```bash
# Check cache status and statistics
python scripts/cache_manager.py stats

# List cached symbols
python scripts/cache_manager.py symbols

# Query specific symbol data
python scripts/cache_manager.py query SPY --start 2024-01-01 --end 2024-12-31

# Check database size
ls -lh .cache/trading_data.db

# Legacy: Check old JSON cache (deprecated)
ls -la .cache/market_data/ 2>/dev/null || echo "No legacy cache found"
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

# Verify AutoGen imports work
python -c "from src.autogen_agents.voter_agent import VoterAgent; print('VoterAgent import successful')"
python -c "from src.autogen_agents.base_agent import BaseAgent; print('BaseAgent import successful')"

# Test cache data loading (SQLite)
python scripts/cache_manager.py query AAPL --start 2024-01-01 --end 2024-12-31

# Check SQLite cache database
sqlite3 .cache/trading_data.db "SELECT COUNT(*) FROM market_cache;"

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
