# Reports Directory Structure

**Framework**: V0-V4 Sentiment Analysis Comparison Study  
**Status**: ✅ Complete 2024 Testing with Advanced Metrics

## Current Structure

```
reports/
├── continuous_backtests/      # V0-V4 backtest results by version
│   ├── V0/                   # Baseline (24 symbols tested)
│   ├── V1/                   # VADER news sentiment
│   ├── V2/                   # VXX volatility fear
│   ├── V3/                   # Combined heuristic
│   └── V4/                   # LLM intelligent reasoning
├── continuation_states_2025/  # Portfolio states for 2025 continuation
├── V0-V4_Framework_Results.md # Comprehensive summary report
├── backtest_analysis_2024.json # Advanced metrics analysis
├── strategy_comparison_2024.csv # Comparative metrics CSV
├── V0-V4_results_summary.csv  # Quick summary CSV
└── README.md                  # This file
```

## Key Reports

### Primary Analysis Files
- **V0-V4_Framework_Results.md**: Complete performance summary with detailed metrics
- **backtest_analysis_2024.json**: Advanced metrics including sentiment effectiveness
- **strategy_comparison_2024.csv**: Spreadsheet-ready comparative analysis

### Data Files
- **continuous_backtests/**: Raw JSON results for each version/symbol combination
- **continuation_states_2025/**: Final portfolio states for continuing into 2025

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

# View specific results
cat reports/continuous_backtests/V4/AAPL_2024_results.json
```
