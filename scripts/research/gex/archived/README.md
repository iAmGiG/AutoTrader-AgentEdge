# Archived GEX Research Scripts

These scripts have been archived because they are no longer actively used in the production pipeline. They are retained for reference and recovery purposes.

## Scripts

### gex_calculator.py

- **Purpose**: Original single-symbol GEX calculator
- **Superseded by**: `dask_gex_calculator.py` (vectorized implementation)
- **Kept for**: Reference if vectorized calculation needs debugging, or as fallback for single-symbol analysis
- **Status**: Functional but slower (100-1000x slower than vectorized approach)

### migrate_gex_database.py

- **Purpose**: Database schema migration utility
- **Use case**: One-time utility used during initial database setup
- **Kept for**: Schema reference and recovery if database needs rebuilding
- **Status**: Functional but not needed for production operation

### parallel_gex_calculator.py

- **Purpose**: Multiprocessing GEX calculator (alternative to dask version)
- **Superseded by**: `dask_gex_calculator.py` (more comprehensive with logging, checkpointing)
- **Kept for**: Fallback if dask version encounters issues
- **Status**: Functional but missing production features (no logging, checkpointing, config management)

## Usage

If you need to use an archived script:

1. Copy it back to `scripts/research/gex/`

   ```bash
   cp scripts/research/gex/archived/gex_calculator.py scripts/research/gex/
   ```

2. Update any imports if needed (unlikely)

3. Run with appropriate parameters

## Production Pipeline

For current GEX calculations, use:

- **Main Pipeline**: `scripts/research/gex/dask_gex_calculator.py`
  - Vectorized pandas operations
  - Logging and checkpointing
  - Configuration-driven parameters
  - ~1,700 records/second throughput

- **Analysis Scripts**:
  - `tsmom_vs_gex_analysis.py` - Momentum signal comparison (Issue #421)
  - `cross_asset_correlation.py` - Cross-asset regime analysis (Issue #496)

- **Maintenance**: `backfill_underlying_prices.py` - Fill missing price data

## Archive Decision Rationale

These scripts were archived to:

- **Reduce code complexity**: 4,247 → ~2,000 lines (53% reduction)
- **Simplify maintenance**: Multiple implementations → 1 production version
- **Preserve functionality**: All tested functionality retained in dask_gex_calculator.py
- **Maintain history**: Archived scripts available for reference and recovery

## Performance Comparison

| Implementation | Records/sec | 17K Days | Method |
|---|---|---|---|
| gex_calculator.py | ~1 | ~4 hours | Row-by-row (slow) |
| parallel_gex_calculator.py | ~500 | ~30 sec | Multiprocessing |
| dask_gex_calculator.py | ~1000+ | ~15 sec | Vectorized + batch inserts |

---

**Archive Date**: 2025-12-18
**Reason**: Production consolidation and code reduction
**Risk**: LOW - All functionality tested and retained in production pipeline
