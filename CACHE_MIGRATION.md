# SQLite Cache Migration Guide

## Overview

This guide helps you migrate from the legacy file-based cache system to the new SQLite-based TradingCacheManager.

## Quick Migration Checklist

- [ ] Run migration script to convert JSON files to SQLite
- [ ] Update imports in your code
- [ ] Change cache method calls to new API
- [ ] Test with your data sources
- [ ] Verify performance improvements
- [ ] Clean up legacy JSON files (optional)

## Step 1: Migrate Existing Cache Data

### Run the Migration Script

```bash
# Preview migration (dry run)
python scripts/migrate_cache_to_sqlite.py --dry-run

# Full migration (creates backup automatically)
python scripts/migrate_cache_to_sqlite.py

# Skip backup if you're confident
python scripts/migrate_cache_to_sqlite.py --no-backup
```

**What the script does:**

- Backs up all JSON files to `.cache/backup_TIMESTAMP/`
- Converts 3 cache formats: UnifiedCacheManager, MarketDataCache, and raw JSON
- Removes duplicates automatically
- Creates `.cache/trading_data.db` SQLite database
- Preserves all metadata (sources, timestamps)

**Expected output:**

```
=== SQLite Cache Migration ===
Migrating: .cache/market_data_AAPL_2025-01-01_2025-01-31_polygon.json
Migrating: .cache/market_data_SPY_2025-10-01_2025-10-31_alpaca.json
...
✅ Migration complete!
   Migrated: 2,163 total rows
   Unique entries: 1,337 (duplicates removed)
   Database: .cache/trading_data.db (0.5 MB)
   Backup: .cache/backup_20250112_143022/
```

## Step 2: Update Your Code

### Option A: Minimal Changes (CacheAdapter)

**Easiest migration path** - Keep existing code mostly unchanged:

```python
# No import changes needed if you were using:
from src.data_sources.cache import cache_adapter

# All existing code works the same:
df = cache_adapter.get_market_data("SPY", "2025-01-01", "2025-01-31", source="polygon")
cache_adapter.set_market_data("SPY", "2025-01-01", "2025-01-31", "polygon", df)
```

**What changed under the hood:**

- CacheAdapter now uses TradingCacheManager (SQLite) instead of UnifiedCacheManager (files)
- Falls back to legacy file cache during transition period
- No API changes required

### Option B: Direct Migration (TradingCacheManager)

**Recommended for new code** - Use SQLite cache directly:

**Before:**

```python
from src.data_sources.cache import UnifiedCacheManager

cache = UnifiedCacheManager()

# Old API
cache.set_market_data(
    symbol="AAPL",
    start_date="2025-01-01",
    end_date="2025-01-31",
    source="alpaca",
    data=df
)

df = cache.get_market_data(
    symbol="AAPL",
    start_date="2025-01-01",
    end_date="2025-01-31",
    source="alpaca"
)
```

**After:**

```python
from src.data_sources.cache import TradingCacheManager

cache = TradingCacheManager()

# New API - simpler!
cache.set(
    symbol="AAPL",
    data=df,
    source="alpaca"
)

df = cache.get(
    symbol="AAPL",
    start="2025-01-01",
    end="2025-01-31",
    source="alpaca"
)
```

**Key differences:**

1. `set_market_data()` → `set()` (dates extracted from DataFrame)
2. `get_market_data()` → `get()`
3. Constructor simpler: `TradingCacheManager()` vs `UnifiedCacheManager(base_dir=...)`

## Step 3: Update Data Sources

### Pattern for Alpaca Data Source

**Before:**

```python
from src.data_sources.cache import UnifiedCacheManager

class AlpacaMarketData:
    def __init__(self, cache_manager: Optional[UnifiedCacheManager] = None):
        self.cache = cache_manager or UnifiedCacheManager()

    def get_bars(self, symbols, start, end):
        # Old cache API
        cached = self.cache.get_market_data(symbol, start, end, source="alpaca")

        # After fetching...
        self.cache.set_market_data(symbol, start, end, "alpaca", df)
```

**After:**

```python
from src.data_sources.cache import TradingCacheManager

class AlpacaMarketData:
    def __init__(self, cache_manager: Optional[TradingCacheManager] = None):
        self.cache = cache_manager or TradingCacheManager()

    def get_bars(self, symbols, start, end):
        # New cache API
        cached = self.cache.get(symbol, start, end, source="alpaca")

        # After fetching...
        # Remove 'symbol' and 'source' columns before caching
        cache_data = df.drop(columns=['symbol', 'source'], errors='ignore')
        self.cache.set(symbol, cache_data, source="alpaca")
```

**Important notes:**

- Drop 'symbol' and 'source' columns before caching (stored as metadata)
- TradingCacheManager extracts date range from DataFrame index automatically

### Pattern for Other Data Sources

Apply the same changes to:

- `src/data_sources/sources/market/alpha_vantage_market.py`
- `src/data_sources/sources/market/polygon_market.py`
- `src/data_sources/sources/market/market_context_tool.py`
- Any custom data sources

## Step 4: Verify Migration

### Run the Test Suite

```bash
python scripts/test_cache_migration.py
```

**Expected output:**

```
======================================================================
SQLite Cache Migration Test Suite
======================================================================

======================================================================
TEST 1: TradingCacheManager (SQLite)
======================================================================
✅ Get: Retrieved 21 days
   Total entries: 1,337
   Unique symbols: 42
   DB size: 0.5 MB

======================================================================
TEST 2: CacheAdapter (uses SQLite)
======================================================================
✅ Get: Retrieved 21 days of AAPL data
   Total entries: 1,337

======================================================================
TEST 3: fetch_unified_market_data (integration)
======================================================================
✅ Fetch: Retrieved 15 days

======================================================================
TEST 4: Deprecation Warnings
======================================================================
✅ Deprecation warning shown for UnifiedCacheManager
✅ Deprecation warning shown for MarketDataCache

======================================================================
TEST 5: Performance Check
======================================================================
✅ Retrieved 105 total rows in 123.45ms
   Average: 24.69ms per symbol
   Performance: ✅ EXCELLENT

Result: 5/5 tests passed
🎉 ALL TESTS PASSED - Migration successful!
```

### Manual Verification

```python
from src.data_sources.cache import TradingCacheManager

cache = TradingCacheManager()

# Check what's in the cache
stats = cache.get_stats()
print(f"Total entries: {stats['total_entries']:,}")
print(f"Symbols: {cache.get_symbols()}")

# Try fetching some data
df = cache.get("SPY", "2025-10-01", "2025-10-31")
if df is not None:
    print(f"✅ SPY data: {len(df)} days")
else:
    print("❌ No SPY data cached")
```

## Step 5: Clean Up Legacy Files (Optional)

**After confirming everything works**, you can clean up old JSON cache files:

### Safety First

```bash
# Keep the backup created by migration script
ls -lh .cache/backup_*/

# Check database has all your data
python scripts/cache_manager.py stats
```

### Remove Legacy JSON Files

```bash
# Remove old unified cache format files
rm .cache/market_data_*.json

# Remove old MD5-hashed cache files (if any)
rm .cache/market_data/*.json

# Keep the SQLite database!
ls -lh .cache/trading_data.db
```

### What to Keep

```
.cache/
├── trading_data.db          # ✅ Keep - This is your new cache
├── backup_TIMESTAMP/        # ✅ Keep - Safety backup
├── market_data_*.json       # ❌ Delete after verification
└── market_data/             # ❌ Delete after verification
    └── *.json
```

## Deprecation Warnings

If you see these warnings, update your code:

```
DeprecationWarning: UnifiedCacheManager (file-based cache) is deprecated.
Use TradingCacheManager (SQLite) for better performance and futures support.
```

```
DeprecationWarning: MarketDataCache (MD5-hashed file cache) is deprecated.
Use TradingCacheManager (SQLite) for better performance.
```

**How to fix:**

1. Replace `UnifiedCacheManager` with `TradingCacheManager`
2. Replace `MarketDataCache` with `TradingCacheManager`
3. Update method calls (see Step 2)

## Common Migration Issues

### Issue 1: "No such table: market_cache"

**Cause:** SQLite database not initialized

**Fix:**

```python
from src.data_sources.cache import TradingCacheManager

# This will create the database if it doesn't exist
cache = TradingCacheManager()
```

Or run the migration script:

```bash
python scripts/migrate_cache_to_sqlite.py
```

### Issue 2: Cache misses after migration

**Cause:** Date format mismatch or source filter too strict

**Debug:**

```python
cache = TradingCacheManager()

# Check what sources are available
stats = cache.get_stats()
print(f"Sources: {stats['sources']}")

# Try without source filter
df = cache.get("AAPL", "2025-01-01", "2025-01-31")  # No source filter
```

### Issue 3: "Database is locked"

**Cause:** Multiple processes writing simultaneously

**Fix:** Increase timeout or serialize writes

```python
cache = TradingCacheManager(timeout=30.0)  # 30 second timeout
```

### Issue 4: Performance slower than expected

**Cause:** Database not vacuumed after migration

**Fix:**

```bash
python scripts/cache_manager.py vacuum
```

Or programmatically:

```python
cache = TradingCacheManager()
cache.vacuum()
```

## Performance Expectations

After migration, you should see:

| Metric | Before (JSON) | After (SQLite) | Expected Improvement |
|--------|---------------|----------------|----------------------|
| Single query | 40-60ms | 5-10ms | 5-10x faster |
| Multi-query (5 symbols) | 200-300ms | 20-30ms | 8-10x faster |
| Write operation | 10-15ms | 2-5ms | 3-5x faster |
| Storage size | 2-5 MB | 0.5-1 MB | 2-5x smaller |

If you don't see these improvements:

1. Run `cache.vacuum()` to optimize the database
2. Check if you're filtering by source unnecessarily
3. Verify indexes exist: `python scripts/cache_manager.py stats`

## Testing Your Migration

### Integration Test

```python
#!/usr/bin/env python3
"""Test your specific data sources after migration."""

from src.data_sources.cache import TradingCacheManager
from src.data_sources.sources.market.unified_market_tool import fetch_unified_market_data

def test_my_migration():
    cache = TradingCacheManager()

    # Test 1: Cache statistics
    stats = cache.get_stats()
    assert stats['total_entries'] > 0, "Cache is empty!"
    print(f"✅ Cache has {stats['total_entries']:,} entries")

    # Test 2: Fetch with cache hit
    df = fetch_unified_market_data("SPY", "2025-10-01", "2025-10-31")
    assert df is not None and not df.empty, "Failed to fetch SPY data"
    print(f"✅ Fetched {len(df)} days of SPY data")

    # Test 3: Verify caching works
    import time
    start = time.time()
    df2 = cache.get("SPY", "2025-10-01", "2025-10-31")
    elapsed = (time.time() - start) * 1000
    assert elapsed < 50, f"Cache query too slow: {elapsed:.2f}ms"
    print(f"✅ Cache query: {elapsed:.2f}ms")

    print("\n🎉 All tests passed!")

if __name__ == "__main__":
    test_my_migration()
```

## Rollback Plan

If you need to rollback to the old system:

### Quick Rollback

```python
# In your code, switch back temporarily:
from src.data_sources.cache import UnifiedCacheManager  # Old system

cache = UnifiedCacheManager()
# Use old API...
```

**Note:** You'll see deprecation warnings, but it will still work.

### Full Rollback

```bash
# 1. Restore JSON files from backup
cp -r .cache/backup_TIMESTAMP/* .cache/

# 2. Remove SQLite database
mv .cache/trading_data.db .cache/trading_data.db.backup

# 3. Update git to previous commit
git log --oneline  # Find commit before migration
git checkout <commit-hash>
```

## Next Steps After Migration

1. **Monitor Performance**

   ```bash
   python scripts/cache_manager.py stats
   ```

2. **Set Up Periodic Maintenance** (crontab example)

   ```bash
   # Run cleanup daily at 2am
   0 2 * * * cd /path/to/project && python scripts/cache_manager.py cleanup --vacuum
   ```

3. **Prepare for Options/Futures** (when ready)

   ```python
   # The schema already supports this!
   cache.set("AAPL_20250117C150", option_df, source="alpaca", asset_type="option")
   ```

4. **Remove Deprecation Warnings**
   - Update all code to use TradingCacheManager
   - Run tests to verify no warnings

## Support

If you encounter issues:

1. **Check documentation**: `src/data_sources/cache/README.md`
2. **Run test suite**: `python scripts/test_cache_migration.py`
3. **Check logs**: Look in `logs/` directory
4. **GitHub issue**: See issue #336 for discussions
5. **Verify database**: `sqlite3 .cache/trading_data.db ".schema"`

## Migration Completed Checklist

- [ ] Migration script ran successfully
- [ ] Test suite passes (5/5 tests)
- [ ] No deprecation warnings in your code
- [ ] Performance improvements confirmed (< 50ms queries)
- [ ] Legacy JSON files backed up and removed
- [ ] Documentation reviewed
- [ ] Data sources updated
- [ ] Integration tests pass

---

**Migration Status:** Once this checklist is complete, your migration to SQLite cache is done! 🎉
