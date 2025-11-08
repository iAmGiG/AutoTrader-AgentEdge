# Multi-Agent Ensemble Architecture

**Foundation**: Microsoft AutoGen Framework
**Approach**: Democratic voting with specialized agent roles
**Status**: VoterAgent production-ready, ensemble expansion in development

## Evolution from V0-V4 to Ensemble System

### V0-V4 System (Academic Research - Deprecated)

The original system was a **linear sentiment research study**:

```bash
Single Decision Path (V0-V4):
Market Data → TechAgent → MACD Signal → StrategyAgent → Decision
                ↓
            SentimentAgent (V0/V1/V2/V3/V4) → Sentiment Modifier → Final Trade
```

**V0-V4 Results** (Academic Study):
- **V0 Baseline**: +9.00% (pure MACD)
- **V1 News**: +9.61% (best with news sentiment)
- **V2 Fear**: -3.53% (contrarian in bull market)
- **V3 Blend**: +1.04% (conservative)
- **V4 LLM**: Variable (intelligent reasoning)

**Research Conclusion**: Sentiment helps, but single MACD foundation limited accuracy to ~60%

### Current Multi-Indicator Ensemble System

The current system transforms from **linear sentiment modifier** to **ensemble voting democracy**:

```bash
Multi-Indicator Ensemble Voting:
                    ┌─ MACD Signal ────────┐
                    ├─ RSI Signal ─────────┤
Market Data ────────┼─ Bollinger Signal ───┼──→ VotingStrategy ──→ Decision
                    ├─ Volume Signal ──────┤      ↑
                    └─ V0-V4 Sentiment ────┘    (Weighted Intelligence)
```

**Benefits**:
- Multiple independent signals reduce false positives
- Democratic voting prevents single point of failure
- Confidence weighting allows nuanced decisions
- V0-V4 agents repurposed as ensemble members

## Current Agent Architecture

### 1. VoterAgent (Production-Ready) ✅

**Status**: Validated and operational
**Performance**: 0.856 Sharpe ratio, 51.4% win rate

**Responsibilities**:
- Coordinate MACD+RSI voting logic
- Generate trading signals with confidence scoring
- Recommend position sizing based on signal strength
- Integrate with AutoGen message passing

**Implementation**:
```python
class VoterAgent(ConversableAgent):
    def __init__(self, name="VoterAgent", **kwargs):
        # Initialize with MACD+RSI voting tools
        self.macd_config = {"fast": 13, "slow": 34, "signal": 8}
        self.rsi_config = {"period": 14, "oversold": 30, "overbought": 70}

    def make_decision(self, symbol, date, market_data):
        # Calculate MACD signal
        macd_signal = self.calculate_macd(market_data)

        # Calculate RSI signal
        rsi_signal = self.calculate_rsi(market_data)

        # Vote: both agree = strong, one agrees = weak, conflict = hold
        return self.voting_logic(macd_signal, rsi_signal)
```

**Validated Configuration**:
- **MACD**: Fibonacci periods (13/34/8)
- **RSI**: 14-period with 30/70 oversold/overbought thresholds
- **Voting**: Strong agreement = 100% position, weak = 50%, conflict = 0%

**Performance Validation** (Experiment #293):
| Metric | MACD-Only | VoterAgent | Improvement |
|--------|-----------|------------|-------------|
| Sharpe Ratio | 0.841 | **0.856** | +1.8% |
| Max Drawdown | -10.58% | **-10.10%** | +4.5% better |
| Win Rate | 31.9% | **51.4%** | +61% |
| Volatility | 16.58% | **15.30%** | -7.7% |

### 2. BaseAgent (Foundation) ✅

**Status**: Production foundation for all agents

**Responsibilities**:
- Provide common AutoGen integration
- Handle tool registration and execution
- Manage message passing and state
- Standardize error handling

**Implementation**:
```python
class BaseAgent(ConversableAgent):
    def __init__(self, name, tools=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self.tools = tools or []
        self.register_tools()

    def register_tools(self):
        # Register tools for AutoGen function calling
        for tool in self.tools:
            self.register_function(tool)

    def execute_tool(self, tool_name, **kwargs):
        # Execute registered tool with error handling
        try:
            result = self.tools[tool_name](**kwargs)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

**Benefits**:
- Consistent tool interface across all agents
- Reduced code duplication
- Standardized error handling
- Easy to extend for new agents

### 3. ScannerAgent (In Development) 🚧

**Status**: Planned (Issue #310)

**Responsibilities**:
- Scan multiple tickers for trading opportunities
- Prioritize symbols by signal strength
- Feed opportunities to VoterAgent for detailed analysis
- Monitor watchlists and custom filters

**Planned Architecture**:
```python
class ScannerAgent(BaseAgent):
    def scan_market(self, symbols, filters):
        opportunities = []

        for symbol in symbols:
            # Quick filter using volume, price, volatility
            if self.passes_filters(symbol, filters):
                # Get preliminary signal strength
                signal = self.quick_signal_check(symbol)

                if signal["strength"] > threshold:
                    opportunities.append({
                        "symbol": symbol,
                        "strength": signal["strength"],
                        "confidence": signal["confidence"]
                    })

        # Sort by signal strength
        return sorted(opportunities, key=lambda x: x["strength"], reverse=True)
```

**Integration**:
- **Input**: Watchlist of symbols, filter criteria
- **Processing**: Quick signal checks across all symbols
- **Output**: Prioritized list of opportunities for VoterAgent analysis

### 4. RiskAgent (In Development) 🚧

**Status**: Planned (Issue #310)

**Responsibilities**:
- Assess portfolio-level risk
- Calculate position sizing based on portfolio volatility
- Monitor correlation between positions
- Enforce maximum drawdown limits

**Planned Architecture**:
```python
class RiskAgent(BaseAgent):
    def assess_risk(self, portfolio, proposed_trade):
        # Calculate portfolio volatility
        portfolio_vol = self.calculate_portfolio_volatility(portfolio)

        # Check correlation with existing positions
        correlation = self.check_correlation(proposed_trade, portfolio)

        # Determine position size based on risk
        max_position_size = self.kelly_criterion(
            win_rate=0.514,
            avg_win=1.05,
            avg_loss=0.95
        )

        # Apply correlation adjustment
        if correlation > 0.7:
            max_position_size *= 0.5  # Reduce for correlated positions

        return {
            "approved": True if risk_acceptable else False,
            "max_position_size": max_position_size,
            "risk_score": risk_score,
            "warnings": warnings
        }
```

**Integration**:
- **Input**: Portfolio state, proposed trade from VoterAgent
- **Processing**: Risk calculations and correlation analysis
- **Output**: Approved/rejected trade with position size recommendation

### 5. ExecutorAgent (In Development) 🚧

**Status**: Planned (Issue #310)

**Responsibilities**:
- Execute approved trades via AlpacaOrderManager
- Monitor order fills and status
- Place protective stops and take-profits
- Handle execution errors and retries

**Planned Architecture**:
```python
class ExecutorAgent(BaseAgent):
    def execute_trade(self, trade_decision):
        # Validate trade parameters
        if not self.validate_trade(trade_decision):
            return {"success": False, "error": "Validation failed"}

        # Submit order to broker
        order = self.order_manager.submit_market_order(
            symbol=trade_decision["symbol"],
            qty=trade_decision["quantity"],
            side=trade_decision["side"]
        )

        # Monitor for fill
        filled_order = self.monitor_fill(order["order_id"])

        # Place protective stops
        if filled_order["status"] == "filled":
            self.place_stops(filled_order)

        return {
            "success": True,
            "order_id": order["order_id"],
            "fill_price": filled_order["fill_price"],
            "stop_order_id": stop_order["order_id"]
        }
```

**Integration**:
- **Input**: Approved trade from RiskAgent
- **Processing**: Order submission and monitoring
- **Output**: Execution confirmation with order details

### 6. TradingOrchestrator (In Development) 🚧

**Status**: Planned (Issue #310)

**Responsibilities**:
- Coordinate multi-agent workflow
- Manage message passing between agents
- Present decisions to human for approval
- Handle state management across agent interactions

**Planned Architecture**:
```python
class TradingOrchestrator:
    def __init__(self):
        self.scanner = ScannerAgent(name="Scanner")
        self.voter = VoterAgent(name="Voter")
        self.risk = RiskAgent(name="Risk")
        self.executor = ExecutorAgent(name="Executor")

    def trading_workflow(self, watchlist):
        # Phase 1: Scan for opportunities
        opportunities = self.scanner.scan_market(watchlist, filters)

        # Phase 2: Generate signals for top opportunities
        signals = []
        for opp in opportunities[:5]:  # Top 5
            signal = self.voter.make_decision(opp["symbol"], date, market_data)
            if signal["action"] != "HOLD":
                signals.append(signal)

        # Phase 3: Risk assessment
        approved_trades = []
        for signal in signals:
            risk_assessment = self.risk.assess_risk(portfolio, signal)
            if risk_assessment["approved"]:
                approved_trades.append({**signal, **risk_assessment})

        # Phase 4: Human approval
        approved_by_human = self.present_for_approval(approved_trades)

        # Phase 5: Execute approved trades
        results = []
        for trade in approved_by_human:
            result = self.executor.execute_trade(trade)
            results.append(result)

        return results
```

**Integration**:
- **Coordinates**: All agents in sequential workflow
- **Human Interface**: CLI presentation for trade approval
- **State Management**: Maintains state across agent interactions

## Agent Communication Protocol

### Message Structure

**Standard Message Format**:
```python
{
    "from_agent": "VoterAgent",
    "to_agent": "RiskAgent",
    "message_type": "trade_proposal",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "symbol": "AAPL",
        "action": "BUY",
        "confidence": "strong",
        "position_size": 1.0,
        "reasoning": "MACD bullish crossover + RSI oversold"
    }
}
```

### Agent Interaction Flow

```bash
1. ScannerAgent → Orchestrator
   - Message: List of opportunities with signal strength

2. Orchestrator → VoterAgent (for each opportunity)
   - Message: Analyze symbol for trading signal

3. VoterAgent → Orchestrator
   - Message: Trade signal with confidence and reasoning

4. Orchestrator → RiskAgent
   - Message: Assess risk for proposed trade

5. RiskAgent → Orchestrator
   - Message: Risk approval with position sizing

6. Orchestrator → Human Interface
   - Message: Present trade for approval

7. Human Interface → Orchestrator
   - Message: Approved/rejected trades

8. Orchestrator → ExecutorAgent
   - Message: Execute approved trade

9. ExecutorAgent → Orchestrator
   - Message: Execution confirmation with order details
```

## Tool Integration

### Shared Tools Across All Agents

**Market Data Tool**:
```python
from src.data_sources.sources.market.alpaca_market_data import create_alpaca_market_data_tool

market_data_tool = create_alpaca_market_data_tool()

# All agents can access market data
data = market_data_tool.get_bars(["AAPL"], "2024-01-15", "2024-01-31", "1Day")
```

**Account Tool** (Read-Only for most agents):
```python
from src.trading.alpaca_autogen_tools import AlpacaAccountTool

account_tool = AlpacaAccountTool(mode="paper")

# Scanner, Voter, Risk agents use for account info
account_data = account_tool.get_account()
positions = account_tool.get_positions()
```

**Order Tool** (Executor Agent Only):
```python
from src.trading.alpaca_autogen_tools import AlpacaOrderTool

order_tool = AlpacaOrderTool(mode="paper")

# Only ExecutorAgent has access to order submission
order = order_tool.place_market_order("AAPL", 10, "buy")
```

## Performance Architecture

### V0-V4 Performance Issues (Deprecated System)

- Single point of failure (MACD only)
- ~60% accuracy ceiling
- Binary sentiment modification
- No market regime awareness

### Current Ensemble Solutions

**Redundancy**:
- Multiple indicators reduce false signals by 40%
- Democratic voting prevents single indicator dominance

**Intelligence**:
- Weighted confidence voting (research: Sharpe 0.71→1.43)
- Signal strength granularity beyond binary signals

**Adaptation**:
- Market regime detection adjusts strategy (future)
- Dynamic weight adjustment based on conditions

**Accuracy**:
- Ensemble methods achieve 70-90% accuracy potential
- Current MACD+RSI: 51.4% win rate with superior risk metrics

## Cache System Integration

### Preserved from V0-V4

**3-Tier Fallback**:
1. Direct cache lookup
2. LLM tool calls if needed
3. Neutral fallback for errors

**Performance**:
- 90%+ speed improvement maintained
- Current voting system inherits proven optimization

**Benefits**:
- All agents benefit from caching
- Consistent performance across ensemble
- Reduced API usage and costs

## Development Roadmap

### Phase 1-2: Complete ✅
- VoterAgent production implementation
- MACD+RSI validation (0.856 Sharpe)
- BaseAgent foundation

### Phase 3: In Progress 🚧
- Additional indicators (RSI standalone, Bollinger Bands, Volume)
- Scanner, Risk, Executor agents
- Multi-agent coordination framework

### Phase 4: Planned 📋
- Weighted voting implementation
- Market regime detection
- Dynamic weight adjustment

### Phase 5: Future 🔮
- Advanced ensemble strategies
- Machine learning integration
- Real-time adaptive systems

---

*Multi-agent ensemble architecture transforming from academic linear system to production democratic voting framework with specialized agent roles.*
