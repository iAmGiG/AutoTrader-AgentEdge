# Interactive CLI Test Plan - Live Testing Guide

**Purpose:** Manual test cases to validate the unified interactive CLI with real user interactions

**Based on:** Issue #334 manual testing + new unified CLI features

**Test Environment:** Paper trading mode (Alpaca)

**Architecture:** LLM-based intelligent routing (see `docs/architecture/llm_routing_architecture.md`)

---

## Routing Architecture Overview

The CLI uses **LLM-based classification** instead of hardcoded keyword patterns:

1. **LLM Parser** determines `request_type`:
   - `"trade"` → Buy/sell/analyze specific ticker
   - `"status_query"` → Account/orders/positions queries

2. **Benefits:**
   - No special cases for ambiguous tickers (ANY, ALL, WHAT, etc.)
   - Natural language understanding via context
   - Scalable without code changes

3. **Fast Keyword Routing** for system features:
   - Scheduler queries → direct routing (no LLM)
   - Alert queries → direct routing (no LLM)

---

## Test Categories

1. **Trade Execution** - Buy/sell orders
2. **Position Monitoring** - Alerts and status checks
3. **Scheduler Management** - Daily automation
4. **Portfolio Queries** - Account information
5. **Error Handling** - Invalid inputs and edge cases
6. **Natural Language** - Various phrasings
7. **LLM Routing** - Ambiguous ticker names
8. **Bare Ticker Input** - Simple ticker symbols (NEW - Issue #356)
9. **Beginner-Friendly UX** - Layman language support (NEW)

---

## Category 1: Trade Execution

### Test 1.1: Simple Buy Request

**Input:**

```
> buy 10 AAPL
```

**Expected Behavior:**

- ✅ Routes to trade handler (not alerts/scheduler/portfolio)
- ✅ Fetches current AAPL price
- ✅ Calculates entry/stop/target
- ✅ Shows position sizing (10 shares)
- ✅ Asks for confirmation
- ✅ Places bracket order if confirmed

**Known Issues from #334:**

- ⚠️ Off-hours: Shows "could not fetch current market price" → OK (expected)
- ⚠️ Bracket order validation: `take_profit.limit_price must be >= base_price + 0.01`
  - **Fix needed:** Ensure target price is at least $0.01 above entry

**Success Criteria:**

- [ ] Order places successfully during market hours
- [ ] Appropriate error message during off-hours
- [ ] Bracket order meets Alpaca validation rules

---

### Test 1.2: Natural Language Buy

**Input:**

```
> is apple at market price a good entry?
```

**Expected Behavior:**

- ✅ Interprets "apple" as AAPL
- ✅ Fetches current market price
- ✅ Runs VoterAgent analysis (MACD+RSI)
- ✅ Presents BUY/SELL/HOLD decision with reasoning
- ✅ Shows entry plan with stop/target

**Known Issues from #334:**

- ⚠️ Bracket order validation error (same as 1.1)

**Success Criteria:**

- [ ] Correctly parses "apple" → AAPL
- [ ] VoterAgent provides decision
- [ ] Order validation passes

---

### Test 1.3: Sell Signal Handling

**Input:**

```
> what about spy at market
```

**Expected Behavior:**

- ⚠️ **IMPORTANT:** System currently rejects SELL signals (no shorting)
- ✅ Should check if SPY position exists
- ✅ If position exists → allow sell
- ✅ If no position → reject with clear message

**Known Issues from #334:**

- ❌ System tries to short sell instead of checking existing positions
- ❌ Error: "Short selling not supported" even when shares owned

**Fix Needed:**

```python
# In _handle_trade_request() or execution layer
if signal == "SELL":
    positions = self.account_monitor.get_positions()
    position = next((p for p in positions if p['symbol'] == ticker), None)

    if not position:
        print("⚠️  Cannot SELL - no position found")
        print("   This system does not support short selling")
        return

    # Proceed with sell of existing position
```

**Success Criteria:**

- [ ] Checks for existing position before SELL
- [ ] Allows sell if position exists
- [ ] Rejects sell with clear message if no position

---

### Test 1.4: Sell Existing Position

**Input (assuming SPY position exists):**

```
> sell all spy
> close my spy position
```

**Expected Behavior:**

- ✅ Detects sell intent
- ✅ Checks for existing SPY position
- ✅ Shows current P/L
- ✅ Confirms quantity to sell
- ✅ Places market sell order

**Success Criteria:**

- [ ] Natural language "sell all" parsed correctly
- [ ] Position check works
- [ ] Sell order places successfully

---

## Category 2: Position Monitoring

### Test 2.1: Check Alerts

**Input:**

```
> check my alerts
> show alerts
> any position alerts?
```

**Expected Behavior:**

- ✅ Routes to `_handle_alerts_request()` (not trade handler)
- ✅ Fetches current broker state
- ✅ Runs `position_tracker.check_alerts()`
- ✅ Shows active alerts with severity
- ✅ Shows alert history (last 5)

**Output Example:**

```
📊 Checking Position Alerts...
✅ No active alerts
   3 position(s) monitored

📜 Alert History (3 total):
   • TQQQ - approaching_take_profit at 14:30:00
   • SPY - stop_adjusted at 09:25:00
```

**Success Criteria:**

- [ ] Keyword "alerts" routes correctly
- [ ] Alert check executes without errors
- [ ] Alert history persists across restarts

---

### Test 2.2: Position Status Query

**Input:**

```
> any positions open
> what positions do I have?
> show my positions
```

**Expected Behavior:**

- ⚠️ **KNOWN BUG from #334:** Fails with "Invalid ticker format"
- ✅ Should route to portfolio handler (not trade handler)
- ✅ Shows list of open positions with P/L

**Known Issues from #334:**

```
ValueError: Invalid request: TradeRequest(ticker='', action='review', ...)
```

- **Root cause:** Parser tries to extract ticker, fails, creates invalid TradeRequest
- **Fix needed:** Add "status" routing keyword to bypass trade parser

**Fix Needed:**

```python
# In _process_request()
if any(word in input_lower for word in ["positions", "position status", "what positions"]):
    await self._handle_portfolio_request(user_input)
    return  # Don't send to trade orchestrator
```

**Success Criteria:**

- [ ] "any positions open" routes to portfolio (not trade)
- [ ] Shows position list correctly
- [ ] No parser errors

---

### Test 2.3: Price Target Query

**Input:**

```
> is there a price target on spy
> what's the target for my aapl position?
```

**Expected Behavior:**

- ✅ Checks existing positions
- ✅ Shows take-profit price for that position
- ✅ Shows stop-loss price
- ✅ Shows distance to targets

**Known Issues from #334:**

- ❌ Parser interprets as new trade request (SELL signal)
- ❌ Tries to short sell instead of checking position details

**Fix Needed:**

- Route "price target" queries to portfolio handler
- Check position details, don't create new trade

**Success Criteria:**

- [ ] Detects query about existing position
- [ ] Shows target/stop prices
- [ ] No unwanted trade suggestions

---

## Category 3: Scheduler Management

### Test 3.1: Scheduler Status

**Input:**

```
> show scheduler status
> what's the scheduler doing?
> when is the next routine?
```

**Expected Behavior:**

- ✅ Routes to `_handle_scheduler_request()`
- ✅ Shows configuration (enabled, times)
- ✅ Shows recent execution history
- ✅ Shows next scheduled tasks

**Output Example:**

```
🤖 Daily Scheduler Status...

Configuration:
   Enabled: True
   Morning routine: 09:20:00 ET
   Evening routine: 15:50:00 ET
   Max retries: 3

📋 Recent Executions (today):
   ✅ morning_routine - completed
      Completed: 2025-01-10T09:20:15

⏰ Scheduled Tasks:
   • morning_routine: 09:20 ET
   • evening_routine: 15:50 ET
```

**Success Criteria:**

- [ ] Keyword "scheduler" routes correctly
- [ ] Configuration displayed
- [ ] Execution history shown

---

### Test 3.2: Execution History

**Input:**

```
> show execution history
> what did the scheduler do today?
```

**Expected Behavior:**

- ✅ Shows today's executions
- ✅ Status for each (completed/failed/pending)
- ✅ Timestamps and error messages if any

**Success Criteria:**

- [ ] History retrieval works
- [ ] Displays last 7 days by default

---

## Category 4: Portfolio Queries

### Test 4.1: Account Status

**Input:**

```
> show portfolio
> what's my account balance?
> show account status
```

**Expected Behavior:**

- ✅ Routes to `_handle_portfolio_request()`
- ✅ Shows equity, cash, buying power
- ✅ Shows PDT status
- ✅ Lists all positions with P/L

**Output Example:**

```
💼 Portfolio Status...

💰 Account:
   Equity: $102,450.00
   Cash: $50,225.00
   Buying Power: $52,000.00
   Pattern Day Trader: False

📊 Positions (3):
   🟢 AAPL: 10 shares @ $185.50
      Value: $1,855.00
      P/L: +$85.00 (+4.58%)
   🔴 TQQQ: 100 shares @ $52.00
      Value: $5,200.00
      P/L: -$200.00 (-3.85%)
```

**Success Criteria:**

- [ ] Account data fetches correctly
- [ ] Position list with P/L shown
- [ ] Emojis display correctly (🟢/🔴)

---

### Test 4.2: Buying Power Query

**Input:**

```
> how much buying power do I have?
> what's my available cash?
```

**Expected Behavior:**

- ✅ Routes to portfolio handler
- ✅ Shows buying power prominently
- ✅ Explains PDT restrictions if applicable

**Known Issues from #334:**

- ⚠️ Fallback values shown: "Using fallback buying power: $50,000"
- **Fix:** Ensure Alpaca API credentials valid

**Success Criteria:**

- [ ] Real buying power from Alpaca (no fallback)
- [ ] Clear display

---

## Category 5: Error Handling

### Test 5.1: Invalid Ticker

**Input:**

```
> buy 10 INVALIDTICKER
```

**Expected Behavior:**

- ✅ Attempts to fetch data
- ✅ Detects invalid ticker
- ✅ Shows helpful error message

**Current Behavior from #334:**

```
❌ Invalid ticker symbol
   The ticker you entered was not recognized by the market.
   Please check the spelling and try again.
   Example: AAPL (not APPL), TSLA, SPY, MSFT
```

**Success Criteria:**

- [ ] Helpful error message shown
- [ ] Suggests valid alternatives
- [ ] Doesn't crash

---

### Test 5.2: Out of Scope Request

**Input:**

```
> what's the weather today?
> tell me a joke
```

**Expected Behavior:**

- ⚠️ **Currently:** Tries to parse as trade request → fails
- ✅ **Should:** Detect out-of-scope, show help message

**Fix Needed:**

- Add fallback handler for unrecognized intents
- Show available command categories

**Success Criteria:**

- [ ] Graceful handling of non-trading requests
- [ ] Suggests valid commands

---

### Test 5.3: Ambiguous Request

**Input:**

```
> spy
> aapl?
```

**Expected Behavior:**

- ✅ Detects insufficient context
- ✅ Asks clarifying question: "Did you mean buy, sell, or check status for SPY?"

**Success Criteria:**

- [ ] Doesn't assume action
- [ ] Prompts for clarification

---

## Category 6: Natural Language Variations

### Test 6.1: Various Buy Phrasings

**Inputs to test:**

```
> buy 10 shares of apple
> purchase aapl
> long spy
> get into tqqq
> open a position in msft
```

**Expected Behavior:**

- ✅ All interpreted as BUY intent
- ✅ Ticker extracted correctly
- ✅ Same trade flow triggered

**Success Criteria:**

- [ ] 5/5 phrasings work correctly

---

### Test 6.2: Various Status Phrasings

**Inputs to test:**

```
> check my positions
> show me what I own
> any open trades?
> position status
> what do I have?
```

**Expected Behavior:**

- ✅ All route to portfolio handler
- ✅ Show position list

**Success Criteria:**

- [ ] 5/5 phrasings route correctly
- [ ] No parser errors

---

### Test 6.3: Various Alert Phrasings

**Inputs to test:**

```
> check alerts
> show position alerts
> any approaching targets?
> alert status
> what alerts do I have?
```

**Expected Behavior:**

- ✅ All route to alerts handler
- ✅ Check alerts successfully

**Success Criteria:**

- [ ] 5/5 phrasings route correctly

---

## Test Execution Plan

### Phase 1: Core Functionality (Priority 1)

Run tests in market hours:

1. Test 1.1 - Simple buy ✅
2. Test 2.1 - Check alerts ✅
3. Test 3.1 - Scheduler status ✅
4. Test 4.1 - Portfolio status ✅

**Goal:** Verify all 4 main features work

---

### Phase 2: Bug Fixes (Priority 2)

Fix known issues from #334:

1. Test 1.3 - Sell signal handling (fix position check)
2. Test 2.2 - Position status query (fix routing)
3. Test 2.3 - Price target query (fix routing)

**Goal:** Address all #334 failures

---

### Phase 3: Edge Cases (Priority 3)

1. Test 5.1 - Invalid ticker
2. Test 5.2 - Out of scope
3. Test 5.3 - Ambiguous requests

**Goal:** Graceful error handling

---

### Phase 4: Natural Language (Priority 4)

1. Test 6.1 - Buy variations (5 phrases)
2. Test 6.2 - Status variations (5 phrases)
3. Test 6.3 - Alert variations (5 phrases)

**Goal:** Verify LLM routing robustness

---

## Category 8: Bare Ticker Input (Issue #356)

### Test 8.1: Bare Ticker - No Position, SELL Signal

**Input:**
```
> pltr
```

**Expected Behavior (FIXED - 2025-01-12):**

1. ✅ Pre-check detects bare ticker pattern (1-5 alphabetic chars)
2. ✅ Reformats to "analyze PLTR" before LLM parsing
3. ✅ If analysis suggests SELL and no position exists:
   - Shows clarification prompt
   - Asks: BUY (go long) vs SHORT (go short) vs REVIEW (just show analysis)
4. ✅ User chooses direction or review-only

**Previous Behavior (BROKEN):**
- ❌ Parser returned `TradeRequest(ticker='', ...)` (empty ticker)
- ❌ Error: "Invalid ticker format"

**Success Criteria:**
- [x] Bare ticker successfully parsed (FIXED 2025-01-12)
- [x] Clarification prompt appears for SELL signal + no position
- [x] User can choose BUY/SHORT/REVIEW
- [x] Choosing BUY flips signal in place (no reprocess loop)
- [x] Quantity preserved if user specified in original request

---

### Test 8.2: Bare Ticker - No Position, BUY Signal

**Input:**
```
> aapl
```

**Expected Behavior:**
1. ✅ Reformats to "analyze AAPL"
2. ✅ If analysis suggests BUY:
   - Shows suggestion normally
   - No clarification needed (signal aligns with default long-only)
3. ✅ User confirms/rejects as usual

**Success Criteria:**
- [ ] Works smoothly without clarification
- [ ] Displays BUY suggestion
- [ ] Executes if confirmed

---

### Test 8.3: Review Request - No Position, SELL Signal

**Input:**
```
> review pltr at market price for trade idea
```

**Expected Behavior (FIXED - 2025-01-12):**

1. ✅ Input contains "review" (not just bare ticker)
2. ✅ LLM parses as action="review"
3. ✅ If analysis suggests SELL and no position:
   - Detects NO explicit sell intent keywords
   - Shows clarification prompt (same as 8.1)

**Previous Behavior (BROKEN):**
- ❌ Immediately blocked: "Cannot execute SELL... system does not support short selling"

**Success Criteria:**
- [ ] Clarification prompt appears
- [ ] User can choose direction
- [ ] No premature blocking

---

## Category 9: Beginner-Friendly UX

### Test 9.1: Layman Sell Terminology

**Input:**
```
> get out of my position in meta
```

**Expected Behavior:**
1. ✅ Detects "get out" as sell indicator
2. ✅ If position exists: proceeds with SELL
3. ✅ If no position: blocks with educational message

**Other Layman Terms Supported:**
- "close my position"
- "dump my shares"
- "liquidate"
- "cash out"

**Success Criteria:**
- [ ] Recognizes layman sell terms
- [ ] Handles correctly based on position status

---

### Test 9.2: Beginner Clarification Response

**Setup:** Trigger clarification prompt (bare ticker + SELL signal + no position)

**Input:**
```
> pltr
[Clarification prompt appears]
> 1
```

**Expected Behavior:**
1. ✅ Accepts number "1" as BUY choice
2. ✅ Also accepts: "buy", "b", "long", "l", "up", "bullish"
3. ✅ Reprocesses with "buy PLTR"

**Success Criteria:**
- [x] Multiple response formats work (FIXED 2025-01-12)
- [x] Clear confirmation message
- [x] No reprocessing loop - flips signal in place
- [x] Quantity preserved from original request

---

### Test 9.3: Educational Tips Command

**Input:**
```
> /tips
```

**Expected Behavior:**
1. ✅ Displays trading basics guide
2. ✅ Explains BUY vs SHORT
3. ✅ Explains signals
4. ✅ Explains position requirements
5. ✅ Shows quick tips for beginners

**Success Criteria:**
- [ ] Guide displays correctly
- [ ] Uses simple, non-jargon language
- [ ] Includes examples

---

### Test 9.4: Plain Language Clarification Prompt

**Setup:** Trigger clarification (bare ticker + SELL + no position)

**Expected Prompt Text:**
```
❓ The analysis suggests PLTR might go DOWN, but you don't own any shares yet.

What would you like to do?
1. BUY shares (bet the stock will go UP)
2. SHORT shares (bet the stock will go DOWN - advanced strategy)
3. Just see the analysis (don't trade)

Your choice [1/2/3 or buy/short/review]: _
```

**Key Features:**
- ✅ Avoids jargon ("LONG" → "BUY shares")
- ✅ Explains in simple terms ("bet the stock will go UP")
- ✅ Labels SHORT as advanced
- ✅ Provides clear options

**Success Criteria:**
- [ ] Text matches expected format
- [ ] No technical jargon
- [ ] Options are clear

---

### Phase 5: Bare Ticker & Beginner UX (Priority 1)

**Status**: ✅ COMPLETED - 2025-01-12

1. ✅ Test 8.1 - Bare ticker with SELL signal
2. ✅ Test 8.2 - Bare ticker with BUY signal
3. ✅ Test 8.3 - Review request with SELL signal
4. ✅ Test 9.1 - Layman sell terminology
5. ✅ Test 9.2 - Beginner clarification responses (no reprocess loop!)
6. ✅ Test 9.3 - /tips command
7. ✅ Test 9.4 - Plain language prompts

**Goal:** ✅ User-friendly improvements verified for non-traders

**Key Fixes Applied:**
- Bare ticker reformatting (e.g., "pltr" → "analyze PLTR")
- Signal override without infinite loops
- Quantity preservation throughout flows
- Layman terminology support ("get", "acquire", "cash out", etc.)
- Educational /tips command
- Double confirmation as safety feature

---

## Test Results Template

Use this format to document results:

```markdown
### Test X.Y: [Test Name]

**Date:** 2025-01-10
**Tester:** [Name]
**Environment:** Paper trading

**Input:**
> [exact user input]

**Expected:**
[what should happen]

**Actual:**
[what actually happened]

**Status:** ✅ PASS / ❌ FAIL / ⚠️ PARTIAL

**Notes:**
[any observations, errors, improvements needed]

**Screenshots/Logs:**
[paste relevant output]
```

---

## Quick Test Script

For rapid testing, use this sequence:

```bash
python main.py

# Test all 4 features quickly
> check my alerts           # Alerts handler
> show scheduler status     # Scheduler handler
> show portfolio           # Portfolio handler
> buy 1 spy                # Trade handler (cancel before confirming)

# Test known bugs
> any positions open       # Should show portfolio (not error)
> is there a target on spy # Should show position details (not sell)

# Exit
> /exit
```

**Expected:** All 6 commands work without errors

---

## Appendix: Known Issues from #334

### Issue A: Bracket Order Validation

**Error:** `take_profit.limit_price must be >= base_price + 0.01`

**Location:** `src/execution/alpaca_execution_manager.py:189`

**Fix:** Ensure target price ≥ entry + $0.01 in risk manager

---

### Issue B: Short Sell Rejection

**Error:** Rejects SELL even when position exists

**Location:** CLI session or execution manager

**Fix:** Check positions before rejecting SELL signals

---

### Issue C: Position Query Parser Failure

**Error:** `Invalid request: TradeRequest(ticker='', ...)`

**Location:** Input parser trying to extract ticker from status query

**Fix:** Add routing keywords for status queries

---

### Issue D: Repeated Print Statements

**Error:** "Using fallback portfolio value: $100,000" repeats

**Location:** Unknown - needs investigation

**Fix:** Check logging configuration

---

## Category 7: LLM Routing - Ambiguous Tickers (NEW)

**Purpose:** Test LLM's ability to distinguish between status queries and ticker names

**Architecture:** LLM parser classifies `request_type` before extracting ticker

---

### Test 7.1: "ANY" as Status Query

**Input:**

```
> any open orders?
> any positions?
> any alerts?
```

**Expected Behavior:**

- ✅ LLM classifies as `request_type = "status_query"`
- ✅ Routes to appropriate status handler (orders/positions/alerts)
- ✅ Does NOT attempt to analyze ticker "ANY"
- ✅ No "could not fetch data for ANY" errors

**LLM Classification:**

- Context: Question word "any" + status keywords
- No trading intent (buy/sell/analyze)
- Result: status_query

**Success Criteria:**

- [ ] All 3 variations route to status handlers
- [ ] No ticker parsing errors
- [ ] Shows correct status information

---

### Test 7.2: "ANY" as Ticker Symbol

**Input:**

```
> buy ANY
> is ANY a good buy?
> analyze ticker ANY
```

**Expected Behavior:**

- ✅ LLM classifies as `request_type = "trade"`
- ✅ Extracts ticker = "ANY"
- ✅ Routes to trade handler
- ✅ Fetches market data for ticker ANY (if exists)

**LLM Classification:**

- Context: Trading action verbs (buy/analyze)
- Specific ticker mentioned in trading context
- Result: trade request with ticker=ANY

**Success Criteria:**

- [ ] All 3 variations route to trade handler
- [ ] Ticker extracted as "ANY"
- [ ] Attempts to analyze/execute trade

---

### Test 7.3: Other Ambiguous Tickers

**Tickers to Test:**

- WHAT, WHO, WHEN, WHERE, WHY, HOW
- ALL, SOME, EVERY
- CHECK, SHOW, LIST

**Status Query Inputs:**

```
> what positions do I have?
> what's my portfolio?
> show me my orders
```

**Expected:** Routes to status handlers (not ticker lookup)

**Trade Request Inputs:**

```
> buy WHAT at market
> is WHO a good investment?
> analyze ticker SHOW
```

**Expected:** Routes to trade handler with ticker extracted

**Success Criteria:**

- [ ] Status queries: 0% ticker misinterpretation
- [ ] Trade requests: 100% correct ticker extraction
- [ ] LLM uses context, not just word matching

---

### Test 7.4: Compound Queries

**Input:**

```
> show me my SPY position
> what's the price target on AAPL?
> any open orders for TQQQ?
```

**Expected Behavior:**

- ✅ LLM classifies as `request_type = "status_query"`
- ✅ Extracts specific ticker: SPY, AAPL, TQQQ
- ✅ Routes to portfolio handler
- ✅ Shows position details for that ticker

**LLM Classification:**

- Context: Asking about existing position/orders
- No intent to create new trade
- Result: status_query with ticker specified

**Success Criteria:**

- [ ] Routes to status handler (not trade)
- [ ] Ticker extracted correctly
- [ ] Shows specific ticker's status

---

### Test 7.5: Edge Cases

**Input 1:** "any"

```
> any
```

**Expected:**

- LLM classifies as ambiguous/insufficient
- Asks for clarification OR defaults to status query

---

**Input 2:** "buy anything"

```
> buy anything
```

**Expected:**

- LLM interprets "anything" as unclear ticker
- Should error with "please specify ticker"

---

**Input 3:** "is there anything I should know?"

```
> is there anything I should know?
```

**Expected:**

- LLM classifies as general status query
- Routes to portfolio/alerts summary

---

**Success Criteria:**

- [ ] Graceful handling of ambiguous inputs
- [ ] Clear error messages when ticker unclear
- [ ] No false positives on ticker extraction

---

### Test 7.6: LLM Reasoning Verification

**Purpose:** Verify LLM is using context, not just keywords

**Test Pairs:** Same word, different contexts

**Pair 1: "check"**

```
> check my alerts          → status_query (system feature)
> check ticker CHECK       → trade (ticker lookup)
```

**Pair 2: "what"**

```
> what positions?          → status_query
> buy WHAT                 → trade (ticker=WHAT)
```

**Pair 3: "show"**

```
> show portfolio           → status_query
> show me analysis of SHOW → trade (ticker=SHOW)
```

**Success Criteria:**

- [ ] 100% accuracy on paired tests
- [ ] Context determines routing, not keyword alone
- [ ] LLM logs show correct reasoning

---

## LLM Routing Test Summary

**Total Test Cases:** 25+ routing scenarios

**Categories Covered:**

1. Ambiguous ticker words (ANY, WHAT, etc.)
2. Status queries vs trade requests
3. Compound queries (ticker + status)
4. Edge cases and clarifications
5. Context-based disambiguation

**Success Metrics:**

- Status query accuracy: ≥ 95%
- Trade request accuracy: ≥ 95%
- Zero ticker misinterpretations for common words
- Fast keyword routing still works (scheduler/alerts)

**Regression Testing:**

- All previous tests (Categories 1-6) must still pass
- No performance degradation
- LLM calls only when needed (not for scheduler/alerts)

---

## Success Metrics

**Test Suite Completion:**

- [ ] 15+ core test cases executed
- [ ] All Priority 1 tests passing
- [ ] Known bugs from #334 fixed
- [ ] Natural language variations working

**User Experience:**

- [ ] No confusing errors
- [ ] Clear routing to correct handlers
- [ ] Helpful error messages
- [ ] Intuitive command flow

**Documentation:**

- [ ] Test results documented
- [ ] Known issues tracked
- [ ] Fix recommendations provided
