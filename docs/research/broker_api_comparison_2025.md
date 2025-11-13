# Broker API Comparison: Indian FinTech vs Alpaca (2025)

**Research Date:** 2025-01-11

**Purpose:** Evaluate Indian fintech broker APIs to identify features/capabilities that Alpaca doesn't offer

---

## Executive Summary

| Broker | API Cost | Markets | Key Differentiators | API Availability |
|--------|----------|---------|---------------------|------------------|
| **Alpaca** | Free | US Stocks, Crypto | Paper trading, fractional shares, commission-free | ✅ Public |
| **Zerodha (Kite)** | ₹2,000/mo (~$24) | NSE/BSE (India) | 10 years historical data, GTT orders, free for personal use (2025) | ✅ Public |
| **Upstox** | ₹1,999/mo (~$24) | NSE/BSE (India) | MTF (margin trading), trailing stop loss, sandbox mode | ✅ Public |
| **Groww** | ₹499/mo (~$6) | NSE/BSE (India) | Cheapest pricing, F&O support, MTF | ✅ Public |
| **Angel One** | **FREE** | NSE/BSE (India) | Completely free, 10 trades/sec, multi-language SDKs | ✅ Public |
| **Quantsapp** | N/A | NSE/BSE (India) | Analytics platform, no public API for developers | ❌ No API |

**Winner by Category:**
- **Price:** Angel One (FREE) > Groww (₹499) > Zerodha/Upstox (₹2,000)
- **Features:** Upstox (most 2025 updates) = Zerodha (historical data)
- **Market Coverage:** Alpaca (US + Crypto) vs Indian brokers (NSE/BSE only)

---

## Detailed Broker Analysis

### 1. Zerodha - Kite Connect API

**Website:** https://kite.trade/

#### Overview
India's largest retail broker with comprehensive REST-like APIs for building complete trading platforms.

#### Pricing (2025 Update)
- **Personal Use:** FREE (launched Feb 2025)
- **Commercial Use:** ₹2,000/month (~$24 USD)
- **Historical Data:** Now bundled free (previously ₹2,000 extra)
- **Change:** Removed historical data surcharge in March 2025

#### Key Features
✅ **Real-time market data** via WebSockets
✅ **Historical data** - Up to 10 years of intraday data (NSE/BSE)
✅ **Order types:** Regular, after-market, cover orders, GTT (Good Till Triggered)
✅ **Portfolio management** - Holdings, positions, margin calculations
✅ **Multi-language support** - Python, Excel, Amibroker, Go

#### What Alpaca Doesn't Have
1. **GTT Orders (Good Till Triggered):** Set price triggers that persist beyond daily sessions
2. **10-year historical intraday data:** Alpaca offers ~5 years
3. **Cover orders:** Pre-defined stop-loss orders built-in
4. **Free personal use tier:** Alpaca is free but no "personal vs commercial" distinction

#### Markets Supported
- NSE (National Stock Exchange, India)
- BSE (Bombay Stock Exchange, India)
- MCX (commodity derivatives)

#### API Documentation
- https://kite.trade/docs/connect/v3/

---

### 2. Upstox API

**Website:** https://upstox.com/developer/api-documentation/

#### Overview
Modern Indian broker with aggressive 2025 feature rollout, focused on algo trading.

#### Pricing
- **Standard Plan:** ₹1,999/month (~$24 USD)
- **Upstox Plus:** Higher tier with expired instruments access

#### Key Features (2025 Updates)
✅ **GTT Orders with Trailing Stop Loss** (Feb-June 2025)
✅ **MTF Support** (Margin Trading Facility) - April 2025
✅ **Sandbox Mode** - Safe testing environment (Jan 2025)
✅ **Enhanced WebSockets** - 5 concurrent connections, 50 instruments/connection (May 2025)
✅ **Expired Instruments API** - Historical data for expired contracts (May 2025)
✅ **Market Quote V3** - Enhanced market data APIs (April 2025)

#### What Alpaca Doesn't Have
1. **MTF (Margin Trading Facility):** Built-in margin funding for positions
2. **Trailing Stop Loss in GTT:** Dynamic stop-loss that trails price
3. **Expired Instruments API:** Access historical data for expired futures/options
4. **Sandbox Mode:** Upstox added this in 2025; Alpaca has paper trading (similar)
5. **5 concurrent WebSocket connections:** Alpaca typically 1 connection/account

#### Markets Supported
- NSE (National Stock Exchange, India)
- BSE (Bombay Stock Exchange, India)

#### API Documentation
- https://upstox.com/developer/api-documentation/open-api/

---

### 3. Groww API

**Website:** https://groww.in/trade-api

#### Overview
Newcomer to trading APIs (launched 2024-2025), positioning as most affordable option.

#### Pricing
- **All APIs:** ₹499/month (~$6 USD) + taxes
- **No usage-based charges**
- **All modules included:** Market feed, orders, portfolio, historical data, margin

#### Key Features
✅ **Flat pricing** - Simplest pricing structure
✅ **F&O Support** - Futures & Options trading
✅ **MTF Support** - Margin Trading Facility
✅ **Multi-exchange** - NSE and BSE
✅ **OpenAlgo integration** - Works with popular algo frameworks

#### What Alpaca Doesn't Have
1. **F&O (Futures & Options):** Alpaca focuses on stocks/crypto, no derivatives
2. **Ultra-low pricing:** $6/month is 75% cheaper than Alpaca competitors
3. **MTF:** Built-in margin trading facility
4. **OpenAlgo integration:** Native integration with algo trading frameworks

#### Markets Supported
- NSE (National Stock Exchange, India)
- BSE (Bombay Stock Exchange, India)
- Supports: Equity, Futures, Options, Index

#### API Documentation
- Access via Groww Trade API Portal (requires Groww account)

---

### 4. Angel One - SmartAPI

**Website:** https://smartapi.angelbroking.com/

#### Overview
**Completely FREE** trading API with comprehensive features - most generous offering.

#### Pricing
- **Trading API:** FREE
- **Historical Data API:** FREE
- **No monthly fees**
- **No hidden charges**

#### Key Features
✅ **Completely free** - Zero cost for all features
✅ **High-speed execution** - 10 trades per second
✅ **Multi-language SDKs** - Python, Java, NodeJS, C#, PHP, Go, R
✅ **WebSocket support** - Real-time tick-by-tick data
✅ **All segments** - Equity, F&O, Commodity, Currency

#### What Alpaca Doesn't Have
1. **Truly free with no restrictions:** Alpaca is free but has rate limits
2. **10 trades/second guarantee:** Clear execution speed commitment
3. **Multi-language SDKs (7 languages):** Alpaca primarily Python/REST
4. **Commodity & Currency trading:** Alpaca doesn't offer these

#### Markets Supported
- NSE (National Stock Exchange, India)
- BSE (Bombay Stock Exchange, India)
- MCX (Multi Commodity Exchange)
- Currency derivatives

#### API Documentation
- https://smartapi.angelbroking.com/

---

### 5. Quantsapp

**Website:** https://www.quantsapp.com/

#### Overview
**NOT a broker API** - This is an analytics platform/app for options traders.

#### Classification
- **Type:** Retail trading analytics application
- **Users:** ~1 million option traders
- **Founded:** 2016, Mumbai, India

#### Key Features
✅ **Options strategy optimizer** - 250 million combinations
✅ **Backtesting tools**
✅ **Option chain analysis**
✅ **Open interest data**
✅ **100+ trading tools** (25 free, 75 paid)

#### API Availability
❌ **No public API for developers**
- Not comparable to broker APIs
- Focused on retail trader app, not programmatic access
- No mention of API in documentation or careers page

#### Verdict
**Not relevant for broker API comparison** - this is a B2C analytics app, not a trading platform API.

---

## Feature Comparison Matrix

### Core Trading Features

| Feature | Alpaca | Zerodha | Upstox | Groww | Angel One |
|---------|--------|---------|--------|-------|-----------|
| **REST API** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **WebSocket (Real-time)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Paper Trading** | ✅ | ❌ | ✅ (Sandbox) | ❌ | ❌ |
| **Historical Data** | ✅ (5yr) | ✅ (10yr) | ✅ | ✅ | ✅ |
| **Order Modification** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Portfolio Tracking** | ✅ | ✅ | ✅ | ✅ | ✅ |

### Advanced Order Types

| Feature | Alpaca | Zerodha | Upstox | Groww | Angel One |
|---------|--------|---------|--------|-------|-----------|
| **Market Orders** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Limit Orders** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Stop Orders** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Bracket Orders** | ❌ | ❌ | ✅ | ❌ | ✅ |
| **Cover Orders** | ❌ | ✅ | ✅ | ❌ | ✅ |
| **GTT (Good Till Triggered)** | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Trailing Stop Loss** | ✅ | ❌ | ✅ (GTT) | ❌ | ❌ |
| **After-Market Orders** | ✅ (extended hours) | ✅ | ✅ | ✅ | ✅ |

### Asset Classes

| Asset Class | Alpaca | Zerodha | Upstox | Groww | Angel One |
|-------------|--------|---------|--------|-------|-----------|
| **Stocks (Equity)** | ✅ (US) | ✅ (India) | ✅ (India) | ✅ (India) | ✅ (India) |
| **Crypto** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Futures** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Options** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Commodities** | ❌ | ✅ (MCX) | ❌ | ❌ | ✅ (MCX) |
| **Currency** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Fractional Shares** | ✅ | ❌ | ❌ | ❌ | ❌ |

### Developer Experience

| Feature | Alpaca | Zerodha | Upstox | Groww | Angel One |
|---------|--------|---------|--------|-------|-----------|
| **Python SDK** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **JavaScript/NodeJS** | ✅ | ✅ | ✅ | ❌ | ✅ |
| **Java** | ❌ | ❌ | ✅ | ❌ | ✅ |
| **Go** | ✅ | ✅ | ❌ | ❌ | ✅ |
| **C#** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **PHP** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **R** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Sandbox/Paper Trading** | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Free Tier** | ✅ | ✅ (personal) | ❌ | ❌ | ✅ |

---

## Unique Features Not in Alpaca

### 1. GTT Orders (Good Till Triggered)
**Available in:** Zerodha, Upstox

**What it is:** Price trigger that persists across sessions (days/weeks) until executed or cancelled.

**Example:**
```
Set: "Buy 100 RELIANCE when price drops to ₹2,400"
Duration: Order stays active for 365 days
Benefit: Don't need to monitor price constantly
```

**Why Alpaca doesn't have it:** US markets have GTC (Good Till Cancelled) orders, but not GTT with persistent price triggers outside regular order book.

**Use Case:** Long-term breakout/breakdown strategies without daily monitoring.

---

### 2. MTF - Margin Trading Facility
**Available in:** Upstox, Groww

**What it is:** Built-in margin funding from broker to hold positions longer than intraday.

**Example:**
```
Buy: ₹100,000 worth of stock
Your capital: ₹25,000
Broker funds: ₹75,000 (MTF)
Hold duration: Multiple days/weeks
Interest: Charged daily on funded amount
```

**Why Alpaca doesn't have it:** Alpaca has margin accounts but not MTF-style funding products.

**Use Case:** Swing trading without full capital deployment.

---

### 3. Trailing Stop Loss in GTT
**Available in:** Upstox (2025 feature)

**What it is:** Dynamic stop-loss that moves with price in favorable direction.

**Example:**
```
Buy: ₹1,000
Trailing SL: 5% below highest price
Price rises to ₹1,200 → SL moves to ₹1,140
Price rises to ₹1,300 → SL moves to ₹1,235
Locks in profits automatically
```

**Why Alpaca doesn't have it:** Alpaca has trailing stops, but Upstox combines it with GTT persistence.

**Use Case:** Trend-following with automatic profit protection.

---

### 4. Futures & Options Trading
**Available in:** Zerodha, Upstox, Groww, Angel One

**What it is:** Derivatives trading on Indian indices/stocks.

**Example:**
```
NIFTY 50 Call Options
Bank NIFTY Futures
Stock-specific options (weekly, monthly expiry)
```

**Why Alpaca doesn't have it:** Regulatory focus on US equities/crypto, not derivatives.

**Use Case:** Hedging, leverage, income strategies (covered calls, spreads).

---

### 5. 10-Year Historical Intraday Data
**Available in:** Zerodha

**What it is:** Minute-level OHLC data going back 10 years (now bundled free).

**Why Alpaca doesn't have it:** Alpaca offers ~5 years historical data.

**Use Case:** Long-term backtesting, regime detection, multi-cycle validation.

---

### 6. Multiple Concurrent WebSocket Connections
**Available in:** Upstox (5 connections)

**What it is:** Subscribe to different instrument sets simultaneously.

**Example:**
```
Connection 1: 50 stocks (portfolio monitoring)
Connection 2: 50 stocks (watchlist scanning)
Connection 3: Index data
Connection 4: Options chain
Connection 5: Backup/failover
```

**Why Alpaca doesn't have it:** Typically 1 WebSocket per account.

**Use Case:** Multi-strategy systems, different update frequencies.

---

### 7. Commodity & Currency Trading
**Available in:** Angel One, Zerodha (MCX)

**What it is:** Trade gold, silver, crude oil, currency pairs.

**Example:**
```
MCX Gold futures
MCX Crude Oil
USD/INR currency pairs
```

**Why Alpaca doesn't have it:** US-focused equities/crypto platform.

**Use Case:** Diversification, inflation hedging, forex trading.

---

### 8. Completely Free API with No Restrictions
**Available in:** Angel One

**What it is:** Zero-cost API access forever, no usage limits beyond fair use.

**Why Alpaca doesn't have it:** Alpaca is free but has rate limits and market data fees for some premium feeds.

**Use Case:** Hobbyists, students, early-stage startups.

---

## Pricing Comparison

| Broker | Monthly Cost (USD) | Free Tier | Paper Trading | Notes |
|--------|-------------------|-----------|---------------|-------|
| **Alpaca** | $0 | ✅ Full access | ✅ | Free with rate limits |
| **Zerodha** | $0 (personal) / $24 (commercial) | ✅ Personal use | ❌ | Historical data now included |
| **Upstox** | $24 | ❌ | ✅ (Sandbox) | Most 2025 feature updates |
| **Groww** | $6 | ❌ | ❌ | Cheapest paid tier |
| **Angel One** | $0 | ✅ All features | ❌ | Completely free, no restrictions |

**Best Value:**
1. **Angel One** - Free with more features than Alpaca
2. **Groww** - $6/month for F&O + MTF
3. **Zerodha** - Free for personal use, $24 commercial

---

## Market Coverage Comparison

### Alpaca (US Markets)
- **Exchanges:** NYSE, NASDAQ, AMEX
- **Instruments:** ~10,000 US stocks
- **Crypto:** Yes (via Alpaca Crypto)
- **Geographic:** United States only

### Indian Brokers (NSE/BSE)
- **Exchanges:** NSE, BSE (+ MCX for some)
- **Instruments:** ~5,000 stocks + derivatives
- **F&O:** Futures & Options on indices/stocks
- **Geographic:** India only

**Verdict:** Alpaca = US markets, Indian brokers = India markets. **No overlap.**

---

## Recommendations

### For US-Based Trading (Stick with Alpaca)
✅ Use Alpaca if trading US stocks/crypto
✅ Alpaca has better US market coverage
✅ Paper trading built-in
✅ Fractional shares

### For India-Based Trading (Consider Alternatives)
✅ **Angel One** - Best free option for India
✅ **Groww** - Cheapest paid tier ($6) with F&O
✅ **Upstox** - Most innovative (2025 features)
✅ **Zerodha** - Most established, 10-year historical data

### For Multi-Market Strategy
⚠️ **Challenge:** No single broker covers US + India
💡 **Solution:** Dual-broker setup
   - Alpaca for US equities/crypto
   - Angel One (free) or Groww ($6) for Indian F&O

### Features to Consider Adding to Our System
1. **GTT-style persistent triggers** - Could implement in our position tracker
2. **Trailing stop loss** - Already have logic, enhance with GTT persistence
3. **Multi-asset support** - Future: Add F&O if expanding to Indian markets
4. **Multiple WebSocket connections** - For multi-strategy monitoring

---

## Integration Feasibility

### Could We Support Indian Brokers?

**Architecture Changes Needed:**

1. **Market Data Sources:**
   - Current: Polygon.io (US data)
   - Needed: NSE/BSE data provider (TrueData, MarketDataFeed, etc.)

2. **Order Management:**
   - Current: AlpacaOrderManager
   - Add: ZerodhaOrderManager, AngelOneOrderManager, etc.
   - Abstract: Common OrderManager interface

3. **Time Zones:**
   - Current: US Eastern Time (9:30 AM - 4:00 PM ET)
   - Add: Indian Standard Time (9:15 AM - 3:30 PM IST)

4. **Regulatory Differences:**
   - US: Pattern Day Trader rules
   - India: Different margin requirements, settlement cycles

**Effort Estimate:** Medium (3-4 weeks)
- Abstraction layer: 1 week
- Broker integration: 1-2 weeks
- Testing: 1 week

**Value:** Access to Indian F&O markets, larger user base (India = 1.4B population)

---

## Conclusion

### What Indian Brokers Offer That Alpaca Doesn't:

**Actually Unique (Alpaca doesn't have these):**
1. ✅ **GTT Orders** - Persistent price triggers across sessions (Zerodha, Upstox)
2. ✅ **Trailing Stop in GTT** - Dynamic stop-loss that persists for days/weeks (Upstox)
3. ✅ **OCO GTT Triggers** - One-Cancels-Other price triggers (Zerodha, Upstox)
4. ✅ **Multiple WebSocket Connections** - 5 concurrent connections, 50 instruments each (Upstox)
5. ✅ **Sandbox Snapshot Testing** - Frozen market replay for deterministic tests (Upstox)
6. ✅ **MTF (Margin Funding)** - Broker-funded swing trades (Upstox, Groww)

**Out of Scope / Not Relevant:**
- ❌ Futures & Options - Alpaca has options, we haven't integrated yet
- ❌ Crypto Trading - Not priority, Alpaca has it
- ❌ Fractional Shares - Not needed for our use case
- ❌ 10-Year Historical Data - 5 years sufficient
- ❌ Commodity/Currency Trading - Out of scope
- ❌ Margin Trading - Alpaca has margin, we're on paper account

### What Alpaca Offers That Indian Brokers Don't:

1. ✅ **US Market Access** - NYSE, NASDAQ stocks (we need this)
2. ✅ **Paper Trading** - Built-in sandbox (we use this)
3. ✅ **Extended Hours Trading** - Pre-market/after-hours (not implemented yet)
4. ✅ **Better Documentation** - More mature platform
5. ✅ **Bracket Orders** - Pre-defined stop/target (we use this)

---

## Technical Inspiration for Our System

### Top 3 Features to Implement (Priority Order)

#### **1. GTT-Style Persistent Price Triggers** ⭐⭐⭐
**Inspiration from:** Zerodha, Upstox

**What it is:**
- Price triggers that stay active for days/weeks (even when system offline)
- Stored on server, checked on each scheduler run
- Different from GTC orders (not in order book)

**Technical Implementation:**
```python
# Add to position tracker state
persistent_triggers = {
    "SPY_breakout": {
        "symbol": "SPY",
        "trigger_price": 620,
        "direction": "above",
        "action": "alert",  # or "buy", "sell"
        "created": "2025-01-11",
        "expires": "2025-02-10",  # 30 days
        "status": "active"
    }
}
# Check on scheduler runs (9:20 AM, 3:50 PM)
```

**Use Case:** "Alert me if SPY hits $620 anytime in next 30 days" without monitoring

**Implementation Effort:** Medium (enhance position tracker + scheduler)

---

#### **2. Persistent Trailing Stop Loss** ⭐⭐⭐
**Inspiration from:** Upstox GTT trailing stop (June 2025)

**What it is:**
- Trailing stop that survives across days/weeks
- Updates on each scheduler run, persists in state
- Locks in profits on swing trades without 24/7 monitoring

**Technical Implementation:**
```python
# Add to position tracker state
position_state = {
    "SPY_position": {
        "entry_price": 600,
        "current_price": 630,
        "highest_price": 630,  # Track this
        "trailing_stop_pct": 5.0,
        "trailing_stop_price": 598.50,  # 630 * 0.95
        "last_updated": "2025-01-11 15:50:00"
    }
}
# Update on each scheduler run
```

**Use Case:** Multi-day swing trade with automatic profit protection

**Implementation Effort:** Low (add to existing scheduler + position state)

---

#### **3. OCO (One-Cancels-Other) Alert Triggers** ⭐⭐
**Inspiration from:** Zerodha, Upstox

**What it is:**
- Set dual breakout/breakdown triggers
- When one triggers, cancel the other
- Useful for range-bound strategies

**Technical Implementation:**
```python
# Add to position tracker
oco_trigger = {
    "SPY_range": {
        "symbol": "SPY",
        "triggers": [
            {"price": 620, "direction": "above", "action": "alert"},
            {"price": 580, "direction": "below", "action": "alert"}
        ],
        "oco": True,  # Cancel other when one triggers
        "status": "active"
    }
}
```

**Use Case:** "Alert if SPY breaks above $620 OR below $580 (whichever first)"

**Implementation Effort:** Low (alert logic enhancement)

---

#### **4. Multiple WebSocket Connections** ⭐⭐
**Inspiration from:** Upstox (5 connections, 50 instruments each)

**What it is:**
- Separate connections for different purposes
- Different update frequencies
- Better separation of concerns + failover

**Technical Consideration:**
- Need to verify if Alpaca allows multiple concurrent WebSocket connections
- Could improve multi-strategy monitoring
- Better resource management (throttle by connection)

**Implementation Effort:** Medium (verify Alpaca support + architecture)

---

#### **5. Extended Hours Trading** ⭐
**Inspiration from:** Indian brokers' pre-market orders

**What it is:**
- Alpaca already supports pre-market (4:00-9:30 AM) and after-hours (4:00-8:00 PM)
- We haven't implemented it in our system yet

**Technical Implementation:**
```python
# Add to order execution
order = alpaca.submit_order(
    symbol="SPY",
    qty=10,
    side="buy",
    type="limit",
    limit_price=600,
    extended_hours=True  # Enable extended hours
)
```

**Use Case:** React to earnings announcements, news events outside regular hours

**Implementation Effort:** Low (Alpaca already has it, just add flag)

---

#### **6. Sandbox Snapshot Testing** ⭐
**Inspiration from:** Upstox sandbox mode (Jan 2025)

**What it is:**
- Save frozen market state snapshots
- Replay specific scenarios deterministically
- Better than live paper trading for unit tests

**Technical Implementation:**
```python
# Save market snapshot
snapshot = {
    "timestamp": "2025-01-10 14:30:00",
    "positions": broker_state.positions,
    "prices": {"SPY": 615.50, "QQQ": 495.25, ...},
    "market_conditions": "volatile_down_5pct"
}
# Replay in tests
```

**Use Case:** Test strategies against specific historical conditions (crash, rally, etc.)

**Implementation Effort:** Medium (testing infrastructure)

---

### Strategic Recommendation:

**Keep Alpaca:**
- ✅ Best for US market focus
- ✅ Paper trading works great
- ✅ Already integrated, stable

**Implement from Indian Brokers:**
1. **GTT persistent triggers** (highest value)
2. **Persistent trailing stops** (easy win)
3. **OCO dual alerts** (nice enhancement)

**Not Implementing:**
- Futures/Options (Alpaca has it, out of scope for now)
- Crypto (Alpaca has it, not priority)
- Margin (Alpaca has it, paper account sufficient)
- Commodities/Forex (out of scope)

**Future Expansion (if needed):**
- Consider **Angel One (FREE)** if expanding to India markets
- Implement broker abstraction layer for multi-broker support (3-4 week effort)

---

## References

- Zerodha Kite API: https://kite.trade/
- Upstox API: https://upstox.com/developer/api-documentation/
- Groww API: https://groww.in/trade-api
- Angel One SmartAPI: https://smartapi.angelbroking.com/
- Quantsapp: https://www.quantsapp.com/ (Analytics app, not API)
- Alpaca Markets: https://alpaca.markets/

**Last Updated:** 2025-01-11
