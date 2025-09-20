# Multi-Indicator Voting System Architecture

**Target**: Transform single MACD system to 90% accuracy ensemble  
**Implementation**: Issues #250, #277-289  
**Status**: Simplified Design - Create directories as needed

## Current Folder Structure (Minimal)

```bash
src/
├── voting/                           # NEW: Core voting system (Issue #250)
│   └── __init__.py                   # Ready for base_voting_strategy.py
│
├── agents/                           # EXISTING: Keep as voting members
│   ├── sentiment_v0.py               # V0-V4 agents become ensemble voters  
│   ├── sentiment_v1.py               # Enhanced for voting integration
│   ├── sentiment_v2.py               # Market fear → regime input
│   ├── sentiment_v3.py               # Heuristic ensemble member
│   ├── sentiment_v4.py               # LLM reasoning member
│   └── tech_agent.py                 # Enhanced for multi-indicator support
│
├── tools/                            # EXISTING: Keep all data sources
│   ├── data_sources/                 # Market data, news APIs
│   ├── cache/                        # Keep 90% performance optimizations!
│   └── news_governor.py              # Keep smart API sampling
│
├── utils/                            # EXISTING: Keep existing utilities
├── analysis/                         # EXISTING: Keep metrics system  
├── validation/                       # EXISTING: Keep V4 validation
└── deprecated/                       # REFERENCE: V0-V4 system docs
```

## Progressive Directory Creation Strategy

### Phase 1: Core Voting (Issue #250)

**Only create when implementing**:

```bash
src/voting/
├── base_voting_strategy.py          # Core voting interface
└── majority_voter.py                # Simple 3/5 majority voting
```

### Phase 2: Add Indicators (Issues #277-279)  

**Create when adding RSI/Bollinger/Volume**:

```bash
src/indicators/                       # Create when implementing #277
├── base_indicator.py                 # Common indicator interface
├── rsi_indicator.py                  # Issue #277
├── bollinger_indicator.py            # Issue #278  
└── volume_indicator.py               # Issue #279
```

### Phase 3: Advanced Features (Issues #281-289)

**Create directories as features are implemented**:

- `src/regime/` - When implementing market regime detection (#284)
- `src/execution/` - When implementing order management (#287)
- `src/analytics/` - When enhancing metrics for ensemble (#280)

### Phase 4: Production Integration (Issues #258-263)

**Create when ready for live trading**:

- `src/integration/` - Alpaca API, real-time pipeline
- `src/monitoring/` - Performance tracking, alerts

```bash

## Implementation Flow (Critical Path)

### Week 1: Foundation (Issues #250, #277-280)
```

1. src/voting/base_voting_strategy.py     # Core voting interface
2. src/indicators/rsi_indicator.py        # First additional indicator  
3. src/indicators/bollinger_indicator.py  # Second additional indicator
4. src/indicators/volume_indicator.py     # Third additional indicator
5. src/analytics/ensemble_metrics.py      # Track performance

```bash

### Week 2: Intelligence (Issues #281-283)
```

1. src/voting/weighted_voter.py           # Confidence-based decisions
2. src/utils/signal_strength.py           # Granular scoring
3. src/analytics/indicator_performance.py # Track individual accuracy

```bash

### Week 3: Adaptation (Issues #284-286)
```

1. src/regime/regime_detector.py          # Market regime detection
2. src/regime/regime_adapter.py           # Dynamic weight adjustment
3. src/timeframe/timeframe_manager.py     # Multi-timeframe confirmation

```bash

### Week 4: Production (Issues #287-289)
```

1. src/execution/order_manager.py         # GTC order system
2. src/execution/risk_manager.py          # Risk controls
3. src/analytics/performance_monitor.py   # Real-time monitoring

```bash

## Key Design Principles

### 1. Modular Architecture
- **Each indicator is independent** - can develop/test separately
- **Voting system is pluggable** - start simple, enhance incrementally
- **Regime detection is optional** - system works without it initially

### 2. Backward Compatibility
- **Keep V0-V4 agents** - they become voting ensemble members
- **Maintain cache system** - 90% performance improvement preserved
- **Existing tools unchanged** - data sources, news governor, etc.

### 3. Progressive Enhancement
- **Start with majority voting** - 3/5 indicators need to agree
- **Add confidence weighting** - better indicators get more influence
- **Add regime adaptation** - behavior changes with market conditions
- **Add production features** - order management, risk controls

### 4. Testing Strategy
- **Individual indicator testing** - Each indicator tested standalone
- **Ensemble backtesting** - Compare ensemble vs individual performance
- **A/B testing** - New system vs deprecated system comparison
- **Production validation** - Paper trading before live deployment

## Integration Points

### With Existing System
- **Cache Integration**: All indicators use existing cache framework
- **Data Pipeline**: Leverage existing market data and news tools
- **Metrics System**: Extend advanced metrics for ensemble tracking
- **V0-V4 Agents**: Become voting members in new architecture

### With New Production Features
- **Alpaca Integration**: Order manager connects to Alpaca API (#258)
- **Real-time Pipeline**: Voting system receives live market data (#259)
- **Strategy Orchestration**: Multiple voting strategies run simultaneously (#260)

## Success Metrics

### Technical Milestones
- **Week 1**: Basic ensemble voting operational (>3 indicators)
- **Week 2**: Weighted confidence system improves Sharpe ratio
- **Week 3**: Market regime adaptation reduces drawdown
- **Week 4**: Production-ready with order management

### Performance Targets (Research-Based)
- **Ensemble Accuracy**: 70-90% (vs current ~60% single MACD)
- **Sharpe Ratio**: >1.0 (research achieved 1.43 with weighting)
- **Max Drawdown**: <20% (research showed 32% reduction)
- **Individual Indicator Win Rate**: Track each indicator's contribution

## Next Steps

1. **Create folder structure** - Set up new directories
2. **Start with Issue #250** - Implement base voting architecture
3. **Add RSI (#277)** - First additional indicator for ensemble
4. **Parallel development** - Bollinger Bands (#278) and Volume (#279)
5. **Iterative enhancement** - Add features incrementally, test continuously

---

*This structure supports systematic development from single MACD to 90% accuracy ensemble while preserving valuable existing components.*
