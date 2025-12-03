# Command Reference

## Interactive CLI Commands (Issue #396)

The AutoGen-Trader CLI provides a comprehensive interactive trading assistant. Launch it with:

```bash
python main.py                     # Interactive mode
python main.py --daemon            # Background scheduler mode
```

### Trading Commands

```bash
# Buy and sell orders
> buy AAPL 10                      # Buy 10 shares of AAPL
> sell MSFT 5                      # Sell 5 shares of MSFT
> cancel ORDER_ID                  # Cancel pending order

# Position and portfolio management
> show positions                   # View all open positions
> show portfolio                   # Portfolio summary with P&L
> show orders                      # View pending orders
> show watchlist                   # View scanner watchlist
```

### Workflow Commands

```bash
# Daily routines
> morning-routine                  # Run morning market scan and analysis
> monitor                          # Monitor active positions for exit signals
> evening-summary                  # Generate end-of-day performance report

# Trade approval workflow
> approve                          # Approve pending trades from scanner
> reject                           # Reject pending trades
```

### Configuration Commands (Issue #358)

```bash
# View YAML configuration files
> show config-file                 # List all config files
> show config-file --file trading  # View trading_config.yaml
> show config-file --file scanner  # View scanner_config.yaml

# Configuration details
> show watchlist                   # View market scanner symbols
> show indicators                  # List available technical indicators
```

### Timeframe Commands (Issue #365)

```bash
# Timeframe management
> show timeframe                   # Display current trading timeframe
> set timeframe 1d                 # Change to daily timeframe (validated)
> set timeframe 1h                 # Change to hourly timeframe (experimental)

# Supported timeframes:
# - 1m, 5m, 15m, 30m (scalping/day trading)
# - 1h, 2h, 4h (intraday swing trading)
# - 1d (daily swing/position trading - validated with 0.856 Sharpe)
# - 1w, 1M (position/long-term trading)
```

⚠️ **Note**: Only 1d timeframe has been validated with production results. Other timeframes are experimental.

### Forward Testing Commands (Issue #324)

```bash
# 30-day validation protocol
> forward-test start TEST_NAME              # Start new forward test
> forward-test start my_test --capital 10000  # Start with custom capital
> forward-test report TEST_NAME             # Generate performance report
> forward-test status                       # Check progress of active tests

# Forward testing validates strategy performance before live deployment
# Tests run for 30 days and generate go/no-go recommendations
```

### Scheduler Commands

```bash
# Automated trading scheduler
> show scheduler                   # View scheduler status and schedule
> enable scheduler                 # Enable automated trading
> disable scheduler                # Disable automation
```

### Help System

```bash
# Interactive help
> /help                            # Show all commands grouped by category
> /help COMMAND                    # Detailed help for specific command
> /help search KEYWORD             # Search commands by keyword
> /help --examples                 # View all command examples

# Typo suggestions - intelligent error handling
> /help mnitor
💡 Did you mean one of these?
  - monitor          Monitor active positions
  - morning-routine  Run morning market scan and analysis

# Exit CLI
> /exit                            # Exit the interactive session
```

### Command Aliases

Many commands support short aliases for faster typing:

- `pos` → `show positions`
- `port` → `show portfolio`
- `ftest` → `forward-test`
- `tf` → `timeframe`
- `morning` → `morning-routine`
- `monitor` → `monitor`

## Environment Setup

- **Python version**: 3.10+
- **Conda environment**: `conda activate AutoTrader`
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
cat docs/archived/experiments/experiment_293_validation/README.md

# Check validation results
cat docs/01_overview/01_system_overview.md

# Review voting system design
cat docs/02_architecture/03_voting_system.md
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
# View active development issues
gh issue list --repo iAmGiG/AutoTrader --label "refactoring"

# Check project board status
gh project list --repo iAmGiG/AutoTrader

# View specific issue details
gh issue view 433 --repo iAmGiG/AutoTrader  # Code quality refactoring epic
gh issue view 436 --repo iAmGiG/AutoTrader  # Related refactoring issues
```

### Documentation Updates

```bash
# View current documentation structure
tree docs/ -I "__pycache__"

# Check documentation status
cat docs/README.md
cat docs/01_overview/01_system_overview.md
cat docs/02_architecture/03_voting_system.md
```

## Legacy Commands (Deprecated)

### V0-V4 Sentiment Framework ❌

```bash
# These commands are deprecated - system moved to archived
python scripts/runs/backtest.py --version V0 --symbol AAPL --year 2024
python scripts/runs/backtest.py --all-versions --symbol AAPL --year 2024
python scripts/analysis/generate_results_summary.py --advanced
```

**Note**: V0-V4 framework deprecated in favor of validated MACD+RSI voting approach. Archived in `src/deprecated/v0_v4_agents/` and `docs/archived/v0_v4_deprecated/`.

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

**Note**: Commands updated for Issue #396 - Interactive CLI with help system, configuration commands, timeframe support, and forward testing.

**Current Focus**: CLI Enhancement (Issue #396) - Complete command documentation and help system.
