# Trade History Database

**Issue**: [#373 Extension](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/373)
**Commit**: 776e1d0

## Overview

The trade history database implements a **hybrid storage approach** for trade lifecycle management:

- **Active Trades**: Stored in JSON files (fast, simple, reliable during market hours)
- **Completed Trades**: Archived to SQLite database (analytics, reporting, visualizations)

This design provides optimal performance for live trading while enabling comprehensive historical analysis.

## Architecture

### Database Schema

```sql
CREATE TABLE trade_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Trade identification
    trade_id TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    asset_type TEXT DEFAULT 'stock',

    -- Entry details
    entry_date TEXT NOT NULL,
    entry_price REAL NOT NULL,
    entry_order_id TEXT,
    quantity INTEGER NOT NULL,

    -- Exit details
    exit_date TEXT,
    exit_price REAL,
    exit_order_id TEXT,
    exit_reason TEXT,

    -- Risk management
    initial_stop_loss REAL,
    initial_take_profit REAL,
    final_stop_loss REAL,
    final_take_profit REAL,
    stop_adjustments INTEGER DEFAULT 0,

    -- Performance metrics
    realized_pnl REAL,
    realized_pnl_pct REAL,
    max_profit_pct REAL,
    max_drawdown_pct REAL,
    holding_period_hours REAL,

    -- Strategy attribution
    strategy_name TEXT,
    signal_strength TEXT,
    signal_confidence REAL,

    -- Execution quality
    entry_slippage_pct REAL,
    exit_slippage_pct REAL,
    commission_paid REAL,

    -- Broker tracking
    broker_account TEXT DEFAULT 'alpaca_paper',

    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    notes TEXT  -- JSON field for additional details
)
```

### Indexes

Optimized for common analytics queries:

- `idx_trade_symbol`: Symbol-based filtering
- `idx_trade_entry_date`: Time-based filtering
- `idx_trade_strategy`: Strategy performance analysis
- `idx_trade_exit_reason`: Exit reason analysis
- `idx_trade_broker`: Multi-broker tracking

## API Reference

### TradingCacheManager Methods

#### `archive_trade(trade_data: Dict[str, Any]) -> bool`

Archive a completed trade to the database.

**Required Fields**:

- `trade_id`: Unique identifier
- `symbol`: Stock symbol
- `entry_date`: Entry datetime (ISO format)
- `entry_price`: Entry price
- `quantity`: Number of shares

**Optional Fields**:

- `exit_date`, `exit_price`, `exit_reason`
- `initial_stop_loss`, `initial_take_profit`
- `realized_pnl`, `realized_pnl_pct`
- `strategy_name`, `signal_strength`, `signal_confidence`
- `broker_account`
- `notes`: Dict (will be JSON serialized)

**Example**:

```python
from src.data_sources.cache import TradingCacheManager

cache = TradingCacheManager()

trade_data = {
    'trade_id': 'TQQQ_2024-01-15T10:30:00',
    'symbol': 'TQQQ',
    'entry_date': '2024-01-15T10:30:00',
    'entry_price': 50.25,
    'quantity': 100,
    'exit_date': '2024-01-15T15:45:00',
    'exit_price': 52.10,
    'exit_reason': 'take_profit',
    'realized_pnl': 185.0,
    'realized_pnl_pct': 3.68,
    'strategy_name': 'VoterAgent',
    'signal_strength': 'BULLISH',
    'signal_confidence': 0.85
}

cache.archive_trade(trade_data)
```

#### `get_trade_history(...) -> pd.DataFrame`

Query trade history with flexible filters.

**Parameters**:

- `symbol`: Filter by symbol (None = all)
- `start_date`: Entry date >= start_date (YYYY-MM-DD)
- `end_date`: Entry date <= end_date (YYYY-MM-DD)
- `strategy`: Filter by strategy name
- `broker_account`: Filter by broker account
- `limit`: Limit number of results

**Example**:

```python
# Get all TQQQ trades from 2024
trades = cache.get_trade_history(
    symbol="TQQQ",
    start_date="2024-01-01"
)

print(f"Total trades: {len(trades)}")
print(f"Win rate: {(trades['realized_pnl'] > 0).sum() / len(trades) * 100:.1f}%")
print(f"Total P&L: ${trades['realized_pnl'].sum():.2f}")

# Get VoterAgent trades from last month
import datetime
last_month = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
voter_trades = cache.get_trade_history(
    strategy="VoterAgent",
    start_date=last_month
)
```

#### `get_trade_stats(...) -> Dict[str, Any]`

Get aggregated trading statistics.

**Parameters**:

- `symbol`: Filter by symbol (None = all)
- `strategy`: Filter by strategy (None = all)

**Returns**:

- `total_trades`: Total number of trades
- `winning_trades`: Number of profitable trades
- `losing_trades`: Number of losing trades
- `win_rate_pct`: Win rate percentage
- `total_pnl`: Total realized P&L
- `avg_pnl`: Average P&L per trade
- `avg_win`: Average winning trade
- `avg_loss`: Average losing trade
- `profit_factor`: Gross profit / gross loss
- `avg_holding_hours`: Average holding period

**Example**:

```python
# Overall stats
stats = cache.get_trade_stats()
print(f"System Performance:")
print(f"  Win Rate: {stats['win_rate_pct']:.1f}%")
print(f"  Profit Factor: {stats['profit_factor']:.2f}")
print(f"  Total P&L: ${stats['total_pnl']:.2f}")
print(f"  Avg Win: ${stats['avg_win']:.2f}")
print(f"  Avg Loss: ${stats['avg_loss']:.2f}")
print(f"  Avg Hold: {stats['avg_holding_hours']:.1f} hours")

# VoterAgent specific stats
voter_stats = cache.get_trade_stats(strategy="VoterAgent")
print(f"\nVoterAgent Performance:")
print(f"  Total Trades: {voter_stats['total_trades']}")
print(f"  Win Rate: {voter_stats['win_rate_pct']:.1f}%")
```

## Integration

### TradeCycle Auto-Archival

The `TradeCycle` class automatically archives trades when positions are closed:

```python
# In trade_lifecycle.py
def close_position(self, reason: str = "Manual close") -> bool:
    # ... existing close logic ...

    if close_result['status'] == 'submitted':
        self.data.state = TradeState.EXIT_TRIGGERED.value
        self.save_state()

        # Automatic archival to database
        self._archive_to_database(reason=reason)

        return True
```

**Key Points**:

- ✅ Non-invasive: Single line addition to existing code
- ✅ Fail-safe: Won't break trade execution if DB unavailable
- ✅ Automatic: No manual intervention required
- ✅ Complete: Captures full trade lifecycle data

## Use Cases

### Performance Analysis

```python
from src.data_sources.cache import TradingCacheManager
import pandas as pd

cache = TradingCacheManager()

# Get all trades
all_trades = cache.get_trade_history()

# Calculate cumulative P&L
all_trades['cumulative_pnl'] = all_trades['realized_pnl'].cumsum()

# Plot equity curve
import matplotlib.pyplot as plt
plt.figure(figsize=(12, 6))
plt.plot(all_trades['entry_date'], all_trades['cumulative_pnl'])
plt.title('Equity Curve')
plt.xlabel('Date')
plt.ylabel('Cumulative P&L ($)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

### Strategy Comparison

```python
# Compare strategies
strategies = ['VoterAgent', 'TradeCycle', 'MACD+RSI']
comparison = []

for strategy in strategies:
    stats = cache.get_trade_stats(strategy=strategy)
    comparison.append({
        'Strategy': strategy,
        'Trades': stats['total_trades'],
        'Win Rate': f"{stats['win_rate_pct']:.1f}%",
        'Total P&L': f"${stats['total_pnl']:.2f}",
        'Profit Factor': f"{stats['profit_factor']:.2f}",
        'Avg P&L': f"${stats['avg_pnl']:.2f}"
    })

df_comparison = pd.DataFrame(comparison)
print(df_comparison.to_string(index=False))
```

### Exit Reason Analysis

```python
# Analyze exit reasons
all_trades = cache.get_trade_history()

# Group by exit reason
exit_analysis = all_trades.groupby('exit_reason').agg({
    'trade_id': 'count',
    'realized_pnl': ['sum', 'mean'],
    'holding_period_hours': 'mean'
})

print("\nExit Reason Analysis:")
print(exit_analysis)

# Win rate by exit reason
win_rate_by_exit = all_trades.groupby('exit_reason').apply(
    lambda x: (x['realized_pnl'] > 0).sum() / len(x) * 100
)
print("\nWin Rate by Exit Reason:")
print(win_rate_by_exit)
```

## Database Location

Trade history is stored in: `.cache/trading_cache.db`

Same database as options and market data for unified analytics.

## Future Enhancements

With this foundation, future features can include:

1. **TradingView-Style Dashboards**
   - Real-time equity curves
   - Drawdown visualization
   - Rolling performance metrics

2. **Advanced Analytics**
   - Monte Carlo simulations
   - Risk-adjusted returns (Sharpe, Sortino)
   - Trade correlation analysis

3. **Performance Attribution**
   - Strategy contribution to overall P&L
   - Symbol performance breakdown
   - Time-of-day/day-of-week analysis

4. **Execution Quality**
   - Slippage tracking
   - Fill rate analysis
   - Commission impact

5. **Reporting**
   - PDF performance reports
   - Email/Slack notifications
   - Automated trade journals

## Related Documentation

- [Issue #373](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/373): Multi-Provider Database Storage
- [sqlite_cache.py](../src/data_sources/cache/sqlite_cache.py): Database implementation
- [trade_lifecycle.py](../src/trading/trade_lifecycle.py): TradeCycle integration
