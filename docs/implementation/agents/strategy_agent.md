# Strategy Agent Documentation

**Last Updated**: 2025-07-11

## Overview

The Strategy Agent is responsible for making trading decisions based on signals from sentiment and technical agents. It implements the enhanced trading strategy with MACD-based entry/exit signals and sentiment filtering.

## Trading Strategy

### Enhanced Strategy Rules (Current)

The agent uses a sentiment-filtered MACD strategy:

1. **Entry Conditions (BUY)**:
   - Sentiment >= 0 (allows neutral sentiment)
   - MACD < 0 AND improving (today > yesterday)
   - No existing position

2. **Exit Conditions (SELL)**:
   - MACD > 0 (positive momentum exhausted)
   - OR Risk threshold exceeded
   - Must have open position

3. **HOLD Conditions**:
   - Entry/exit conditions not met
   - Insufficient capital
   - Invalid signals

### Decision Flow

```
Receive Signals
    ↓
Validate Inputs
    ├── Check Sentiment Score
    ├── Verify MACD Values
    └── Assess Current Position
         ↓
Apply Strategy Rules
    ├── Entry Logic (MACD < 0 & improving)
    ├── Exit Logic (MACD > 0)
    └── Risk Management
         ↓
Generate Decision
    └── {action, qty, reasoning}
```

## Key Components

### 1. Signal Processing

```python
def decide_trade(self, signals, price, trade_date):
    """
    Main decision method that processes signals.
    
    Args:
        signals: Dict with 'sentiment' and 'technical' data
        price: Current market price
        trade_date: Date of the trading decision
    
    Returns:
        Dict with 'action', 'qty', 'reasoning'
    """
```

### 2. Strategy Implementation

```python
# Enhanced strategy (sentiment >= 0)
if sentiment_score >= 0:
    if macd_today < 0 and macd_today > macd_yest:
        # MACD negative but improving
        return {"action": "BUY", ...}
    elif position > 0 and macd_today > 0:
        # MACD turned positive, exit
        return {"action": "SELL", ...}
```

### 3. Risk Management

- **Position Sizing**: Fixed 100 shares (configurable)
- **Capital Check**: Ensures sufficient funds
- **Drawdown Monitoring**: Tracks equity curve
- **Max Position**: Single position at a time

## Performance Metrics

The agent calculates various performance metrics:

1. **Returns**:
   - Total Return %
   - Annualized Return
   - Risk-adjusted Return

2. **Risk Metrics**:
   - Sharpe Ratio
   - Max Drawdown
   - Volatility

3. **Trade Statistics**:
   - Win Rate
   - Average Win/Loss
   - Number of Trades

### Metric Calculation

```python
def calculate_metrics(self, initial_capital):
    """Calculate performance metrics from equity curve."""
    metrics = {
        'total_return': (final - initial) / initial * 100,
        'sharpe_ratio': returns.mean() / returns.std() * sqrt(252),
        'max_drawdown': calculate_max_drawdown(equity_curve),
        'win_rate': wins / total_trades * 100
    }
```

## Integration with Other Agents

### Input Requirements

```python
signals = {
    'sentiment': {
        'score': 0.7,        # 0-1 scale
        'confidence': 0.8,    # Confidence level
        'analysis': '...'     # Text explanation
    },
    'technical': {
        'macd_today': -0.5,   # Current MACD value
        'macd_yest': -0.8,    # Previous MACD
        'analysis': {...}     # Detailed analysis
    }
}
```

### Output Format

```python
decision = {
    'action': 'BUY',          # BUY/SELL/HOLD
    'qty': 100,               # Number of shares
    'reasoning': '...',       # Explanation
    'conditions_met': {       # Which rules triggered
        'sentiment_ok': True,
        'macd_entry': True
    }
}
```

## Configuration

### Strategy Parameters

```python
# Configurable thresholds
SENTIMENT_THRESHOLD = 0.0    # Minimum sentiment (0 = neutral)
POSITION_SIZE = 100          # Shares per trade
RISK_THRESHOLD = 0.20        # 20% drawdown limit
```

### Backtesting Settings

- Initial capital: $100,000
- Commission: $0 (simplified)
- Slippage: Not modeled
- Data frequency: Daily

## Usage Example

```python
# Initialize strategy agent
strategy = StrategyAgent()

# Process signals for a trading day
signals = coordinator.get_signals(date, symbol)
decision = strategy.decide_trade(
    signals=signals,
    price=current_price,
    trade_date=date
)

# Execute decision
if decision['action'] == 'BUY':
    execute_buy_order(decision['qty'], price)
elif decision['action'] == 'SELL':
    execute_sell_order(decision['qty'], price)
```

## Recent Improvements (2025-07-11)

1. **Simplified Strategy**: Single enhanced version (sentiment >= 0)
2. **MACD Fix Impact**: Now uses correct MACD line values
3. **VXX Integration**: Works with sentiment agent's fallback
4. **Better Reasoning**: Captures decision logic for analysis

## Performance Characteristics

### Strengths

- Clear entry/exit rules
- Combines sentiment + technical
- Risk management built-in
- Transparent decision logic

### Limitations

- Single position only
- Fixed position sizing
- Daily frequency only
- No stop-loss orders

## Future Enhancements

1. **Dynamic Position Sizing**: Based on confidence/volatility
2. **Multiple Positions**: Portfolio management
3. **Stop-Loss Integration**: Risk limits per trade
4. **Intraday Capability**: Higher frequency trading
5. **Machine Learning**: Adaptive strategy parameters
