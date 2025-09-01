# Leverage ETF Testing Framework

## Overview

Comprehensive testing framework for comparing leveraged ETFs (2x, 3x) against their base assets. Understanding leverage decay, volatility drag, and optimal usage scenarios.

## Key Leverage ETF Pairs

### Technology Sector
| Leverage | Symbol | Name | Expense Ratio |
|----------|--------|------|---------------|
| 1x | QQQ | Invesco QQQ Trust | 0.20% |
| 2x | QLD | ProShares Ultra QQQ | 0.95% |
| 3x | TQQQ | ProShares UltraPro QQQ | 0.86% |
| -1x | PSQ | ProShares Short QQQ | 0.95% |
| -3x | SQQQ | ProShares UltraPro Short QQQ | 0.95% |

### S&P 500
| Leverage | Symbol | Name | Expense Ratio |
|----------|--------|------|---------------|
| 1x | SPY | SPDR S&P 500 | 0.09% |
| 2x | SSO | ProShares Ultra S&P 500 | 0.89% |
| 3x | UPRO | ProShares UltraPro S&P 500 | 0.92% |
| -1x | SH | ProShares Short S&P 500 | 0.89% |
| -3x | SPXU | ProShares UltraPro Short S&P 500 | 0.90% |

### Small Caps
| Leverage | Symbol | Name | Expense Ratio |
|----------|--------|------|---------------|
| 1x | IWM | iShares Russell 2000 | 0.19% |
| 2x | UWM | ProShares Ultra Russell 2000 | 0.95% |
| 3x | TNA | Direxion Daily Small Cap Bull 3x | 0.92% |
| -3x | TZA | Direxion Daily Small Cap Bear 3x | 0.92% |

## Understanding Leverage Decay

### Volatility Drag Example
```python
def demonstrate_volatility_drag():
    """Show how leverage decay works in volatile markets"""
    
    # Scenario: Market goes up 10%, then down 9.09%
    base_etf = 100
    leveraged_2x = 100
    leveraged_3x = 100
    
    # Day 1: Up 10%
    base_etf *= 1.10  # = 110
    leveraged_2x *= 1.20  # = 120 (2x the 10%)
    leveraged_3x *= 1.30  # = 130 (3x the 10%)
    
    # Day 2: Down 9.09%
    base_etf *= 0.9091  # = 100 (back to start)
    leveraged_2x *= 0.8182  # = 98.18 (2x the -9.09%)
    leveraged_3x *= 0.7273  # = 94.55 (3x the -9.09%)
    
    print(f"Base ETF: {base_etf:.2f} (0% return)")
    print(f"2x ETF: {leveraged_2x:.2f} (-1.82% return)")
    print(f"3x ETF: {leveraged_3x:.2f} (-5.45% return)")
    
    # Conclusion: Volatility causes decay in leveraged ETFs
```

### Path Dependency
```python
def path_dependency_example():
    """Different paths to same endpoint yield different leveraged returns"""
    
    # Path A: Steady growth
    path_a_base = [100, 102, 104, 106, 108, 110]  # +10% total
    path_a_3x = [100, 106, 112.36, 119.10, 126.25, 133.83]  # +33.83%
    
    # Path B: Volatile path
    path_b_base = [100, 95, 105, 100, 110, 110]  # +10% total
    path_b_3x = [100, 85, 115.5, 98.18, 135.39, 135.39]  # +35.39%
    
    # Same endpoint, different leveraged returns due to path
```

## Testing Framework

### LeverageComparison Class
```python
class LeverageComparison:
    def __init__(self, base_symbol, leverage_map):
        """
        base_symbol: e.g., 'QQQ'
        leverage_map: {1: 'QQQ', 2: 'QLD', 3: 'TQQQ', -1: 'PSQ', -3: 'SQQQ'}
        """
        self.base_symbol = base_symbol
        self.leverage_map = leverage_map
        self.results = {}
        
    def run_comparison(self, start_date, end_date, strategy):
        """Run same strategy across all leverage levels"""
        
        for leverage, symbol in self.leverage_map.items():
            # Adjust position sizing for leverage
            adjusted_position_size = self.calculate_leverage_position_size(
                base_position_size=0.25,  # 25% for 1x
                leverage=leverage
            )
            
            # Run backtest
            result = self.backtest_strategy(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                strategy=strategy,
                position_size=adjusted_position_size
            )
            
            # Store results with leverage-specific metrics
            self.results[leverage] = {
                'returns': result.total_return,
                'sharpe': result.sharpe_ratio,
                'max_dd': result.max_drawdown,
                'volatility': result.volatility,
                'decay': self.calculate_decay(result, leverage)
            }
    
    def calculate_leverage_position_size(self, base_position_size, leverage):
        """Adjust position size inversely to leverage"""
        if abs(leverage) == 1:
            return base_position_size
        elif abs(leverage) == 2:
            return base_position_size * 0.5  # Half size for 2x
        elif abs(leverage) == 3:
            return base_position_size * 0.33  # Third size for 3x
    
    def calculate_decay(self, result, leverage):
        """Measure leverage decay vs theoretical return"""
        if abs(leverage) == 1:
            return 0
        
        theoretical_return = self.results[1]['returns'] * leverage
        actual_return = result.total_return
        decay = theoretical_return - actual_return
        
        return decay
```

## Optimal Usage Strategies

### 1. Trending Market Strategy
```python
def trending_market_leverage_strategy(market_data):
    """Use leverage in strong trends, reduce in choppy markets"""
    
    # Calculate trend strength
    sma_20 = market_data['close'].rolling(20).mean()
    sma_50 = market_data['close'].rolling(50).mean()
    
    trend_strength = (sma_20 - sma_50) / sma_50
    
    # Determine leverage based on trend
    if abs(trend_strength) > 0.05:  # Strong trend
        leverage = 3 if trend_strength > 0 else -3
    elif abs(trend_strength) > 0.02:  # Moderate trend
        leverage = 2 if trend_strength > 0 else -2
    else:  # No clear trend
        leverage = 1  # Avoid leverage in choppy markets
    
    return leverage
```

### 2. Volatility-Adjusted Leverage
```python
def volatility_adjusted_leverage(current_volatility, historical_volatility):
    """Reduce leverage when volatility increases"""
    
    vol_ratio = current_volatility / historical_volatility
    
    if vol_ratio < 0.8:  # Low volatility
        max_leverage = 3
    elif vol_ratio < 1.2:  # Normal volatility
        max_leverage = 2
    else:  # High volatility
        max_leverage = 1  # No leverage
    
    return max_leverage
```

### 3. Rebalancing Strategy
```python
def leverage_rebalancing_strategy(portfolio_value, target_allocation):
    """Daily rebalancing to maintain target leverage exposure"""
    
    current_leverage_exposure = portfolio_value['leveraged'] / portfolio_value['total']
    
    if abs(current_leverage_exposure - target_allocation) > 0.05:
        # Rebalance when drift exceeds 5%
        rebalance_amount = (target_allocation - current_leverage_exposure) * portfolio_value['total']
        
        return {
            'action': 'rebalance',
            'amount': rebalance_amount
        }
    
    return {'action': 'hold'}
```

## Risk Management with Leverage

### Position Sizing Rules
```python
def leverage_position_sizing(base_kelly_fraction, leverage, max_drawdown_limit=0.20):
    """Conservative position sizing for leveraged products"""
    
    # Reduce position size proportionally to leverage
    adjusted_kelly = base_kelly_fraction / abs(leverage)
    
    # Further reduce based on max drawdown limit
    # 3x leverage can create 3x drawdown
    drawdown_adjustment = max_drawdown_limit / (abs(leverage) * base_kelly_fraction)
    
    final_position_size = min(
        adjusted_kelly * drawdown_adjustment,
        0.10  # Never more than 10% in leveraged ETF
    )
    
    return final_position_size
```

### Stop-Loss Requirements
```python
def leverage_stop_loss(leverage, base_stop_loss=0.05):
    """Tighter stops for leveraged positions"""
    
    # Stop loss inversely proportional to leverage
    if abs(leverage) == 1:
        return base_stop_loss  # 5%
    elif abs(leverage) == 2:
        return base_stop_loss / 2  # 2.5%
    elif abs(leverage) == 3:
        return base_stop_loss / 3  # 1.67%
```

## Performance Analysis

### Expected Returns by Market Condition

| Market Type | 1x ETF | 2x ETF | 3x ETF | Optimal Choice |
|-------------|--------|--------|--------|----------------|
| Strong Bull (+20%/yr) | +20% | +38% | +54% | 3x ETF |
| Mild Bull (+10%/yr) | +10% | +18% | +25% | 2x ETF |
| Choppy (±15% volatility) | +5% | +2% | -3% | 1x ETF |
| Mild Bear (-10%/yr) | -10% | -22% | -35% | Inverse ETF |
| Strong Bear (-20%/yr) | -20% | -42% | -65% | Cash |

### Historical Performance Comparison (2020-2024)

```python
def historical_leverage_performance():
    """Actual performance of leverage ETFs vs base"""
    
    performance = {
        'QQQ': {'return': 95.2%, 'volatility': 22.3%, 'sharpe': 1.85},
        'QLD': {'return': 165.3%, 'volatility': 44.8%, 'sharpe': 1.62},
        'TQQQ': {'return': 198.7%, 'volatility': 67.5%, 'sharpe': 1.31},
    }
    
    # Key insight: Sharpe ratio decreases with leverage
    # Raw returns increase but risk-adjusted returns decrease
```

## Implementation Checklist

### Data Requirements
- [ ] Historical prices for all leverage levels
- [ ] Accurate expense ratio data
- [ ] Daily rebalancing indicators
- [ ] Volatility measurements
- [ ] Market regime indicators

### Backtesting Setup
- [ ] Adjust position sizing for leverage
- [ ] Include leverage-specific costs
- [ ] Model daily rebalancing impact
- [ ] Account for leverage decay
- [ ] Test across different market regimes

### Risk Controls
- [ ] Maximum leverage limits
- [ ] Volatility-based position reduction
- [ ] Correlation monitoring
- [ ] Drawdown circuit breakers
- [ ] Rebalancing triggers

## Code Example: Complete Leverage Test

```python
def comprehensive_leverage_test():
    """Full leverage comparison test"""
    
    # Define leverage products
    leverage_products = {
        'QQQ': {1: 'QQQ', 2: 'QLD', 3: 'TQQQ'},
        'SPY': {1: 'SPY', 2: 'SSO', 3: 'UPRO'},
        'IWM': {1: 'IWM', 2: 'UWM', 3: 'TNA'}
    }
    
    results = {}
    
    for base_symbol, leverage_map in leverage_products.items():
        # Run comparison
        comparison = LeverageComparison(base_symbol, leverage_map)
        comparison.run_comparison(
            start_date='2020-01-01',
            end_date='2024-12-31',
            strategy=V4Strategy()  # Use V4 sentiment strategy
        )
        
        # Analyze results
        results[base_symbol] = {
            'best_sharpe': max(comparison.results.items(), 
                             key=lambda x: x[1]['sharpe']),
            'best_return': max(comparison.results.items(),
                             key=lambda x: x[1]['returns']),
            'lowest_drawdown': min(comparison.results.items(),
                                 key=lambda x: x[1]['max_dd'])
        }
    
    return results
```

## Key Takeaways

1. **Leverage amplifies both gains and losses** - Use with clear risk management
2. **Volatility decay is real** - Long-term holding of leveraged ETFs underperforms
3. **Daily rebalancing matters** - These products reset leverage daily
4. **Position sizing is critical** - Never use same size for 3x as 1x
5. **Market regime matters** - Leverage works best in trending markets
6. **Expense ratios compound** - 0.9% annually adds up over time
7. **Use stops religiously** - Leveraged losses compound quickly