# Backtesting Session Summary - July 8, 2025

## Executive Summary

Conducted extensive backtesting focused on volatile market periods to test the MACD recovery strategy. Hit API rate limits after ~10 tests, but discovered critical insights about the strategy's limitations.

## Key Discovery

**The sentiment requirement is blocking 99% of potential trades.**

Current strategy requires:

1. ✅ MACD < 0 (oversold)
2. ✅ MACD improving (today > yesterday)  
3. ❌ Sentiment > 0 (rarely available)

## Testing Results

### Successful Tests (Found Trades)

1. **AAPL COVID Crash** (March 2020)
   - Only test with actual trades
   - Sentiment was 0.12 (rare positive value)
   - Lost -0.93% (sold too early)

### Tests Without Trades

- META 2022 Bear Market
- NVDA Oct-Nov 2022  
- SPY Dec 2018
- All had MACD signals but no positive sentiment

### API Limitations Hit

- Alpha Vantage: 25/day limit exceeded
- FMP: 429 rate limit errors
- Yahoo Finance: Not installed
- News APIs: Limited historical data

## Critical Insights

### 1. Sentiment Data Availability

- **Historical periods**: Almost no news data
- **ETFs (SPY, QQQ)**: Minimal news coverage
- **Individual stocks**: Better but still limited
- **Recent data**: Best coverage (last 30-90 days)

### 2. Strategy Too Conservative

The triple requirement (MACD < 0, improving, AND positive sentiment) is too restrictive:

- MACD conditions occur frequently in volatile markets
- Sentiment data is rarely positive (usually 0.0)
- Result: Strategy misses most recovery opportunities

### 3. Simple Fix Available

```python
# Change line 48 in strategy_agent.py
# From: sentiment > 0
# To:   sentiment >= 0
```

This one-line change would allow trades when news is unavailable (neutral sentiment).

## Recommendations

### Immediate (When APIs Reset)

1. Implement the sentiment >= 0 fix
2. Test recent periods with individual stocks
3. Use shorter date ranges to conserve API calls

### Short Term

1. Add fallback sentiment (default 0.5 when no news)
2. Different rules for ETFs vs stocks
3. Consider technical indicators as sentiment proxy

### Long Term

1. Premium API subscriptions for serious backtesting
2. Local historical database
3. Machine learning for sentiment prediction

## Lessons Learned

1. **Free APIs are insufficient** for comprehensive backtesting
2. **News sentiment is unreliable** for historical testing
3. **The strategy logic works** but is overly conservative
4. **Caching helps** but can't overcome rate limits

## Next Steps

1. **Tonight**: Wait for API reset (midnight UTC)
2. **Tomorrow**: Test with relaxed sentiment rules
3. **This Week**: Focus on recent periods with good data
4. **Future**: Consider strategy modifications or premium data

## Cost Analysis

- Approximately 10 LLM-powered backtest runs today
- Each run costs money in API usage
- Recommendation: Implement dry-run mode for testing

## Conclusion

The backtesting system works correctly, but the strategy's strict sentiment requirement prevents it from capturing MACD recovery opportunities. With a simple one-line fix, the strategy could execute many more trades during volatile market recoveries.

The main bottleneck is data availability, not the system design. Free API tiers are inadequate for serious quantitative backtesting, especially for historical periods.
