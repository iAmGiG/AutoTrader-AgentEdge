# Known Issues

## 1. Bracket Order Price Validation During Off-Hours

**Status**: ✅ MITIGATED (2025-11-23)
**Severity**: Medium → Low
**Affects**: Bracket orders placed outside market hours

### Description

When placing bracket orders outside of market hours (weekends, after-hours):

- Market data API returns fallback/cached prices (or default $100)
- Alpaca's order validation uses real-time quote prices
- This causes validation errors like: `take_profit.limit_price must be >= base_price + 0.01`

### Example

```text
Analysis shows: AAPL @ $258.45 (from historical data)
Calculated target: $267.50 (+3.5%)
Alpaca validates against: $268.69 (current market quote)
Result: ERROR - target $267.50 < base $268.69
```

### Root Cause

1. `UnifiedPriceFetcher` cannot get live prices during off-hours
2. VoterStrategy uses historical close prices for analysis
3. Alpaca's order API validates against internal real-time quotes
4. Price mismatch causes bracket order rejection

### ✅ Implemented Solution (2025-11-23)

**Feature**: Intelligent off-hours handling with automatic fallback

The `AlpacaExecutionManager` now implements comprehensive off-hours support:

1. **Market Hours Detection**: Automatically detects weekend/off-hours (9:30 AM - 4:00 PM ET, Mon-Fri)
2. **Price Recalculation**: Fetches latest Alpaca quote/trade and recalculates brackets using strategy config
3. **Configurable Percentages**: Uses `stop_loss_pct` (default 5%) and `take_profit_pct` (default 8%) from config
4. **Automatic Fallback**: If bracket order fails during off-hours, automatically places simple market order
5. **Clear Warnings**: Explicit messaging about missing bracket protection

**User Experience During Weekends**:

```text
⚠️  Market is CLOSED (weekend/off-hours).
    Bracket orders may fail validation during off-hours.
❌ Bracket order validation failed (off-hours): take_profit.limit_price must be >= base_price + 0.01
   🔄 Attempting fallback: simple market order without brackets...
✅ Simple market order placed: abc123
   ⚠️  NOTE: Stop-loss and take-profit NOT set (bracket order failed).
   Manual risk management required!
   Target: $712.80, Stop: $624.72
```

### Benefits

- ✅ **Demo-Ready**: System works on weekends for presentations
- ✅ **Production-Safe**: Normal bracket orders during market hours
- ✅ **Clear Warnings**: Users understand exactly what protection is missing
- ✅ **Automatic Handling**: No manual intervention required
- ✅ **Configurable**: Strategy percentages from config, not hardcoded

### Testing During Weekends

Orders place successfully with clear warnings:

1. Bracket order attempted first
2. If validation fails → automatic fallback to simple market order
3. Success returned with warning message
4. Target/stop prices logged for manual monitoring
5. Portfolio and order display work normally

### Implemented Fixes (2025-11-23)

- [x] Added `_is_market_hours()` detection in execution manager
- [x] Fetch latest quote/trade from Alpaca for accurate pricing
- [x] Calculate bracket prices from Alpaca's validated price
- [x] Market hours check with clear warnings
- [x] Automatic fallback to simple market orders during off-hours
- [x] Configurable stop_loss_pct and take_profit_pct parameters

### Future Enhancements

- [ ] Queue orders for next market open (scheduler integration)
- [ ] User choice prompt: "fallback to simple order" vs "queue for market open"
- [ ] Extended hours trading support (extended_hours=True flag)
- [ ] Post-fill bracket leg addition (add stop/target after entry fills)

### Related Files

- `src/execution/alpaca_execution_manager.py:88-148`
- `src/trading/unified_price_fetcher.py:40-100`
- `src/strategies/real_voter_strategy.py:121-133`

### Testing

```bash
# Test during market hours
python test_real_alpaca.py  # Should work Mon-Fri 9:30am-4pm ET

# Test during off-hours
python test_bug_fixes.py    # Uses stub mode - works anytime
```

---

## 2. Short Selling Prevention

**Status**: Working as designed
**Severity**: N/A (Feature)

All SELL signals are blocked at execution level to prevent unintentional short selling. Only BUY orders are allowed for new positions. This is a safety feature, not a bug.

---

**Last Updated**: 2025-11-08
**Next Review**: When implementing portfolio position tracking
