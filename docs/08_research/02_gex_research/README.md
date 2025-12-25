# GEX Research Documentation

**Research Track**: Paper 3 - Options Flow Analysis
**Issue**: #394
**Status**: 🛑 STOP - Hypothesis Invalidated (Dec 2025)
**Date Range**: 2024-2025 (out-of-sample testing)

---

## Research Status Update (Dec 2025)

> **⚠️ IMPORTANT**: Later research (#516, #518, #519) invalidated the GEX-as-filter hypothesis.
> See [../README.md](../README.md) for the consolidated research summary.

| Finding | Status | Evidence |
| ------- | ------ | -------- |
| GEX regime filtering improves TSMOM | 🛑 STOP | #516: Median improvement -2.9% (worse) |
| GEX-only strategy viable | 🛑 STOP | Inconsistent methodology across scripts |
| Hybrid GEX+Technicals | 🛑 STOP | Underperforms pure strategies |

**Why the contradiction?** The early results below (5/6 wins) used different methodology than later rigorous testing:

- Early tests: Limited look-ahead protection, inconsistent cost modeling
- Later tests (#516-#519): Proper `shift(1)`, turnover-proportional costs, EPSILON protection

**Preserved below** for historical reference and methodology learnings.

---

## Important Caveat: Practitioner Use Case Not Tested

> **⚠️ FAIRNESS NOTE**: The tests that invalidated GEX (#516-#519) tested **swing trading** (Close→Close+1 overnight holds). Practitioners who use GEX for a living typically use it for **day trading** (Open→Close intraday). These are fundamentally different use cases.

### What Practitioners Actually Claim

| Aspect | Practitioner Approach | What We Tested |
| ------ | --------------------- | -------------- |
| **Timeframe** | Intraday (Open→Close) | Swing (Close→Close+1) |
| **Holding Period** | Minutes to hours | Overnight |
| **Signal Use** | S/R levels, volatility forecast | Binary regime filter |
| **GEX Application** | "Fade the open" / "follow momentum" | Static position sizing |
| **Primary Edge** | Volatility prediction | Directional prediction |

### What Our Research Actually Proved

| Use Case | Status | Notes |
| -------- | ------ | ----- |
| GEX as overnight swing filter | 🛑 STOP | Tested and invalidated (#516) |
| GEX + TSMOM hybrid (daily bars) | 🛑 STOP | Median -2.9% worse than pure TSMOM |
| GEX for intraday mean reversion | ❓ **UNTESTED** | Practitioners' primary use case |
| Gamma walls as S/R levels | ❓ **UNTESTED** | Common practitioner technique |
| GEX for volatility sizing | ❓ **UNTESTED** | Straddle sizing, not direction |

### Why This Matters

Practitioners argue that dealer hedging flows happen **during the trading day** as price moves toward gamma concentrations. The mechanism doesn't support overnight holding because:

1. **Dealer rebalancing is intraday** - They delta-hedge throughout the session
2. **Gamma walls are dynamic** - They shift with price and OI changes
3. **The edge is in volatility, not direction** - High gamma = low vol, low gamma = high vol

**Conclusion**: Our "GEX doesn't work" finding applies specifically to swing/position trading. The intraday practitioner use case remains **neither validated nor invalidated** by this research.

---

## Methodology Post-Mortem (Dec 2025)

### Why the Early Tests Were Unrealistic

The "5/6 wins" results should be treated as a guide for **what not to do**:

#### 1. Look-Ahead Bias (Fatal Flaw)

The early tests had "limited look-ahead protection" - using `Close(t)` to execute at `Close(t)`. In reality, you cannot buy at the closing price using a signal calculated from that same closing price.

- **Early tests**: Signal from `Close(t)` → Execute at `Close(t)` ❌
- **Later tests (#516)**: Signal from `Close(t)` → Execute at `Close(t+1)` via `shift(1)` ✅
- **Result**: When proper execution lag was applied, the edge disappeared

#### 2. Transaction Cost Underestimation

| Strategy | Trades/Year | Cost Impact |
| -------- | ----------- | ----------- |
| Technicals (MACD+RSI) | 23-38 | Moderate |
| GEX-Only | 33-137 | **High** - spread/slippage destroys small edge |

A strategy with a small edge and high turnover is often unprofitable in practice.

#### 3. Sample Size (n=6)

Testing on 6 symbols is statistically anecdotal. The "100% win rate" claims are highly suspect even without the look-ahead bias.

### Mathematical Research Gaps

#### 1. Stationarity & Normalization

**The Gap**: Raw GEX values (`Total Gamma * Open Interest`) are not stationary. As markets rise, spot prices and OI grow. A "High GEX" in 2020 might be "Low GEX" in 2025 due to market inflation.

**What Was Tried**: S² scaling (#502) - failed.

**Missing Math**: Rolling Z-Scores or Percentile Ranks over trailing window (e.g., 252 days). This would define "High Gamma" relative to recent past, not absolute numbers.

```python
# What should have been tested
gex_zscore = (gex - gex.rolling(252).mean()) / gex.rolling(252).std()
signal = gex_zscore > 1.5  # High relative to recent history
```

#### 2. Scalar Reduction of a Curve

**The Gap**: "Total GEX" reduces the entire options chain (thousands of strikes) to a single number.

**What's Lost**: Gamma distribution matters. Concentrated gamma near spot behaves differently than widely spread gamma, even with identical "Total GEX" sums.

**Missing Math**: Gamma Kurtosis or Skew analysis could provide better signals.

#### 3. Binary Regime Classification

**The Gap**: Strategy treats regimes as binary (Positive vs Negative).

**Reality**: Dealer hedging impact is continuous. "Slightly negative" gamma is very different from "deeply negative."

**Missing Math**: Model as continuous variable or probability function, not binary switch.

### If Future Research Were Attempted

These tests would need to be done **before** revisiting GEX strategies:

#### 1. Fix the Math: Rolling Z-Score Normalization

Raw GEX (`Gamma * OI * Spot`) naturally doubles as S&P rises from 3000→6000. A threshold defined in 2020 is meaningless in 2025.

```python
def calculate_gex_zscore(df, window=252):
    """
    Normalize GEX relative to its own history (1 trading year).
    Fixes market inflation affecting signals.
    """
    rolling_mean = df['total_gex'].rolling(window=window).mean()
    rolling_std = df['total_gex'].rolling(window=window).std()

    # Z-Score: how many std devs from rolling mean
    df['gex_zscore'] = (df['total_gex'] - rolling_mean) / rolling_std
    return df

# Usage in strategy:
# Instead of: if total_gex > 0:
# Use: if gex_zscore > 1.5:  # High gamma relative to recent history
```

#### 2. Test Intraday Execution (Day Trade Angle)

Since `Close(t)` → `Close(t+1)` swing strategy failed, test intraday predictive power:

```python
# Hypothesis: Dealers hedge primarily during the day
# Test: Calculate GEX from yesterday's close
#       Enter at Market Open, Exit at Market Close

# If GEX highly positive → dealers suppress volatility intraday
#   → Expect mean reversion (fade the open)
# If GEX negative → dealers amplify moves
#   → Expect trend expansion (follow the open)

signal = "FADE" if gex_zscore > 1.5 else "FOLLOW" if gex_zscore < -1.5 else "NEUTRAL"
entry_price = df['open']
exit_price = df['close']
```

#### 3. Distance to Gamma Flip (Continuous Signal)

Instead of binary positive/negative, use distance to Zero Gamma Level:

```python
def calculate_gamma_flip_distance(df):
    """
    Continuous signal based on proximity to regime change.
    Zero Gamma Level is already in database.
    """
    # Normalized distance to flip level
    df['flip_distance'] = (df['close'] - df['zero_gamma_level']) / df['close']

    # As price approaches flip level, volatility increases
    # Far above flip → stability (dealers long gamma, suppress moves)
    # Near flip → instability (dealers hedging direction uncertain)
    # Far below flip → volatility (dealers short gamma, amplify moves)

    return df

# Usage: fade moves when flip_distance > 0.05
#        follow moves when flip_distance < -0.05
#        reduce size when abs(flip_distance) < 0.02 (near flip = uncertain)
```

#### 4. Gamma Concentration (Beyond Total GEX)

Total GEX loses the "lines" - where gamma is concentrated matters:

```python
def calculate_gamma_walls(chain_df, spot_price, threshold_pct=0.10):
    """
    Identify strikes with concentrated gamma (>10% of total).
    Market with gamma at 5500 and 5600 behaves differently
    than gamma spread evenly, even with same "Total GEX".
    """
    total_gamma = chain_df['gamma'].abs().sum()
    chain_df['gamma_pct'] = chain_df['gamma'].abs() / total_gamma

    walls = chain_df[chain_df['gamma_pct'] > threshold_pct][['strike', 'gamma_pct']]

    # Distance to nearest wall affects expected behavior
    nearest_wall = walls.iloc[(walls['strike'] - spot_price).abs().argmin()]
    distance_to_wall = (spot_price - nearest_wall['strike']) / spot_price

    return walls, distance_to_wall
```

**Summary**: All four fixes address real mathematical gaps. None were tested in the original research.

---

## Overview

This directory contains comprehensive research on using **Gamma Exposure (GEX)** signals for trading compared to traditional technical analysis (MACD + RSI).

## Research Question

**Does options flow data (GEX) provide alpha over conventional technical indicators?**

Specifically:

1. Does GEX-based signaling outperform MACD+RSI technical analysis?
2. Do GEX + Technicals (hybrid) beat either alone?
3. Which market conditions favor GEX vs technicals?

## Interactive Visualizer

### [GEX Regime Trace Comparator](../../../tools/gex-visualizer/index.html)

Interactive visualization tool demonstrating GEX methodology differences. See [gex_visualizer_guide.md](gex_visualizer_guide.md) for full documentation.

**Features**:

- Dual view: Normalized vs Absolute (S² scaled) GEX
- 21 historical snapshots (2020-2025)
- Media controls with keyboard shortcuts
- Price history sparkline
- Terminology glossary

**Location**: `tools/gex-visualizer/index.html`

---

## Key Documents

### 1. [gex_vs_technicals_results.md](gex_vs_technicals_results.md)

Primary results document with:

- Walk-forward backtest results for 6 symbols
- Performance metrics (Sharpe, returns, drawdown, win rate)
- Comparison tables and detailed symbol breakdowns
- Production recommendations

**Quick Summary**:

- GEX beats technicals in 5/6 tests (83% win rate)
- Average Sharpe improvement: +0.318 (+52% relative)
- TQQQ: +1.019 Sharpe (largest improvement)
- SPY: +0.714 Sharpe (strong performance on flagship ETF)

### 2. [statistical_analysis.md](statistical_analysis.md)

Rigorous statistical testing with:

- Paired t-tests for Sharpe significance
- Binomial tests for win rate
- Effect size analysis (Cohen's d)
- Bayesian interpretation
- Sample size limitations and recommendations

**Key Finding**: Medium effect size (d=0.705) but NOT statistically significant at p<0.05 due to small sample size (n=6). However, practical significance is strong.

### 3. [data_inventory.md](data_inventory.md)

GEX data sources and availability:

- Database location and schema
- Symbols available and date ranges
- Data quality metrics
- Update frequency and coverage

### 4. [gex_pipeline_architecture.md](gex_pipeline_architecture.md)

Technical architecture for GEX calculation:

- Daily GEX computation pipeline
- Regime classification logic
- Data flow from options chains to trading signals
- Scalability considerations

## Research Scripts

### Core Analysis

| Script | Purpose | Output |
| -------- | --------- | -------- |
| `scripts/research/gex_vs_technicals.py` | Walk-forward backtest comparison | YAML results + SQLite DB |
| `scripts/research/consolidate_gex_results.py` | Generate markdown report from results | Consolidated MD report |
| `scripts/research/analyze_gex_significance.py` | Statistical significance testing | Console report with p-values |

### Data Pipeline

| Script | Purpose | Output |
| -------- | --------- | -------- |
| `scripts/research/gex/batch_gex_calculator.py` | Batch GEX calculation | SQLite database |
| `scripts/research/gex/parallel_gex_calculator.py` | Parallel processing for speed | SQLite database |
| `scripts/research/gex/dask_gex_calculator.py` | Distributed computing version | SQLite database |

## Results Database

**Location**: `.cache/backtest_results.db`

**Schema**: `gex_vs_technicals` table

```sql
CREATE TABLE gex_vs_technicals (
    id INTEGER PRIMARY KEY,
    run_timestamp TEXT,
    symbol TEXT,
    train_period TEXT,
    test_period TEXT,
    tech_return REAL,
    tech_sharpe REAL,
    tech_max_dd REAL,
    tech_win_rate REAL,
    tech_trades INTEGER,
    gex_return REAL,
    gex_sharpe REAL,
    gex_max_dd REAL,
    gex_win_rate REAL,
    gex_trades INTEGER,
    hybrid_return REAL,
    hybrid_sharpe REAL,
    hybrid_max_dd REAL,
    hybrid_win_rate REAL,
    hybrid_trades INTEGER,
    winner TEXT,
    gex_improvement REAL
);
```

## Methodology

### Walk-Forward Design

- **Train Period**: 2020-2023 (parameter validation, not optimization)
- **Test Period**: 2024-2025 (out-of-sample)
- **Rationale**: Avoid overfitting by testing on recent unseen data

### Strategy Variants

1. **TECHNICALS (MACD+RSI)**
   - MACD: Fibonacci parameters (13/34/8)
   - RSI: 14-period, 30/70 thresholds
   - Voting: Both agree = strong signal, one signals = weak, disagree = hold
   - **Baseline**: Current VoterAgent approach (0.856 Sharpe validated on AAPL)

2. **GEX-ONLY**
   - Signal from gamma exposure regime transitions
   - POSITIVE gamma → bullish (dealers stabilize)
   - NEGATIVE gamma → bearish (dealers amplify)
   - NEUTRAL → hold
   - Trade on regime changes

3. **HYBRID (GEX+Technicals)**
   - GEX regime filters technical signals
   - Amplify technicals in favorable GEX regime
   - Dampen technicals in unfavorable regime
   - Goal: Best of both worlds

### Symbols Tested

| Symbol | Type | Liquidity | Options Activity |
| -------- | ------ | ----------- | ------------------ |
| SPY | S&P 500 Index | Very High | Very High |
| QQQ | Nasdaq-100 Index | Very High | Very High |
| IWM | Russell 2000 | High | High |
| TQQQ | 3x Nasdaq Bull | High | Medium |
| SOXL | 3x Semiconductor Bull | High | Medium |
| SQQQ | 3x Nasdaq Bear | Medium | Medium |

## Key Findings Summary

### Performance by Asset Class

**Index ETFs (SPY, QQQ, IWM)**:

- ✅ GEX wins all 3/3
- Average improvement: +0.336 Sharpe
- Most consistent gains

**3x Leveraged Bull (TQQQ, SOXL)**:

- ✅ GEX wins 2/2
- Average improvement: +0.528 Sharpe
- **Amplified advantage** - leverage magnifies GEX signals

**3x Leveraged Bear (SQQQ)**:

- ❌ GEX underperforms
- Improvement: -0.158 Sharpe
- Hybrid approach works better for inverse products

### Trade Characteristics

**Technicals (MACD+RSI)**:

- Trade frequency: 23-38 trades/year
- Win rate: 52-64%
- More selective entries

**GEX-Only**:

- Trade frequency: 33-137 trades/year
- Win rate: 26-62%
- More active, captures regime shifts
- Higher turnover but better risk-adjusted returns

**Hybrid**:

- Trade frequency: 3-11 trades/year
- Win rate: 0-100% (small sample!)
- Too few trades for reliable assessment

### Statistical Significance

**Formal Tests**:

- Paired t-test: p=0.1447 (NOT significant at α=0.05)
- Win rate: p=0.1094 (NOT significant)
- **Effect size**: d=0.705 (MEDIUM)

**Interpretation**:

- Small sample size (n=6) limits statistical power
- Practical significance is strong (large Sharpe improvements)
- Consistent directionality (5/6 wins)
- Recommend cautious deployment with monitoring

## Recommendations

### Production Deployment

#### ✅ RECOMMENDED for GEX-Only Strategy:

1. **SPY** - Flagship index, +0.714 Sharpe improvement
2. **TQQQ** - Leveraged, +1.019 Sharpe improvement (negative to positive!)
3. **QQQ** - Tech index, +0.124 Sharpe improvement
4. **IWM** - Small cap, +0.170 Sharpe improvement
5. **SOXL** - Semiconductors, +0.037 Sharpe improvement

**Deployment Approach**:

- Start with paper trading (60 days)
- Monitor real-time Sharpe vs benchmark
- Deploy to 10-20% of capital if validated
- Scale up gradually with circuit breakers

#### ❌ NOT RECOMMENDED:

1. **SQQQ** (or other inverse ETFs) - GEX underperforms, use hybrid or technicals
2. **Hybrid approach** - Doesn't consistently outperform pure GEX, adds complexity

### Future Research Priorities

#### High Priority

1. **Expand sample size** to 15+ symbols
   - Add: DIA, EFA, TLT, UPRO, SPXL, etc.
   - Goal: Achieve statistical significance with more data points

2. **Extended time period** - Test on 2023 data
   - Validate consistency across different market regimes
   - Check for regime-specific effects

3. **Real-time validation** - Paper trade for 90 days
   - Confirm backtest results hold in live market
   - Test execution costs and slippage

#### Medium Priority

1. **Regime-specific analysis**
   - High vs low volatility performance
   - Bull vs bear market comparison
   - Earnings season impact

2. **GEX parameter optimization**
   - Optimal regime transition thresholds
   - Signal smoothing techniques
   - Confirmation requirements

#### Lower Priority

1. **Transaction cost analysis**
   - Model bid-ask spreads
   - Commission impact on returns
   - Optimal position sizing given costs

2. **Multi-asset portfolio**
   - Diversification benefits
   - Correlation structure
   - Portfolio-level risk management

## Data Sources

### GEX Database

**Location**: `.cache/gex_research.db`

**Table**: `options_daily_summary`

**Columns**:

- `symbol`: ETF ticker
- `trading_date`: Date of observation
- `regime`: POSITIVE, NEGATIVE, NEUTRAL, UNKNOWN
- `underlying_price`: ETF price
- `total_gex`: Total gamma exposure
- `net_call_gex`: Call gamma exposure
- `net_put_gex`: Put gamma exposure
- `asset_class`: Classification

**Coverage**:

- Symbols: SPY, QQQ, IWM, TQQQ, SQQQ, SOXL
- Date range: 2020-01-02 to 2025-12-16
- Rows: ~1,500 per symbol

### Results Storage

**YAML Files**: `docs/08_research/02_gex_research/results/*.yaml`

- Human-readable results
- Easy to version control
- One file per symbol

**SQLite Database**: `.cache/backtest_results.db`

- Persistent storage
- Query-friendly
- Timestamped runs for comparison

## Limitations and Caveats

### Sample Size

- Only 6 symbols tested
- Limits statistical significance
- Some symbols correlated (QQQ, TQQQ, SQQQ all Nasdaq-linked)

### Time Period

- Single out-of-sample period (2024-2025)
- May be regime-specific
- Bull market bias in recent data

### Data Quality

- GEX data availability varies by symbol
- Options liquidity affects GEX calculation reliability
- Real-time GEX may differ from end-of-day calculations

### Implementation Risks

- Backtest doesn't include transaction costs
- Slippage not modeled
- Assumes perfect execution
- No consideration of liquidity constraints

### Generalization

- Results specific to tested ETFs
- May not apply to individual stocks
- Options market structure matters

## Conclusion

**GEX signals show strong practical advantages over technical indicators**, especially on:

- Index ETFs (SPY, QQQ, IWM)
- Leveraged bull products (TQQQ, SOXL)
- Recent market conditions (2024-2025)

**Statistical significance is limited** due to small sample size (n=6), but:

- Effect size is medium (d=0.705)
- Directionality is consistent (5/6 wins)
- Magnitude of improvements is economically meaningful

**Recommendation**:

1. Proceed to paper trading phase on SPY and TQQQ
2. Expand research to 15+ symbols for statistical validation
3. Monitor real-time performance for 60-90 days
4. Deploy cautiously with circuit breakers if validated

**Next Steps**: Paper 3 Implementation Plan (to be created) will detail deployment roadmap.

---

**Research Status**: ✅ Phase 1 Complete (Walk-forward testing)
**Next Phase**: Paper trading validation (60 days)
**Target Production**: Q1 2026 (conditional on validation)
