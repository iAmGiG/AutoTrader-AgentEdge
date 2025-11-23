# Cache System Developer Guide

**Audience**: Developers integrating with or extending the cache system
**Last Updated**: November 2025 (Issue #336)

---

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

### Using CacheAdapter (Backward Compatibility)

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

---

## API Reference

### TradingCacheManager

**Constructor:**

```python
TradingCacheManager(
    db_path: str = ".cache/trading_data.db"
)
```

**Parameters:**
- `db_path`: Path to SQLite database file (default: `.cache/trading_data.db`)

---

#### `get()` - Retrieve Cached Data

```python
def get(
    self,
    symbol: str,
    start: str,
    end: str,
    source: str = None,
    asset_type: str = "stock"
) -> Optional[pd.DataFrame]:
```

**Parameters:**
- `symbol`: Stock ticker (e.g., "AAPL", "SPY")
- `start`: Start date in YYYY-MM-DD format
- `end`: End date in YYYY-MM-DD format
- `source`: Optional data source filter ("alpaca", "polygon", "alpha_vantage")
- `asset_type`: Asset type ("stock", "option", "future")

**Returns:**
- `pd.DataFrame` with OHLCV data if found
- `None` if cache miss

**Example:**

```python
df = cache.get("AAPL", "2025-01-01", "2025-01-31", source="alpaca")
if df is not None:
    print(f"Loaded {len(df)} days from cache")
else:
    print("Cache miss - fetch from API")
```

---

#### `set()` - Store Data in Cache

```python
def set(
    self,
    symbol: str,
    data: pd.DataFrame,
    source: str,
    asset_type: str = "stock",
    ttl_hours: int = None
) -> None:
```

**Parameters:**
- `symbol`: Stock ticker
- `data`: DataFrame with OHLCV columns (must have 'close' column minimum)
- `source`: Data source ("alpaca", "polygon", "alpha_vantage")
- `asset_type`: Asset type ("stock", "option", "future")
- `ttl_hours`: Optional custom TTL (overrides smart expiration)

**Required DataFrame Columns:**
- `close` (required)
- `open`, `high`, `low`, `volume` (recommended)
- `vwap`, `transactions` (optional)

**Example:**

```python
# DataFrame must have a datetime index
cache.set("AAPL", df, source="alpaca", asset_type="stock")

# Custom TTL (48 hours)
cache.set("AAPL", df, source="alpaca", ttl_hours=48)
```

---

#### `delete()` - Remove Cached Data

```python
def delete(
    self,
    symbol: str,
    start: str = None,
    end: str = None,
    source: str = None,
    asset_type: str = "stock"
) -> int:
```

**Parameters:**
- `symbol`: Stock ticker
- `start`: Optional start date filter
- `end`: Optional end date filter
- `source`: Optional source filter
- `asset_type`: Asset type

**Returns:**
- Number of entries deleted

**Examples:**

```python
# Delete all AAPL data
deleted = cache.delete("AAPL")

# Delete specific date range
deleted = cache.delete("AAPL", "2025-01-01", "2025-01-31")

# Delete specific source
deleted = cache.delete("AAPL", source="alpaca")
```

---

#### `get_stats()` - Cache Statistics

```python
def get_stats(self) -> Dict[str, Any]:
```

**Returns:**

```python
{
    'db_path': str,              # Database file path
    'db_size_mb': float,         # Size in megabytes
    'total_entries': int,        # Total cached entries
    'unique_symbols': int,       # Number of unique symbols
    'expired_entries': int,      # Entries past expiration
    'date_range': {
        'min_date': str,         # Earliest date in cache
        'max_date': str          # Latest date in cache
    },
    'by_source': {
        'alpaca': int,           # Entries per source
        'polygon': int,
        ...
    },
    'by_asset_type': {
        'stock': int,            # Entries per asset type
        'option': int,
        ...
    }
}
```

**Example:**

```python
stats = cache.get_stats()
print(f"Cache contains {stats['unique_symbols']} symbols")
print(f"Date range: {stats['date_range']['min_date']} to {stats['date_range']['max_date']}")
```

---

#### `cleanup_expired()` - Remove Expired Entries

```python
def cleanup_expired(self) -> int:
```

**Returns:**
- Number of expired entries deleted

**Example:**

```python
deleted = cache.cleanup_expired()
print(f"Removed {deleted} expired entries")
```

---

#### `vacuum()` - Optimize Database

```python
def vacuum(self) -> None:
```

Reclaims unused space after deletions.

**Example:**

```python
cache.cleanup_expired()
cache.vacuum()  # Reclaim space
```

---

#### `get_symbols()` - List Cached Symbols

```python
def get_symbols(self, asset_type: str = "stock") -> List[str]:
```

**Parameters:**
- `asset_type`: Asset type filter

**Returns:**
- List of unique symbols

**Example:**

```python
symbols = cache.get_symbols(asset_type="stock")
print(f"Cached symbols: {', '.join(symbols)}")
```

---

## Smart Expiration Logic

The cache automatically manages TTL based on data age:

| Data Age | TTL | Rationale |
|----------|-----|-----------|
| < 2 days old | 24 hours | Recent data changes frequently |
| ≥ 2 days old | 10 years | Historical data is immutable |

**Examples:**

```python
# Recent data (expires in 24 hours)
today = datetime.now()
recent_df = fetch_data("AAPL", today - timedelta(days=1), today)
cache.set("AAPL", recent_df, source="alpaca")

# Historical data (expires in 10 years)
historical_df = fetch_data("AAPL", "2024-01-01", "2024-12-31")
cache.set("AAPL", historical_df, source="alpaca")

# Custom TTL (overrides smart logic)
cache.set("AAPL", df, source="alpaca", ttl_hours=48)
```

---

## Multi-Asset Support

### Stocks (Current)

```python
cache.set("AAPL", df, source="alpaca", asset_type="stock")
df = cache.get("AAPL", start, end, asset_type="stock")
```

### Options (Schema Ready)

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

### Futures (Schema Ready)

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

---

## Integration Patterns

### Data Source Integration

```python
from src.data_sources.cache import TradingCacheManager

class MyDataSource:
    def __init__(self):
        self.cache = TradingCacheManager()

    def fetch_data(self, symbol, start, end):
        # Check cache first
        cached = self.cache.get(symbol, start, end, source="my_source")
        if cached is not None:
            logger.info(f"Cache hit for {symbol}")
            return cached

        # Fetch from API
        df = self._fetch_from_api(symbol, start, end)

        # Cache for future use
        self.cache.set(symbol, df, source="my_source")

        return df
```

### Using CacheAdapter for Backward Compatibility

```python
from src.data_sources.cache import cache_adapter

# Old code continues to work
df = cache_adapter.get_market_data("AAPL", "2025-01-01", "2025-01-31")
```

---

## Performance Optimization

### 1. Use Range Queries

Let SQL filter dates instead of loading everything:

```python
# Good: Efficient SQL query
df = cache.get("AAPL", "2025-01-01", "2025-01-31")

# Bad: Loading more than needed
df = cache.get("AAPL", "2024-01-01", "2025-12-31")
df = df[df.index >= "2025-01-01"]  # Filtering in Python
```

### 2. Periodic Maintenance

```python
# Weekly cleanup (cron job)
cache.cleanup_expired()
cache.vacuum()
```

### 3. Monitor Database Size

```python
stats = cache.get_stats()
if stats['db_size_mb'] > 100:  # 100 MB threshold
    logger.warning(f"Cache size: {stats['db_size_mb']} MB")
    cache.cleanup_expired()
    cache.vacuum()
```

---

## Troubleshooting

### Cache Miss (Expected)

```python
df = cache.get("AAPL", "2025-01-01", "2025-01-31")
if df is None:
    # Reasons:
    # 1. Data not cached yet (first request)
    # 2. Data expired (check TTL)
    # 3. Symbol/date range not available
    df = fetch_from_api("AAPL", "2025-01-01", "2025-01-31")
    cache.set("AAPL", df, source="api_name")
```

### Database Locked Error

SQLite serializes writes:

```python
# If you see "database is locked":
# - Reads are concurrent (OK)
# - Writes are serialized (one at a time)
# - Default timeout: 5 seconds

# The cache manager already handles write serialization
# with threading.Lock() - you shouldn't see this error
```

### Corrupted Database

```bash
# Check integrity
sqlite3 .cache/trading_data.db "PRAGMA integrity_check;"

# Rebuild from backup
mv .cache/trading_data.db .cache/trading_data.db.corrupt
python scripts/migrate_cache_to_sqlite.py
```

---

## Administrative CLI

### View Statistics

```bash
python scripts/cache_manager.py stats
```

### Cleanup Expired Entries

```bash
python scripts/cache_manager.py cleanup
```

### Optimize Database

```bash
python scripts/cache_manager.py vacuum
```

### List Cached Symbols

```bash
python scripts/cache_manager.py symbols
```

### Export Data

```bash
python scripts/cache_manager.py export SPY --start 2025-01-01 --end 2025-12-31
```

### Query Cache

```bash
python scripts/cache_manager.py query SPY --start 2025-10-01 --end 2025-10-31
```

### Clear Cache

```bash
# Clear specific symbol
python scripts/cache_manager.py clear --symbol SPY --confirm

# Clear all data (dangerous!)
python scripts/cache_manager.py clear --all --confirm
```

---

## Best Practices

1. **Always specify `asset_type`** when working with options/futures
2. **Use `source` parameter** to distinguish data from different providers
3. **Let smart expiration work** - only use custom TTL when necessary
4. **Run periodic cleanup** in production (weekly cron job)
5. **Monitor database size** and vacuum when >1GB
6. **Use CacheAdapter** during migration for backward compatibility

---

## Migration from Legacy Cache

See [CACHE_MIGRATION.md](../../CACHE_MIGRATION.md) for complete migration guide.

**Quick migration:**

```python
# Before (UnifiedCacheManager)
from src.data_sources.cache import UnifiedCacheManager
cache = UnifiedCacheManager()
cache.set_market_data(symbol, start, end, source, df)
df = cache.get_market_data(symbol, start, end, source)

# After (TradingCacheManager)
from src.data_sources.cache import TradingCacheManager
cache = TradingCacheManager()
cache.set(symbol, df, source=source)
df = cache.get(symbol, start, end, source=source)

# Or use CacheAdapter (no code changes)
from src.data_sources.cache import cache_adapter
df = cache_adapter.get_market_data(symbol, start, end, source)
```

---

## Testing

### Run Tests

```bash
# Basic tests (5 tests)
python scripts/test_cache_migration.py

# Advanced tests (24 tests)
python scripts/test_cache_advanced.py
```

### Test Coverage

- Basic operations (set/get/filtering)
- Edge cases (empty data, duplicates, date handling)
- Expiration logic (TTL, cleanup)
- Multi-asset support
- Performance benchmarks
- Concurrent access (thread safety)
- Cache management operations

**All 29/29 tests passing** ✅

---

## Performance Benchmarks

Query performance (production data):

| Operation | File Cache | SQLite Cache | Improvement |
|-----------|------------|--------------|-------------|
| Single symbol query | 45ms | 5ms | **9x faster** |
| Multi-symbol (10) | 225ms | 25ms | **9x faster** |
| Range query | 180ms | 8ms | **22x faster** |
| Write operation | 12ms | 3ms | **4x faster** |
| Storage size | 2.1 MB (54 files) | 0.5 MB | **4x smaller** |

---

## Additional Tables (Issue #373)

The cache database also includes:

### Raw Options Chain Storage

```python
from src.data_sources.cache import TradingCacheManager

cache = TradingCacheManager()

# Store raw options data
cache.store_raw_options(
    symbol="SPY",
    trading_date="2024-01-15",
    options_df=options_data,
    source="polygon"
)

# Retrieve options
options = cache.get_raw_options("SPY", "2024-01-15")
```

### Trade History Analytics

```python
# Archive completed trade
cache.archive_trade({
    'trade_id': 'AAPL_2024-01-15T10:30:00',
    'symbol': 'AAPL',
    'entry_date': '2024-01-15T10:30:00',
    'entry_price': 185.50,
    'quantity': 100,
    'exit_price': 188.20,
    'realized_pnl': 270.00,
    'strategy_name': 'VoterAgent'
})

# Query trade history
trades = cache.get_trade_history(strategy="VoterAgent")

# Get statistics
stats = cache.get_trade_stats(strategy="VoterAgent")
print(f"Win rate: {stats['win_rate_pct']:.1f}%")
```

See [Trade History Database](../trade_history_database.md) for complete API reference.

---

## Related Documentation

- **[Cache System Architecture](../02_architecture/04_cache_system.md)** - Technical design
- **[Trade History Database](../trade_history_database.md)** - Trade analytics API
- **[CACHE_MIGRATION.md](../../CACHE_MIGRATION.md)** - Migration guide
- **[Troubleshooting](../03_reference/04_troubleshooting.md)** - Common issues
- **Issue #336** - SQLite cache implementation
- **Issue #373** - Multi-provider options and trade history storage

---

*Developer guide for SQLite cache system integration and usage.*
