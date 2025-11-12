# Interactive CLI Testing Session - 2025-01-11

**Tester:** User (live testing)
**System:** Unified Interactive CLI
**Branch:** DocsGroomingAndReview
**Focus:** Natural language UX and system feel

---

## Test Case: "buy qqq at a pullback"

### User Intent
- **Action:** BUY
- **Ticker:** QQQ
- **Timing:** "at a pullback" (wait for price to drop, then buy)
- **Expected:** System suggests limit order below current price

### System Response
```
⏳ Analyzing trade...
Using fallback portfolio value: $100,000
Using fallback buying power: $50,000

⚠️  WARNING: SELL signal detected.
   This system does not support short selling.
   Only SELL if you currently hold this position.
   Otherwise, ignore this signal.

======================================================================
📊 QQQ @ $623.23
======================================================================
⬇️ SELL SUGGESTED
   Confidence: 65.0%

📈 Analysis:
   • Weak signal: Only MACD signals SELL
   • MACD: SELL (histogram: -1.247295)
   • RSI: HOLD (value: 56.2)
   • ⚠️ Weak signal from single indicator
```

### Issues Identified

#### ❌ Issue 1: User Intent Ignored
**Severity:** High
**Category:** UX / Parser

**Problem:**
- User said **BUY**, system suggested **SELL**
- Strategy analyzer overrode user's explicit request
- System feels mechanical - doesn't listen to user

**Root Cause:**
- Parser extracts action="buy" correctly
- But orchestrator runs strategy analysis independently
- Strategy signal (SELL) replaces user intent (BUY)

**Expected Behavior:**
```
📊 QQQ @ $623.23
⬆️ BUY (as requested)

⚠️  Note: Current signals show bearish (SELL)
   MACD: SELL, RSI: HOLD
   Confidence in BUY setup: 35% (low)

Suggested pullback entry: $605.00 (-2.9% from current)
Continue with BUY limit order? [yes/no/wait]
```

**Created Issue:** #347 - UX: Respect user intent when signals disagree

---

#### ❌ Issue 2: "Pullback" Context Not Understood
**Severity:** High
**Category:** Parser / Natural Language Understanding

**Problem:**
- "at a pullback" means wait for price to drop
- User wants limit order below current price
- System doesn't understand timing context

**Root Cause:**
- Parser doesn't extract timing intent ("pullback", "dip", "breakout")
- No field in TradeRequest for entry timing
- No logic to suggest limit prices for pullbacks

**Expected Behavior:**
```
User wants to: BUY at a pullback
Current price: $623.23
Suggested entry: $605.00 (-2.9% pullback)

Options:
1. Place limit order at $605.00
2. Set price alert at $605.00
3. Custom entry price: _____
```

**Created Issue:** #344 - LLM Parser: Support 'pullback' and price timing context

---

#### ❌ Issue 3: No Position Context
**Severity:** Medium
**Category:** Data / UX

**Problem:**
- System suggests SELL without checking if user holds QQQ
- Shows "short selling" warning without position check
- Missing context: "You currently hold X shares"

**Root Cause:**
- Trade suggestions don't query existing positions
- No display of current holdings before recommendation
- API call to Alpaca every time (no local cache)

**Expected Behavior:**
```
📊 QQQ @ $623.23
📊 Current Position: 0 shares

⬆️ BUY (as requested)
[... rest of analysis ...]
```

Or if position exists:
```
📊 QQQ @ $623.23
📊 Current Position: 10 shares @ $610.00 (avg entry)
   Unrealized P/L: +$132.30 (+2.17%)

⬆️ BUY ADDITIONAL suggested
Add to existing position? [yes/no]
```

**Created Issues:**
- #345 - Check existing positions before SELL suggestions
- #346 - Local position/order cache with staleness check

---

## UX Findings: "Mechanical Feel"

### What Makes It Feel Mechanical

1. **Ignores user's stated intent**
   - User says BUY → System says SELL
   - Feels like system doesn't listen

2. **No context awareness**
   - Doesn't check what user already holds
   - Doesn't remember recent queries
   - Treats each request in isolation

3. **Technical jargon over helpful guidance**
   - "SELL SUGGESTED" when user said buy
   - "Short selling warning" when user has no position
   - Shows signals but doesn't explain in user's context

4. **Doesn't understand nuance**
   - "pullback" = user wants to wait for dip
   - "breakout" = user wants to wait for rally
   - System treats all requests as immediate

### What Would Make It Feel More Human

1. **Respect user intent**
   - If user says BUY, analyze BUY (even if signals say SELL)
   - Provide context: "Signals are bearish but here's your BUY analysis"

2. **Show position context**
   - "You don't hold QQQ" before suggesting sell
   - "You have 10 shares" when analyzing position

3. **Understand timing**
   - "pullback" → suggest entry below current price
   - "dip" → same as pullback
   - "breakout" → suggest entry above current price
   - "now" → market order or current price

4. **Collaborative, not dictatorial**
   - "Here's what I see (signals), what do you think?"
   - "Signals disagree with your plan - are you sure?"
   - "I'd suggest X but you asked for Y - want to proceed?"

---

## Recommendations for Testing

### High Priority UX Issues
1. ✅ **Issue #347** - Respect user intent (critical UX flaw)
2. ✅ **Issue #344** - Understand pullback/timing context
3. ✅ **Issue #345** - Show position context before suggestions

### Performance/Caching
4. ✅ **Issue #346** - Local cache for positions/orders

### Testing Approach

**Continue Interactive Testing:**
- Test more natural language variations
- Try different timing contexts ("on a dip", "at breakout", "wait for")
- Test with and without existing positions
- Test when signals agree vs disagree with user

**Specific Test Cases to Try:**
```
1. "buy SPY on a dip"
2. "sell my AAPL position"
3. "wait for QQQ to break 630 then buy"
4. "what's my position in TQQQ?"
5. "should I sell NVDA?" (when holding)
6. "should I sell NVDA?" (when not holding)
7. "buy MSFT at market"
8. "set alert for SPY at 600"
```

---

## Test Results Summary

| Category | Status | Issues Created |
|----------|--------|----------------|
| **User Intent** | ❌ Not respected | #347 |
| **Timing Context** | ❌ Not understood | #344 |
| **Position Context** | ❌ Not shown | #345 |
| **Local Caching** | ❌ Not implemented | #346 |
| **LLM Routing** | ✅ Works (from previous session) | - |
| **Mode Toggle** | ✅ Works | - |
| **Order Status** | ✅ Works | - |

---

## Next Steps

### Immediate (High Priority)
1. Implement user intent priority (#347)
2. Add pullback/timing context to parser (#344)
3. Show position context in suggestions (#345)

### Short Term (Medium Priority)
4. Implement local broker cache (#346)
5. Continue interactive testing with fixes
6. Document UX patterns in ADRs

### Future Testing
- Test with paper trading (real executions)
- Test scheduler integration
- Test position alerts with live positions
- Multi-day testing (cache staleness, persistence)

---

## Key Learnings

**UX Philosophy:**
> "A layman shouldn't have to think hard. The system should understand context, respect intent, and guide intelligently without being mechanical."

**Design Principles Discovered:**
1. **User intent > Strategy signals** - Respect what user asks for
2. **Context is king** - Show what's relevant (positions, prices, timing)
3. **Collaborative, not dictatorial** - Suggest, don't command
4. **Natural language = understand nuance** - "pullback" ≠ "buy now"

**Technical Debt Identified:**
- No position context in trade suggestions
- No local caching (hits API every time)
- Parser doesn't understand timing nuance
- User intent can be overridden by strategy

---

---

## Test Case 2: "what is my stop level on meta"

### User Intent
- **Query:** Check stop loss level for existing META position
- **Expected:** Show stop loss order details (price, status)
- **Context:** User has META position with bracket orders (stop + take profit)

### System Response
```
💼 Portfolio Status...

📊 Positions (2):
   🔴 META: 8 shares @ $0.00
      Value: $4,999.52
      P/L: $-25.00 (-0.50%)
   🟢 SPY: 14 shares @ $0.00
      Value: $9,536.94
      P/L: $330.61 (+3.59%)
```

### Issues Identified

#### ❌ Issue 4: Stop Level Query Shows Portfolio, Not Orders
**Severity:** High
**Category:** Router / Handler

**Problem:**
- User asked about "stop level" (order info)
- System routed to portfolio handler (position info)
- Didn't show actual stop loss orders set on Alpaca

**Root Cause:**
- Router doesn't recognize "stop level" as order query
- No dedicated handler for position-specific orders
- Keywords like "stop", "target", "take profit" not in routing

**Expected Behavior:**
```
📋 META Orders:

✅ ENTRY (Filled)
   BUY 8 shares @ $625.12
   Filled: 2025-01-11 09:35:00

🔴 STOP LOSS (Open)
   Stop Price: $610.00 (-2.4% from entry)
   Order ID: abc123...
   Status: PENDING

🟢 TAKE PROFIT (Open)
   Limit Price: $675.00 (+8.0% from entry)
   Order ID: def456...
   Status: PENDING

📊 Current: META @ $624.96
   Distance to stop: -2.4%
   Distance to target: +8.0%
```

**Created Issue:** #348 - CLI: Show order details when asking about stops/targets

---

#### ✅ Issue 5: Entry Price Shows $0.00 (BUG) - RESOLVED
**Severity:** High
**Category:** Data / Bug
**Status:** ✅ FIXED in commit 87dbcfb (2025-11-11)

**Problem:**
```
🔴 META: 8 shares @ $0.00    <-- Should show actual entry price
   P/L: $-25.00 (-0.50%)
```

This is mathematically impossible:
- If entry = $0.00, P/L would be +∞%
- Shows -0.50% loss but entry is $0.00?
- Can't calculate accurate P/L without entry price

**Root Cause (IDENTIFIED):**
- Code was displaying `current_price` field instead of `avg_entry_price`
- Alpaca position dict doesn't provide `current_price` directly
- Field needed to be calculated from `market_value / qty`

**Solution Implemented:**
- Extract `avg_entry_price` from position data correctly
- Calculate `current_price` from `market_value / qty`
- Use `cost_basis / qty` as fallback if `avg_entry_price` is 0
- Display both entry and current prices separately with clear labels

**Fixed Behavior:**
```
🔴 META: 8 shares @ $625.12 (avg entry)
   Current: $624.96
   Value: $4,999.68
   P/L: $-1.28 (-0.20%)
```

**Issue #349:** ✅ CLOSED - Fixed in commit 87dbcfb

---

#### ❌ Issue 6: Can't Distinguish Filled vs Open Orders
**Severity:** Medium
**Category:** UX / Data Display

**Problem:**
- System shows positions but not order history
- Can't see which orders are filled vs pending
- No visibility into bracket order legs (stop/target)

**Expected Behavior:**
```
📋 Order History for META:

✅ FILLED
   BUY 8 META @ $625.12 (market)
   Filled: 2025-01-11 09:35:00

🟡 PENDING
   STOP LOSS @ $610.00 (stop)
   Order ID: abc123...

🟡 PENDING
   TAKE PROFIT @ $675.00 (limit)
   Order ID: def456...
```

**Covered by Issue:** #348 (order details handler)

---

## Test Results Summary (Updated)

| Test Case | Issue Found | Severity | Issue # | Status |
|-----------|-------------|----------|---------|--------|
| "buy qqq at pullback" | User intent ignored | High | #347 | Open |
| "buy qqq at pullback" | Pullback not understood | High | #344 | Open |
| "buy qqq at pullback" | No position context | Medium | #345 | Open |
| General | No local cache | Medium | #346 | Open |
| "stop level on meta" | Shows portfolio not orders | High | #348 | Open |
| Portfolio display | Entry price = $0.00 | High | #349 | ✅ Fixed |
| Order visibility | Can't see filled vs open | Medium | #348 | Open |

**Total Issues Found:** 7 issues across 6 unique problems
**Resolved:** 1 issue (#349)
**Remaining Open:** 5 unique issues (#344, #345, #346, #347, #348)

---

## Related Documents

- Test Plan: `docs/features/05_interactive_cli_test_plan.md`
- CLI Implementation: `src/cli/cli_session.py`
- Parser: `src/parsers/llm_parser.py`
- Orchestrator: `src/core/trading_orchestrator.py`

**Issues Created (Testing Session):**
- #344 - Parser: Pullback/timing context
- #345 - Position context in suggestions
- #346 - Local broker cache
- #347 - Respect user intent priority
- #348 - Show order details for stop/target queries
- #349 - BUG: Entry price shows $0.00
