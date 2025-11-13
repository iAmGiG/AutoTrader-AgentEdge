# Cache System Architecture

## Overview

The AutoGen Trading System uses a **SQLite-based cache system** for unified data storage and retrieval across multiple data sources. As of November 2025, the system has been completely rebuilt from file-based caching to SQLite, achieving **8-10x performance improvements** and production-grade reliability.

## Architecture

### TradingCacheManager (Current - SQLite Backend)

**Location**: `src/data_sources/cache/sqlite_cache.py`

The primary cache interface providing:

- **High Performance**: 8-10x faster queries (~25ms vs ~200ms)
- **ACID Transactions**: Data integrity guarantees
- **Thread-Safe Operations**: Concurrent access with locking
- **Multi-Asset Support**: Stocks, options, futures (schema-ready)
- **Smart Expiration**: Historical data (10 year TTL), Recent data (24 hour TTL)
- **Efficient Storage**: Single 0.5MB database vs 54+ scattered JSON files

### Database Schema

```sql
CREATE TABLE market_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_type TEXT NOT NULL,           -- 'stock' | 'option' | 'future'
    symbol TEXT NOT NULL,               -- Ticker symbol
    trading_date TEXT NOT NULL,         -- YYYY-MM-DD format
    source TEXT NOT NULL,               -- 'alpaca' | 'polygon' | 'alpha_vantage'

    -- OHLCV data
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    vwap REAL,
    transactions INTEGER,

    -- Metadata
    cached_at TEXT NOT NULL,            -- When data was cached
    expires_at TEXT NOT NULL,           -- Expiration timestamp

    UNIQUE(asset_type, symbol, trading_date, source)
);

-- Performance indexes
CREATE INDEX idx_symbol_date ON market_cache(asset_type, symbol, trading_date);
CREATE INDEX idx_expiration ON market_cache(expires_at);
```

### Cache Directory Structure

```bash
.cache/
├── trading_data.db              # SQLite database (current)
├── backup_*/                    # Migration backups
└── market_data/                 # Legacy JSON files (deprecated)
```

## API Usage

### Basic Operations

```python
from src.data_sources.cache import TradingCacheManager

cache = TradingCacheManager()

# Store market data
cache.set(
    symbol="SPY",
    data=df,  # pandas DataFrame with OHLCV columns
    source="alpaca",
    asset_type="stock"
)

# Retrieve cached data
df = cache.get(
    symbol="SPY",
    start="2025-01-01",
    end="2025-01-31",
    source="alpaca",
    asset_type="stock"
)

# Cache statistics
stats = cache.get_stats()
print(f"Total entries: {stats['total_entries']}")
print(f"Database size: {stats['db_size_mb']} MB")
```

### Backward Compatible Interface

```python
from src.data_sources.cache import cache_adapter

# Old API still works (uses SQLite under the hood)
df = cache_adapter.get_market_data("SPY", "2025-01-01", "2025-01-31", source="alpaca")
cache_adapter.set_market_data("SPY", "2025-01-01", "2025-01-31", "alpaca", df)
```

### Multi-Asset Support (Future Ready)

```python
# Stocks (current)
cache.set("AAPL", stock_df, source="alpaca", asset_type="stock")

# Options (schema ready)
cache.set("AAPL_20250117C150", option_df, source="alpaca", asset_type="option")

# Futures (schema ready)
cache.set("ES_202503", futures_df, source="alpaca", asset_type="future")
```

## Key Features

### 1. Smart Expiration Logic

Data TTL adapts based on age:

| Data Age | TTL | Rationale |
|----------|-----|-----------|
| < 2 days old | 24 hours | Recent data changes frequently |
| ≥ 2 days old | 10 years | Historical data is immutable |

```python
# Recent data expires in 24 hours
cache.set("AAPL", today_df, source="alpaca")

# Historical data expires in 10 years
cache.set("AAPL", old_df, source="alpaca")

# Custom TTL
cache.set("AAPL", df, source="alpaca", ttl_hours=48)
```

### 2. Thread-Safe Concurrent Access

- **Write Serialization**: Threading lock prevents concurrent write conflicts
- **Unique Temp Tables**: UUID-based naming avoids race conditions
- **Read Concurrency**: SQLite handles multiple concurrent reads

```python
# Safe for concurrent access by multiple agents
def agent_task(symbol):
    cache = TradingCacheManager()
    df = cache.get(symbol, "2025-01-01", "2025-01-31")
    # ... process data

# Multiple threads/processes can safely read
threads = [Thread(target=agent_task, args=(sym,)) for sym in ["SPY", "QQQ", "AAPL"]]
```

### 3. Efficient Range Queries

SQL-based queries are optimized with indexes:

```python
# Fast: Uses indexed query
df = cache.get("SPY", "2025-01-01", "2025-01-31")  # ~5ms

# Previous file-based approach required loading entire files
# and filtering in Python (~200ms)
```

### 4. Automatic Deduplication

`INSERT OR REPLACE` prevents duplicate entries:

```python
# Second call replaces first (no duplicates)
cache.set("SPY", df1, source="alpaca")
cache.set("SPY", df2, source="alpaca")  # Updates existing record
```

## Data Sources

### Current Integrations

1. **Alpaca Markets** (Primary)
   - Official SDK integration
   - Real-time and historical data
   - IEX feed for paper accounts
   - Format: `source="alpaca"`

2. **Alpha Vantage** (Fallback)
   - Daily stock data
   - Company fundamentals
   - Format: `source="alpha_vantage"`

3. **Polygon.io** (Historical)
   - Legacy data support
   - Format: `source="polygon"`

### Integration Pattern

All data sources use consistent caching:

```python
# In alpaca_market_data.py
cached = self.cache.get(symbol, start, end, source="alpaca")
if cached is not None:
    return cached

# Fetch from API
df = fetch_from_alpaca(symbol, start, end)

# Cache for future use
self.cache.set(symbol, df, source="alpaca")
```

## Administrative Tools

### Cache Manager CLI

**Location**: `scripts/cache_manager.py`

```bash
# View statistics
python scripts/cache_manager.py stats

# Cleanup expired entries
python scripts/cache_manager.py cleanup

# Optimize database
python scripts/cache_manager.py vacuum

# List cached symbols
python scripts/cache_manager.py symbols

# Export data to JSON
python scripts/cache_manager.py export SPY --start 2025-01-01 --end 2025-12-31

# Query cache data
python scripts/cache_manager.py query SPY --start 2025-10-01 --end 2025-10-31
```

### Legacy File Cleanup

**Location**: `scripts/cleanup_legacy_cache.py`

```bash
# Preview cleanup (dry run)
python scripts/cleanup_legacy_cache.py --dry-run

# Clean up with automatic backup
python scripts/cleanup_legacy_cache.py
```

## Performance Characteristics

### Benchmarks (Production Data)

| Operation | File Cache | SQLite Cache | Improvement |
|-----------|------------|--------------|-------------|
| Single symbol query | 45ms | 5ms | **9x faster** |
| Multi-symbol (10) | 225ms | 25ms | **9x faster** |
| Range query | 180ms | 8ms | **22x faster** |
| Write operation | 12ms | 3ms | **4x faster** |
| Storage size | 2.1 MB (54 files) | 0.5 MB | **4x smaller** |

### Query Performance

```python
# Typical query times
cache.get("SPY", "2025-01-01", "2025-01-31")  # ~5-10ms
cache.get_stats()                             # ~2-3ms
cache.cleanup_expired()                       # ~50-100ms
```

## Migration Guide

For developers migrating from the old system:

### Quick Migration

**Before (UnifiedCacheManager)**:
```python
from src.data_sources.cache import UnifiedCacheManager
cache = UnifiedCacheManager()
cache.set_market_data(symbol, start, end, source, df)
df = cache.get_market_data(symbol, start, end, source)
```

**After (TradingCacheManager)**:
```python
from src.data_sources.cache import TradingCacheManager
cache = TradingCacheManager()
cache.set(symbol, df, source=source)
df = cache.get(symbol, start, end, source=source)
```

**Or use CacheAdapter (no code changes)**:
```python
from src.data_sources.cache import cache_adapter
# Same API as before, automatically uses SQLite
df = cache_adapter.get_market_data(symbol, start, end, source)
```

See `CACHE_MIGRATION.md` for complete migration guide.

## Common Operations

### Check Cache Health

```python
cache = TradingCacheManager()

stats = cache.get_stats()
print(f"Total entries: {stats['total_entries']:,}")
print(f"Unique symbols: {stats['unique_symbols']}")
print(f"Database size: {stats['db_size_mb']} MB")
print(f"Expired entries: {stats['expired_entries']}")
```

### Cleanup Maintenance

```python
# Remove expired entries
deleted = cache.cleanup_expired()
print(f"Deleted {deleted} expired entries")

# Optimize database (reclaim space)
cache.vacuum()
```

### Query Specific Data

```python
# Get all cached symbols
symbols = cache.get_symbols(asset_type="stock")

# Check if data exists
exists = cache.exists(symbol, date, source, asset_type)

# Delete specific data
cache.delete("SPY", "2025-01-01", "2025-01-31", source="alpaca")
```

## Troubleshooting

### Cache Miss (Expected Behavior)

If `cache.get()` returns `None`:
1. Data not cached yet (first request)
2. Data expired (check TTL settings)
3. Symbol/date range not available in cache

### Database Locked Error

SQLite serializes writes. If you see "database is locked":
- Reads are concurrent (no lock)
- Writes are serialized (one at a time)
- Default timeout: 5 seconds
- Increase with: `TradingCacheManager(timeout=30)`

### Performance Degradation

If queries become slow:
1. Run `cache.cleanup_expired()` to remove old data
2. Run `cache.vacuum()` to reclaim space
3. Check database size with `cache.get_stats()`
4. Consider archiving very old data

## Testing

### Test Coverage

- **Basic Tests**: `scripts/test_cache_migration.py` (5 tests)
- **Advanced Tests**: `scripts/test_cache_advanced.py` (24 tests)
- **Total**: 29/29 tests passing (100% pass rate)

Test categories:
- Basic operations (set/get/filtering)
- Edge cases (empty data, duplicates, date handling)
- Expiration logic (TTL, cleanup)
- Multi-asset support
- Performance benchmarks
- Concurrent access (thread safety)
- Cache management operations

### Run Tests

```bash
# Basic tests
python scripts/test_cache_migration.py

# Advanced tests (comprehensive)
python scripts/test_cache_advanced.py

# Both test suites
python scripts/test_cache_migration.py && python scripts/test_cache_advanced.py
```

## Legacy System (Deprecated)

### UnifiedCacheManager (File-Based)

**Status**: Deprecated as of November 2025
**Location**: `src/data_sources/cache/unified_cache.py`

The old file-based cache is deprecated but maintained for backward compatibility:

- ⚠️ Deprecation warnings shown when used
- 📁 Stores data as JSON files in `.cache/market_data/`
- 🔄 CacheAdapter provides automatic fallback during migration
- 📅 Planned removal: Q2 2025

**Why deprecated:**
- No concurrent access safety
- Slower queries (200ms+ vs 25ms)
- File fragmentation issues
- Not futures-ready
- Manual cache cleanup required

## Best Practices

1. **Always use TradingCacheManager** for new code
2. **Specify asset_type** explicitly for options/futures
3. **Run periodic cleanup** (`cache.cleanup_expired()` weekly)
4. **Monitor database size** and vacuum when >1GB
5. **Use source filtering** to distinguish data from different providers
6. **Leverage smart expiration** - let the cache handle TTL automatically
7. **Enable WAL mode** for high-concurrency scenarios (see Performance Tuning)

## Performance Tuning

For high-frequency trading or heavy concurrent access:

```python
import sqlite3

# Enable WAL (Write-Ahead Logging) mode for better concurrency
with sqlite3.connect('.cache/trading_data.db') as conn:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")  # 10 second timeout
```

## Future Enhancements

Planned improvements:
- [ ] Compression for large datasets (gzip BLOB columns)
- [ ] Sharding for multi-TB deployments
- [ ] Read replicas for high-concurrency scenarios
- [ ] Time-series specific optimizations
- [ ] Automatic cache warming for common symbols
- [ ] Cache hit/miss metrics and monitoring

## Documentation

- **Implementation**: `src/data_sources/cache/README.md` (comprehensive guide)
- **Migration**: `CACHE_MIGRATION.md` (developer migration guide)
- **Testing**: `scripts/test_cache_advanced.py` (test examples)
- **Issue**: #336 (implementation details and discussion)

## Related Issues

- Issue #336: SQLite Cache System implementation (COMPLETED)
- Issue #287: GTC daily execution support
- Issue #306: Position management with multi-date queries
