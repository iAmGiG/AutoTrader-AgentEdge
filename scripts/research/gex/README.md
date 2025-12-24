# GEX Research Pipeline

Production-ready scripts for Gamma Exposure (GEX) research and analysis.

## Quick Start

### Calculate Daily GEX Metrics

```bash
# Run full pipeline
python dask_gex_calculator.py

# Dry run (show what would be processed)
python dask_gex_calculator.py --dry-run

# Process specific symbols
python dask_gex_calculator.py --symbols SPY QQQ IWM

# Use custom configuration
python dask_gex_calculator.py --config custom_config.yaml
```

**Output**: Updates `options_daily_summary` table in `.cache/gex_research.db`

### Analyze GEX Research

```bash
# TSMOM vs GEX momentum comparison (Issue #421)
python tsmom_vs_gex_analysis.py
# Output: docs/08_research/02_gex_research/tsmom_vs_gex_analysis.md

# Cross-asset regime correlation (Issue #496)
python cross_asset_correlation.py
# Output: docs/08_research/02_gex_research/cross_asset_correlation.md
```

### Maintain Data

```bash
# Backfill missing underlying prices
python backfill_underlying_prices.py
```

## Configuration

Edit `gex_pipeline_config.yaml` to customize:

- Database location and optimization settings
- Processing chunk sizes and batch sizes
- Number of parallel workers
- Logging level and directory
- Data validation thresholds

## Performance

- **Raw data**: 50.88M options records
- **Processing**: ~10 minutes (1,700+ records/second)
- **Output**: 17,835 daily GEX metrics across 34 symbols
- **Coverage**: 2020-01-02 to 2025-12-16

## Scripts

| Script | Purpose | Time | Status |
|--------|---------|------|--------|
| `dask_gex_calculator.py` | Calculate daily GEX metrics | ~10 min | ✓ Production |
| `tsmom_vs_gex_analysis.py` | Momentum signal comparison | ~2 min | ✓ Complete |
| `cross_asset_correlation.py` | Cross-asset regime analysis | ~2 min | ✓ Complete |
| `backfill_underlying_prices.py` | Fill missing price data | ~5 min | ✓ Utility |

## For Historical Reference

See `archived/` directory for previous pipeline implementations:

- Single-symbol calculator (original approach)
- Database migration utilities
- Multiprocessing variant

These scripts are kept for reference and recovery purposes only.

## Big Data Techniques

This pipeline demonstrates key big data optimization patterns:

- **Vectorized Operations**: Pandas groupby aggregations (100-1000x speedup)
- **Chunked Reading**: 100K record chunks for memory efficiency
- **Batch Inserts**: executemany() with 1000-row batches (5-10x faster)
- **SQLite Optimization**: WAL mode + 1GB mmap + page cache
- **Multiprocessing**: 5+ workers on 64GB RAM
- **Incremental Updates**: Skip already processed symbols

## Data Schema

### options_daily_summary

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

## Related Issues

- **#501**: Big Data GEX Calculation Pipeline (✓ Completed)
- **#421**: TSMOM vs GEX Comparative Analysis (✓ Completed)
- **#496**: Cross-Asset Regime Correlation (✓ Completed)
- **#394**: GEX Forward Testing (✓ Completed)

## Architecture

See `docs/08_research/02_gex_research/gex_pipeline_architecture.md` for detailed technical documentation of the pipeline design.

---

**Status**: ✓ Production Ready
**Last Updated**: 2025-12-18
**Consolidated**: 4,247 → ~2,000 lines (53% reduction)
