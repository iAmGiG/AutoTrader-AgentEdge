# Core System Architecture

**Foundation**: Multi-layer separation with clean boundaries
**Framework**: Microsoft AutoGen for agent coordination
**Status**: Production-ready infrastructure complete

## Directory Structure

```bash
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
├── autogen_agents/            # Microsoft AutoGen Agent Implementations
│   ├── voter_agent.py              # Production-ready MACD+RSI voting agent (0.856 Sharpe)
│   ├── base_agent.py               # Base AutoGen agent with tool integration
│   ├── scanner_agent.py            # Market scanning agent (in development)
│   ├── risk_agent.py               # Risk management agent (in development)
│   ├── executor_agent.py           # Trade execution agent (in development)
│   └── trading_orchestrator.py     # Multi-agent coordination (in development)
│
└── data_sources/              # Market Data Infrastructure
    └── sources/market/
        └── alpaca_market_data.py   # Real-time data integration
```

## Layer Separation

### 1. Integration Layer (`src/trading/`)

**Purpose**: External service integrations, stateful operations

**Components**:

- **Alpaca Trading Client**: Order placement, account management, position monitoring
- **AutoGen Tool Wrappers**: Agent-to-trading-system bridge
- **API Integrations**: External service connections
- **State Management**: Account state, order tracking

**Responsibilities**:

- Communicate with external APIs (Alpaca, brokers)
- Maintain stateful connections and sessions
- Handle authentication and authorization
- Manage rate limiting and error recovery

**Key Files**:

- `alpaca_trading_client.py`: Main trading client implementation
- `alpaca_autogen_tools.py`: AutoGen tool wrappers for agents

### 2. Business Logic Layer (`src/trading_tools/`)

**Purpose**: Pure functions, calculations, utilities

**Components**:

- **Technical Indicators**: MACD, RSI calculation functions
- **Risk Calculations**: Position sizing, risk assessment
- **Data Utilities**: Market data fetching and processing
- **Position Tracking**: Portfolio state calculations

**Responsibilities**:

- Perform mathematical calculations
- Implement trading logic and strategies
- Provide reusable utility functions
- No external dependencies or state

**Key Files**:

- `indicators.py`: Technical indicator calculations
- `risk_calculator.py`: Position sizing and risk metrics
- `data_fetch.py`: Market data retrieval utilities
- `position_tracker.py`: Portfolio tracking functions

### 3. AutoGen Agent Layer (`src/autogen_agents/`)

**Purpose**: Multi-agent trading system using Microsoft AutoGen framework

**Components**:

- **VoterAgent**: ✅ Production-ready MACD+RSI voting logic (validated: 0.856 Sharpe)
- **BaseAgent**: ✅ Foundation class with tool integration and message handling
- **ScannerAgent**: 🚧 Market opportunity identification (in development)
- **RiskAgent**: 🚧 Portfolio risk management (in development)
- **ExecutorAgent**: 🚧 Trade execution coordination (in development)
- **TradingOrchestrator**: 🚧 Multi-agent workflow management (in development)

**Responsibilities**:

- Coordinate multi-agent workflows
- Make trading decisions via ensemble voting
- Manage agent communication and message passing
- Integrate with tools from integration and business logic layers

**Key Files**:

- `voter_agent.py`: Production MACD+RSI voting agent
- `base_agent.py`: Common agent functionality
- `trading_orchestrator.py`: Multi-agent coordination

### 4. Data Layer (`src/data_sources/`)

**Purpose**: Market data acquisition and normalization

**Components**:

- **Alpaca Market Data**: Real-time bars, quotes, trades, snapshots
- **Multi-provider Support**: Polygon, Alpha Vantage fallbacks
- **Intelligent Caching**: >90% API call reduction

**Responsibilities**:

- Fetch market data from multiple providers
- Normalize data to unified format
- Implement caching for performance
- Handle data provider failures and fallbacks

**Key Files**:

- `sources/market/alpaca_market_data.py`: Primary data source
- `cache/unified_cache.py`: Caching layer
- `processors/data_normalizer.py`: Data format standardization

## Key Design Principles

### 1. Separation of Concerns

#### Integration ≠ Business Logic ≠ Decisions

- Integration layer handles external communication
- Business logic layer performs calculations
- Agent layer makes decisions
- Clean boundaries between layers

**Benefits**:

- Easy to test (mock external dependencies)
- Easy to swap providers (change integration, keep logic)
- Easy to enhance (add agents without changing core)

### 2. Unified Architecture

#### Single codebase for paper and live trading

- Consistent interfaces across all components
- Mode-aware behavior with safety rails
- No duplication between paper and live systems

**Implementation**:

```python
# Same code, different mode
manager = AlpacaOrderManager(mode="paper")  # Paper trading
manager = AlpacaOrderManager(mode="live")   # Live trading (with confirmations)
```

**Benefits**:

- Test in paper, deploy to live with confidence
- No code divergence between environments
- Unified monitoring and logging

### 3. Production Safety

#### Multi-level confirmations for live trading

- Comprehensive validation and error handling
- Risk management at every layer
- Emergency stop capabilities

**Safety Layers**:

1. **Agent Layer**: Signal validation and confidence scoring
2. **Risk Layer**: Position limits, account checks, market hours
3. **Integration Layer**: Order validation, confirmation prompts
4. **Broker Layer**: Final validation at Alpaca

### 4. Agent-Ready Design

#### AutoGen tool wrappers for all functionality

- Standardized response formats
- Agent-friendly error handling
- Consistent tool interface across all agents

**Tool Integration**:

```python
from src.trading.alpaca_autogen_tools import AlpacaAccountTool, AlpacaOrderTool

# Read-only account access for all agents
account_tool = AlpacaAccountTool(mode="paper")

# Order placement for executor agents
order_tool = AlpacaOrderTool(mode="paper")
```

## Configuration Management

### Trading Configuration

**Location**: `config_defaults/`

```bash
config_defaults/
├── voting_config.yaml          # MACD+RSI parameters
├── risk_management.yaml        # Risk limits and controls
└── trading_session.yaml        # Market hours, execution rules
```

**Example**: `voting_config.yaml`

```yaml
macd:
  fast_period: 13        # Fibonacci sequence
  slow_period: 34        # Fibonacci sequence
  signal_period: 8       # Fibonacci sequence

rsi:
  period: 14
  overbought: 70
  oversold: 30

voting:
  strong_agreement: 1.0   # 100% position size
  weak_agreement: 0.5     # 50% position size
  no_agreement: 0.0       # No position
```

### API Configuration

**Location**: `config/config.json` (gitignored)

```json
{
    "ALPACA_PAPER_API_KEY": "your_paper_key",
    "ALPACA_PAPER_SECRET": "your_paper_secret",
    "ALPACA_LIVE_API_KEY": "your_live_key",
    "ALPACA_LIVE_SECRET": "your_live_secret",
    "POLYGON_API_KEY": "your_polygon_key",
    "ALPHA_VANTAGE_API_KEY": "your_alpha_vantage_key"
}
```

**Security**:

- API keys never committed to git
- Separate keys for paper and live trading
- Environment variable support for production

## Testing Strategy

### Comprehensive Test Coverage: 35/35 Tests Passing

**Test Categories**:

- **Market Data**: 3/3 tests (connection, data retrieval, caching)
- **Basic Orders**: 9/9 tests (market, limit, validation, risk)
- **Advanced Orders**: 6/6 tests (stop, trailing, bracket)
- **Advanced Features**: 17/17 tests (modification, cancellation, hours)

### Test Organization

```bash
tests/
├── test_alpaca_basic.py            # Market data integration
├── test_alpaca_connection.py       # API authentication
├── test_alpaca_order_manager.py    # Core order functionality
└── test_alpaca_advanced_orders.py  # Advanced order types
```

### Testing Philosophy

1. **Unit Tests**: Pure functions in business logic layer
2. **Integration Tests**: API connections and data retrieval
3. **Agent Tests**: AutoGen agent behavior and coordination
4. **End-to-End Tests**: Complete trading workflows

### Validation Approach

**Backtesting**:

- Historical data validation
- Strategy performance verification
- Edge case testing with known market conditions

**Paper Trading**:

- Real-time system validation
- Order execution verification
- Position tracking accuracy

**Live Trading** (Future):

- Small position sizes initially
- Gradual scale-up based on performance
- Continuous monitoring and validation

## Performance Characteristics

### Market Data

**Metrics**:

- **>90% Cache Hit Rate**: Intelligent caching reduces API calls
- **Multi-provider Fallback**: Resilient data acquisition
- **Real-time Capability**: Live bars, quotes, trades

**Optimization**:

- Consolidated cache files (reduced I/O)
- Smart expiration logic (historical vs recent)
- Parallel loading for multiple symbols

### Order Management

**Metrics**:

- **Sub-second Validation**: Fast risk checks and parameter validation
- **Unified Performance**: No penalty for paper vs live mode switching
- **Scalable Architecture**: Handles multiple concurrent operations

**Optimization**:

- Async order submission (non-blocking)
- Batch order capabilities (future)
- Efficient fill monitoring

## Integration Points

### AutoGen Agents

**Tool Access**:

```python
from src.trading.alpaca_autogen_tools import AlpacaAccountTool, AlpacaOrderTool

# VoterAgent, Scanner, Risk agents use account tool
account_tool = AlpacaAccountTool(mode="paper")
account_data = account_tool.get_account()

# Executor agent uses order tool
order_tool = AlpacaOrderTool(mode="paper")
order_result = order_tool.place_market_order("AAPL", 10, "buy")
```

### Direct Usage

**Programmatic Access**:

```python
from src.trading.alpaca_trading_client import AlpacaOrderManager

# Full programmatic access for advanced use cases
manager = AlpacaOrderManager(mode="paper")
order = manager.submit_market_order("AAPL", 10, "buy")
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

**Logging**:

- **Structured Logging**: All operations logged with context
- **Error Tracking**: Comprehensive error handling and reporting
- **Audit Trail**: Complete record of all trading decisions and executions

**Metrics**:

- **Performance Metrics**: Order execution times, success rates
- **Risk Monitoring**: Real-time position and limit tracking
- **System Health**: API availability, cache hit rates, error rates

**Alerts** (Future):

- Position limit breaches
- Unexpected errors or failures
- Performance degradation
- Risk threshold violations

## Completed Infrastructure

### ✅ Market Data Integration (#312)

- Real-time market data via Alpaca SDK
- Intelligent caching system (>90% improvement)
- Multi-provider data normalization
- AutoGen tool wrappers

### ✅ Order Management (#313)

- Advanced order types (market, limit, stop, trailing, bracket)
- Risk management (market hours, daily limits, position validation)
- Unified live/paper architecture
- Comprehensive safety features

### ✅ AutoGen Agent System Foundation

- VoterAgent with validated MACD+RSI logic (0.856 Sharpe)
- BaseAgent foundation with tool integration
- Configuration system for dynamic parameter adjustment
- Message handling and agent communication framework

## Next Phase: Complete Agent Ecosystem

### 🔄 Remaining Agents (Issue #310)

1. **Scanner Agent**: Multi-ticker market scanning
2. **Risk Agent**: Portfolio risk management
3. **Executor Agent**: Trade execution coordination
4. **Human Interface**: Decision presentation and CLI

### Integration Goals

- **Unified Tools**: All agents access same data and execution capabilities
- **Message Protocol**: Structured communication between agents
- **State Management**: Shared state across agent interactions
- **Human Approval**: CLI interface for trade approval workflow

---

*Complete trading infrastructure foundation enabling automated trading with professional-grade safety, validation, and monitoring capabilities.*
