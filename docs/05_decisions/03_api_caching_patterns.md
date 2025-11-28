# API Integration & Caching Patterns

**Status:** Accepted | **Date:** November 2025

## Context

Market data APIs have rate limits and latency that impact user experience:

- Alpaca: 200 requests/min (free tier)
- Alpha Vantage: 5 requests/min
- Polygon: 5 requests/min (free tier)

Without caching, repeated operations hit rate limits and introduce 100-500ms latency per call.

## Decision

### Cache-First Architecture

All market data access follows a cache-first pattern:

```text
Request → Cache Check → [HIT] → Return cached data
                     → [MISS] → Fetch from API → Store in cache → Return
```

### SQLite-Based Cache (TradingCacheManager)

**Location:** `src/data_sources/cache/sqlite_cache.py`

**Key Features:**

- ACID transactions for data integrity
- Thread-safe concurrent access
- Smart expiration (historical: 10yr TTL, recent: 24hr TTL)
- 8-10x faster than previous file-based cache

**Schema Design:**

```sql
market_cache (
    asset_type TEXT,     -- 'stock', 'option', 'future'
    symbol TEXT,
    trading_date TEXT,
    source TEXT,         -- 'alpaca', 'polygon', 'alpha_vantage'
    open, high, low, close, volume REAL,
    cached_at TEXT,
    expires_at TEXT,
    UNIQUE(asset_type, symbol, trading_date, source)
)
```

### TTL Strategy

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Historical (>1 day old) | 10 years | Data never changes |
| Recent (today/yesterday) | 24 hours | May update during session |
| Options chains | 1 hour | Greeks change frequently |
| News/alerts | 15 minutes | Time-sensitive |

### API Fallback Chain

```python
# Priority order for market data
sources = ["alpaca", "polygon", "alpha_vantage"]

for source in sources:
    try:
        data = fetch_from(source)
        if data:
            return data
    except RateLimitError:
        continue  # Try next source
```

### Piggyback Pattern (Issue #337)

Broker API calls return extra data - cache it opportunistically:

```python
# When fetching positions, also cache current prices
positions = broker.get_positions()
for pos in positions:
    price_cache.set(pos.symbol, pos.current_price, ttl=60)
```

## Consequences

**Benefits:**

- 90%+ cache hit rate in production
- Sub-millisecond response for cached data
- Graceful degradation when APIs fail

**Trade-offs:**

- Cache invalidation complexity for real-time data
- Storage growth (mitigated by TTL cleanup)

## Implementation

- Main cache: `src/data_sources/cache/sqlite_cache.py`
- Admin tools: `scripts/cache_manager.py`
- Full docs: `docs/02_architecture/04_cache_system.md`
