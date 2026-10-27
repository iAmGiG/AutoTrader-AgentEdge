# Cache System

SQLite-based market data caching for the AutoGen Trading System.

## Quick Links

**For comprehensive documentation, see:**

- **[Cache System Architecture](../../docs/02_architecture/04_cache_system.md)** - Full technical documentation
- **[Developer Guide](../../docs/04_development/04_cache_developer_guide.md)** - API reference and examples

## Components

- **`sqlite_cache.py`** - `TradingCacheManager` (the SQLite market-data cache)
- **`cache_adapter.py`** - `cache_adapter`, the shared market-data interface the tools use
- **`unified_broker_cache.py`** - `unified_broker_cache`, broker state and position/order snapshots
- **`base_cache.py`, `ohlcv_cache.py`, `options_cache.py`, `trade_cache.py`** - per-domain parts (#438)
- **`lazy.py`** - `LazyInstance`: the shared instances are built on first use (#600)

## Location

The database is `<repo>/.cache/trading_data.db`; `$AUTOTRADER_CACHE_DIR` moves it (see
`src/utils/state_paths.py`). Importing the package creates nothing: `cache_adapter` and
`unified_broker_cache` open the database on first use. The test suite points
`$AUTOTRADER_CACHE_DIR` at a temporary directory for every test (`tests/conftest.py`).

## Quick Start

```python
from src.cache import TradingCacheManager

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
python scripts/utilities/cache_manager.py stats

# Cleanup expired entries
python scripts/utilities/cache_manager.py cleanup

# See all commands
python scripts/utilities/cache_manager.py --help
```

## Testing

```bash
pytest tests/unit/data_sources/test_sqlite_cache.py tests/unit/test_cache_manager_script.py
```

## Migration

> **Note**: The migration script has been removed (Issue #435) after completing its purpose. SQLite cache is now the standard. Legacy JSON cache files can be safely deleted - the cache will rebuild automatically from API calls.

---

**Implementation**: Issue #336
**Status**: Production (November 2025)
**Performance**: 8-10x faster, 90%+ cache hit rate
