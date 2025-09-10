# Trading System Architecture Overview

**Status**: Core Infrastructure Complete (September 9, 2025)  
**Foundation**: Market Data (#312) + Order Management (#313) = Full Trading Capability

## System Architecture

### Directory Structure
```
src/
├── trading/                    # Trading Operations & Integrations
│   ├── alpaca_trading_client.py    # Order management, account monitoring
│   └── alpaca_autogen_tools.py     # AutoGen agent integration
│
├── trading_tools/             # Pure Trading Functions
│   ├── data_fetch.py               # Market data utilities
│   ├── indicators.py               # MACD, RSI calculations
│   ├── position_tracker.py         # Position management utilities
│   └── risk_calculator.py          # Risk assessment functions
│
├── autogen_agents/            # AutoGen Agent Implementations
│   └── voter_agent.py              # MACD+RSI voting agent
│
└── data_sources/              # Market Data Infrastructure
    └── sources/market/
        └── alpaca_market_data.py   # Real-time data integration
```

## Layer Separation

### 1. Integration Layer (`src/trading/`)
**Purpose**: External service integrations, stateful operations

- **Alpaca Trading Client**: Order placement, account management, position monitoring
- **AutoGen Tool Wrappers**: Agent-to-trading-system bridge
- **API Integrations**: External service connections
- **State Management**: Account state, order tracking

### 2. Business Logic Layer (`src/trading_tools/`)
**Purpose**: Pure functions, calculations, utilities

- **Technical Indicators**: MACD, RSI calculation functions
- **Risk Calculations**: Position sizing, risk assessment
- **Data Utilities**: Market data fetching and processing
- **Position Tracking**: Portfolio state calculations

### 3. Agent Layer (`src/autogen_agents/`)
**Purpose**: Decision-making agents using AutoGen framework

- **VoterAgent**: MACD+RSI voting logic (validated: 0.856 Sharpe)
- **Future Agents**: Scanner, Risk Manager, Executor, Human Interface

### 4. Data Layer (`src/data_sources/`)
**Purpose**: Market data acquisition and normalization

- **Alpaca Market Data**: Real-time bars, quotes, trades, snapshots
- **Multi-provider Support**: Polygon, Alpha Vantage fallbacks
- **Intelligent Caching**: >90% API call reduction

## Data Flow

```
Market Data → Agents → Trading Tools → Trading Operations
     ↓           ↓           ↓              ↓
1. Real-time  2. MACD+RSI  3. Risk        4. Order
   market        voting       calculation    placement
   data          decisions    position       via Alpaca
                              sizing         API
```

## Complete Trading Infrastructure

### ✅ Completed Components

**Market Data Integration (#312)**:
- Real-time market data via Alpaca SDK
- Intelligent caching system
- Multi-provider data normalization
- AutoGen tool wrappers

**Order Management (#313)**:
- Advanced order types (market, limit, stop, trailing, bracket)
- Risk management (market hours, daily limits, position validation)
- Unified live/paper architecture
- Comprehensive safety features

**Voting System Foundation**:
- VoterAgent with validated MACD+RSI logic
- Configuration system for parameters
- AutoGen BaseAgent integration

### 🔄 Next Phase: Complete Agent Ecosystem

**Remaining Agents (Issue #310)**:
1. **Scanner Agent**: Multi-ticker market scanning
2. **Risk Agent**: Portfolio risk management  
3. **Executor Agent**: Trade execution coordination
4. **Human Interface**: Decision presentation and CLI

## Key Design Principles

### 1. **Separation of Concerns**
- **Integration** ≠ **Business Logic** ≠ **Decisions**
- Clean boundaries between layers
- Pure functions where possible

### 2. **Unified Architecture**
- Single codebase for paper and live trading
- Consistent interfaces across all components
- Mode-aware behavior with safety rails

### 3. **Production Safety**
- Multi-level confirmations for live trading
- Comprehensive validation and error handling
- Risk management at every layer

### 4. **Agent-Ready Design**
- AutoGen tool wrappers for all functionality
- Standardized response formats
- Agent-friendly error handling

## Configuration Management

### Trading Configuration
```
config_defaults/
├── voting_config.yaml          # MACD+RSI parameters
├── risk_management.yaml        # Risk limits and controls
└── trading_session.yaml        # Market hours, execution rules
```

### API Configuration
```
config/
└── config.json                 # API keys (gitignored)
    ├── ALPACA_PAPER_API_KEY
    ├── ALPACA_PAPER_SECRET
    ├── ALPACA_LIVE_API_KEY     # For live trading
    └── ALPACA_LIVE_SECRET
```

## Testing Strategy

### Comprehensive Test Coverage: 35/35 Tests Passing
- **Market Data**: 3/3 tests (connection, data retrieval, caching)
- **Basic Orders**: 9/9 tests (market, limit, validation, risk)
- **Advanced Orders**: 6/6 tests (stop, trailing, bracket)
- **Advanced Features**: 17/17 tests (modification, cancellation, hours)

### Test Organization
```
tests/
├── test_alpaca_basic.py            # Market data integration
├── test_alpaca_connection.py       # API authentication
├── test_alpaca_order_manager.py    # Core order functionality
└── test_alpaca_advanced_orders.py  # Advanced order types
```

## Performance Characteristics

### Market Data
- **>90% Cache Hit Rate**: Intelligent caching reduces API calls
- **Multi-provider Fallback**: Resilient data acquisition
- **Real-time Capability**: Live bars, quotes, trades

### Order Management
- **Sub-second Validation**: Fast risk checks and parameter validation
- **Unified Performance**: No penalty for paper vs live mode switching
- **Scalable Architecture**: Handles multiple concurrent operations

## Integration Points

### AutoGen Agents
```python
from src.trading.alpaca_autogen_tools import AlpacaAccountTool, AlpacaOrderTool

# Read-only account access for all agents
account_tool = AlpacaAccountTool(mode="paper")

# Order placement for executor agents
order_tool = AlpacaOrderTool(mode="paper")
```

### Direct Usage
```python
from src.trading.alpaca_trading_client import AlpacaOrderManager

# Full programmatic access
manager = AlpacaOrderManager(mode="paper")
```

## Production Readiness

### Live Trading Checklist
- ✅ **Safety Rails**: Multi-level confirmations
- ✅ **Risk Management**: Position limits, daily limits, buying power
- ✅ **Error Handling**: Comprehensive validation and recovery
- ✅ **Logging**: Complete audit trail
- ✅ **Testing**: Full test coverage with edge cases
- ✅ **Documentation**: Complete usage and API documentation

### Monitoring & Observability
- **Structured Logging**: All operations logged with context
- **Error Tracking**: Comprehensive error handling and reporting
- **Performance Metrics**: Order execution times, success rates
- **Risk Monitoring**: Real-time position and limit tracking

---

*Complete trading infrastructure foundation enabling automated trading with professional-grade safety, validation, and monitoring capabilities.*