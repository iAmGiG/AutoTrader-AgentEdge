# AutoGen Project Restructure Plan

## ✅ COMPLETED RESTRUCTURE

**Status**: AutoGen restructure completed successfully (September 8, 2025)

### Problems Solved:
- **✅ Mixed Legacy**: V0-V4 sentiment agents archived to `src/legacy/`
- **✅ Analysis Bloat**: Complex optimization tools moved to legacy
- **✅ Clear Separation**: Clean agent/tool/interface separation implemented
- **✅ Dead Code**: Obfuscation testing and unused code archived

## New Clean Structure

```
src/
├── autogen_agents/              # AutoGen-specific agents
│   ├── __init__.py
│   ├── scanner_agent.py         # Multi-ticker scanning (#304)
│   ├── voter_agent.py           # MACD+RSI voting decisions
│   ├── risk_agent.py            # Position/portfolio risk management (#306)  
│   ├── executor_agent.py        # Trade execution (paper/live)
│   └── orchestrator.py          # Agent coordination and human handoff
├── trading_tools/               # Pure functions for agents
│   ├── __init__.py
│   ├── indicators.py            # MACD(13/34/8), RSI calculations
│   ├── data_fetch.py            # Market data retrieval  
│   ├── position_tracker.py      # Position management utilities
│   ├── risk_calculator.py       # Portfolio risk metrics
│   └── broker_api.py            # Paper/live trade execution
├── human_interface/             # Human interaction components (#305, #308)
│   ├── __init__.py
│   ├── cli_interface.py         # CLI for trade decisions (#308)
│   ├── decision_formatter.py    # Format signals for human review
│   └── web_interface.py         # Future: web dashboard integration
├── data_sources/                # Keep essential data tools (RENAMED from src/data/)
│   ├── market/                  # Market data APIs (keep)
│   └── cache/                   # Caching system (keep)
└── legacy/                      # Archive old code
    ├── v0_v4_sentiment/         # V0-V4 sentiment agents
    ├── analysis/                # Complex optimization tools
    ├── validation/              # Obfuscation testing
    └── deprecated_strategies/   # Old voting strategies
```

## What Gets Moved to Legacy

### `legacy/v0_v4_sentiment/`
- All V0-V4 sentiment agents (complexity traps)
- `src/core/agents/` (old sentiment agents)
- `src/deprecated/` (already deprecated)

### `legacy/analysis/`  
- `src/analysis/optimization/` (we chose parameters, use config system)
- `src/analysis/metrics_analyzer.py` (V0-V4 research tool)
- Complex performance analysis (keep simple metrics only)

### `legacy/validation/`
- `src/validation/obfuscation_validator.py` (LLM testing, not needed for human-in-loop)
- V4 date obfuscation testing (irrelevant)

### `legacy/deprecated_strategies/`
- `src/core/strategies/` (old voting implementations)
- Complex strategy frameworks (use simple MACD+RSI)

## What Gets Kept and Refactored

### `trading_tools/` (Pure Functions)
**FROM**: `src/core/indicators/`
- Clean MACD(13/34/8) calculation
- RSI(14/30/70) calculation  
- Remove complex indicator variations

**FROM**: `src/data/sources/market/`
- Market data fetching (Polygon, Alpha Vantage)
- Cache management
- Clean up to essential functions only

### `data_sources/` (Renamed from src/data/)
- Keep market data APIs
- Keep caching system
- Remove news processing (not needed for MACD+RSI)

## New AutoGen Agent Architecture

### `scanner_agent.py` (Issue #304)
```python
class ScannerAgent:
    """Multi-ticker scanning with MACD+RSI voting"""
    def scan_tickers(self, ticker_list) -> List[Signal]
    def calculate_confidence(self, macd_data, rsi_data) -> float
    def generate_alert(self, signal) -> Alert
```

### `voter_agent.py` (Issue #293 validated)  
```python
class VoterAgent:
    """MACD+RSI voting decisions"""
    def evaluate_signal(self, market_data) -> VotingResult
    def check_consensus(self, macd_signal, rsi_signal) -> bool
    def calculate_entry_price(self, signal) -> float
```

### `risk_agent.py` (Issue #306)
```python  
class RiskAgent:
    """Position and portfolio risk management"""
    def track_positions(self) -> List[Position]
    def check_exit_conditions(self, position) -> ExitRecommendation  
    def calculate_portfolio_risk(self) -> RiskMetrics
```

### `orchestrator.py` (Issues #305, #308)
```python
class TradingOrchestrator:
    """Coordinate agents and human handoff"""  
    def coordinate_scan_and_vote(self) -> Decision
    def handoff_to_human(self, decision) -> HumanResponse
    def execute_approved_trade(self, approval) -> TradeResult
```

## Implementation Steps

1. **✅ Create New Structure** - Set up autogen_agents/, trading_tools/, human_interface/
2. **✅ Move Legacy Code** - Archive V0-V4, analysis, validation to legacy/  
3. **✅ Extract Pure Functions** - Move calculations to trading_tools/
4. **✅ Create AutoGen Agents** - Implement scanner, voter, risk, executor agents
5. **✅ Build Orchestrator** - Multi-agent coordination with human handoff
6. **🔄 Update Configuration** - Extend config system for agents (in progress)
7. **🔄 Clean Up Imports** - Fix all references after restructure (next)

## Benefits
- **Clean Separation**: Agents vs tools vs human interface
- **AutoGen Ready**: Native multi-agent conversations
- **Maintainable**: Legacy code archived, new code organized  
- **Testable**: Pure functions easy to unit test
- **Focused**: Only code needed for validated MACD+RSI system

## Related Issues
- #307 - This restructure implementation  
- #304 - Scanner agent
- #305 - Human decision interface
- #306 - Position management  
- #308 - CLI interface
- #303 - Configuration system extension