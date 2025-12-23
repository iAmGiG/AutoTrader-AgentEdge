# GEX Calculation Pipeline Architecture

**Issue**: #501
**Status**: Implemented
**Last Updated**: 2025-12-17

## Overview

Production-grade pipeline for calculating Gamma Exposure (GEX) metrics from 50M+ options records. Designed for scalability, reliability, and maintainability.

## Data Flow

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        options_chains (50M+ records)                 │
│         SQLite: symbol, trading_date, gamma, delta, OI, etc.        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CHUNKED READING (100K/chunk)                    │
│                    Memory-efficient data loading                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    VECTORIZED GEX CALCULATION                        │
│                                                                      │
│  1. Clean data (fill NaN, filter outliers)                          │
│  2. Calculate weighted_gamma = gamma * open_interest                │
│  3. Aggregate by trading_date:                                       │
│     - total_gex, net_call_gex, net_put_gex                          │
│     - zero_gamma_level, max_gamma_strike                            │
│     - regime classification                                          │
│  4. Calculate data quality score                                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BATCH INSERT (1000/batch)                         │
│              executemany() with WAL mode for speed                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│               options_daily_summary (~16K records)                   │
│     SQLite: symbol, date, regime, gex metrics, quality score        │
└─────────────────────────────────────────────────────────────────────┘
```

## Big Data Techniques

### 1. Vectorized Operations (Pandas)

**Before (Naive)**:

```python
# O(n) Python loop - SLOW
for row in rows:
    gamma = row['gamma'] * row['open_interest']
    total += gamma
```

**After (Vectorized)**:

```python
# O(1) C-level operation - FAST
df['weighted_gamma'] = df['gamma'] * df['open_interest']
total = df['weighted_gamma'].sum()
```

**Speedup**: 100-1000x for large datasets

### 2. Chunked Reading

```python
# Memory-efficient: processes 100K rows at a time
for chunk in pd.read_sql_query(query, conn, chunksize=100_000):
    process(chunk)
```

**Benefit**: Handles datasets larger than RAM

### 3. SQLite Optimizations

```sql
PRAGMA journal_mode=WAL      -- Concurrent reads/writes
PRAGMA cache_size=-102400    -- 100MB page cache
PRAGMA mmap_size=1073741824  -- 1GB memory-mapped I/O
PRAGMA synchronous=OFF       -- Faster writes (bulk ops)
PRAGMA temp_store=MEMORY     -- Temp tables in RAM
```

**Benefit**: 5-10x faster bulk inserts

### 4. Batch Inserts

```python
# Single INSERT per record - SLOW
for record in records:
    cursor.execute(insert_sql, record)

# Batch INSERT - FAST
cursor.executemany(insert_sql, records[:1000])
```

**Benefit**: Reduces transaction overhead

### 5. Incremental Processing

```python
# Only process new dates
processed = get_processed_dates(symbol)
new_data = df[~df['trading_date'].isin(processed)]
```

**Benefit**: Resume from failures, skip already done

## Configuration

**File**: `scripts/research/gex/gex_pipeline_config.yaml`

```yaml
database:
  path: ".cache/gex_research.db"
  journal_mode: "WAL"
  cache_size_mb: 100
  mmap_size_mb: 1024

processing:
  read_chunk_size: 100000
  write_batch_size: 1000
  num_workers: 0  # Auto-detect

logging:
  log_dir: "logs/gex_pipeline"
  level: "INFO"

validation:
  min_contracts: 50
  min_open_interest: 100
  max_gamma: 1.0
```

## Files

| File | Purpose |
|------|---------|
| `dask_gex_calculator.py` | Main pipeline with logging |
| `gex_pipeline_config.yaml` | Configuration |
| `tsmom_vs_gex_analysis.py` | Momentum analysis script |
| `cross_asset_correlation.py` | Cross-asset regime analysis |
| `backfill_underlying_prices.py` | Maintenance utility |

### Archived Scripts

Previous implementations are available in `archived/`:

- `gex_calculator.py` - Original single-symbol calculator
- `parallel_gex_calculator.py` - Multiprocessing variant
- `migrate_gex_database.py` - One-time database migration utility

## Usage

```bash
# Run full pipeline
python scripts/research/gex/dask_gex_calculator.py

# Dry run (show what would be processed)
python scripts/research/gex/dask_gex_calculator.py --dry-run

# Process specific symbols
python scripts/research/gex/dask_gex_calculator.py --symbols SPY QQQ IWM

# Custom config
python scripts/research/gex/dask_gex_calculator.py --config my_config.yaml
```

## Output

### options_daily_summary Schema

| Column | Type | Description |
|--------|------|-------------|
| symbol | TEXT | Ticker symbol |
| trading_date | TEXT | YYYY-MM-DD |
| underlying_price | REAL | Stock price |
| total_gex | REAL | Total gamma exposure (normalized) |
| net_call_gex | REAL | Call gamma / call OI |
| net_put_gex | REAL | Put gamma / put OI |
| zero_gamma_level | REAL | Strike where gamma = 0 |
| max_gamma_strike | REAL | Strike with highest gamma |
| regime | TEXT | POSITIVE_GAMMA / NEGATIVE_GAMMA / NEUTRAL |
| call_oi_concentration | REAL | Call OI / Total OI |
| put_oi_concentration | REAL | Put OI / Total OI |
| contracts_count | INT | Number of option contracts |
| expirations_count | INT | Unique expiration dates |
| data_quality_score | REAL | 0-1 quality metric |
| calculation_method | TEXT | Algorithm used |
| calculation_timestamp | TEXT | When calculated |
| asset_class | TEXT | equity/volatility/bond/commodity/real_estate |

### Reports

Generated in `docs/08_research/03_gex_research/reports/`:

- Regime distribution by asset class
- Symbol-level breakdown
- Data quality summary

## Performance

| Approach | Records/sec | 16K Days |
|----------|-------------|----------|
| Naive (row-by-row) | ~1 | ~4 hours |
| Vectorized | ~500 | ~30 sec |
| Vectorized + Batch Insert | ~1000+ | ~15 sec |

## Error Handling

1. **Database Lock**: 120-second timeout with retry
2. **Invalid Data**: Filtered by max_gamma threshold
3. **Missing Values**: Filled with defaults (gamma=0, OI=1)
4. **Partial Failure**: Checkpoints every 5 symbols

## Monitoring

Logs written to `logs/gex_pipeline/`:

```text
2025-12-17 22:30:00 - INFO - Processing SPY...
2025-12-17 22:30:05 - INFO - SPY: 1010 new days calculated
2025-12-17 22:30:05 - INFO - Checkpoint: 5/34 symbols, 2500 new days
```

## Related Issues

- #421 - TSMOM vs GEX Comparative Analysis (depends on this)
- #496 - Cross-Asset Regime Correlation (depends on this)
- #394 - GEX Forward Testing (depends on this)
