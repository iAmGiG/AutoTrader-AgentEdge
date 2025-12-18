# GEX Research Data Inventory

## Database Status (as of 2025-12-17)

| Metric | Value |
|--------|-------|
| **Total Records** | 50,876,306 |
| **Unique Symbols** | 34 |
| **Date Range** | 2020-01-02 to 2025-12-16 |
| **Underlying Price Fill** | 100% |
| **Database Location** | `.cache/gex_research.db` |
| **Source** | gex-llm-patterns Alpha Vantage collection |

## Asset Class Coverage

| Asset Class | Symbols | Total Records |
|-------------|---------|---------------|
| Equity | SPY, QQQ, IWM, TQQQ, SOXL, TSLA, AAPL, MSFT, DIA + leveraged ETFs | 42.9M |
| Volatility | UVXY, VXX | 2.6M |
| Commodity | GLD, SLV | 1.1M |
| Bond | TLT, IEF, LQD | 1.1M |
| Real Estate | IYR | 271K |

## Symbol Detail

| Symbol | Asset Class | Records | Date Range | Notes |
|--------|-------------|---------|------------|-------|
| SPY | equity | 13,722,202 | 2020-01-02 to 2025-12-15 | Primary benchmark |
| QQQ | equity | 10,636,646 | 2020-01-02 to 2025-12-15 | Tech/Nasdaq |
| IWM | equity | 6,840,344 | 2020-01-02 to 2025-12-16 | Small cap |
| TQQQ | equity | 2,373,122 | 2020-01-02 to 2025-12-16 | 3x Nasdaq |
| UVXY | volatility | 2,148,438 | 2020-01-02 to 2025-12-16 | 1.5x VIX |
| SOXL | equity | 2,023,984 | 2020-01-02 to 2025-12-16 | 3x Semiconductors |
| TSLA | equity | 1,718,072 | 2020-01-02 to 2020-12-04 | Individual stock |
| SQQQ | equity | 1,475,746 | 2020-01-02 to 2025-12-16 | 3x Inverse Nasdaq |
| SOXS | equity | 1,232,646 | 2020-01-02 to 2025-12-16 | 3x Inverse Semi |
| GLD | commodity | 832,380 | 2020-01-02 to 2020-12-03 | Gold |
| TECL | equity | 769,136 | 2020-01-02 to 2021-05-19 | 3x Tech |
| DIA | equity | 616,314 | 2020-01-02 to 2020-12-04 | Dow Jones |
| FAS | equity | 594,216 | 2020-01-02 to 2021-06-02 | 3x Financials |
| FAZ | equity | 583,931 | 2020-01-02 to 2021-05-24 | 3x Inverse Financials |
| AAPL | equity | 515,282 | 2020-01-02 to 2020-12-04 | Individual stock |
| NUGT | equity | 468,086 | 2020-01-02 to 2021-05-11 | 2x Gold Miners |
| LABU | equity | 451,009 | 2020-01-02 to 2021-05-19 | 3x Biotech |
| IEF | bond | 450,888 | 2020-01-02 to 2020-12-03 | 7-10yr Treasury |
| VXX | volatility | 434,980 | 2020-01-02 to 2020-12-03 | VIX Short-term |
| TLT | bond | 388,844 | 2020-01-02 to 2020-12-03 | 20+ yr Treasury |
| TECS | equity | 333,292 | 2020-01-02 to 2021-05-10 | 3x Inverse Tech |
| MSFT | equity | 303,704 | 2020-01-02 to 2020-12-04 | Individual stock |
| SLV | commodity | 285,584 | 2020-01-02 to 2020-12-03 | Silver |
| IYR | real_estate | 271,486 | 2020-01-02 to 2020-12-03 | Real Estate |
| LABD | equity | 270,896 | 2020-01-02 to 2021-05-14 | 3x Inverse Biotech |
| DUST | equity | 250,844 | 2020-01-02 to 2021-05-13 | 2x Inverse Gold Miners |
| LQD | bond | 243,350 | 2020-01-02 to 2020-12-03 | Investment Grade Corp |
| TZA | equity | 123,484 | 2020-01-02 to 2020-07-23 | 3x Inverse Small Cap |
| TNA | equity | 123,294 | 2020-01-02 to 2020-07-23 | 3x Small Cap |
| UPRO | equity | 112,628 | 2020-01-02 to 2020-07-22 | 3x S&P 500 |
| VTI | equity | 92,254 | 2020-01-02 to 2020-12-03 | Total Market |
| SPXU | equity | 71,966 | 2020-01-02 to 2020-07-23 | 3x Inverse S&P |
| SPXS | equity | 60,016 | 2020-01-03 to 2020-07-23 | 3x Inverse S&P |
| SPXL | equity | 57,242 | 2020-01-02 to 2020-07-23 | 3x S&P 500 |

## GEX Calculation Status

| Table | Records | Symbols | Status |
|-------|---------|---------|--------|
| options_chains | 50,876,306 | 34 | Complete |
| options_daily_summary | 17,835 | 34 | **COMPLETE** (#501) |

## Data Quality

- **Greeks available**: delta, gamma, theta, vega, rho, implied_volatility
- **Price fields**: bid, ask, last, mark, mid_price, underlying_price
- **Volume metrics**: volume, open_interest, vol_oi_ratio
- **Spread metrics**: bid_ask_spread, bid_ask_spread_pct
- **Quality score**: data_quality_score per record

## Research Readiness

### Completed Validation

- [x] SPY 2020-2021 GEX-volatility hypothesis (3.81x vol ratio, 10.1x extreme moves)

### Pipeline Architecture

See [gex_pipeline_architecture.md](gex_pipeline_architecture.md) for:

- Big data processing techniques (vectorized pandas, batch inserts)
- SQLite optimizations (WAL, mmap, cache)
- Configuration and usage

### Ready for Analysis

- [ ] Calculate GEX metrics for all 34 symbols (#501)
- [ ] Cross-asset regime correlation (#496)
- [ ] Volatility spillover analysis (#497)
- [ ] Multi-asset TSMOM comparison (#498)
- [ ] TSMOM vs GEX comparative analysis (#421)

## Data Gaps

1. **TSLA, AAPL, MSFT, DIA**: Only 2020 data (ends Dec 2020)
2. **GLD, SLV, TLT, IEF, LQD, IYR, VXX**: Only 2020 data
3. **Leveraged ETFs (TNA, TZA, UPRO, SPXU, SPXL, SPXS)**: Only Jan-Jul 2020

### Full 5-Year Coverage (2020-2025)

- SPY, QQQ, IWM, TQQQ, UVXY, SOXL, SQQQ, SOXS

These 8 symbols with full coverage are sufficient for cross-asset regime analysis.
