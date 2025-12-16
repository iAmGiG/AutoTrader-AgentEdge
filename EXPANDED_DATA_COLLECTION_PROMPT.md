# Expanded Historical Options Data Collection

**Status**: After SQLite migration is complete, expand collection scope
**Purpose**: Build comprehensive multi-asset options database for regime research
**API Capacity**: Premium Alpha Vantage (1000 calls/min) - plenty of headroom

## Rationale

The initial SQLite migration will collect SPY/QQQ/IWM (3 symbols, ~4,662 calls). With the premium API tier having 1000 calls/min capacity and the historical_collector already built, we can expand to additional asset classes without significantly impacting collection time.

This enables research across:

- Tech-heavy equities (already have)
- Broad market proxies
- Bond ETFs (volatility regime correlation)
- Precious metals (alternative assets)
- Sector rotation studies

## Expanded Ticker List

### Equities (Tech + Broad Market) - 8 tickers

- **SPY** (S&P 500 - broad market)
- **QQQ** (Nasdaq 100 - tech heavy)
- **IWM** (Russell 2000 - small cap)
- **AAPL** (Apple - mega cap tech)
- **MSFT** (Microsoft - mega cap tech)
- **TSLA** (Tesla - volatile growth)
- **VTI** (Vanguard Total Stock - entire market)
- **DIA** (Dow Jones - large cap)

### Bond ETFs - 3 tickers

- **TLT** (iShares 20+ Year Treasury - long duration)
- **IEF** (iShares 7-10 Year Treasury - intermediate)
- **LQD** (iShares Investment Grade Corporate - credit)

### Commodities/Precious Metals - 2 tickers

- **GLD** (SPDR Gold - precious metals)
- **SLV** (iShares Silver - precious metals)

### Volatility - 1 ticker

- **VXX** (iPath S&P 500 VIX Short-Term Futures - volatility)

### Real Estate - 1 ticker

- **IYR** (iShares U.S. Real Estate - sector)

### Summary

Total: 15 tickers across 4 asset classes

## Collection Parameters

### Time Horizons

- **Primary**: 2020-01-01 to today (~5 years)
- **Optional Extended**: 2018-01-01 to today (~7 years) if API quota allows

### Estimated API Calls

| Scenario | Tickers | Years | Trading Days | API Calls | Premium Time | Notes |
|----------|---------|-------|--------------|-----------|--------------|-------|
| Base (SPY/QQQ/IWM) | 3 | 5 | 1,554 | 4,662 | ~5 min | Already planned |
| Expanded (15 tickers) | 15 | 5 | 1,554 | 23,310 | ~23 min | Recommended |
| Extended (15 tickers) | 15 | 7 | 2,180 | 32,700 | ~33 min | Nice-to-have |

### Collection Strategy

**Phase 1** (after SQLite migration):

```bash
python scripts/data_collection/start_historical_collection.py \
    --symbols SPY QQQ IWM AAPL MSFT TSLA VTI DIA TLT IEF LQD GLD SLV VXX IYR \
    --start-date 2020-01-01 \
    --end-date 2025-12-16 \
    --rate-limit 900
```

**Phase 2** (optional, if extended history needed):

```bash
python scripts/data_collection/start_historical_collection.py \
    --symbols SPY QQQ IWM AAPL MSFT TSLA VTI \
    --start-date 2018-01-01 \
    --end-date 2019-12-31 \
    --rate-limit 900
```

## Database Structure

Extend the SQLite schema to handle the expanded dataset:

```sql
-- Enhanced options_chains table
CREATE TABLE options_chains (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    asset_class TEXT,  -- 'equity', 'bond', 'commodity', 'volatility'
    date TEXT NOT NULL,
    strike REAL NOT NULL,
    expiration TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'call', 'put'
    bid REAL, ask REAL, last REAL,
    volume INTEGER, open_interest INTEGER,
    delta REAL, gamma REAL, theta REAL, vega REAL,
    implied_volatility REAL,
    created_at TIMESTAMP,
    UNIQUE(symbol, date, strike, expiration, type)
);

-- Daily summary with asset class
CREATE TABLE options_daily_summary (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    asset_class TEXT,
    date TEXT NOT NULL,
    total_gex REAL,
    call_gex REAL, put_gex REAL,
    zero_gamma_level REAL,
    regime TEXT,
    UNIQUE(symbol, date)
);
```

## Research Applications

### Regime Correlation Studies

- How does bond volatility (TLT GEX) correlate with equity volatility (SPY GEX)?
- Do commodities (GLD/SLV) show leading indicators for risk regimes?

### Asset Class Rotation

- When SPY is in negative gamma, are bonds in positive gamma?
- Hedge correlation: equities down, bonds up?

### Volatility Regime Classification

- VXX GEX regime vs SPY/QQQ regime alignment
- Cross-asset volatility propagation

### Sector Rotation

- Compare sector ETF (IYR) GEX with broad market (SPY)
- Small cap (IWM) vs large cap (DIA) regime differences

### Multi-Asset Momentum

- TSMOM performance correlation across asset classes
- Do bonds show different TSMOM patterns than equities?

## Success Criteria

- [ ] SQLite database extended to 15 tickers
- [ ] All ~23K API calls completed successfully
- [ ] ~11.6M+ options contracts stored across all tickers
- [ ] Database size < 2GB (acceptable for research)
- [ ] Query performance maintained (<1s for symbol/date lookups)
- [ ] GEX calculated for all tickers/dates
- [ ] Regime classification complete
- [ ] Summary statistics generated per asset class
- [ ] Ready for cross-asset regime correlation analysis

## Implementation Notes

1. **Collection order**: Start with high-volume equities (SPY/QQQ), then bonds, commodities, volatility
2. **Error handling**: Some tickers may have limited historical options - gracefully skip missing data
3. **Data validation**: Ensure Greeks are reasonable (delta 0-1, gamma > 0, etc.)
4. **Resume capability**: If collection interrupted, can resume from last completed date
5. **Duplicate prevention**: UNIQUE constraint prevents re-storing existing data

## Next Steps After Collection

1. **Cross-asset correlation matrix** - GEX regimes across all tickers
2. **Regime synchronization analysis** - Which tickers move together?
3. **Hedge ratio optimization** - What beta for different regimes?
4. **Multi-asset TSMOM** - Does it work across equities/bonds/commodities?
5. **Volatility spillover** - Which asset class leads volatility regime changes?

## Cost Estimate

- Premium API: 1000 calls/min → 23K calls ÷ 900 calls/min = ~26 minutes runtime
- Storage: ~1.5-2GB SQLite database
- Computation: ~1-2 hours for full GEX/regime calculation
- **Total wall-clock time**: ~1 hour for full collection + analysis

## Authorization Note

This expanded collection uses the same premium Alpha Vantage API key already authorized for gex-llm-patterns research. The extended scope (15 tickers vs 3) is still within fair usage limits for research purposes.
