# V0-V4 Testing Approach Summary

**Updated**: 2025-08-19  
**Status**: 🎯 Refocused on Continuous Year-Long Backtests

## 🚀 Current Approach: Simple Continuous Backtests with Checkpoints

### Simplified Implementation ✨ **NEW**
We now use **simple continuous backtesting** with checkpoint/resume functionality:
- **V0**: Jan 1 → Dec 31, 2024 (baseline, fixed sentiment = 1.0)
- **V1**: Jan 1 → Dec 31, 2024 (VADER + Google News sentiment)
- **V2**: Jan 1 → Dec 31, 2024 (VXX volatility market fear)
- **V3**: Jan 1 → Dec 31, 2024 (heuristic V1+V2 combination)
- **V4**: Jan 1 → Dec 31, 2024 (LLM intelligent reasoning)

### Key Features ✨ **NEW**
✅ **Portfolio Continuity**: Each starts with $10K and compounds throughout the year  
✅ **Checkpoint/Resume**: Can stop and restart at any point  
✅ **Version Isolation**: Each V0-V4 in separate folder with status tracking  
✅ **Multi-Year Support**: Easy to extend to 2025, 2026...  
✅ **Simple & Focused**: 350 lines vs 900+ lines (much cleaner)  

### Available Scripts ✨ **UPDATED**
- `scripts/runs/simple_continuous_backtest.py` - **NEW** simplified continuous testing
- `scripts/demo_continuous_backtest.py` - **NEW** demonstration of checkpoint features  
- `scripts/analyze_fragmented_vs_continuous.py` - Problem analysis (legacy)

## 🗑️ Deprecated: Fragmented Monthly Approach

### What Was Wrong
❌ **Monthly Restarts**: Each month started with fresh $10,000  
❌ **No Continuity**: Portfolio didn't carry forward between months  
❌ **Artificial Results**: 60 mini-backtests instead of 5 strategies  
❌ **Zero Returns**: All showed 0% due to fragmentation  

### Moved to Deprecated
- `reports/deprecated/fragmented_monthly_tests/` - All 60 fragmented results
- Includes 30 successful tests but with flawed approach
- Historical value for system validation, not performance analysis

## 📊 File Organization & Results Structure ✨ **NEW**

### Version-Specific Folder Structure
```
reports/continuous_backtests/
├── V0/
│   ├── AAPL_2024_checkpoint.json    # Complete state for resuming
│   ├── AAPL_2024_results.json       # Trading performance analysis
│   └── AAPL_2025_checkpoint.json    # Multi-year support
├── V1/
│   ├── AAPL_2024_checkpoint.json
│   └── AAPL_2024_results.json
├── V2/ ... V3/ ... V4/
```

### File Purpose & Content Differences ✨ **IMPORTANT**

**📄 Results File (`*_results.json`)** - Optimized for analysis:
- **Purpose**: Trading performance analysis and comparison
- **Trades Array**: Only actual buy/sell transactions (24 trades for V0)
- **Daily Values**: Truncated to final period only (saves space)
- **Contains**: Performance metrics, trade summary, final stats
- **Use Case**: Compare V0-V4 performance, generate reports

**💾 Checkpoint File (`*_checkpoint.json`)** - Complete state:
- **Purpose**: Resume long-running backtests without data loss
- **Trades Array**: Same as results (actual transactions)
- **Daily Values**: **Complete 252-day history** (every trading day)
- **Contains**: Full portfolio state, all daily valuations, sentiment scores
- **Use Case**: Resume interrupted tests, verify complete data coverage

**Key Insight**: Checkpoint files prove complete year coverage (Jan 2 → Dec 31, 2024 = 252 trading days)

### Continuous Year-Long Output
```
V0: +X.XX% total | $XX,XXX final | XX trades (baseline)
V1: +Y.YY% total | $YY,YYY final | YY trades (news sentiment)
V2: +Z.ZZ% total | $ZZ,ZZZ final | ZZ trades (volatility fear)
V3: +A.AA% total | $AA,AAA final | AA trades (combined heuristic)
V4: +B.BB% total | $BB,BBB final | BB trades (LLM reasoning)
```

### Performance Metrics
- **Total Return %**: True compound annual performance
- **Final Portfolio Value**: Ending cash + position value
- **Number of Trades**: Total buy/sell transactions
- **Win Rate**: Percentage of profitable trades
- **Average Trade Return**: Mean return per trade

## 🎯 Research Objective

**Core Question**: Does gradual LLM introduction (V0→V1→V2→V3→V4) provide measurable value in financial sentiment analysis?

**Expected Findings**:
- V0: Pure MACD baseline performance
- V1: News sentiment improvement over V0
- V2: Market fear awareness improvement
- V3: Combined heuristic benefits
- V4: LLM reasoning superiority (expected best performance)

## ⏱️ Execution Time Estimates

- **V0**: ~1 minute (no API calls)
- **V1**: ~30-60 minutes (Google News API)
- **V2**: ~10-15 minutes (VXX data only)
- **V3**: ~30-60 minutes (News + VXX)
- **V4**: ~60-90 minutes (News + VXX + LLM reasoning)

**Total**: ~2.5-4 hours for complete V0-V4 suite

---
*Focus: Meaningful continuous performance measurement for V0-V4 sentiment analysis research*