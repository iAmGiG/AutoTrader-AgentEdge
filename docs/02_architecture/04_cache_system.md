# Cache System Architecture

## Overview

The RH2MAS cache system provides unified data storage and retrieval for market data and news across multiple data sources. The system was recently overhauled to fix fragmentation issues and improve performance.

## Components

### UnifiedCacheManager

**Location**: `src/tools/cache/unified_cache.py`

Primary cache interface that handles:

- Market data caching (OHLCV)
- News data caching
- Source-agnostic storage format
- Dynamic validation thresholds
- Consolidated file support

### Cache Directory Structure

```bash
.cache/
├── market_data/
│   ├── AAPL_2024-01-01_2024-12-31_polygon_consolidated.json
│   ├── VXX_2024-01-01_2024-12-31_alpha_vantage_consolidated.json
│   └── backup_fragments/  # Old fragmented files
└── news_filtered/
    └── monthly cache files (filtered reliable sources)
```

## Key Features

### 1. Pattern Matching

The cache manager searches for both regular and consolidated files:

```python
pattern1 = f"{symbol}_*_{source}.json"
pattern2 = f"{symbol}_*_{source}_consolidated.json"
matching_files = list(self.market_dir.glob(pattern1)) + list(self.market_dir.glob(pattern2))
```

### 2. Dynamic Validation

Thresholds adapt based on requested date range:

```python
calendar_days = (end_dt - start_dt).days + 1
expected_trading_days = calendar_days * 0.7  # ~70% of calendar days are trading days
min_threshold = max(expected_trading_days * 0.5, 5)  # At least 50% coverage
```

### 3. Cache Consolidation

Fragmented cache files are merged using union operations:

- Removes duplicates
- Sorts by date
- Preserves all unique records
- Creates single consolidated file per symbol/year

## Data Sources

### Market Data

1. **Polygon.io** (Primary)
   - 5 calls/minute rate limit
   - 2 years historical data
   - Format: `_polygon.json` or `_polygon_consolidated.json`

2. **Alpha Vantage** (Fallback)
   - 25 calls/day limit
   - Used primarily for VXX data
   - Format: `_alpha_vantage.json` or `_alpha_vantage_consolidated.json`

### News Data

1. **Google Custom Search API**
   - 100 calls/day limit
   - Smart sampling via NewsGovernor
   - Monthly cache files
   - Premium sources (WSJ, Bloomberg, Reuters)

## Common Issues and Solutions

### Issue: Cache Fragmentation

**Symptoms**: Date jumps in backtests, missing trading days
**Solution**: Consolidate cache files using union operations
**Prevention**: Always use UnifiedCacheManager for data access

### Issue: Monthly Backtest Failures

**Symptoms**: "No market data available" for month-specific tests
**Solution**: Dynamic validation thresholds based on date range
**Fix Location**: `unified_cache.py` lines 119-128

### Issue: File Not Found

**Symptoms**: Cache exists but not found by manager
**Solution**: Update pattern matching to include consolidated files
**Fix Location**: `unified_cache.py` lines 209-211

## Performance Optimizations

1. **Consolidated Files**: Reduce file I/O by merging fragments
2. **Smart Caching**: NewsGovernor reduces API calls by 80-90%
3. **Expiration Logic**: Historical data cached long-term, recent data refreshed
4. **Parallel Loading**: Multiple cache files loaded concurrently

## Testing Validation

Successfully tested with:

- AAPL: 252 trading days, continuous progression
- AMZN: All V0-V3 versions completed
- SPY: All V0-V3 versions completed
- VXX: Consolidated from 21 fragments to 3 annual files

## Future Improvements

1. **Database Backend**: Consider SQLite for better query performance
2. **Compression**: Add gzip compression for large cache files
3. **Distributed Cache**: Redis for multi-machine deployments
4. **Cache Warming**: Pre-fetch commonly used symbols
