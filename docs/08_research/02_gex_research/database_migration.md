# GEX Database Migration Strategy

**Status**: Pending C-chat data collection completion
**Source**: gex-llm-patterns `.cache/options_historical.db`
**Target**: AutoTrader `.cache/gex_research.db`

---

## Overview

The gex-llm-patterns project (C-chat) is collecting 5+ years of options data with premium Alpha Vantage API. Rather than duplicate this work, we use a symlink or copy strategy to access the same database from AutoTrader.

## Database Schema (Source)

### options_chains (~3.1M records)

Complete options chain data with full Greeks:

```sql
CREATE TABLE options_chains (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    strike REAL NOT NULL,
    option_type TEXT NOT NULL,  -- 'call' or 'put'
    expiration TEXT NOT NULL,

    -- Pricing
    bid REAL, ask REAL, last REAL, mark REAL,
    bid_size INTEGER, ask_size INTEGER,
    volume INTEGER, open_interest INTEGER,

    -- Greeks (Alpha Vantage calculated)
    delta REAL, gamma REAL, theta REAL, vega REAL, rho REAL,
    implied_volatility REAL,

    -- Metrics
    underlying_price REAL,
    mid_price REAL,
    bid_ask_spread REAL,
    bid_ask_spread_pct REAL,
    vol_oi_ratio REAL,

    -- Metadata
    data_source TEXT,
    data_quality_score REAL,
    asset_class TEXT,
    created_at TEXT,

    UNIQUE(symbol, trading_date, strike, option_type, expiration)
);
```

### options_daily_summary (empty, ready for GEX calc)

Pre-calculated daily GEX metrics:

```sql
CREATE TABLE options_daily_summary (
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    underlying_price REAL,

    -- GEX calculations
    total_gex REAL,
    net_call_gex REAL,
    net_put_gex REAL,
    zero_gamma_level REAL,
    max_gamma_strike REAL,
    regime TEXT,  -- 'POSITIVE_GAMMA', 'NEGATIVE_GAMMA', 'NEUTRAL'

    -- OI concentration
    call_oi_concentration REAL,
    put_oi_concentration REAL,

    -- Metadata
    contracts_count INTEGER,
    expirations_count INTEGER,
    data_quality_score REAL,
    calculation_method TEXT,
    calculation_timestamp TEXT,
    asset_class TEXT,

    PRIMARY KEY (symbol, trading_date)
);
```

### collection_progress

Tracks which dates have been collected:

```sql
CREATE TABLE collection_progress (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'completed', 'failed', 'pending'
    contracts_count INTEGER,
    error_message TEXT,
    api_call_made INTEGER,
    created_at TEXT
);
```

---

## Migration Strategies

### Option 1: Symlink (Recommended)

**Pros:**

- Zero storage duplication
- Always synchronized with gex-llm-patterns data
- Instant "migration"
- Both projects benefit from continued collection

**Cons:**

- Changes in gex-llm-patterns affect AutoTrader
- Requires both projects on same filesystem

**Usage:**

```bash
cd a:\Projects\AutoGen-Trader
python scripts/research/gex/link_gex_database.py --mode symlink
```

Result: `.cache/gex_research.db` → `a:\Projects\gex-llm-patterns\.cache\options_historical.db`

### Option 2: Copy

**Pros:**

- Independent database (safety)
- Can modify without affecting gex-llm-patterns
- Survives if gex-llm-patterns deleted

**Cons:**

- Duplicates ~500MB-2GB of data
- Not synchronized (need to recopy for updates)

**Usage:**

```bash
cd a:\Projects\AutoGen-Trader
python scripts/research/gex/link_gex_database.py --mode copy
```

### Option 3: Schema Extension (Future)

If we want to integrate options into production AutoTrader cache:

```sql
-- Add to existing trading_data.db
CREATE TABLE options_chains (...);  -- Same schema as above
CREATE TABLE options_daily_summary (...);
```

This allows unified queries across equity OHLCV and options Greeks.

---

## Usage in AutoTrader

Once linked/copied, access the data:

```python
import sqlite3
import pandas as pd

# Connect to GEX research database
conn = sqlite3.connect(".cache/gex_research.db")

# Query options chains
spy_options = pd.read_sql("""
    SELECT * FROM options_chains
    WHERE symbol = 'SPY'
    AND trading_date = '2024-01-15'
""", conn)

# Query daily GEX summary (after calculation)
gex_history = pd.read_sql("""
    SELECT trading_date, symbol, total_gex, regime
    FROM options_daily_summary
    WHERE symbol IN ('SPY', 'QQQ', 'TLT')
    ORDER BY trading_date
""", conn)

conn.close()
```

---

## Current Collection Status (C-chat)

| Ticker | Status | Records | Date Range |
|--------|--------|---------|------------|
| SPY | Collecting | ~1.0M | 2020-2025 |
| QQQ | Collecting | ~1.0M | 2020-2025 |
| IWM | Collecting | ~1.0M | 2020-2025 |

**Total**: ~3.1M contracts across 1,554 trading days (5 years)

**Next**: Expand to 15 tickers (AAPL, MSFT, TSLA, VTI, DIA, TLT, IEF, LQD, GLD, SLV, VXX, IYR)

---

## GEX Calculation Pipeline

After data collection completes, populate `options_daily_summary`:

```python
from scripts.research.gex.gex_calculator import GEXCalculator

calculator = GEXCalculator(db_path=".cache/gex_research.db")

# Calculate GEX for all collected dates
for symbol in ['SPY', 'QQQ', 'IWM']:
    calculator.calculate_historical_gex(
        symbol=symbol,
        start_date="2020-01-01",
        end_date="2025-12-16"
    )
```

This will:

1. Read options_chains for each date
2. Calculate total GEX (Σ gamma × OI × 100 × spot²)
3. Find zero-gamma level
4. Classify regime (POSITIVE/NEGATIVE/NEUTRAL)
5. Store in options_daily_summary

---

## Cross-Project Benefits

This approach enables:

1. **gex-llm-patterns (Paper 3)**: LLM pattern validation research
2. **AutoTrader**: Multi-asset regime correlation (#496-#500)
3. **Shared infrastructure**: One collection, multiple uses
4. **Data quality**: Both projects validate from same source

---

## Next Steps

1. **Wait for C-chat** to complete SPY/QQQ/IWM collection (~5 min)
2. **Expand collection** to 15 tickers (~23 additional minutes)
3. **Symlink database** using `link_gex_database.py --mode symlink`
4. **Calculate GEX** to populate options_daily_summary
5. **Begin research** on issues #496-#500

---

## References

- gex-llm-patterns: `src/cache/sqlite_options_manager.py` (schema definition)
- AutoTrader: `scripts/research/gex/gex_calculator.py` (GEX calculation)
- Collection script: gex-llm-patterns `scripts/data_collection/start_historical_collection.py`
