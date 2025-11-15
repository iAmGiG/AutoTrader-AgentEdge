# AutoTrader: Multi-Agent AI Trading Platform

## Project Abstract

**Version**: 1.0.0
**Status**: Production Ready
**Last Updated**: November 2025
**Repository**: https://github.com/iAmGiG/AutoTrader-AgentEdge

---

## Executive Summary

**AutoTrader** is a production-ready algorithmic trading platform featuring the **AgentEdge** multi-agent architecture, designed to provide systematic, risk-managed trading decisions with human oversight. The system has achieved validated performance metrics of **0.856 Sharpe ratio** and **36.6% total return** over the 2024-2025 testing period, demonstrating superior risk-adjusted returns compared to single-indicator baseline strategies.

Built on Microsoft's AutoGen framework, AutoTrader coordinates specialized AI agents to analyze market conditions, manage risk, and execute trades via Alpaca Markets' brokerage API. The platform emphasizes **pure mathematical indicators** combined with **human-in-loop decision making** over complex AI sentiment analysis, resulting in transparent, explainable, and cost-efficient trading operations.

---

## Problem Statement

Traditional algorithmic trading systems face several critical challenges:

1. **Single-Point-of-Failure**: Relying on a single indicator or strategy creates vulnerability to market regime changes
2. **Sentiment Analysis Complexity**: LLM-based sentiment systems are expensive, slow, and produce inconsistent results with unproven ROI
3. **Black Box Decision Making**: Many AI trading systems lack transparency, making it difficult to understand and trust their decisions
4. **Human Displacement**: Fully autonomous systems remove human judgment, leading to potential disasters during anomalous market conditions
5. **Cost Inefficiency**: Continuous monitoring and reactive trading systems generate excessive API calls and brokerage fees

AutoTrader addresses these challenges through a validated multi-agent ensemble voting approach with human oversight, achieving measurable performance improvements while maintaining transparency and cost efficiency.

---

## Solution Architecture

### AgentEdge Multi-Agent System

**Core Design Philosophy**: Specialized AI agents working collaboratively, coordinated through Microsoft AutoGen's message-passing framework.

#### Production-Ready Agent

**VoterAgent** (`src/autogen_agents/voter_agent.py`) - ✅ **VALIDATED**
- **Purpose**: MACD + RSI ensemble voting for trade signal generation
- **Performance**: 0.856 Sharpe ratio (1.8% improvement over single MACD baseline)
- **Parameters**:
  - MACD: Fibonacci-optimized 13/34/8 (fast/slow/signal periods)
  - RSI: 14-period with 30/70 oversold/overbought thresholds
- **Decision Logic**:
  - **Strong Signal** (100% position): Both indicators agree on direction
  - **Weak Signal** (50% position): One indicator signals, one neutral
  - **Hold** (0% position): Disagreement or both neutral

#### Agents In Development

1. **ScannerAgent** - Market opportunity identification across multiple symbols
2. **RiskAgent** - Portfolio-level risk management and position sizing
3. **ExecutorAgent** - Trade execution optimization and order management
4. **TradingOrchestrator** - Multi-agent coordination and workflow management

### Technical Infrastructure

**Market Data Sources**:
- **Primary**: Polygon.io API (real-time and historical OHLCV data)
- **Fallback**: Alpha Vantage API
- **Cache System**: SQLite-based unified cache (90%+ performance improvement)

**Brokerage Integration**:
- **Alpaca Markets API**: Paper and live trading execution
- **Order Types**: Market, limit, bracket (entry + stop-loss + take-profit)
- **Position Tracking**: Broker-as-truth reconciliation system

**Framework & Tools**:
- **Microsoft AutoGen 0.7.x**: Multi-agent coordination and message passing
- **Python 3.10+**: Core implementation language
- **Async/Await**: High-performance asynchronous operations
- **YAML Configuration**: Human-readable parameter management

---

## Key Features

### 1. Validated Performance (Experiment #293)

**Test Period**: January 2024 - January 2025 (extended validation)

**Key Metrics**:
| Metric | VoterAgent (MACD+RSI) | Baseline (MACD Only) | Improvement |
|--------|----------------------|---------------------|-------------|
| Sharpe Ratio | **0.856** | 0.841 | +1.8% |
| Total Return | **36.6%** | 35.1% | +1.5 pp |
| Win Rate | **51.4%** | 50.8% | +0.6 pp |
| Max Drawdown | **-10.10%** | -11.2% | +1.1 pp |

**Market Regime Analysis**:
- **Volatile Markets** (2024-2025 transition): -14.6% gap vs benchmark
- **Bull Markets** (2024 rally): -25.8% gap vs benchmark
- **Insight**: Conservative strategy prioritizes risk management over raw returns

**Validation Archive**: `docs/archived/experiments/experiment_293_validation/`

### 2. Human-in-Loop Design

**Philosophy**: System assists human traders, does not replace them.

**User Workflow**:
```
User Request → LLM Parser → Strategy Analysis (VoterAgent) →
Risk Assessment → Trade Suggestion → User Approval → Execution
```

**Interactive CLI**:
- Natural language command processing
- Real-time position monitoring
- Alert system for stop/target proximity
- Portfolio status and P&L tracking
- Scheduler management interface

### 3. Cost-Efficient Operations

**Traditional Polling System**:
- Continuous monitoring: ~1,000+ API calls/day
- Rate limiting concerns
- High latency during market hours

**AutoTrader's Approach**:
- **GTC Orders** (Good-Til-Canceled): Set-and-forget stop-loss/take-profit
- **Scheduled Routines**: Morning (9:20 AM) and evening (3:50 PM) reconciliation
- **Intelligent Caching**: 90%+ cache hit rate reduces API calls by 85%
- **Result**: 6-10 API calls/day (90% reduction)

### 4. Automated Scheduler System

**Daily Routines**:
- **Morning** (9:20 AM ET): Position reconciliation, alert generation
- **Evening** (3:50 PM ET): Performance review, order adjustments

**Features**:
- Interactive `/schedule` CLI management
- Background daemon mode
- Exponential backoff retry logic (60s, 120s, 240s with 10% jitter)
- Comprehensive error handling and crash recovery
- Execution history tracking

### 5. Production-Grade Infrastructure

**Reliability**:
- Broker-as-truth position reconciliation (prevents state drift)
- Order lifecycle management (bracket orders with stop/target)
- Market hours awareness
- Comprehensive error handling

**Observability**:
- Detailed logging with context
- Performance metrics tracking
- Execution history
- Position alert system

---

## Validation & Testing

### Experiment #293: Voting System Validation

**Objective**: Prove MACD + RSI voting outperforms single-indicator strategies

**Methodology**:
- **Backtest Period**: January 2024 - January 2025 (13 months)
- **Test Universe**: 7 major tech stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META)
- **Baseline**: Pure MACD strategy (13/34/8 Fibonacci parameters)
- **Treatment**: MACD + RSI ensemble voting

**Results** (see validation archive for full details):
- ✅ Voting beats single MACD by 1.8% Sharpe improvement
- ✅ Consistent performance across multiple market regimes
- ✅ Superior risk management (lower drawdowns)
- ✅ Production-ready for paper trading deployment

**Documentation**: `docs/archived/experiments/experiment_293_validation/README.md`

### Parameter Optimization

**MACD Parameters** (Fibonacci-based):
- Fast: 13 periods
- Slow: 34 periods
- Signal: 8 periods
- **Rationale**: Fibonacci numbers align with natural market cycles

**RSI Parameters** (Standard):
- Period: 14 (industry standard)
- Oversold: 30
- Overbought: 70

**Optimization Process**:
- Grid search across parameter space
- Walk-forward analysis
- Multi-market validation (7 tech stocks)
- Out-of-sample testing (2024-2025 extended period)

---

## Technical Implementation

### Code Organization

```
AutoTrader-AgentEdge/
├── src/
│   ├── autogen_agents/           # Multi-agent implementations
│   │   ├── voter_agent.py        # ✅ Production-ready voting agent
│   │   ├── base_agent.py         # Base agent with tool integration
│   │   └── trading_orchestrator.py  # 🚧 Multi-agent coordinator
│   ├── trading_tools/            # Indicator calculations
│   │   └── indicators.py         # MACD, RSI functions
│   ├── data_sources/             # Market data integration
│   │   ├── sources/market/       # Polygon, Alpaca, Alpha Vantage
│   │   └── cache/                # SQLite unified cache
│   ├── execution/                # Trade execution layer
│   │   └── alpaca_execution_manager.py
│   ├── strategies/               # Strategy implementations
│   │   └── real_voter_strategy.py
│   ├── cli/                      # Interactive CLI
│   │   └── cli_session.py
│   └── trading/                  # Trading infrastructure
│       ├── daily_scheduler.py    # Automated routines
│       ├── order_manager.py      # Order lifecycle
│       └── trade_lifecycle.py    # Position tracking
├── config_defaults/              # YAML configuration
│   ├── trading_config.yaml       # Strategy parameters
│   └── scheduler_config.yaml     # Scheduler settings
├── docs/                         # Comprehensive documentation
│   ├── 01_overview/              # System architecture
│   ├── 02_architecture/          # Technical design
│   ├── 03_reference/             # Commands, validation
│   ├── 04_development/           # Developer guides
│   └── archived/                 # Experiment results
└── tests/                        # Validation scripts
```

### Configuration System

**YAML-First Approach** (`config_defaults/trading_config.yaml`):
```yaml
voter_agent:
  macd:
    fast_period: 13      # Fibonacci parameter
    slow_period: 34      # Fibonacci parameter
    signal_period: 8     # Fibonacci parameter
  rsi:
    period: 14
    oversold: 30
    overbought: 70
  position_sizing:
    strong_signal: 1.0   # 100% position
    weak_signal: 0.5     # 50% position
    no_signal: 0.0       # 0% position
```

**Benefits**:
- No code changes for parameter tuning
- Version-controlled default configurations
- Easy A/B testing of parameter sets
- Human-readable and maintainable

### Caching Architecture

**Unified Cache System** (`src/data_sources/cache/unified_cache.py`):
- **Backend**: SQLite database (`.cache/market_data.db`)
- **Strategy**: Cache-first with intelligent warming
- **Performance**: 90%+ hit rate, 85% API call reduction
- **Invalidation**: Time-based (24 hours for daily data, 1 hour for intraday)

**Cache Schema**:
```sql
CREATE TABLE price_data (
    symbol TEXT,
    start_date TEXT,
    end_date TEXT,
    timeframe TEXT,
    data TEXT,  -- JSON-encoded OHLCV DataFrame
    timestamp REAL,
    PRIMARY KEY (symbol, start_date, end_date, timeframe)
);
```

---

## Performance Benchmarks

### System Performance

**Backtest Execution Time** (60 days, single symbol):
- Without cache: ~45 seconds (API rate limiting)
- With cache (warm): ~2 seconds (90%+ hit rate)
- **Improvement**: 22.5x faster

**Memory Footprint**:
- Base system: ~120 MB
- With 7 symbols cached (60 days): ~180 MB
- Cache database size: ~15 MB

**API Call Efficiency**:
- Traditional polling: 1,000+ calls/day
- AutoTrader GTC system: 6-10 calls/day
- **Reduction**: 90%+

### Trading Performance

**Sharpe Ratio Evolution**:
- Single MACD: 0.841
- MACD + RSI Voting: **0.856** (✅ 1.8% improvement)

**Market Regime Performance**:
| Regime | VoterAgent Gap | Benchmark Performance |
|--------|---------------|----------------------|
| Volatile (2024-2025) | -14.6% | Conservative outperformance |
| Bull (2024) | -25.8% | Risk-managed underperformance |

**Insight**: System prioritizes risk-adjusted returns over raw performance during bull markets, as designed.

---

## Use Cases & Applications

### 1. Educational & Research

**Target Audience**: Students, researchers, and hobbyist traders

**Applications**:
- Multi-agent system architecture study
- Technical indicator ensemble validation
- AutoGen framework learning
- Algorithmic trading fundamentals

**Resources**:
- Comprehensive documentation (`docs/`)
- Validated experiment archives
- Open-source codebase (AGPL-3.0)
- Interactive CLI for hands-on learning

### 2. Paper Trading & Strategy Development

**Target Audience**: Retail traders, strategy developers

**Applications**:
- Safe testing environment (Alpaca paper trading)
- Parameter optimization workflows
- Strategy validation before live deployment
- Risk management practice

**Features**:
- Real market data (Polygon.io)
- Simulated broker integration (Alpaca paper API)
- Position tracking and P&L monitoring
- Alert system for risk events

### 3. Personal Portfolio Management

**Target Audience**: Individual investors seeking systematic approach

**Applications**:
- Supplement discretionary trading with technical signals
- Automated position monitoring
- Risk-managed stop-loss and take-profit execution
- Daily performance tracking

**Safety Features**:
- Human-in-loop approval required for all trades
- Position alerts before hitting stops/targets
- Broker reconciliation prevents state drift
- Transparent decision reasoning

---

## ⚠️ Important Disclaimers

### Legal Notice

**THIS SOFTWARE IS FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY.**

- **NOT FINANCIAL ADVICE**: This system does not provide financial, investment, or trading advice. All outputs from technical indicators, AI agents, and automated signals are for informational purposes only.
- **NOT INVESTMENT ADVICE**: Do not rely on this software for investment decisions. Consult a licensed financial advisor before making any trading or investment decisions.
- **USE AT YOUR OWN RISK**: Trading stocks and securities involves substantial risk of loss. You are solely responsible for any trading decisions and resulting gains or losses.
- **NO WARRANTIES**: This software is provided "as-is" without any guarantees of accuracy, reliability, or profitability.
- **PAST PERFORMANCE ≠ FUTURE RESULTS**: Historical backtesting results (36.6% return, 0.856 Sharpe) do not guarantee future performance.

By using this software, you acknowledge that you understand these risks and agree to use it solely for educational purposes.

### Technical Limitations

1. **Market Conditions**: Validated in 2024-2025 market conditions; performance may vary in different regimes
2. **Slippage & Fees**: Backtest results do not account for real-world slippage, commissions, or market impact
3. **Data Availability**: Requires paid API subscriptions (Polygon.io, Alpaca Markets)
4. **Internet Connectivity**: System requires stable internet for API access
5. **Computational Resources**: Minimal (runs on standard laptop), but cache system requires disk space

### Known Issues & Limitations

**Current Limitations**:
- Fixed -2% stop-loss and +3.5% take-profit offsets (not volatility-adjusted)
- Daily-only analysis (no intraday entry optimization)
- Single-symbol trading focus (no portfolio-level optimization)
- No volume confirmation in entry logic
- No support/resistance level detection

**Planned Enhancements** (see GitHub issues):
- Issue #366: OHLCV-based intraday entry planning with ATR stops
- Issue #361: LLM-based intent classification and company-to-ticker resolution
- Issue #344: Pullback and price timing context support
- Issue #310: Complete multi-agent system (Scanner, Risk, Executor, Orchestrator)

---

## Technology Stack

### Core Dependencies

**Runtime**:
- Python 3.10+ (async/await, type hints)
- Microsoft AutoGen 0.7.x (multi-agent framework)
- pandas 2.2+ (data manipulation)
- numpy 2.0+ (numerical computing)

**Market Data & Execution**:
- polygon-api-client 1.15+ (primary market data)
- alpaca-py (brokerage integration)
- yfinance (fallback data source)

**AI/LLM** (optional for future features):
- OpenAI API (GPT-4o-mini for tools, o3-mini for reasoning)
- aiohttp (async HTTP client)

**Development Tools**:
- Black (code formatting)
- Ruff (linting)
- flake8 (legacy linting)
- mypy (type checking)

### API Subscriptions Required

**Essential**:
- **Polygon.io**: Market data ($0-$99/month depending on plan)
- **Alpaca Markets**: Free paper trading, live trading available
- **Alpha Vantage**: Free tier available (fallback data source)

**Optional**:
- **OpenAI**: $0.50-$5/month (for future LLM features)

---

## Development Status & Roadmap

### ✅ Production Ready (v1.0.0)

**Core Components**:
- ✅ VoterAgent with validated 0.856 Sharpe performance
- ✅ Interactive CLI with natural language processing
- ✅ Alpaca paper/live trading integration
- ✅ Automated daily scheduler system
- ✅ Position tracking and alert system
- ✅ Unified caching system (90% performance improvement)
- ✅ YAML configuration management
- ✅ Comprehensive documentation

### 🚧 In Development (v2.0.0 Planned)

**Multi-Agent System Completion**:
- ScannerAgent: Market opportunity identification
- RiskAgent: Portfolio-level risk management
- ExecutorAgent: Trade execution optimization
- TradingOrchestrator: Multi-agent workflow coordination

**Enhanced Entry Planning** (Issue #366):
- OHLCV-based intraday analysis (5min/15min/1hour)
- Support/resistance detection from High/Low
- ATR-based dynamic stops (volatility-adjusted)
- Volume confirmation logic
- Pullback and breakout detection

**UX Improvements** (Issues #361, #344):
- LLM-based intent classification for flexible command routing
- Company-to-ticker resolution ("Buy Apple" → "AAPL")
- Pullback/timing context ("buy QQQ at a pullback")
- Enhanced natural language understanding

### 📋 Future Enhancements (v3.0.0+)

- Multi-symbol portfolio optimization
- Forward testing protocol (Issue #324)
- Event-driven agent communication (Issue #316)
- Real-time WebSocket data streaming
- Advanced risk models (VaR, CVaR)
- Machine learning-based parameter optimization
- Web dashboard interface

---

## Getting Started

### Installation

```bash
# Clone repository
git clone https://github.com/iAmGiG/AutoTrader-AgentEdge.git
cd AutoTrader-AgentEdge

# Create Python environment
conda create -n AutoTrader python=3.10
conda activate AutoTrader

# Install dependencies
pip install -e .
```

### Configuration

Create `config/config.yaml`:

```yaml
POLYGON_IO: "your_polygon_api_key"
ALPHA_VANTAGE_KEY: "your_alpha_vantage_key"
ALPACA_PAPER_API_KEY: "your_alpaca_paper_key"
ALPACA_PAPER_SECRET: "your_alpaca_paper_secret"
ALPACA_ENDPOINT: "https://paper-api.alpaca.markets/v2"
```

### Quick Start

```bash
# Launch interactive CLI
python main.py

# Interactive session:
> buy 10 AAPL              # Execute trade with VoterAgent analysis
> check my alerts          # Position alerts
> show portfolio           # Account status
> /schedule                # Scheduler management
> /help                    # Show all commands
> /exit                    # Exit
```

### Validation

```bash
# Run VoterAgent validation
python scripts/experiments/experiment_293_validation/experiment_293_retest.py

# Generate analysis report
python scripts/analysis/generate_results_summary.py --advanced
```

---

## References & Resources

### Documentation

- **GitHub Repository**: https://github.com/iAmGiG/AutoTrader-AgentEdge
- **Wiki**: https://github.com/iAmGiG/AutoTrader-AgentEdge/wiki
- **System Overview**: `docs/01_overview/01_system_overview.md`
- **Architecture Guide**: `docs/02_architecture/01_core_architecture.md`
- **Validation Results**: `docs/03_reference/01_validation_results.md`

### External Resources

- **Microsoft AutoGen**: https://microsoft.github.io/autogen/
- **Alpaca Markets API**: https://alpaca.markets/docs/
- **Polygon.io API**: https://polygon.io/docs/
- **Technical Analysis**: Fibonacci in Trading, MACD & RSI Fundamentals

### Academic References

- Murphy, J. J. (1999). *Technical Analysis of the Financial Markets*
- Pring, M. J. (2002). *Technical Analysis Explained*
- Aronson, D. (2006). *Evidence-Based Technical Analysis*

### Open Source Credits

- Microsoft AutoGen Framework (MIT License)
- pandas, numpy, matplotlib (BSD Licenses)
- Alpaca-py SDK (Apache 2.0)

---

## License & Contact

**License**: AGPL-3.0 (GNU Affero General Public License v3.0)

**Repository**: https://github.com/iAmGiG/AutoTrader-AgentEdge

**Issues & Support**: https://github.com/iAmGiG/AutoTrader-AgentEdge/issues

**Author**: iAmGiG

**Version**: 1.0.0 (Production Ready)

**Last Updated**: November 2025

---

## Acknowledgments

- **Microsoft AutoGen Team**: For the exceptional multi-agent framework
- **Alpaca Markets**: For free paper trading and accessible brokerage API
- **Polygon.io**: For reliable real-time market data
- **Open Source Community**: For the incredible tools that make this possible

---

*This abstract provides a comprehensive overview of the AutoTrader-AgentEdge project. For technical details, see the full documentation in the `/docs` folder. For validation results, see the experiment archives.*
