# Trading Cache System

## Overview

The AutoGen Trading System uses SQLite-based caching for efficient storage and retrieval of market data. The new **TradingCacheManager** replaces the legacy file-based cache system with a centralized, performant database solution.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                          │
│  (Alpaca, Alpha Vantage, Polygon, etc.)                 │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              CacheAdapter (Abstraction Layer)            │
│         Provides backward compatibility APIs             │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│          TradingCacheManager (SQLite Backend)            │
│                                                           │
│  • Smart expiration (24hr recent, 10yr historical)      │
│  • Efficient range queries with SQL                      │
│  • ACID transactions for data integrity                  │
│  • Multi-asset support (stocks, options, futures)       │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
              .cache/trading_data.db
              (SQLite Database)
```

## Why SQLite?

### Before (File-Based Cache)
- 54+ scattered JSON files
- ~200ms+ to load multiple symbols
- No concurrent access safety
- Duplicate data across files
- Manual file locking required

### After (SQLite Cache)
- Single 0.5 MB database
- ~25ms average query (8x faster)
- Built-in transaction safety
- Automatic deduplication
- Native concurrent access

## Quick Start

### Basic Usage

```python
from src.data_sources.cache import TradingCacheManager

# Initialize cache
cache = TradingCacheManager()

# Store market data
cache.set(
    symbol="AAPL",
    data=df,  # pandas DataFrame with OHLCV data
    source="alpaca",
    asset_type="stock"
)

# Retrieve cached data
df = cache.get(
    symbol="AAPL",
    start="2025-01-01",
    end="2025-01-31",
    source="alpaca",  # Optional: filter by source
    asset_type="stock"
)

# Check cache statistics
stats = cache.get_stats()
print(f"Total entries: {stats['total_entries']}")
print(f"Database size: {stats['db_size_mb']} MB")
```

### Using CacheAdapter (Recommended for Compatibility)

```python
from src.data_sources.cache import cache_adapter

# Get market data (tries cache first, falls back to legacy)
df = cache_adapter.get_market_data(
    symbol="SPY",
    start_date="2025-10-01",
    end_date="2025-10-31",
    source="any"  # or specific: "alpaca", "polygon", etc.
)

# Set market data
cache_adapter.set_market_data(
    symbol="SPY",
    start_date="2025-10-01",
    end_date="2025-10-31",
    source="polygon",
    data=df
)
```

## Database Schema

```sql
CREATE TABLE market_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_type TEXT NOT NULL,           -- 'stock', 'option', 'future'
    symbol TEXT NOT NULL,               -- Ticker symbol
    trading_date TEXT NOT NULL,         -- YYYY-MM-DD format
    source TEXT NOT NULL,               -- Data source (alpaca, polygon, etc.)

    -- OHLCV data
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    vwap REAL,
    transactions INTEGER,

    -- Metadata
    created_at TEXT NOT NULL,           -- When cached
    expires_at TEXT NOT NULL,           -- Expiration timestamp

    UNIQUE(asset_type, symbol, trading_date, source)
);

CREATE INDEX idx_symbol_date ON market_cache(asset_type, symbol, trading_date);
CREATE INDEX idx_expiration ON market_cache(expires_at);
```

## Smart Expiration Logic

The cache uses intelligent TTL based on data recency:

| Data Age | TTL | Rationale |
|----------|-----|-----------|
| < 2 days old | 24 hours | Recent data changes frequently |
| ≥ 2 days old | 10 years | Historical data is immutable |

```python
# Recent data (short TTL)
cache.set("AAPL", recent_df, source="alpaca")  # Expires in 24 hours

# Historical data (long TTL)
cache.set("AAPL", historical_df, source="alpaca")  # Expires in 10 years

# Custom TTL
cache.set("AAPL", df, source="alpaca", ttl_hours=48)  # 48 hour TTL
```

## Multi-Asset Support

The system is designed for stocks, options, and futures:

### Stocks (Current)
```python
cache.set("AAPL", df, source="alpaca", asset_type="stock")
df = cache.get("AAPL", start, end, asset_type="stock")
```

### Options (Future Ready)
```python
cache.set(
    symbol="AAPL_20250117C150",  # Option symbol format
    data=option_df,
    source="alpaca",
    asset_type="option"
)

df = cache.get(
    symbol="AAPL_20250117C150",
    start="2025-01-01",
    end="2025-01-17",
    asset_type="option"
)
```

### Futures (Future Ready)
```python
cache.set(
    symbol="ES_202503",  # Futures contract
    data=futures_df,
    source="alpaca",
    asset_type="future"
)

df = cache.get(
    symbol="ES_202503",
    start="2025-01-01",
    end="2025-03-20",
    asset_type="future"
)
```

## Cache Management

### CLI Tool

Use the cache management CLI for administrative tasks:

```bash
# View cache statistics
python scripts/cache_manager.py stats

# Cleanup expired entries
python scripts/cache_manager.py cleanup

# Optimize database (reclaim space)
python scripts/cache_manager.py vacuum

# List all cached symbols
python scripts/cache_manager.py symbols

# Export data to JSON
python scripts/cache_manager.py export SPY --start 2025-01-01 --end 2025-12-31

# Clear specific symbol
python scripts/cache_manager.py clear --symbol SPY --confirm

# Query cache data
python scripts/cache_manager.py query SPY --start 2025-10-01 --end 2025-10-31
```

### Programmatic Management

```python
from src.data_sources.cache import TradingCacheManager

cache = TradingCacheManager()

# Get statistics
stats = cache.get_stats()
print(f"Total entries: {stats['total_entries']:,}")
print(f"Unique symbols: {stats['unique_symbols']}")
print(f"Date range: {stats['date_range']['min_date']} to {stats['date_range']['max_date']}")

# Cleanup expired entries
deleted = cache.cleanup_expired()
print(f"Deleted {deleted} expired entries")

# Optimize database
cache.vacuum()

# Get cached symbols
symbols = cache.get_symbols(asset_type="stock")
print(f"Cached symbols: {symbols}")

# Delete specific data
deleted = cache.delete(
    symbol="AAPL",
    start="2025-01-01",
    end="2025-01-31",
    source="alpaca"
)
```

## Migration Guide

### For Developers

If you're using the old cache system:

**Before (UnifiedCacheManager):**
```python
from src.data_sources.cache import UnifiedCacheManager

cache = UnifiedCacheManager()
cache.set_market_data(symbol, start, end, source, df)
df = cache.get_market_data(symbol, start, end, source)
```

**After (TradingCacheManager):**
```python
from src.data_sources.cache import TradingCacheManager

cache = TradingCacheManager()
cache.set(symbol, df, source=source)
df = cache.get(symbol, start, end, source=source)
```

**Using CacheAdapter (Easiest Migration):**
```python
from src.data_sources.cache import cache_adapter

# Same API as before, but uses SQLite backend
cache_adapter.set_market_data(symbol, start, end, source, df)
df = cache_adapter.get_market_data(symbol, start, end, source)
```

### Data Migration

To migrate existing JSON cache files to SQLite:

```bash
# Dry run (preview migration)
python scripts/migrate_cache_to_sqlite.py --dry-run

# Full migration (creates backup)
python scripts/migrate_cache_to_sqlite.py

# Skip backup creation
python scripts/migrate_cache_to_sqlite.py --no-backup
```

The migration script:
- Backs up existing JSON files to `.cache/backup_TIMESTAMP/`
- Migrates all cache formats (UnifiedCacheManager, MarketDataCache)
- Removes duplicates automatically
- Preserves all metadata (source, timestamps)

## Performance

### Benchmarks

Query performance (5 symbols, 2 months each):

| Operation | File Cache | SQLite Cache | Improvement |
|-----------|------------|--------------|-------------|
| Single symbol query | 45ms | 5ms | 9x faster |
| Multi-symbol query | 225ms | 25ms | 9x faster |
| Range query | 180ms | 8ms | 22x faster |
| Write operation | 12ms | 3ms | 4x faster |

Database size comparison:
- 54 JSON files: ~2.1 MB total
- SQLite database: 0.5 MB (4x smaller)

### Optimization Tips

1. **Use range queries**: Let SQL filter dates instead of loading everything
```python
# Good: Efficient SQL query
df = cache.get("AAPL", "2025-01-01", "2025-01-31")

# Bad: Loading more data than needed
df = cache.get("AAPL", "2024-01-01", "2025-12-31")
df = df[df.index >= "2025-01-01"]  # Filtering in Python
```

2. **Vacuum periodically**: After large deletions
```python
cache.cleanup_expired()
cache.vacuum()  # Reclaim space
```

3. **Batch inserts**: Use transactions for multiple writes
```python
# The cache manager handles this automatically in .set()
```

## Troubleshooting

### Cache Miss (Expected Behavior)

If cache.get() returns None:
1. Data not cached yet (first request)
2. Data expired (check TTL)
3. Symbol/date range not available

### Database Locked Error

SQLite databases have write serialization:
- Reads are concurrent (multiple processes OK)
- Writes are serialized (one at a time)
- Timeout is 5 seconds by default

If you see "database is locked":
- Increase timeout: `TradingCacheManager(db_path="...", timeout=30)`
- Check for long-running transactions

### Corrupted Database

If database becomes corrupted:
```bash
# Check integrity
sqlite3 .cache/trading_data.db "PRAGMA integrity_check;"

# Rebuild from backup
mv .cache/trading_data.db .cache/trading_data.db.corrupt
python scripts/migrate_cache_to_sqlite.py  # Re-migrate from JSON backups
```

## Best Practices

1. **Always specify asset_type** when working with options/futures
2. **Use CacheAdapter** for backward compatibility during migration
3. **Run cleanup periodically** in production (cron job)
4. **Monitor database size** and vacuum when it grows significantly
5. **Use source filtering** to avoid cache conflicts between data sources
6. **Set appropriate TTLs** for your use case (default is smart)

## API Reference

### TradingCacheManager

**Constructor:**
```python
TradingCacheManager(
    db_path: str = ".cache/trading_data.db",
    timeout: float = 5.0
)
```

**Methods:**

- `get(symbol, start, end, source=None, asset_type="stock") -> pd.DataFrame | None`
- `set(symbol, data, source, asset_type="stock", ttl_hours=None) -> None`
- `delete(symbol, start=None, end=None, source=None, asset_type="stock") -> int`
- `get_stats() -> Dict[str, Any]`
- `cleanup_expired() -> int`
- `vacuum() -> None`
- `get_symbols(asset_type="stock") -> List[str]`

### CacheAdapter

**Methods:**

- `get_market_data(symbol, start_date, end_date, source="any") -> pd.DataFrame | None`
- `set_market_data(symbol, start_date, end_date, source, data) -> None`
- `clear_market_cache(symbol=None, source=None) -> None`
- `get_cache_stats() -> Dict[str, Any]`

## Future Enhancements

Planned improvements:
- [ ] Compression for large datasets
- [ ] Sharding for multi-TB deployments
- [ ] Read replicas for high-concurrency
- [ ] Time-series specific optimizations
- [ ] Automatic cache warming
- [ ] Cache hit/miss metrics

## Support

For issues or questions:
1. Check this documentation
2. Run `python scripts/test_cache_migration.py` to validate setup
3. Review logs in `logs/` directory
4. Check GitHub issue #336 for related discussions
