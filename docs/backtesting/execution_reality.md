# Execution Reality: Slippage, Commissions, and Market Impact

## Overview

Real-world execution costs that academia often ignores but significantly impact trading performance. These costs can turn a profitable strategy on paper into a losing one in practice.

## Types of Execution Costs

### 1. Commission Structure

#### Per-Share Commissions
```python
def calculate_commission(shares, price_per_share):
    """Calculate total commission for stock trades"""
    
    # Typical retail broker structure
    base_commission = 0.005 * shares  # $0.005 per share
    
    # Regulatory fees
    sec_fee = (shares * price_per_share) * 0.0000278  # SEC fee
    finra_fee = shares * 0.000119  # FINRA TAF
    
    # Exchange fees (varies by exchange and order type)
    exchange_fee = shares * 0.0030  # Typical exchange fee
    
    total_commission = base_commission + sec_fee + finra_fee + exchange_fee
    
    # Minimum commission (some brokers)
    return max(total_commission, 1.00)  # $1 minimum
```

#### Options Commissions
```python
def calculate_option_commission(contracts):
    """Calculate commission for options trades"""
    
    # Per-contract pricing
    base_commission = contracts * 0.65  # $0.65 per contract
    
    # Exchange and regulatory fees
    exchange_fee = contracts * 0.50  # Varies by exchange
    orf_fee = contracts * 0.0388  # Options Regulatory Fee
    
    return base_commission + exchange_fee + orf_fee
```

### 2. Slippage Models

#### Fixed Slippage
```python
def fixed_slippage(price, side, slippage_bps=10):
    """Simple fixed slippage in basis points"""
    slippage_pct = slippage_bps / 10000
    
    if side == 'buy':
        return price * (1 + slippage_pct)
    else:  # sell
        return price * (1 - slippage_pct)
```

#### Volatility-Adjusted Slippage
```python
def volatility_slippage(price, volatility, side):
    """Slippage increases with volatility"""
    # Base slippage + volatility component
    base_slippage = 0.0005  # 5 bps base
    vol_component = volatility * 0.02  # 2% of volatility
    
    total_slippage = base_slippage + vol_component
    
    if side == 'buy':
        return price * (1 + total_slippage)
    else:
        return price * (1 - total_slippage)
```

#### Volume-Adjusted Slippage
```python
def volume_slippage(price, order_size, avg_volume, side):
    """Slippage based on order size relative to volume"""
    
    # Calculate participation rate
    participation = order_size / avg_volume
    
    # Slippage increases with participation
    if participation < 0.01:  # Less than 1% of volume
        slippage = 0.0005  # 5 bps
    elif participation < 0.05:  # 1-5% of volume
        slippage = 0.0010  # 10 bps
    elif participation < 0.10:  # 5-10% of volume
        slippage = 0.0025  # 25 bps
    else:  # More than 10% of volume
        slippage = 0.0050 + (participation - 0.10) * 0.05
    
    if side == 'buy':
        return price * (1 + slippage)
    else:
        return price * (1 - slippage)
```

### 3. Market Impact Models

#### Linear Market Impact
```python
def linear_market_impact(order_size, avg_volume, volatility):
    """Almgren-Chriss style linear impact"""
    
    # Temporary impact (dissipates after trade)
    participation = order_size / avg_volume
    temp_impact = 0.1 * volatility * np.sqrt(participation)
    
    # Permanent impact (moves the market)
    perm_impact = 0.01 * participation
    
    return {
        'temporary': temp_impact,
        'permanent': perm_impact,
        'total': temp_impact + perm_impact
    }
```

#### Square-Root Market Impact
```python
def sqrt_market_impact(order_size, avg_volume, spread):
    """Square-root law of market impact"""
    
    participation = order_size / avg_volume
    
    # Impact proportional to square root of size
    impact = spread * np.sqrt(participation) * 2.0
    
    return impact
```

## Execution Cost Framework

### RealWorldExecutor Class
```python
class RealWorldExecutor:
    def __init__(self, config):
        self.commission_schedule = config['commissions']
        self.slippage_model = config['slippage_model']
        self.market_impact_model = config['market_impact_model']
        self.failure_rate = config.get('failure_rate', 0.001)  # 0.1% failure
        
    def execute_trade(self, signal, market_data):
        """Execute trade with real-world costs"""
        
        # Check for execution failure
        if np.random.random() < self.failure_rate:
            return ExecutionResult(
                status='failed',
                reason='Order rejected or system failure'
            )
        
        # Calculate actual quantity (partial fills)
        requested_qty = signal.quantity
        actual_qty = self.apply_partial_fill(requested_qty, market_data)
        
        # Calculate execution price with slippage
        base_price = signal.price
        slippage = self.calculate_slippage(
            base_price, 
            actual_qty,
            market_data['volatility'],
            market_data['avg_volume'],
            signal.side
        )
        
        # Apply market impact
        market_impact = self.calculate_market_impact(
            actual_qty,
            market_data['avg_volume'],
            market_data['spread']
        )
        
        # Final execution price
        if signal.side == 'buy':
            exec_price = base_price + slippage + market_impact
        else:
            exec_price = base_price - slippage - market_impact
        
        # Calculate commission
        commission = self.calculate_commission(
            actual_qty,
            exec_price,
            signal.asset_type
        )
        
        return ExecutionResult(
            status='success',
            quantity=actual_qty,
            price=exec_price,
            commission=commission,
            slippage=slippage,
            market_impact=market_impact,
            total_cost=commission + (slippage + market_impact) * actual_qty
        )
    
    def apply_partial_fill(self, requested_qty, market_data):
        """Simulate partial fills based on liquidity"""
        available_liquidity = market_data['bid_size'] if selling else market_data['ask_size']
        
        if requested_qty <= available_liquidity:
            return requested_qty
        else:
            # Partial fill with some randomness
            fill_rate = np.random.uniform(0.7, 0.95)
            return int(requested_qty * fill_rate)
```

## Cost Analysis Framework

### Transaction Cost Analysis (TCA)
```python
class TransactionCostAnalyzer:
    def __init__(self):
        self.trades = []
        
    def analyze_trade(self, trade):
        """Detailed cost breakdown for a trade"""
        
        costs = {
            'commission': trade.commission,
            'spread_cost': trade.spread_cost,
            'slippage': trade.slippage_cost,
            'market_impact': trade.market_impact_cost,
            'total': trade.total_cost
        }
        
        # Calculate cost in basis points
        costs_bps = {
            k: (v / (trade.quantity * trade.price)) * 10000 
            for k, v in costs.items()
        }
        
        return {
            'absolute_costs': costs,
            'costs_bps': costs_bps,
            'execution_quality': self.rate_execution(costs_bps['total'])
        }
    
    def rate_execution(self, total_cost_bps):
        """Rate execution quality"""
        if total_cost_bps < 5:
            return 'Excellent'
        elif total_cost_bps < 10:
            return 'Good'
        elif total_cost_bps < 20:
            return 'Fair'
        else:
            return 'Poor'
```

## Practical Examples

### Example 1: Small Retail Trade
```python
# Trading 100 shares of AAPL at $150
trade = {
    'symbol': 'AAPL',
    'quantity': 100,
    'price': 150.00,
    'avg_volume': 50_000_000,
    'spread': 0.01,
    'volatility': 0.25
}

# Costs breakdown:
# Commission: $0.50 (100 * $0.005)
# SEC fee: $0.04 (100 * 150 * 0.0000278)
# Slippage: $0.75 (5 bps on $15,000)
# Market impact: Negligible
# Total cost: $1.29 (8.6 bps)
```

### Example 2: Large Institutional Trade
```python
# Trading 100,000 shares of SPY at $400
trade = {
    'symbol': 'SPY',
    'quantity': 100_000,
    'price': 400.00,
    'avg_volume': 80_000_000,
    'spread': 0.01,
    'volatility': 0.15
}

# Costs breakdown:
# Commission: $500 (100,000 * $0.005)
# SEC fee: $111.20
# Slippage: $4,000 (10 bps due to size)
# Market impact: $2,000 (5 bps permanent impact)
# Total cost: $6,611.20 (16.5 bps)
```

## Impact on Strategy Performance

### Before/After Cost Analysis

| Strategy | Gross Return | Net Return | Cost Impact |
|----------|--------------|------------|-------------|
| High Frequency (Daily) | 25% | 8% | -17% |
| Swing Trading (Weekly) | 18% | 14% | -4% |
| Position Trading (Monthly) | 15% | 13.5% | -1.5% |

### Break-Even Analysis
```python
def calculate_breakeven(avg_trade_size, commission_per_share, spread, slippage):
    """Calculate minimum profit needed to break even"""
    
    # Round-trip costs
    commission_cost = 2 * commission_per_share
    spread_cost = spread
    slippage_cost = 2 * slippage
    
    total_cost_pct = (commission_cost / avg_trade_size + 
                      spread_cost + slippage_cost)
    
    return {
        'min_profit_pct': total_cost_pct,
        'min_profit_bps': total_cost_pct * 10000,
        'annual_cost': total_cost_pct * trades_per_year
    }
```

## Optimization Strategies

### 1. Reduce Trading Frequency
- Fewer trades = lower total commission impact
- Focus on higher-conviction signals
- Increase minimum profit targets

### 2. Improve Execution Timing
- Trade during liquid hours (first/last hour)
- Avoid market open volatility
- Use limit orders when possible

### 3. Smart Order Routing
- Split large orders across time
- Use algorithmic execution (VWAP, TWAP)
- Access multiple liquidity sources

### 4. Position Sizing Optimization
```python
def optimal_position_size(signal_strength, volatility, execution_costs):
    """Kelly Criterion adjusted for execution costs"""
    
    # Expected return after costs
    gross_return = signal_strength * volatility
    net_return = gross_return - execution_costs
    
    # Only trade if profitable after costs
    if net_return <= 0:
        return 0
    
    # Kelly fraction adjusted for costs
    win_rate = 0.55  # Historical win rate
    avg_win = net_return
    avg_loss = volatility
    
    kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    
    # Conservative adjustment
    return min(kelly_fraction * 0.25, 0.20)  # Max 20% position
```

## Configuration Example

```json
{
    "execution_config": {
        "commissions": {
            "stocks": {
                "per_share": 0.005,
                "minimum": 1.00
            },
            "options": {
                "per_contract": 0.65
            },
            "regulatory_fees": {
                "sec_rate": 0.0000278,
                "finra_taf": 0.000119
            }
        },
        
        "slippage_model": {
            "type": "hybrid",
            "base_slippage_bps": 5,
            "volatility_multiplier": 0.02,
            "volume_impact": true
        },
        
        "market_impact_model": {
            "type": "square_root",
            "temporary_impact_factor": 0.1,
            "permanent_impact_factor": 0.01
        },
        
        "execution_constraints": {
            "max_participation_rate": 0.10,
            "min_order_size": 100,
            "partial_fill_threshold": 0.70
        }
    }
}
```

## Best Practices

1. **Always Model Costs**: Never backtest without execution costs
2. **Be Conservative**: Overestimate costs rather than underestimate
3. **Track Actual Costs**: Compare model to real execution data
4. **Adapt to Market Conditions**: Costs vary with volatility and liquidity
5. **Consider Order Types**: Market orders have higher slippage than limit orders
6. **Time Your Trades**: Execution quality varies throughout the day
7. **Size Appropriately**: Larger positions have disproportionate impact