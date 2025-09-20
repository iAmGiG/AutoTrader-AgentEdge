# Alpaca Order Management System

**Status**: ✅ PRODUCTION READY (September 9, 2025)  
**Implementation**: `src/trading/alpaca_trading_client.py`  
**Tests**: 29/29 passing (`tests/test_alpaca_order_manager.py`, `tests/test_alpaca_advanced_orders.py`)  
**AutoGen Integration**: `src/trading/alpaca_autogen_tools.py`

## Overview

Complete order management system built on the official Alpaca Markets SDK with advanced order types, comprehensive risk management, and unified live/paper trading architecture.

## Architecture

```bash
src/trading/
├── alpaca_trading_client.py     # Core order management classes
└── alpaca_autogen_tools.py      # AutoGen agent integration

Classes:
├── AlpacaTradingClient          # Base client with unified live/paper support
├── AlpacaAccountMonitor         # Account status and position monitoring  
└── AlpacaOrderManager           # Complete order management with risk controls
```

## Core Features

### Order Types

- **Market Orders**: Immediate execution at current market price
- **Limit Orders**: Execute at specified price or better (GTC/DAY support)
- **Stop Orders**: Trigger market order when price reaches stop level
- **Trailing Stop Orders**: Dynamic stop that follows price movement
- **Bracket Orders**: Entry + take profit + stop loss combinations

### Risk Management

- **Market Hours Validation**: Timezone-aware trading session checking
- **Daily Trade Limits**: Configurable maximum orders per market day
- **Position Validation**: Automatic position requirement checks for sell orders
- **Buying Power Checks**: Real-time buying power validation
- **Order Size Limits**: Configurable maximum order size enforcement

### Safety Features

- **Unified Live/Paper Architecture**: Single codebase, different credentials
- **Multi-level Confirmations**: Extra safety for live trading operations
- **Mode-aware Logging**: Clear indicators for live vs paper operations
- **Comprehensive Validation**: Multiple validation layers before order submission

## Usage Examples

### Basic Order Placement

```python
from src.trading.alpaca_trading_client import AlpacaOrderManager

# Initialize with risk limits
manager = AlpacaOrderManager(
    mode="paper",  # or "live"
    risk_limits={
        'max_order_size': 1000,
        'max_daily_trades': 50
    }
)

# Market order
result = manager.place_market_order("AAPL", 100, "buy")
print(f"Order status: {result['status']}")

# Limit order
result = manager.place_limit_order_gtc("AAPL", 100, "buy", 150.00)
print(f"Order ID: {result['order_id']}")
```

### Advanced Order Types

```python
# Stop order
result = manager.place_stop_order("AAPL", 100, "sell", 140.00)

# Trailing stop (5% trail)
result = manager.place_trailing_stop_order(
    "AAPL", 100, "sell", trail_percent=0.05
)

# Bracket order (entry + profit target + stop loss)
result = manager.place_bracket_order(
    symbol="AAPL",
    qty=100,
    side="buy",
    entry_limit_price=150.00,  # None for market entry
    take_profit_price=160.00,
    stop_loss_price=140.00
)
```

### Order Management

```python
# Modify existing order
result = manager.modify_order(
    order_id="abc123",
    qty=150,  # Change quantity
    limit_price=155.00  # Change price
)

# Cancel single order
result = manager.cancel_order("abc123")

# Cancel all orders for symbol
result = manager.cancel_all_orders(symbol="AAPL")

# Cancel all open orders
result = manager.cancel_all_orders()
```

## AutoGen Integration

```python
from src.trading.alpaca_autogen_tools import AlpacaOrderTool, AlpacaAccountTool

# For agents - read-only account access
account_tool = AlpacaAccountTool(mode="paper")
status = account_tool.get_account_status()
positions = account_tool.get_positions()

# For agents - full order management
order_tool = AlpacaOrderTool(mode="paper")
result = order_tool.place_market_order("AAPL", 100, "buy")
```

## Configuration

### Risk Limits

```python
risk_limits = {
    'max_order_size': 1000,        # Maximum shares per order
    'max_daily_trades': 50,        # Maximum orders per market day
    'max_position_percent': 0.10   # Maximum position size (10% of portfolio)
}
```

### Market Hours Behavior

- **Regular Hours**: 9:30 AM - 4:00 PM ET
- **Extended Hours**: 4:00 AM - 8:00 PM ET (configurable)
- **Closed Market**: Orders queued with warnings
- **Validation Mode**: `warn_only=True` (default) or `warn_only=False` (block)

## Error Handling

All methods return standardized response format:

```python
{
    'status': 'submitted|error|cancelled',
    'message': 'Human-readable description',
    'order_id': 'alpaca_order_id',  # If successful
    'symbol': 'AAPL',
    'qty': 100.0,
    'mode': 'paper|live'
}
```

## Testing

### Test Coverage: 29/29 Passing

- **Basic Orders**: Market, limit, validation, risk limits
- **Advanced Orders**: Stop, trailing stop, bracket orders
- **Market Hours**: Timezone handling, session validation
- **Risk Management**: Daily limits, position checks, buying power
- **Error Handling**: Invalid parameters, API failures
- **Mode Awareness**: Paper vs live operation validation

### Run Tests

```bash
python tests/test_alpaca_order_manager.py      # Basic functionality
python tests/test_alpaca_advanced_orders.py    # Advanced order types
```

## Production Deployment

### Live Trading Setup

1. Add live credentials to `config/config.json`:

   ```json
   {
     "ALPACA_LIVE_API_KEY": "your_live_key",
     "ALPACA_LIVE_SECRET": "your_live_secret"
   }
   ```

2. Initialize with live mode:

   ```python
   manager = AlpacaOrderManager(mode="live")
   ```

3. **Safety Confirmations**: All live operations require explicit confirmation

### Paper Trading (Default)

- Uses paper account credentials
- Full feature compatibility
- No confirmations required
- Safe for development and testing

## Dependencies

- **alpaca-py**: Official Alpaca Markets Python SDK
- **pytz**: Timezone handling for market hours
- **typing**: Type hints and optional parameters
- **logging**: Comprehensive operation logging

## Related Documentation

- [Alpaca Market Data Integration](alpaca_market_data_integration.md)
- [AutoGen Agent Architecture](architecture/)
- [Trading Tools Pure Functions](../src/trading_tools/)

---

*Complete order management system enabling full trading automation with safety, validation, and production-ready architecture.*
