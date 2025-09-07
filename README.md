# RH2MAS: Practical Multi-Agent Trading Platform

## Overview

RH2MAS (Reflective Hybrid-Head Multi-Agent System) is a **production-ready trading platform** that combines multi-agent architecture with advanced technical analysis for real-world trading applications. Built on a foundation of proven voting algorithms and enhanced with sophisticated regime detection.

**🚀 Production Features**: 
- **MACD + RSI Voting System** - Core production trading agents with Fibonacci enhancement
- **✅ Enhanced Fibonacci Regime Module v2.0** - Advanced market regime detection with statistical validation
- **Optimized Parameters** - Validated MACD (8/21/5) and EMA filtering (21-period, 2% threshold)
- Multi-indicator ensemble voting with confidence-based decisions
- Real-time paper trading with Alpaca API integration (coming soon)
- Advanced risk management and portfolio optimization
- Comprehensive performance analytics and backtesting
- 90%+ performance improvements through cache optimization

## Core Production Agents: Multi-Indicator Voting System

The platform implements a production-ready multi-indicator voting system with two core agents:

### Primary Trading Agents

**MACD + RSI Voting Agent** (`macd_rsi_voting_agent.py`):
- **MACD Signal Generation**: Optimized 8/21/5 parameters (fast/slow/signal)
- **RSI Momentum Analysis**: 14-period RSI with 30/70 oversold/overbought levels
- **Fibonacci EMA Filter**: 21-period EMA with 2% threshold for signal validation
- **Consensus Voting**: Strong signals when both indicators agree, weak when only one signals
- **Validated Performance**: 9.5% average return, 0.678 Sharpe ratio (20-month validation)

**Fibonacci Voting Agent** (`fibonacci_voting_agent.py`):
- **Enhanced Regime Detection**: 7 market regimes (STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR, VOLATILE, RANGE_BOUND)
- **Statistical Validation**: Garman-Klass volatility estimation, ADX-based trend strength
- **Dynamic Position Sizing**: Kelly Criterion-inspired sizing based on regime confidence
- **Adaptive Filtering**: Regime-aware signal filtering with confidence-based logic
- **Proven Results**: +3.36% excess return vs buy-and-hold, superior risk management

### Performance Architecture

**Cache-Optimized Data Pipeline**:
1. **UnifiedCacheManager**: 90%+ speed improvement through intelligent caching
2. **Multi-Source Data**: Polygon.io primary, Alpha Vantage fallback
3. **Real-time Processing**: Instant indicator calculations with cached market data

**Statistical Validation Framework**:
- Walk-forward analysis preventing look-ahead bias
- Monte Carlo simulation (100+ runs) for robustness testing
- Multi-market validation across bull, bear, sideways, volatile conditions
- Professional risk metrics (Sharpe, Calmar, maximum drawdown)

## Production Architecture

### Core Components

1. **MACD+RSI Voting Agent**: Primary production trading agent with Fibonacci enhancement
2. **Fibonacci Voting Agent**: Advanced regime detection with statistical validation
3. **Enhanced Fibonacci Regime Module**: 7-regime market classification in `src/tools/regime_detection/`
4. **UnifiedCacheManager**: High-performance data caching and retrieval system
5. **Statistical Validation Suite**: Comprehensive backtesting and validation framework
6. **Multi-Indicator Framework**: Extensible architecture for additional technical indicators

*Future Components (In Development)*:
- **RiskAgent**: Comprehensive risk management with position sizing and portfolio controls
- **ExecutionAgent**: Alpaca API integration for paper/live trading
- **AlertAgent**: Multi-channel notifications and monitoring

### Data Infrastructure

**Trading APIs**:
- **Alpaca**: Paper and live trading execution (real-time order management)
- **Polygon.io**: Real-time and historical market data (WebSocket + REST)
- **Alpha Vantage**: Fallback market data source

**Technical Analysis Tools**:
- **Enhanced Fibonacci Regime Module**: Advanced market regime detection
- **Multi-Indicator Suite**: MACD, RSI, EMA filters with validated parameters
- **Statistical Validation**: Walk-forward analysis, Monte Carlo simulation

**Data Management**:
- **UnifiedCacheManager**: 90%+ performance improvement through intelligent caching
- **Multi-Source Aggregation**: Polygon.io primary, Alpha Vantage fallback
- **Real-time Pipeline**: WebSocket data streaming for live decision making (coming soon)

## Installation

```bash
# Python 3.10+ required
conda create -n RH2MAS python=3.10
conda activate RH2MAS

# Install dependencies
pip install -e .
```

## Configuration

Create `config/config.json` with required API keys:

```json
{
  "ALPACA_API_KEY": "...",         // Paper/live trading
  "ALPACA_SECRET_KEY": "...",      // Trading authentication
  "ALPACA_BASE_URL": "paper-api.alpaca.markets",  // Paper trading URL
  "OPENAI_API_KEY": "sk-...",      // V4 LLM analysis
  "POLYGON_API_KEY": "...",        // Real-time market data
  "ALPHA_VANTAGE_KEY": "...",      // Fallback market data
  "GOOGLE_API_KEY": "...",         // News sentiment analysis
  "GOOGLE_CSE_ID": "..."           // Custom search engine ID
}
```

Note: This file is excluded from version control for security.

## Usage

### Production Trading (Coming Soon)

```bash
# Start paper trading with ensemble strategies
python scripts/trading/live_trading.py --mode paper

# Real-time performance monitoring
python scripts/monitoring/dashboard.py

# Portfolio analysis and risk metrics
python scripts/analysis/portfolio_analysis.py
```

### Production Voting System

```bash
# Test production voting agents
python test_phase1_integration.py

# Basic voting system demo
python examples/basic_voting_demo.py

# Fibonacci experiments and validation
python scripts/fibonacci_experiments/statistical_validation.py

# Parameter optimization
python scripts/fibonacci_experiments/fibonacci_permutation_tester.py
```

### Risk Management and Alerts

```bash
# Configure risk parameters
python scripts/risk/configure_risk_limits.py

# Test alert system
python scripts/alerts/test_notifications.py
```

## Project Structure

```bash
RH2MAS/
├── src/
│   ├── core/
│   │   ├── agents/       # Production voting agents (MACD+RSI, Fibonacci)
│   │   └── indicators/   # Technical indicators (RSI, MACD, etc.)
│   ├── tools/
│   │   ├── regime_detection/  # Fibonacci regime module and market analysis
│   │   └── data_sources/      # Market data providers and caching
│   ├── data/
│   │   └── cache/        # UnifiedCacheManager and data optimization
│   └── utils/            # Common utilities and helpers
├── scripts/
│   ├── fibonacci_experiments/  # Fibonacci regime testing and validation
│   ├── runs/             # Legacy V0-V4 backtesting (deprecated reference)
│   └── analysis/         # Results analysis and reporting
├── docs/
│   ├── architecture/     # System design and component structure
│   ├── trading/          # Trading setup and risk management
│   └── api/              # API integration guides
├── config/               # API configuration (local only)
├── reports/              # Trading results and performance analytics
└── .cache/               # Unified caching system
```

## Documentation

**Trading Setup**:
- [Trading Guide](docs/trading/setup.md) - Paper and live trading setup
- [Risk Management](docs/trading/risk_management.md) - Position sizing and portfolio controls
- [API Integration](docs/api/alpaca_setup.md) - Alpaca and data provider setup

**System Architecture**:
- [Fibonacci Integration Guide](docs/integration/fibonacci_enhanced_integration_guide.md) - Complete integration documentation
- [Quick Reference](docs/integration/quick_reference.md) - Essential commands and usage
- [Regime Detection Tools](docs/fibonacci_regime/regime_detection_tools.md) - Technical analysis modules

**Reference**:
- [Commands](docs/reference/commands.md) - All available scripts and commands
- [Troubleshooting](docs/reference/troubleshooting.md) - Common issues and solutions

## Development Status

### Production-Ready Foundation ✅

- **✅ Phase 1 Complete**: MACD+RSI voting system with Fibonacci enhancement integrated
- **✅ Validated Parameters**: MACD 8/21/5, EMA21 filter, optimized through extensive testing
- **✅ Enhanced Regime Detection**: 7-regime classification with statistical validation
- **✅ Performance Proven**: +3.36% excess return vs buy-and-hold, superior risk management
- **✅ Cache-Optimized Architecture**: 90%+ performance improvement through intelligent caching
- **✅ Multi-Asset Support**: Stocks, ETFs tested across 20-month validation period
- **✅ Statistical Framework**: Walk-forward analysis, Monte Carlo simulation, professional metrics

### Active Production Development 🚧

**Phase 2: CCI Integration (Next Priority)**:
- CCI Module Development - Add Commodity Channel Index to regime detection
- Multi-Indicator Ensemble - Combine MACD + Fibonacci + CCI signals
- Enhanced Win Rate Target - >55% win rate improvement through multi-indicator consensus
- Extended Validation - Test on AAPL, MSFT, GOOGL, AMZN, TSLA with CCI enhancement

**Future Development**:
- [Alpaca API Integration](https://github.com/iAmGiG/RH2MAS/issues/258) - Paper trading implementation
- [Comprehensive Risk Agent](https://github.com/iAmGiG/RH2MAS/issues/177) - Position sizing and risk controls  
- [Real-time Data Pipeline](https://github.com/iAmGiG/RH2MAS/issues/259) - WebSocket integration
- [Performance Dashboard](https://github.com/iAmGiG/RH2MAS/issues/261) - Real-time monitoring interface

### Project Evolution

Originally developed as an academic research framework, RH2MAS has evolved into a practical trading platform focused on proven technical analysis with statistical validation. The current production system emphasizes validated multi-indicator voting with sophisticated regime detection.

**Key Advantages**:

- **Statistically Validated**: Extensive backtesting with walk-forward analysis and Monte Carlo simulation
- **Production-Ready Agents**: MACD+RSI voting with Fibonacci regime enhancement
- **Superior Performance**: +3.36% excess return vs buy-and-hold with better risk management
- **Extensible Architecture**: Clean separation of agents, tools, and experiments for future enhancement
- **Open Source**: Complete transparency in strategy logic, parameters, and validation results

## License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
