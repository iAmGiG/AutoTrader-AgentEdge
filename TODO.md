# TODO: V0-V4 Sentiment Analysis Study

**Last Updated**: 2025-08-20  
**Status**: 🎯 READY FOR V1/V3/V4 COMPLETION

## 🎯 CURRENT MISSION: Complete V0-V4 Testing

**Research Objective**: Demonstrate the progressive value of LLM integration through **5-phase sentiment analysis comparison** (V0-V4) with consistent MACD trading strategy.

## ✅ CURRENT STATUS

### Completed Agents & Testing
- ✅ **V0**: +9.00% return, 24 trades (pure MACD baseline)
- ✅ **V2**: +2.33% return, 16 trades (VXX volatility market fear) 
- ✅ **Infrastructure**: Monthly news cache (49 files), smart sampling, unified architecture

### Architecture Complete
- ✅ **News Cache**: Monthly consolidation, 81.5% deduplication, date filtering
- ✅ **Tools**: Polygon.io + Alpha Vantage + Google Search + VXX + SPY/QQQ
- ✅ **Memory Queuing**: 30x API call reduction, quarterly batch preparation
- ✅ **Clean Architecture**: 4 core agents with proper tool separation

## 🚧 IMMEDIATE PRIORITIES

### 1. 📊 V1 Agent Re-run (NEXT)
- **Status**: Needs fresh run with clean monthly cache
- **Tools**: VADER + Google Search news with smart sampling
- **Expected**: Better results than previous contaminated cache run
- **Command**: Use flexible testing suite with weekly sampling

### 2. 🔗 V3 Heuristic Agent (Pending V1)
- **Status**: Ready for implementation after V1 completion  
- **Approach**: Adaptive weighting of V1 + V2 based on volatility regime
- **Logic**: Combine news sentiment + market fear signals intelligently

### 3. 🧠 V4 LLM Agent (Final Implementation)
- **Status**: Core logic ready, needs final implementation
- **Enhancement**: Consider hierarchical news system (Issue #208)
- **Features**: Market psychology, contrarian signals, multi-factor analysis
- **Key**: Only agent using LLM for decision-making

### 4. 📈 Quarterly Testing Framework
- **Status**: Ready for deployment across 2024 quarters
- **Scope**: V0-V4 comparison with statistical significance testing
- **Output**: Performance metrics, Sharpe ratios, academic documentation

## 🎯 V4 LLM Context Recognition (Documented Limitation)

**Known Issue**: V4 can potentially recognize companies from headlines (e.g., "Apple", "iPhone")

**Why Acceptable**:
- Realistic scenario - real traders know what they're trading
- Stateless API calls - recognition is probabilistic, not deterministic  
- Title-only analysis limits context exploitation
- Noisy Google Search results add realistic variability

**Enhancement Path**: Issue #208 - Hierarchical adaptive news system with SPY/QQQ market context

## 🚀 DEVELOPMENT COMMANDS

```bash
# Test V1 foundation
python -c "from src.tools.processors.sentiment_analyzer import SentimentAnalyzer; sa = SentimentAnalyzer(); print('✅ VADER ready:', sa.analyze_text('Bullish earnings beat expectations'))"

# Run V1 with clean cache (when ready)
python scripts/runs/simple_continuous_backtest.py --versions V1 --symbol AAPL

# V4 validation testing
python scripts/obfuscation_test.py

# Check monthly cache status
ls .cache/news_monthly/AAPL/
```

## 📊 SUCCESS METRICS

**Implementation Goals**:
- [ ] V1 re-run with clean monthly cache
- [ ] V3 heuristic combination operational  
- [ ] V4 LLM reasoning finalized
- [ ] Quarterly V0-V4 testing complete
- [ ] Statistical significance demonstrated
- [ ] Academic-quality research documentation

**Research Validation Target**:
- Clear performance progression V0→V4 documented
- Risk-adjusted returns comparison (Sharpe ratios)
- LLM value quantified and statistically significant

---

*Historical completed work archived in `deprecated/TODO_COMPLETED.md`*