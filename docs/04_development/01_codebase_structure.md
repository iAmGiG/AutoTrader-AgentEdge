# Codebase Structure

**Purpose**: Developer guide to file organization and component layout
**Last Updated**: November 2025
**Status**: Production VoterAgent with multi-agent framework in development

## Project Structure

```bash
AutoGen-TradingSystem/
├── src/                              # Core implementation
│   ├── autogen_agents/              # AutoGen multi-agent system
│   │   ├── base_agent.py            # Base AutoGen agent foundation
│   │   ├── voter_agent.py           # ✅ PRODUCTION (0.856 Sharpe)
│   │   ├── scanner_agent.py         # 🚧 In development
│   │   ├── risk_agent.py            # 🚧 In development
│   │   ├── executor_agent.py        # 🚧 In development
│   │   └── trading_orchestrator.py  # 🚧 In development
│   │
│   ├── trading/                     # Trading execution & lifecycle
│   │   ├── alpaca_trading_client.py # Alpaca API integration
│   │   ├── alpaca_autogen_tools.py  # AutoGen tool wrappers
│   │   ├── order_manager.py         # Order placement & tracking
│   │   ├── position_manager.py      # Position management
│   │   ├── trading_cycle.py         # Cost-efficient trade cycle
│   │   ├── market_scanner.py        # Market opportunity detection
│   │   ├── simple_signals.py        # Signal generation
│   │   └── unified_state_manager.py # State persistence
│   │
│   ├── trading_tools/               # Technical analysis (pure functions)
│   │   ├── indicators.py            # MACD & RSI calculations
│   │   ├── data_fetch.py            # Market data retrieval
│   │   └── risk_calculator.py       # Risk metrics
│   │
│   ├── data_sources/                # Data integration layer
│   │   ├── tools.py                 # Unified tool configuration
│   │   ├── cache/                   # Data caching system (>90% improvement)
│   │   │   ├── cache_adapter.py     # Cache router
│   │   │   ├── unified_cache.py     # Cache manager
│   │   │   └── market_data_cache.py # Market-specific caching
│   │   │
│   │   ├── sources/market/          # Market data providers
│   │   │   ├── alpaca_market_data.py      # Primary real-time data
│   │   │   ├── unified_market_tool.py     # Unified interface
│   │   │   ├── polygon_historical_tool.py # Polygon.io
│   │   │   └── alpha_vantage_market.py    # Fallback source
│   │   │
│   │   └── processors/              # Data processing
│   │       ├── data_normalizer.py   # Format standardization
│   │       └── sentiment_analyzer.py # News sentiment (deprecated)
│   │
│   ├── voting/                      # Voting strategy system
│   │   ├── base_voting_strategy.py  # Base voting framework
│   │   └── basic_voting_strategy.py # MACD+RSI voting logic
│   │
│   ├── core/indicators/             # Indicator library
│   │   ├── base_indicator.py        # Base indicator class
│   │   ├── simple_rsi.py            # RSI implementation
│   │   └── indicator_library.py     # Indicator collection
│   │
│   ├── human_interface/             # CLI & decision formatting
│   │   ├── cli_interface.py         # Command-line interface
│   │   └── decision_formatter.py    # Output formatting
│   │
│   └── utils/                       # Utility functions
│       ├── date_utils.py            # Date/time utilities
│       ├── agent_utils.py           # Agent helpers
│       └── output_manager.py        # Result organization
│
├── config/                          # API configuration (gitignored)
│   └── config.json                  # API keys and secrets
│
├── config_defaults/                 # Default configurations
│   ├── trading_config.py            # Trading parameters
│   └── *.yaml                       # YAML configs
│
├── scripts/                         # Utility scripts
│   ├── experiments/                 # Backtesting experiments
│   │   ├── experiment_293_validation/ # VoterAgent validation
│   │   └── configuration_system/      # Parameter testing
│   ├── analysis/                    # Results analysis
│   └── data/                        # Data collection
│
├── tests/                           # Test suite
│   ├── unit/                        # Unit tests
│   ├── tools/                       # Tool integration tests
│   ├── test_alpaca_basic.py         # Alpaca connection tests
│   ├── test_alpaca_market_data.py   # Market data tests
│   ├── test_alpaca_order_manager.py # Order management tests
│   └── test_alpaca_advanced_orders.py # Advanced order tests
│
├── docs/                            # Documentation
│   ├── 01_overview/                 # System overview
│   ├── 02_architecture/             # Technical design
│   ├── 03_reference/                # Reference docs
│   └── 04_development/              # Developer guides
│
├── state/                           # JSON state management
│   ├── positions.json               # Position tracking
│   └── orders.json                  # Order history
│
├── reports/                         # Generated reports
│   ├── active/voting_strategy/      # Current experiments
│   └── README.md                    # Reports index
│
├── main.py                          # Unified CLI entry point
├── pyproject.toml                   # Project configuration
├── requirements.txt                 # Python dependencies
└── README.md                        # Project overview
```

## Directory Responsibilities

### src/autogen_agents/ - AutoGen Multi-Agent System

**Purpose**: Microsoft AutoGen agent implementations for trading decisions

**Files**:

- `base_agent.py`: Foundation class extending AutoGen AssistantAgent
- `voter_agent.py`: Production MACD+RSI voting agent (0.856 Sharpe)
- `scanner_agent.py`: Market scanning (in development)
- `risk_agent.py`: Risk management (in development)
- `executor_agent.py`: Trade execution (in development)
- `trading_orchestrator.py`: Multi-agent coordination (in development)

### src/trading/ - Trading Operations

**Purpose**: Broker integration and trade lifecycle management

**Files**:

- `alpaca_trading_client.py`: Alpaca API integration (paper + live)
- `alpaca_autogen_tools.py`: AutoGen tool wrappers for agents
- `order_manager.py`: Order placement, modification, cancellation
- `position_manager.py`: Position tracking (broker as source of truth)
- `trading_cycle.py`: Cost-efficient daily routines
- `market_scanner.py`: Opportunity detection
- `simple_signals.py`: Signal generation helpers

### src/trading_tools/ - Pure Trading Functions

**Purpose**: Stateless calculations and utilities

**Files**:

- `indicators.py`: MACD, RSI, and voting logic calculations
- `data_fetch.py`: Market data retrieval utilities
- `risk_calculator.py`: Position sizing and risk metrics

### src/data_sources/ - Data Integration

**Purpose**: Market data acquisition, caching, and normalization

**Structure**:

- `cache/`: 90%+ API call reduction through intelligent caching
- `sources/market/`: Multiple provider support (Alpaca, Polygon, Alpha Vantage)
- `processors/`: Data normalization and format standardization

### src/voting/ - Voting Strategy Framework

**Purpose**: Multi-indicator ensemble voting system

**Files**:

- `base_voting_strategy.py`: Abstract voting framework
- `basic_voting_strategy.py`: MACD+RSI voting implementation

### src/utils/ - Utility Functions

**Purpose**: General-purpose helper functions

**Files**:

- `date_utils.py`: Date/time processing and timezone handling
- `agent_utils.py`: Agent configuration and parsing
- `output_manager.py`: Organized result management

## Key File Descriptions

### main.py - Unified Entry Point

**Commands**:

```bash
python main.py test-voter              # Test VoterAgent with AAPL
python main.py check-positions          # Check paper trading positions
python main.py paper-trade [SYMBOL]    # Full trading cycle check
python main.py analysis                 # Generate analysis reports
```

### src/autogen_agents/voter_agent.py

**Production-Ready Agent** with validated performance:

**Configuration**:

- MACD: 13/34/8 (Fibonacci periods)
- RSI: 14/30/70 (period/oversold/overbought)
- Voting: Strong/weak/conflicting consensus

**Performance**:

- Sharpe Ratio: 0.856
- Win Rate: 51.4%
- Max Drawdown: -10.10%

### src/trading/alpaca_trading_client.py

**Unified Paper/Live Trading**:

**Classes**:

- `AlpacaTradingClient`: Base client with mode selection
- `AlpacaAccountMonitor`: Account status and positions
- `AlpacaOrderManager`: Complete order lifecycle

**Safety Features**:

- Explicit paper/live mode selection
- Live trading confirmations required
- Error handling and logging

### src/trading/trading_cycle.py

**Cost-Efficient Operations**:

**Daily Routines**:

- Morning (9:20 AM ET): Reconcile, adjust stops, report
- Evening (3:50 PM ET): EOD review, next-day prep

**Efficiency**:

- ~10-15 API calls/day (vs 100+ reactive systems)
- 90%+ cost reduction
- GTC orders minimize monitoring

## Data Flow Architecture

```bash
┌────────────────────────────────────┐
│  Market Data Acquisition            │
│  (Alpaca → Polygon → Alpha Vantage) │
└────────────┬───────────────────────┘
             ↓
┌────────────────────────────────────┐
│  Cache Layer (90%+ hit rate)        │
└────────────┬───────────────────────┘
             ↓
┌────────────────────────────────────┐
│  VoterAgent Decision                │
│  ├─ MACD calculation (13/34/8)      │
│  ├─ RSI calculation (14/30/70)      │
│  └─ Voting consensus                │
└────────────┬───────────────────────┘
             ↓
┌────────────────────────────────────┐
│  Risk Management                    │
│  ├─ Position sizing                 │
│  ├─ Portfolio limits                │
│  └─ Confidence threshold            │
└────────────┬───────────────────────┘
             ↓
┌────────────────────────────────────┐
│  Order Execution (Alpaca)           │
│  ├─ Market/bracket orders           │
│  ├─ Stop/trailing stops             │
│  └─ Fill monitoring                 │
└────────────┬───────────────────────┘
             ↓
┌────────────────────────────────────┐
│  Position Tracking                  │
│  ├─ Broker state reconciliation     │
│  ├─ Progressive stop adjustment     │
│  └─ State persistence               │
└────────────────────────────────────┘
```

## Configuration Management

### API Keys (config/config.json)

**Gitignored** - Never committed to version control

```json
{
  "POLYGON_API_KEY": "...",
  "ALPHA_VANTAGE_KEY": "...",
  "OPENAI_API_KEY": "sk-...",
  "ALPACA_PAPER_API_KEY": "...",
  "ALPACA_PAPER_SECRET": "...",
  "ALPACA_LIVE_API_KEY": "...",
  "ALPACA_LIVE_SECRET": "..."
}
```

### Trading Parameters (config_defaults/trading_config.py)

**Version-controlled** - Default trading parameters

```python
# MACD Configuration
macd_config = {"fast": 13, "slow": 34, "signal": 8}

# RSI Configuration
rsi_config = {"period": 14, "oversold": 30, "overbought": 70}

# Exit Strategy
exit_config = {
    "balanced": {"take_profit": 0.08, "stop_loss": 0.05},
    "conservative": {"take_profit": 0.05, "stop_loss": 0.03},
    "aggressive": {"take_profit": 0.12, "stop_loss": 0.08}
}
```

## Testing Structure

### Test Organization

```bash
tests/
├── test_alpaca_basic.py              # Basic Alpaca integration (3/3)
├── test_alpaca_market_data.py        # Market data retrieval
├── test_alpaca_order_manager.py      # Order management (9/9)
├── test_alpaca_advanced_orders.py    # Advanced orders (6/6)
├── unit/agents/                      # Unit tests for agents
└── tools/                            # Tool integration tests
```

### Test Coverage

**Current**: 35/35 tests passing

- Market Data: 3/3
- Basic Orders: 9/9
- Advanced Orders: 6/6
- Advanced Features: 17/17

## Dependencies

### Core Framework

```
autogen-agentchat>=0.7.2      # AutoGen agents
autogen-core>=0.7.2           # AutoGen core
autogen-ext>=0.7.2            # AutoGen extensions
```

### Trading & Data

```
alpaca-py                     # Alpaca trading
polygon-api-client>=1.15.0    # Market data
pandas>=2.2.0                 # Data manipulation
numpy>=2.0.0                  # Numerical computing
```

### AI & LLM

```
openai>=1.71.0                # LLM integration
tiktoken                      # Token counting
```

## Architecture Principles

### 1. Separation of Concerns

- **Agents**: Decision making (AutoGen agents)
- **Tools**: Data access and calculations (pure functions)
- **Trading**: Broker integration and execution
- **Data Sources**: Data acquisition and caching

### 2. Broker as Source of Truth

Always reconcile local state with broker:

1. Fetch broker state (single API call)
2. Compare with local JSON state
3. Update local state
4. Execute any needed changes

### 3. Cost Efficiency

- GTC orders reduce monitoring
- Batch data fetches
- Intelligent caching (>90% hit rate)
- ~10-15 API calls/day vs 100+ reactive

### 4. Extensibility

**Adding Agents**:

```python
class NewAgent(BaseAgent):
    def __init__(self, name, **kwargs):
        super().__init__(name=name, tools=tools, **kwargs)

    def generate_reply(self, messages, context=None):
        # Custom logic
        pass
```

**Adding Tools**:

```python
new_tool = FunctionTool(
    func=my_function,
    name="tool_name",
    description="Tool description"
)
ALL_TOOLS.append(new_tool)
```

---

*Comprehensive guide to codebase organization for contributors and developers.*
