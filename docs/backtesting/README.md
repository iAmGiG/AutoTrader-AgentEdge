# Backtesting Laboratory Documentation

## Overview

The RH2MAS backtesting laboratory is a powerful personal trading research platform designed to test strategies without academic constraints. This documentation covers the enhanced backtesting framework that goes beyond simple historical simulation to include real-world trading conditions.

## Core Philosophy

**Test what actually works, not what's novel for papers.**

- Include transaction costs, slippage, and market impact
- Test across different market regimes and volatility conditions
- Use leverage products and alternative strategies
- Apply practical filters that academia ignores

## Documentation Structure

### Core Backtesting Features

- **[practical_filters.md](practical_filters.md)** - Volume, spread, event-based filters
- **[execution_reality.md](execution_reality.md)** - Slippage, commissions, market impact
- **[leverage_testing.md](leverage_testing.md)** - 2x/3x ETF comparison framework
- **[technical_variations.md](technical_variations.md)** - Indicator parameters and alternatives

### Advanced Analytics

- **[monte_carlo_framework.md](monte_carlo_framework.md)** - Confidence intervals and robustness
- **[parameter_optimization.md](parameter_optimization.md)** - Grid search, genetic algorithms
- **[walk_forward_analysis.md](walk_forward_analysis.md)** - Out-of-sample validation
- **[strategy_tournament.md](strategy_tournament.md)** - Automated strategy comparison

### Performance Analysis

- **[risk_metrics.md](risk_metrics.md)** - Sharpe, Sortino, Calmar, VaR
- **[drawdown_analysis.md](drawdown_analysis.md)** - Maximum and average drawdowns
- **[trade_statistics.md](trade_statistics.md)** - Win rate, profit factor, streaks
- **[regime_analysis.md](regime_analysis.md)** - Bull/bear/sideways performance

## Quick Start Guide

### Basic Backtesting

```bash
# Run standard V0-V4 comparison
python scripts/runs/backtest.py --all-versions

# Test specific strategy
python scripts/runs/backtest.py --version V4 --symbol AAPL
```

### Enhanced Backtesting (Coming Soon)

```bash
# Test with practical filters
python scripts/runs/backtest.py --filters enabled --filter-config filters.json

# Include execution costs
python scripts/runs/backtest.py --slippage 0.1 --commission 0.005

# Test leverage ETFs
python scripts/runs/backtest.py --leverage-comparison QQQ

# Run parameter optimization
python scripts/runs/backtest.py --optimize --method bayesian
```

## Implementation Roadmap

### Phase 1: Reality Checks (Active)
- Issue #264: Practical trading filters
- Issue #267: Execution cost modeling

### Phase 2: Strategy Expansion
- Issue #265: Leverage ETF testing
- Issue #266: Technical indicator variations

### Phase 3: Advanced Analytics
- Issue #268: Monte Carlo framework
- Issue #269: Parameter optimization

### Phase 4: Production Features
- Issue #258-263: Live trading capabilities

## Key Enhancements

### 1. Practical Trading Filters

Filters that academia ignores but traders need:
- **Volume Filter**: Skip low-volume days
- **Spread Filter**: Avoid wide bid-ask spreads
- **Event Filter**: FOMC, earnings, options expiry
- **Gap Filter**: Excessive overnight moves

### 2. Execution Reality

Real costs that impact returns:
- **Slippage**: Price movement during execution
- **Commissions**: $0.005/share + regulatory fees
- **Market Impact**: Large order price effects
- **Partial Fills**: Incomplete order execution

### 3. Leverage Testing

Compare performance across leverage levels:
- QQQ vs QLD (2x) vs TQQQ (3x)
- SPY vs SSO (2x) vs UPRO (3x)
- Risk-adjusted return analysis
- Optimal leverage determination

### 4. Advanced Analytics

Professional-grade analysis tools:
- Monte Carlo confidence intervals
- Walk-forward out-of-sample testing
- Parameter optimization tournaments
- Market regime performance analysis

## Performance Metrics

### Risk-Adjusted Returns
- **Sharpe Ratio**: Return per unit of volatility
- **Sortino Ratio**: Return per unit of downside risk
- **Calmar Ratio**: Return per unit of maximum drawdown
- **Information Ratio**: Active return vs tracking error

### Risk Metrics
- **Value at Risk (VaR)**: Worst expected loss at confidence level
- **Expected Shortfall**: Average loss beyond VaR
- **Maximum Drawdown**: Worst peak-to-trough decline
- **Recovery Time**: Time to recover from drawdowns

### Trading Statistics
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss
- **Average Win/Loss**: Risk-reward per trade
- **Trade Duration**: Average holding period

## Best Practices

1. **Always include transaction costs** in final performance evaluation
2. **Test across multiple market regimes** (bull/bear/sideways)
3. **Use walk-forward analysis** for parameter selection
4. **Apply practical filters** for realistic results
5. **Compare leveraged vs unleveraged** for risk assessment
6. **Run Monte Carlo simulations** for confidence intervals
7. **Document all assumptions** about execution and costs

## Related Documentation

- [V0-V4 Architecture](../architecture/V0-V4_ARCHITECTURE.md) - Core strategy framework
- [Advanced Metrics](../analysis/advanced_metrics_system.md) - Metrics implementation
- [Commands Reference](../reference/commands.md) - All available commands