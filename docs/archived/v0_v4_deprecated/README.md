# V0-V4 Sentiment Framework (DEPRECATED)

**Status**: ❌ **DEPRECATED** - Moved from active development

## Deprecation Reason

The V0-V4 sentiment-based framework was retired in favor of the simpler, more effective voting strategy:

- **Complexity vs ROI**: V0-V4 required extensive infrastructure (news APIs, LLMs, sentiment processing) for unproven benefits
- **Voting Success**: Simple MACD + RSI voting achieved better risk-adjusted returns with much less complexity
- **Focus Shift**: Resources redirected to Fibonacci regime detection for proven voting foundation

## Historical Context

### Framework Overview

- **V0 (Baseline)**: Fixed sentiment = 1.0, pure MACD strategy foundation  
- **V1 (NLP)**: VADER sentiment analysis on Google Search news
- **V2 (Market Fear)**: VXX/VIX volatility-based sentiment
- **V3 (Hybrid)**: Weighted combination of V1 + V2 sentiment
- **V4 (LLM)**: GPT-4o-mini reasoning with date obfuscation

### Results Summary

- **Best Performance**: NVDA V0 (+106.73%) - notably the baseline without sentiment
- **Complex Sentiment**: V1-V4 showed mixed results, no consistent advantage over V0 baseline
- **Infrastructure Cost**: Required multiple APIs, complex data pipelines, higher latency

## Archived Files

### `/analysis/` - Summary Reports

- `V0-V4_Framework_Results.md` - Comprehensive performance analysis
- `backtest_analysis_2024.json` - Advanced metrics comparison

### `/continuous_backtests/` - Raw Results  

- `V0/` through `V4/` - Individual version results by ticker
- 8 tech stocks + 2 ETFs tested across all versions

### `/continuation_states_2025/` - Portfolio States

- Final portfolio positions for 2025 continuation testing
- Preserved for historical completeness

### `/data/` - Export Files

- `strategy_comparison_2024.csv` - Comparative spreadsheet analysis
- `V0-V4_results_summary.csv` - Quick summary metrics

## Key Lessons Learned

1. **Simplicity Wins**: V0 baseline often outperformed complex sentiment versions
2. **Voting Superior**: Direct indicator consensus beat sentiment-weighted approaches
3. **Infrastructure Burden**: Complex systems harder to maintain, debug, and scale
4. **Focus Benefits**: Concentrating on one approach (voting) yielded better results

## Migration Path

Components from V0-V4 that informed current voting system:

- **MACD Implementation**: Core technical analysis preserved in voting system
- **Performance Metrics**: Risk analysis methods carried forward
- **Testing Framework**: Systematic backtesting approach maintained
- **Cache System**: Market data caching infrastructure reused

## Access Historical Results

```bash
# View comprehensive analysis
cat reports/archived/v0_v4_deprecated/analysis/V0-V4_Framework_Results.md

# Check specific version results
cat reports/archived/v0_v4_deprecated/continuous_backtests/V4/AAPL_2024_results.json

# Generate legacy analysis (if needed)
python scripts/analysis/generate_results_summary.py --advanced
```

---
*Archived September 5, 2025 - Moved to focus on voting + Fibonacci regime detection*
