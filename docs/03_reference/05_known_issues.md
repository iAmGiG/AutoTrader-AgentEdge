# Known Issues

## 1. Bracket Order Price Validation During Off-Hours

**Status**: Known limitation
**Severity**: Medium
**Affects**: Bracket orders placed outside market hours

### Description

When placing bracket orders outside of market hours (weekends, after-hours):

- Market data API returns fallback/cached prices (or default $100)
- Alpaca's order validation uses real-time quote prices
- This causes validation errors like: `take_profit.limit_price must be >= base_price + 0.01`

### Example

```
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

### Workarounds

**Option 1: Market Hours Only** (Recommended for Production)

```python
# Only allow bracket orders during market hours
if not self._is_market_hours():
    return OrderResult(
        success=False,
        message="Bracket orders only supported during market hours"
    )
```

**Option 2: Market Entry Only During Off-Hours**

```python
# Place market order without bracket during off-hours
# Then add stop/target after fill
if not self._is_market_hours():
    # Place simple market order
    # Monitor fill, then add bracket legs
```

**Option 3: Fetch Last Quote Price**

```python
# Use Alpaca's last quote API for validation
quote = self.market_data.get_latest_quote(ticker)
if quote:
    current_price = (quote['bid'] + quote['ask']) / 2
    # Recalculate bracket prices
```

### Temporary Solution

For testing during weekends:

1. Use stub mode (no real OrderManager)
2. Test during market hours (Mon-Fri 9:30am-4pm ET)
3. Use simple market orders without brackets

### Permanent Fix (TODO)

- [ ] Add `get_latest_quote()` fallback in execution manager
- [ ] Use Alpaca's quote API for price validation
- [ ] Calculate bracket prices from validated base price
- [ ] Add market hours check before bracket orders
- [ ] Consider GTC limit orders instead of market+bracket

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
