# Reports Directory Structure

**Framework**: V0-V4 Sentiment Analysis Comparison Study  
**Status**: ✅ Complete 2024 Testing with Advanced Metrics

## Current Structure

```
reports/
├── analysis/                   # Analysis reports and summaries
│   ├── V0-V4_Framework_Results.md    # Comprehensive summary report
│   └── backtest_analysis_2024.json   # Advanced metrics analysis
├── data/                       # CSV data exports
│   ├── strategy_comparison_2024.csv  # Comparative metrics
│   └── V0-V4_results_summary.csv     # Quick summary
├── continuous_backtests/      # Raw V0-V4 backtest results
│   ├── V0/                   # Baseline (9 symbols tested)
│   ├── V1/                   # VADER news sentiment
│   ├── V2/                   # VXX volatility fear
│   ├── V3/                   # Combined heuristic
│   └── V4/                   # LLM intelligent reasoning
├── continuation_states_2025/  # Portfolio states for 2025 continuation
└── README.md                  # This file
```

## Key Reports

### Analysis Reports (`analysis/`)
- **V0-V4_Framework_Results.md**: Complete performance summary with detailed metrics
- **backtest_analysis_2024.json**: Advanced metrics including sentiment effectiveness

### Data Exports (`data/`)
- **strategy_comparison_2024.csv**: Spreadsheet-ready comparative analysis
- **V0-V4_results_summary.csv**: Quick summary table

### Raw Results (`continuous_backtests/`)
- Raw JSON results for each version/symbol combination
- Checkpoint files for resume capability

### Continuation States (`continuation_states_2025/`)
- Final portfolio states for continuing into 2025

## Test Coverage

### Symbols Tested (8 tickers + 2 ETFs)
- **Tech Giants**: AAPL, MSFT, NVDA, META, GOOGL
- **Others**: AMZN, TSLA, GOOG
- **ETFs**: SPY, QQQ

### Performance Highlights
- **Best Overall**: NVDA V0 (+106.73%)
- **Best V4**: NVDA (+89.82%)
- **Most Consistent**: SPY (all versions positive)

## Advanced Metrics Available
- Sharpe/Calmar ratios
- Sentiment effectiveness by bucket
- Market regime analysis
- Trade quality metrics
- Risk-adjusted performance

## Access Commands

```bash
# Generate basic summary
python scripts/generate_results_summary.py

# Generate advanced metrics analysis
python scripts/generate_results_summary.py --advanced

# View analysis report
cat reports/analysis/V0-V4_Framework_Results.md

# View specific results
cat reports/continuous_backtests/V4/AAPL_2024_results.json
```
