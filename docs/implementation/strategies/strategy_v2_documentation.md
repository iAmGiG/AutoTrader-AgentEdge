# Strategy V2 Documentation

## Overview

Strategy V2 is an enhanced version of the MACD + sentiment trading strategy that addresses the primary limitation discovered during backtesting: the lack of news data for historical periods.

## Key Change

**V1 Requirement**: `sentiment > 0` (strictly positive)  
**V2 Requirement**: `sentiment >= 0` (allows neutral)

This single change enables the strategy to trade when news data is unavailable, which is common for:
- Historical periods (>90 days old)
- ETFs and index funds
- Small-cap stocks
- After-hours/pre-market periods

## Implementation

File: `src/agents/strategy_agent_v2.py`

### Entry Conditions (ALL must be true)
```python
if (
    macd_y is not None and macd_y < 0 and      # Yesterday's MACD negative
    macd_t is not None and macd_t > macd_y and  # Today's MACD improving
    sentiment >= 0                               # Sentiment neutral or positive
):
    action = "BUY"
```

### Exit Conditions (ANY triggers exit)
```python
if (
    (macd_y < 0 and macd_t < macd_y) or  # MACD deteriorating while negative
    (macd_y > 0 and macd_t < 0)           # MACD crossing below zero
):
    action = "SELL"
```

## Rationale

### Problem with V1
- Required positive sentiment (`sentiment > 0`)
- News APIs have limited historical coverage
- Result: ~99% of MACD signals blocked
- Only 1 successful example found in testing (AAPL COVID)

### Solution in V2
- Accept neutral sentiment (`sentiment >= 0`)
- Treats "no news" as neutral rather than blocking
- Preserves protection against negative sentiment
- Enables backtesting on historical data

## Expected Impact

### Before (V1)
- Trades only when positive news available
- Misses most recovery opportunities
- Unusable for historical backtesting

### After (V2)
- Trades on MACD signals unless negative news
- Captures more recovery opportunities
- Enables meaningful historical analysis

## Risk Considerations

### Potential Risks
1. **More False Signals**: Without news confirmation, may enter trades based solely on technical indicators
2. **Market Regime Changes**: MACD patterns might behave differently without sentiment context
3. **Overfitting**: Strategy might perform differently in live trading with real news

### Mitigations
1. **Exit Rules Unchanged**: Still exits on MACD deterioration
2. **Negative Sentiment Protection**: Still blocks trades when sentiment < 0
3. **Position Sizing**: Fixed 100 shares limits risk per trade

## Usage

### In Backtesting
```python
from src.agents.strategy_agent_v2 import StrategyAgent

# Use V2 for historical backtesting
strategy = StrategyAgent(name="StrategyV2")
decision = strategy.decide_trade(aggregated_data, price, date)
```

### Updating Existing Code
In `backtest_mas.py`, change import:
```python
# From:
from src.agents.strategy_agent import StrategyAgent

# To:
from src.agents.strategy_agent_v2 import StrategyAgent
```

## Testing Results

### Comparison Test
- V1: Blocks trades when sentiment = 0.0
- V2: Allows trades when sentiment = 0.0
- Both: Block trades when sentiment < 0

### Real-World Example
**AAPL March 2020 COVID Recovery**
- Date: 2020-03-23
- MACD: -2.89 → -2.31 (improving)
- Sentiment: 0.0 (no news data)
- V1: HOLD (blocked)
- V2: BUY (allowed)
- Result: AAPL rallied 30%+ in following weeks

## Recommendations

1. **Use V2 for Backtesting**: Essential for historical analysis
2. **Use V1 for Live Trading**: When real-time news is available
3. **Monitor Performance**: Compare V2 backtest results with V1
4. **Consider Hybrid**: Use different thresholds for different assets

## Future Enhancements

1. **Configurable Threshold**: Make sentiment threshold a parameter
2. **Asset-Specific Rules**: Different thresholds for stocks vs ETFs
3. **Synthetic Sentiment**: Generate sentiment from technical indicators
4. **Confidence Scoring**: Weight trades by sentiment strength

## Conclusion

Strategy V2 is a pragmatic solution to the news data availability problem. By allowing neutral sentiment, it enables meaningful backtesting while preserving the core MACD recovery logic. This change should dramatically increase the number of trades executed during backtesting, providing better insights into the strategy's potential performance.