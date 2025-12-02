# Trading Pipeline - Complete Daily Workflow

## Issue #323: Full Trading Pipeline Workflow

## Overview

The `TradingPipeline` orchestrates all system components into a seamless, automated daily trading workflow. It coordinates data collection, signal generation, order execution, position management, and end-of-day reconciliation into a single, cohesive process.

## Architecture

### Five-Phase Workflow

```text
┌─────────────────┐
│ Data Collection │ ─→ Validate market data, check market hours
└────────┬────────┘
         ↓
┌─────────────────┐
│    Analysis     │ ─→ VoterAgent scans watchlist, generates signals
└────────┬────────┘
         ↓
┌─────────────────┐
│   Execution     │ ─→ ExecutorAgent places orders
└────────┬────────┘
         ↓
┌─────────────────┐
│   Management    │ ─→ Monitor positions, update trailing stops
└────────┬────────┘
         ↓
┌─────────────────┐
│  End-of-Day     │ ─→ Reconcile with broker, generate reports
└─────────────────┘
```

### Component Integration

| Component | Role | Integration Point |
|-----------|------|-------------------|
| **VoterAgent** | Signal generation | Analysis phase - MACD+RSI voting |
| **ExecutorAgent** | Order placement | Execution phase - Market/bracket orders |
| **PositionManager** | Position tracking | Management + EOD phases |
| **OrderManager** | Broker interface | Execution phase - Alpaca API |
| **MarketData** | Price data | Data collection + analysis |
| **DailyScheduler** | Timing/automation | Optional - schedule pipeline runs |

## Usage

### Basic Usage

```python
import asyncio
from src.autogen_agents.voter_agent import VoterAgent
from src.autogen_agents.executor_agent import ExecutorAgent
from src.trading.trading_pipeline import TradingPipeline

async def run_daily_workflow():
    # Create agents
    voter = VoterAgent(name="voter", use_config_file=True)
    executor = ExecutorAgent(name="executor", paper_trading=True)

    # Create pipeline
    pipeline = TradingPipeline(
        voter_agent=voter,
        executor_agent=executor,
        watchlist=["SPY", "QQQ", "AAPL", "MSFT"],
    )

    # Run full workflow
    metrics = await pipeline.run_full_pipeline()

    print(f"Status: {metrics.pipeline_status}")
    print(f"Signals: {metrics.total_signals}")
    print(f"Orders: {metrics.total_orders}")

asyncio.run(run_daily_workflow())
```

### With Full Broker Integration

```python
from src.trading.alpaca_trading_client import get_trading_client
from src.trading.order_manager import OrderManager
from src.trading.position_manager import PositionManager

# Initialize broker components
client = get_trading_client(paper=True)
position_mgr = PositionManager(client)
order_mgr = OrderManager(client, position_mgr)

# Create agents with broker connection
executor = ExecutorAgent(
    name="executor",
    order_manager=order_mgr,
    position_manager=position_mgr,
    paper_trading=True,
)

# Create pipeline
pipeline = TradingPipeline(
    voter_agent=voter,
    executor_agent=executor,
    position_manager=position_mgr,
    order_manager=order_mgr,
    watchlist=watchlist,
)

# Run
metrics = await pipeline.run_full_pipeline()
```

### Command-Line Demo

```bash
# Basic run with default watchlist
python examples/run_trading_pipeline.py

# Custom watchlist
python examples/run_trading_pipeline.py --watchlist SPY,QQQ,NVDA,TSLA

# Dry-run mode (no actual orders)
python examples/run_trading_pipeline.py --dry-run

# Live trading (use with caution!)
python examples/run_trading_pipeline.py --mode live --watchlist SPY
```

## Phase Details

### Phase 1: Data Collection

**Purpose**: Validate market conditions and data availability

**Actions**:

- Check if market is open (9:30 AM - 4:00 PM ET)
- Validate watchlist ticker symbols
- Verify data freshness

**Output**:

```python
{
    "market_open": True,
    "tickers_validated": 25,
    "data_fresh": True
}
```

### Phase 2: Analysis

**Purpose**: Generate trading signals using VoterAgent

**Actions**:

- Fetch 60 days of OHLCV data for each ticker
- Run MACD+RSI voting analysis
- Filter signals by confidence threshold
- Categorize as STRONG/WEAK/CONFLICT/NEUTRAL

**Output**:

```python
{
    "signals": [
        {
            "ticker": "SPY",
            "action": "BUY",
            "confidence": 0.75,
            "position_size": 1.0,  # Full position
            "signal_type": "STRONG",
            "reasoning": "Strong consensus: Both MACD and RSI signal BUY"
        },
        {
            "ticker": "QQQ",
            "action": "BUY",
            "confidence": 0.55,
            "position_size": 0.5,  # Half position
            "signal_type": "WEAK",
            "reasoning": "Weak signal: Only MACD signals BUY"
        }
    ],
    "total_analyzed": 25
}
```

### Phase 3: Execution

**Purpose**: Place orders for approved signals

**Actions**:

- Calculate position sizes (10% of account per signal)
- Adjust by position_size multiplier (0.5 for weak signals)
- Fetch current prices for quantity calculation
- Submit market orders via ExecutorAgent
- Track execution results

**Output**:

```python
{
    "orders_placed": 2,
    "executions": [
        {
            "id": "abc123",
            "symbol": "SPY",
            "side": "buy",
            "qty": 15,
            "status": "submitted",
            "filled_price": 660.50
        }
    ]
}
```

### Phase 4: Management

**Purpose**: Monitor open positions and risk

**Actions**:

- Refresh positions from broker (force_refresh=True)
- Log position health (P&L, quantity, market value)
- Track unrealized gains/losses
- *(Future: Update trailing stops via TrailingStopManager)*

**Output**:

```python
{
    "positions_updated": 5,
    "positions": [
        {
            "symbol": "SPY",
            "qty": 15,
            "unrealized_pl_pct": 0.0234,  # 2.34%
            "market_value": 9907.50
        }
    ]
}
```

### Phase 5: End-of-Day

**Purpose**: Reconcile state and generate reports

**Actions**:

- Force-refresh all positions from broker (broker-as-truth)
- Calculate total unrealized P&L
- Fetch account portfolio value
- Create daily report directory
- Log summary statistics

**Output**:

```python
{
    "report_path": "reports/daily/2025-01-27_pipeline.md",
    "reconciliation_complete": True,
    "position_count": 5,
    "total_pnl": 450.75,
    "portfolio_value": 103450.75
}
```

## Pipeline Metrics

After completion, the pipeline returns a `PipelineMetrics` object:

```python
@dataclass
class PipelineMetrics:
    started_at: datetime
    completed_at: datetime
    total_phases: int = 5
    phases_completed: int
    phases_failed: int
    total_signals: int
    total_orders: int
    total_errors: int
    phase_results: List[PhaseResult]
```

Example output:

```text
Status: COMPLETED
Duration: 45.2s
Phases Completed: 5/5
Signals Generated: 3
Orders Placed: 2
Errors: 0

Phase Breakdown:
  data_collection: completed (2.1s)
  analysis: completed (32.5s)
  execution: completed (5.8s)
  management: completed (3.2s)
  end_of_day: completed (1.6s)
```

## Error Handling

### Phase-Level Resilience

Each phase has independent error handling:

- Errors in one phase don't crash the pipeline
- Failed phases are tracked in `phases_failed` metric
- Partial success is captured (some phases succeed, others fail)

### Pipeline Status States

| Status | Description |
|--------|-------------|
| `IDLE` | Not yet started |
| `RUNNING` | Currently executing |
| `COMPLETED` | All phases succeeded |
| `PARTIAL_SUCCESS` | Some phases succeeded, some failed |
| `FAILED` | All phases failed or fatal error |

### Example Error Handling

```python
try:
    metrics = await pipeline.run_full_pipeline()

    if metrics.phases_failed > 0:
        print(f"⚠️ {metrics.phases_failed} phases failed")
        for result in metrics.phase_results:
            if result.errors:
                print(f"  {result.phase.value}: {result.errors}")

except Exception as e:
    print(f"❌ Pipeline crashed: {e}")
```

## Scheduling Integration

### With DailyScheduler

```python
from src.trading.daily_scheduler import DailyScheduler, ScheduledTask

async def scheduled_pipeline_task():
    """Task wrapper for scheduler."""
    metrics = await pipeline.run_full_pipeline()
    return metrics.pipeline_status.value

# Create scheduler
scheduler = DailyScheduler()

# Schedule morning run at 9:45 AM ET (15 min after market open)
scheduler.schedule_task(
    ScheduledTask(
        name="morning_pipeline",
        time_et="09:45",
        task_func=scheduled_pipeline_task,
        enabled=True,
    )
)

# Schedule afternoon run at 3:00 PM ET
scheduler.schedule_task(
    ScheduledTask(
        name="afternoon_pipeline",
        time_et="15:00",
        task_func=scheduled_pipeline_task,
        enabled=True,
    )
)

# Run scheduler
await scheduler.run()
```

### Cron Schedule (Linux)

```bash
# Run at 9:45 AM ET weekdays
45 9 * * 1-5 cd /path/to/AutoTrader && python examples/run_trading_pipeline.py

# Run at 3:00 PM ET weekdays
0 15 * * 1-5 cd /path/to/AutoTrader && python examples/run_trading_pipeline.py --mode paper
```

## Configuration

### Watchlist Configuration

Load from `config_defaults/scanner_config.yaml`:

```yaml
default_watchlist:
  etfs:
    - SPY
    - QQQ
    - DIA
  tech_giants:
    - AAPL
    - MSFT
    - NVDA
  # ... more categories
```

The pipeline automatically flattens all categories into a single watchlist.

### Custom Watchlist

```python
pipeline = TradingPipeline(
    voter_agent=voter,
    executor_agent=executor,
    watchlist=["TQQQ", "SOXL", "UPRO"],  # Override config
)
```

## Testing

### Unit Test Structure

```python
import pytest
from src.trading.trading_pipeline import TradingPipeline

@pytest.mark.asyncio
async def test_pipeline_phases():
    """Test each phase independently."""
    pipeline = TradingPipeline(
        voter_agent=mock_voter,
        executor_agent=mock_executor,
        watchlist=["SPY"],
    )

    # Test data collection
    result = await pipeline._data_collection_phase()
    assert result["tickers_validated"] == 1

    # Test analysis (with mock data)
    result = await pipeline._analysis_phase()
    assert "signals" in result

@pytest.mark.asyncio
async def test_full_pipeline():
    """Test complete workflow."""
    metrics = await pipeline.run_full_pipeline()

    assert metrics.total_phases == 5
    assert metrics.phases_completed >= 0
    assert metrics.pipeline_status in [
        PipelineStatus.COMPLETED,
        PipelineStatus.PARTIAL_SUCCESS,
        PipelineStatus.FAILED,
    ]
```

## Future Enhancements

- [ ] Integrate TrailingStopManager in management phase (#321)
- [ ] Add RiskAgent pre-execution validation (#387)
- [ ] Implement report generation (markdown/HTML)
- [ ] Add pipeline state persistence for resume
- [ ] Create performance dashboard
- [ ] Email/Slack notifications on completion
- [ ] Multi-timeframe analysis support
- [ ] Portfolio rebalancing logic

## Related Issues

- #321 - TrailingStopManager integration
- #322 - Live execution layer (AlpacaExecutionManager)
- #387 - RiskAgent validation
- #388 - ExecutorAgent coordination
- #390 - AgentBus event publishing

## See Also

- [VoterAgent Documentation](../../autogen_agents/voter_agent.py)
- [ExecutorAgent Documentation](../../autogen_agents/executor_agent.py)
- [DailyScheduler](./daily_scheduler.py)
- [PositionManager](./position_manager.py)
