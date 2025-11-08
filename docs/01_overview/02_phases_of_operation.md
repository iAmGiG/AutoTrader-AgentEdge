# System Phases of Operation

**Purpose**: Detailed breakdown of how the AutoGen-TradingSystem operates from market data acquisition through trade execution.

This document outlines the five sequential phases that comprise a complete trading cycle in the AutoGen-TradingSystem.

## Phase 1: Market Data Acquisition

**Objective**: Obtain reliable, cached market data from multiple providers

```bash
Real-time market data from Alpaca SDK
  ↓
Intelligent caching system (>90% API call reduction)
  ↓
Multi-provider data normalization
```

### Key Components

**Alpaca Market Data Client**:
- Primary data source via official alpaca-py SDK
- Real-time bars, quotes, trades, and snapshots
- IEX feed support for paper trading accounts
- Automatic pagination and error handling

**UnifiedCacheManager**:
- JSON file-based caching system
- Smart expiration (historical data cached long-term, recent data refreshed)
- Pattern matching for consolidated and fragmented files
- >90% reduction in API calls

**Data Normalization**:
- Converts provider-specific formats to unified schema
- Standardized column names and data types
- Timezone handling and timestamp conversion
- Consistent interface across Alpaca, Polygon, Alpha Vantage

### Data Flow

1. **Agent requests market data** via AutoGen tool wrapper
2. **Cache check**: UnifiedCacheManager searches for cached data
3. **Cache hit**: Return cached data (90%+ of requests)
4. **Cache miss**: Fetch from Alpaca SDK, normalize, cache, return
5. **Multi-provider fallback**: Polygon → Alpha Vantage if needed

### Performance Metrics

- **Cache Hit Rate**: >90%
- **API Call Reduction**: >90%
- **Response Time**: <100ms for cached data, <2s for fresh fetches
- **Data Quality**: Validated against known trading days and continuity

## Phase 2: Signal Generation

**Objective**: Generate trading signals using validated MACD+RSI voting strategy

```bash
VoterAgent processes market data
  ↓
MACD+RSI voting logic (0.856 Sharpe ratio)
  ↓
Signal generation with confidence scoring
```

### Key Components

**VoterAgent** (Production-Ready):
- Microsoft AutoGen agent implementation
- MACD+RSI voting coordination
- Confidence scoring (strong/weak/none)
- Position sizing recommendations

**Technical Indicators**:
- **MACD**: Fibonacci periods (13/34/8) for trend momentum
- **RSI**: 14-period for overbought/oversold conditions
- **Voting Logic**: Both agree = strong signal, one agrees = weak signal

### Signal Types

| Signal Condition | Action | Position Size | Confidence |
|-----------------|--------|---------------|------------|
| MACD BUY + RSI BUY | BUY | 100% | Strong |
| MACD BUY + RSI HOLD | BUY | 50% | Weak |
| MACD HOLD + RSI BUY | BUY | 50% | Weak |
| MACD SELL + RSI SELL | SELL | 100% | Strong |
| MACD SELL + RSI HOLD | SELL | 50% | Weak |
| Conflicting signals | HOLD | 0% | None |

### Decision Flow

1. **VoterAgent receives** market data request
2. **Calculate MACD** using Fibonacci periods (13/34/8)
3. **Calculate RSI** using 14-period lookback
4. **Compare signals** via voting logic
5. **Determine action** (BUY/SELL/HOLD) with confidence
6. **Recommend position size** based on signal strength
7. **Return structured decision** to orchestrator

### Validated Performance

- **Sharpe Ratio**: 0.856 (vs 0.841 for MACD-only)
- **Win Rate**: 51.4% (vs 31.9% for MACD-only)
- **Max Drawdown**: -10.10% (vs -10.58% for MACD-only)
- **Volatility**: 15.30% (lower than single indicator)

## Phase 3: Risk Assessment

**Objective**: Validate trade safety and calculate appropriate position sizing

```bash
Risk calculation and position sizing
  ↓
Market hours validation
  ↓
Daily limit checks and position validation
```

### Key Components

**Risk Calculator**:
- Position sizing based on account equity
- Maximum position limits per trade
- Daily trading limits enforcement
- Drawdown protection

**Market Hours Validator**:
- NYSE/NASDAQ trading hours (9:30 AM - 4:00 PM ET)
- Pre-market and after-hours restrictions
- Holiday schedule checking
- Extended hours support (optional)

**Account Validator**:
- Buying power verification
- Pattern day trader (PDT) rule compliance
- Margin requirements checking
- Cash account settlement rules

### Risk Checks

**Pre-Trade Validation**:
1. ✅ Market is open for trading
2. ✅ Sufficient buying power available
3. ✅ Position size within account limits
4. ✅ Daily trade count under limits
5. ✅ No conflicting open positions
6. ✅ Symbol is tradeable (not halted)

**Position Sizing**:
```python
# Example calculation
account_equity = $10,000
max_position_pct = 10%  # Per-trade limit
signal_confidence = "strong"  # From VoterAgent

if signal_confidence == "strong":
    position_size = account_equity * max_position_pct * 1.0  # 100%
elif signal_confidence == "weak":
    position_size = account_equity * max_position_pct * 0.5  # 50%
else:
    position_size = 0  # No position

# Result: $1,000 max position for strong signal, $500 for weak
```

### Safety Rails

- **Multi-level confirmations** for live trading
- **Paper trading enforcement** unless explicitly overridden
- **Daily limit protection** prevents over-trading
- **Emergency stop-all** capability

## Phase 4: Trade Execution

**Objective**: Execute validated trades with proper order management

```bash
Order placement via Alpaca API
  ↓
Order monitoring and fill detection
  ↓
Position tracking and management
```

### Key Components

**AlpacaOrderManager**:
- Unified order placement interface
- Support for all order types
- Fill monitoring with automatic state transitions
- Error handling and retry logic

**Order Types Supported**:
- **Market**: Immediate execution at current price
- **Limit**: Execute at specified price or better
- **Stop**: Trigger at stop price, execute as market
- **Trailing Stop**: Dynamic stop that follows price
- **Bracket**: OCO (One-Cancels-Other) with take-profit and stop-loss

**Position Tracker**:
- Real-time position monitoring
- P&L calculation (realized and unrealized)
- Average entry price tracking
- Position state management

### Execution Flow

1. **VoterAgent decision** passed to OrderManager
2. **Order validation** (risk checks, parameters)
3. **Order submission** to Alpaca API
4. **Order acknowledgment** with order ID
5. **Fill monitoring** (polling or webhook)
6. **Fill confirmation** triggers state update
7. **Position tracking** begins
8. **Stop orders placed** for risk management

### Order States

```bash
NEW → SUBMITTED → ACCEPTED → FILLED
                       ↓
                   CANCELED (if user cancels)
                       ↓
                   EXPIRED (if GTC expires)
                       ↓
                   REJECTED (if validation fails)
```

### Fill Monitoring

**Active Monitoring**:
- Poll Alpaca API every 5-10 seconds
- Check order status until filled/canceled
- Update position state on fill confirmation
- Trigger exit strategy on position open

**Fill Confirmation**:
- Order ID and fill price recorded
- Position average price calculated
- Stop orders automatically placed
- Notification sent (optional)

## Phase 5: Multi-Agent Coordination (In Development)

**Objective**: Coordinate multiple specialized agents for comprehensive trading system

```bash
Scanner Agent → Market opportunity identification
  ↓
Risk Agent → Portfolio risk management
  ↓
Executor Agent → Trade execution coordination
  ↓
Orchestrator → Multi-agent workflow management
```

### Planned Components

**Scanner Agent** (Issue #310):
- Multi-ticker market scanning
- Opportunity identification across portfolio
- Integration with VoterAgent for signal generation
- Prioritization of trading candidates

**Risk Agent** (Issue #310):
- Portfolio-level risk assessment
- Correlation analysis between positions
- Maximum drawdown monitoring
- Position sizing across multiple holdings

**Executor Agent** (Issue #310):
- Trade execution coordination
- Order batching and optimization
- Slippage minimization
- Execution quality monitoring

**Trading Orchestrator** (Issue #310):
- Multi-agent workflow coordination
- Message passing between agents
- State management across agent interactions
- Human-in-the-loop decision presentation

### Future Architecture

```bash
Human Request
  ↓
Trading Orchestrator
  ├─→ Scanner Agent (Find opportunities)
  ├─→ VoterAgent (Generate signals)
  ├─→ Risk Agent (Assess portfolio risk)
  └─→ Executor Agent (Execute trades)
       ↓
Human Approval
  ↓
Order Execution
```

### Integration Points

- **Shared Tools**: All agents access same market data, position tracking, order management
- **Message Protocol**: Structured AutoGen messages for inter-agent communication
- **State Persistence**: Shared state across agent coordination
- **Human Interface**: CLI presentation of agent recommendations for approval

## Complete Trading Cycle Example

### Scenario: AAPL Trade from Signal to Exit

**Phase 1: Data Acquisition**
- Scanner requests AAPL data for 2024-01-15 to 2024-01-31
- UnifiedCacheManager finds cached data (cache hit)
- Returns 11 trading days of OHLCV data in <50ms

**Phase 2: Signal Generation**
- VoterAgent calculates MACD: Bullish crossover detected
- VoterAgent calculates RSI: 45 (neutral, not oversold)
- Voting result: MACD BUY + RSI HOLD = WEAK BUY signal
- Position size: 50% (weak signal modifier)

**Phase 3: Risk Assessment**
- Market hours: ✅ Open (2:30 PM ET)
- Account equity: $10,000
- Max position: $1,000 (10% limit)
- Signal adjustment: $500 (50% of max due to weak signal)
- Buying power: ✅ $8,500 available
- Risk checks: ✅ All passed

**Phase 4: Trade Execution**
- Order type: Market order for $500 of AAPL (~3 shares at $170)
- Submission: Order #abc123 accepted
- Fill monitoring: Filled at $170.25 after 2 seconds
- Position tracking: 3 shares AAPL, avg price $170.25
- Stop placement: Stop-loss at -5% ($161.74)

**Phase 5: Position Management** (Current System)
- Monitor for exit signal (VoterAgent checks daily)
- Stop-loss monitoring (OrderManager)
- Exit on MACD+RSI SELL signal or stop trigger
- Close position and record trade result

---

## Performance Optimization

### Caching Strategy
- **Historical data**: Cached indefinitely (immutable)
- **Recent data**: Refreshed daily (market close)
- **Intraday data**: 5-minute expiration (real-time needs)

### API Rate Limits
- **Alpaca Free**: 200 requests/minute
- **Cache hit rate**: >90% reduces effective usage to <20 requests/minute
- **Batch requests**: Multiple symbols per request where possible

### Error Handling
- **Retry logic**: 3 attempts with exponential backoff
- **Fallback providers**: Polygon → Alpha Vantage → cached data
- **Graceful degradation**: Continue with cached data if API unavailable

---

*Comprehensive operational flow from market data acquisition through multi-agent coordination and trade execution.*
