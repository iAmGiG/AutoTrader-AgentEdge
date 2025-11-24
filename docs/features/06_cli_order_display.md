# CLI Order Display Patterns

**Feature**: Grouped, hierarchical order display for open orders command
**Status**: Proposed in Issue #371, implementation pending
**Purpose**: Make order relationships and position structure immediately scannable

---

## Overview

The `open orders` command displays all pending orders with visual grouping to show bracket relationships, multi-PT structures, and position direction. This replaces the flat list format with a hierarchical display that reveals order structure at a glance.

---

## Display Format

### Grouped Display Example

```
📊 5 Open Order(s):

┌─ $SPY Position (3 orders) - LONG
│  🟢 buy 7.0 @ market - NEW (1b449d18)
│  🎯 PT1: sell 7.0 @ $595.00 - HELD (7aab4c55)  ← closest target
│  🎯 PT2: sell 7.0 @ $600.00 - HELD (8ccf5d66)
│  🛑 SL: sell 7.0 @ $580.00 - HELD (9dde6e77)   ← furthest from entry
│
└─ $O Position (2 orders) - SHORT
   ⚪ sell 88.0 @ market - NEW (c15bc2e9)
   🎯 PT1: buy 88.0 @ $55.00 - HELD (d1ef7f88)   ← closest target
   🛑 SL: buy 88.0 @ $62.00 - HELD (e2fg8g99)    ← furthest from entry
```

---

## Design Elements

### 1. $TICKER Prefix

**Purpose**: Visual escape sequence for tickers
**Format**: `$SPY`, `$AAPL`, `$O`

**Benefits**:
- Matches trading terminal conventions
- Immediately scannable among text
- Machine-parseable for automation
- Separates ticker from surrounding content

### 2. Position Direction

**Shows**: Overall position bias for the order group

**Values**:
- `LONG` - Bullish equity position or long call
- `SHORT` - Bearish equity position or short call
- `LONG CALL` - Bullish option position
- `LONG PUT` - Bearish option position
- `SHORT PUT` - Bullish STO (sell to open)
- `SHORT CALL` - Bearish STO (sell to open)

**Example**: `$SPY Position (3 orders) - LONG`

### 3. Order Type Emojis

| Emoji | Meaning | When Used |
|-------|---------|-----------|
| 🟢 | Buy order | Entry for LONG, exit for SHORT |
| ⚪ | Sell order | Exit for LONG, entry for SHORT |
| 🎯 | Profit Target | Take-profit orders (PT1, PT2, ...) |
| 🛑 | Stop-Loss | Risk management stop orders |

### 4. PT Numbering

**Logic**: PT1 is always the closest profit target to current price

**LONG Position** (ascending prices):
```
Entry → PT1 @ $595 → PT2 @ $600 → SL @ $580
```

**SHORT Position** (descending prices):
```
Entry → PT1 @ $55 → SL @ $62
```

**Reasoning**: Shows natural profit progression from entry → nearest target → further targets → stop

### 5. Visual Hierarchy

**Box Drawing Characters**:
- `┌─` Top border (first order in group)
- `│` Continuation lines (middle orders)
- `└─` Bottom border (last order in group)
- Blank line between position groups

**Purpose**: Visual connection shows which orders belong together

### 6. One-Line Format

**Format**: `[emoji] [side] [qty] @ [price] - [status] ([order_id])`

**Example**: `🟢 buy 7.0 @ market - NEW (1b449d18)`

**Benefits**:
- All critical info visible at a glance
- Compact, scannable format
- No scrolling needed for multi-order positions

---

## Options Display

### Direction Logic

**LONG CALL** (Bullish):
- Higher prices = profit
- PT ordering: Ascending (same as LONG stock)

**LONG PUT** (Bearish):
- Lower prices = profit
- PT ordering: Descending (same as SHORT stock)

**SHORT CALL** (Bearish STO):
- Lower prices = profit (expire worthless is ideal)
- Maximum profit = premium collected
- Display: "max profit @ expiry" instead of PT

**SHORT PUT** (Bullish STO):
- Higher prices = profit (expire worthless is ideal)
- Maximum profit = premium collected
- Display: "max profit @ expiry" instead of PT

### Options Example

```
┌─ $SPY Position (3 orders) - LONG CALL
│  🟢 buy 1 $600C exp 2025-02-21 @ $2.50 - FILLED (abc123)
│  🎯 PT1: sell 1 @ $3.50 - HELD (def456)
│  🛑 SL: sell 1 @ $1.50 - HELD (ghi789)
│
└─ $IWM Position (2 orders) - SHORT PUT (STO)
   ⚪ sell 1 $220P exp 2025-02-21 @ $1.20 - FILLED (xyz789)
   🎯 max profit @ expiry (worthless) - $120.00 credit
   🛑 SL: buy 1 @ $2.50 - HELD (mno456)
```

---

## Special Cases

### Orphaned Orders

Orders without clear bracket structure display ungrouped:

```
┌─ $SPY Position (2 orders) - LONG
│  🟢 buy 10.0 @ market - NEW (abc123)
│  🛑 SL: sell 10.0 @ $590.00 - HELD (def456)

Ungrouped Orders:
  ⚪ sell 5.0 $AAPL @ limit $175.00 - NEW (ghi789)
```

### Partial Fills

Show filled quantity vs total quantity:

```
│  🟢 buy 7.0/10.0 @ market - PARTIALLY_FILLED (abc123)
```

### Mixed Order Types

Single symbol with multiple order structures:

```
┌─ $SPY Position (4 orders)
│  Bracket #1:
│  🟢 buy 10.0 @ market - FILLED (abc123)
│  🎯 PT1: sell 10.0 @ $595.00 - HELD (def456)
│  🛑 SL: sell 10.0 @ $585.00 - HELD (ghi789)
│
│  Standalone:
│  ⚪ sell 5.0 @ limit $600.00 - NEW (jkl012)
```

---

## Implementation Details

### Data Sources

- **Order metadata**: `AlpacaAccountMonitor.get_orders()`
- **Bracket relationships**: `order_class` and `legs` fields from Alpaca API
- **Position direction**: Infer from entry order side or query local state

### Grouping Algorithm

1. Fetch all open orders from broker
2. Identify bracket relationships via `order_class` and `legs` metadata
3. Group orders by symbol
4. Within each symbol group:
   - Detect position direction (buy entry = LONG, sell entry = SHORT)
   - Sort orders: Entry first → PTs by proximity → SL last
5. Format output with box drawing characters

### Files Modified

- `src/cli/cli_session.py` - `_handle_order_status()` method
- `src/trading/alpaca_trading_client.py` - Already returns grouped legs
- Optional: `src/trading/unified_state_manager.py` - Position direction lookup

---

## Testing Checklist

- [ ] Single market order (no grouping needed)
- [ ] Bracket order (entry + PT + SL)
- [ ] Multiple PTs (entry + PT1 + PT2 + SL)
- [ ] Short position with proper ordering
- [ ] Multiple tickers displayed correctly
- [ ] Options display (calls and puts, long and short)
- [ ] Partially filled orders
- [ ] Held orders from bracket legs
- [ ] Orphaned/ungrouped orders
- [ ] Mixed order types (bracket + standalone)

---

## Future Enhancements

**Visual**:
- Color coding by P&L (green = profitable, red = losing)
- Live price updates with distance to targets
- Highlight imminent stop triggers

**Interactive**:
- Quick cancel: `cancel order 3` to cancel PT2
- Bulk operations: `cancel all $SPY orders`
- Interactive order modification from CLI

**Analysis**:
- Export to CSV/JSON for analysis
- Generate order flow diagrams
- Historical order pattern analysis

---

## Related Documentation

- [Alpaca Integration](../02_architecture/05_integration_apis.md) - Order data structure
- [CLI Trade Assistant](../04_development/03_cli_trade_assistant.md) - Trading interface architecture
- [Scheduler CLI Reference](scheduler_cli_reference.md) - Related CLI patterns

## Related Issues

- [Issue #371](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/371) - Implementation tracking

---

*User experience design for terminal-based trading. Patterns evolve based on real-world usage feedback.*
