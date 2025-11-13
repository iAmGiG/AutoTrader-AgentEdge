# Cache System

SQLite-based market data caching for the AutoGen Trading System.

## Quick Links

**For comprehensive documentation, see:**
- **[Cache System Architecture](../../../docs/02_architecture/04_cache_system.md)** - Full technical documentation
- **[Developer Guide](../../../docs/04_development/cache_developer_guide.md)** - API reference and examples
- **[Migration Guide](../../../CACHE_MIGRATION.md)** - Migrating from file-based cache

## Components

- **`sqlite_cache.py`** - TradingCacheManager (production SQLite backend)
- **`cache_adapter.py`** - Backward-compatible abstraction layer
- **`unified_cache.py`** - Deprecated file-based cache (legacy)
- **`market_data_cache.py`** - Deprecated legacy cache (legacy)

## Quick Start

```python
from src.data_sources.cache import TradingCacheManager

cache = TradingCacheManager()

# Store data
cache.set("AAPL", df, source="alpaca", asset_type="stock")

# Retrieve data
df = cache.get("AAPL", "2025-01-01", "2025-01-31", source="alpaca")
```

## Key Features

- **8-10x faster** than file-based cache
- **ACID transactions** for data integrity
- **Thread-safe** concurrent access
- **Smart expiration**: Historical (10yr TTL), Recent (24hr TTL)
- **Futures-ready**: Supports stocks, options, futures

## Administrative Tools

```bash
# View cache statistics
python scripts/cache_manager.py stats

# Cleanup expired entries
python scripts/cache_manager.py cleanup

# See all commands
python scripts/cache_manager.py --help
```

## Testing

```bash
# Run basic tests
python scripts/test_cache_migration.py

# Run comprehensive tests
python scripts/test_cache_advanced.py
```

## Migration

To migrate from legacy JSON cache:

```bash
python scripts/migrate_cache_to_sqlite.py
```

See [CACHE_MIGRATION.md](../../../CACHE_MIGRATION.md) for detailed migration instructions.

---

**Implementation**: Issue #336
**Status**: Production (November 2025)
**Performance**: 8-10x faster, 90%+ cache hit rate
