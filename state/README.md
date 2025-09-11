# State Management

This directory contains state files for the RH2MAS trading system.

## Current State Files

The system uses simple JSON files for state persistence:

### **positions.json** (TradeCycle)
- **Purpose**: Trade lifecycle state persistence (SIGNAL → ORDER → POSITION → CLOSED)
- **Managed By**: `TradeCycle` class in `src/trading/trade_lifecycle.py`
- **Contains**: Individual trade data by symbol with order IDs, prices, timestamps
- **Location**: `state/positions.json`
- **Format**: `{symbol: TradeData}` dictionary structure

## State Management Implementation

### **Simple JSON Persistence**
- **Primary Source**: Alpaca broker API (live data)
- **Local Files**: State persistence across restarts only
- **No Complex Caching**: Direct API calls with rate limiting

### **Trade Lifecycle States**
```
SIGNAL_GENERATED → ORDER_PENDING → POSITION_OPEN → POSITION_CLOSED
```

### **Usage Example**
```python
# Create trade cycle
trade = TradeCycle('TQQQ', 'BULLISH', 0.75)

# Place bracket order (entry + stop + target)
success = trade.place_entry_order(current_price)

# Monitor for fills
if trade.check_order_fills():
    # State automatically transitions: ORDER_PENDING → POSITION_OPEN
    pass

# Save state to positions.json
trade.save_state()
```

### **State File Structure**
```json
{
  "TQQQ": {
    "symbol": "TQQQ",
    "state": "open", 
    "entry_price": 50.00,
    "quantity": 100,
    "order_ids": {"parent": "order_123"}
  }
}
```

## Legacy Files

**Status**: Legacy files moved to `/deprecated/state_legacy/` at project root.

---

*Simple state management for production trading system.*

*Last Updated: September 10, 2025 - Post Critical Implementation Fixes*