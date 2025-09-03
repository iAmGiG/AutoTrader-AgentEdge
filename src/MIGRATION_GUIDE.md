# Migration Guide: V0-V4 → Multi-Indicator Voting System

**Purpose**: Guide for transitioning from single MACD system to 90% accuracy ensemble  
**Timeline**: 4-week implementation (Issues #250, #277-289)  
**Status**: Ready to begin development

## Overview: What's Changing

### From Single Strategy → Ensemble Voting
- **Old**: Single MACD with V0-V4 sentiment overlay (~60% accuracy)
- **New**: Multi-indicator ensemble with voting mechanism (90% target accuracy)

### From Academic Research → Production Trading
- **Old**: Built for papers and backtesting
- **New**: Production-ready with order management and risk controls

## Folder Structure Migration

### What's Being Deprecated (Reference Only)
```
src/deprecated/
├── README.md                    # Why we moved on + performance baseline
└── v0_v4_original_system/       # Original files (DO NOT MODIFY)
```

### New Structure (Progressive Development)
```
src/
├── voting/          # NEW: Core ensemble voting system (#250) - CREATED
├── agents/          # ENHANCED: V0-V4 become voting members - EXISTING
├── tools/           # KEEP: Data sources, cache, news governor - EXISTING
├── utils/           # KEEP: Existing utilities - EXISTING
├── analysis/        # ENHANCED: Extend for ensemble metrics - EXISTING
└── deprecated/      # REFERENCE: V0-V4 system preserved

# CREATE AS NEEDED (Don't pre-create empty directories):
# src/indicators/    # When implementing #277 (RSI)
# src/regime/        # When implementing #284 (market regime)  
# src/execution/     # When implementing #287 (order management)
# src/integration/   # When implementing #258 (Alpaca API)
```

## Phase-by-Phase Migration

### Phase 1A: Core Voting System (Week 1)

#### Step 1: Implement Base Voting Architecture (#250)
```python
# NEW FILE: src/voting/base_voting_strategy.py
class BaseVotingStrategy:
    def collect_signals(self) -> Dict[str, float]:
        """Collect signals from all indicators"""
        
    def make_decision(self, signals: Dict) -> VotingDecision:
        """Simple majority voting (3/5 indicators)"""
```

#### Step 2: Add RSI Indicator (#277)  
```python
# NEW FILE: src/indicators/rsi_indicator.py
class RSIIndicator(BaseIndicator):
    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """14-period RSI calculation"""
        
    def generate_signal(self, rsi_value: float) -> float:
        """<30 = buy signal, >70 = sell signal"""
```

#### Step 3: Keep V0-V4 as Voting Members
```python
# ENHANCED: src/agents/voting_coordinator.py  
class VotingCoordinator:
    def __init__(self):
        self.indicators = [MACD(), RSI(), BollingerBands(), Volume()]
        self.sentiment_agents = [V0(), V1(), V2(), V3(), V4()]
        
    def coordinate_vote(self) -> TradingDecision:
        """Combine technical indicators + sentiment agents"""
```

### Phase 1B: Weighted Intelligence (Week 2)

#### Upgrade to Confidence Voting (#281)
```python
# NEW FILE: src/voting/weighted_voter.py
class WeightedVoter(BaseVotingStrategy):
    def calculate_confidence(self, signals: Dict) -> float:
        """0-1 confidence score for position sizing"""
        
    def weighted_decision(self, signals: Dict) -> WeightedDecision:
        """Research target: Sharpe 0.71 → 1.43"""
```

### Phase 2: Market Intelligence (Week 3)

#### Add Regime Detection (#284)
```python
# NEW FILE: src/regime/regime_detector.py
class RegimeDetector:
    def detect_regime(self, market_data: pd.DataFrame) -> MarketRegime:
        """Bull/Bear/Sideways using 50/200 SMA + volatility"""
        
    def adapt_strategy(self, regime: MarketRegime) -> Dict:
        """Regime-specific indicator weights"""
```

### Phase 3: Production Ready (Week 4)

#### Order Management (#287)
```python  
# NEW FILE: src/execution/order_manager.py
class OrderManager:
    def place_gtc_order(self, decision: VotingDecision) -> Order:
        """Daily GTC orders based on voting confidence"""
        
    def manage_positions(self) -> Dict:
        """Track and reconcile positions"""
```

## Code Migration Strategy

### What to Keep (DON'T Change)
1. **Cache System** - 90% performance improvement preserved
2. **Data Sources** - Market data, news tools work unchanged  
3. **Advanced Metrics** - Extend for ensemble tracking
4. **V0-V4 Logic** - Becomes voting ensemble members

### What to Replace (NEW Implementation)
1. **Single MACD Strategy** → Multi-indicator ensemble
2. **Fixed Position Sizing** → Confidence-weighted sizing
3. **Static Parameters** → Regime-adaptive behavior
4. **Sequential Processing** → Parallel voting

### Integration Points

#### With Existing Cache System
```python
# All new indicators use existing cache
from src.tools.cache.unified_cache import UnifiedCacheManager

class RSIIndicator:
    def __init__(self):
        self.cache = UnifiedCacheManager()  # Keep existing optimization!
```

#### With V0-V4 Agents  
```python
# V0-V4 become ensemble voting members
class VotingEnsemble:
    def __init__(self):
        self.technical_indicators = [MACD(), RSI(), Bollinger(), Volume()]
        self.sentiment_agents = [V0(), V1(), V2(), V3(), V4()]  # Keep all!
        
    def collect_all_votes(self) -> EnsembleDecision:
        """9 total voting members: 4 technical + 5 sentiment"""
```

## Testing Strategy

### Parallel Testing (Recommended)
1. **Keep old system running** - For comparison and fallback
2. **A/B test new components** - Individual indicators first
3. **Gradual ensemble build** - Add indicators one by one
4. **Performance comparison** - New vs old system metrics

### Validation Approach
```python
# Test individual components
def test_rsi_indicator():
    """Test RSI against known values"""
    
def test_voting_ensemble():  
    """Test ensemble vs individual indicators"""
    
def test_regime_detection():
    """Test bull/bear detection accuracy"""
```

## Performance Expectations

### Week 1 Targets
- **Basic ensemble operational** - Simple majority voting
- **Improved win rate** - RSI+MACD should show 15% improvement
- **Maintained speed** - Cache optimizations preserved

### Week 4 Targets  
- **90% accuracy ensemble** - Research-backed target
- **Sharpe ratio >1.0** - Significant improvement over ~0.8
- **Production ready** - Order management, risk controls

### Fallback Plan
- **Old system remains** - Available in src/deprecated/ 
- **Gradual migration** - Can revert individual components
- **Performance monitoring** - Continuous comparison

## Success Metrics

### Technical Milestones
- [ ] Week 1: Basic voting system operational (Issues #250, #277-280)
- [ ] Week 2: Weighted confidence improves Sharpe ratio (Issues #281-283)  
- [ ] Week 3: Market regime adaptation reduces drawdown (Issues #284-286)
- [ ] Week 4: Production-ready with order management (Issues #287-289)

### Performance Validation
- [ ] Ensemble accuracy >70% (target 90%)
- [ ] Individual indicator tracking functional  
- [ ] Regime detection reduces drawdown
- [ ] Order management ready for paper trading

## Next Actions

1. **Start with Issue #250** - Base voting architecture
2. **Implement RSI (#277)** - First additional indicator
3. **Parallel Bollinger/Volume** - Build ensemble incrementally
4. **Continuous testing** - Compare new vs deprecated system
5. **Document everything** - Keep detailed performance logs

---

*This migration transforms RH2MAS from an academic research framework into a production-ready ensemble trading system while preserving all valuable existing components.*