# Configuration System Experiment

**Research Question**: How can we make trading parameters flexible and adjustable without code changes?

## Problem Statement
Trading parameters are currently hardcoded throughout the codebase:
- MACD(13/34/8) hardcoded in multiple files
- RSI(14/30/70) fixed in agent code  
- Exit strategies not configurable
- No way to A/B test different parameters

## Solution: Centralized Configuration System

### Benefits Demonstrated
1. **Easy Parameter Tuning** - Change JSON, not code
2. **A/B Testing** - Run parallel configs
3. **Environment-Specific Settings** - dev/test/prod configs
4. **Audit Trail** - Version control parameter changes
5. **Single Source of Truth** - All components use same config

## Scripts

### `config_usage_demo.py`
**Purpose**: Demonstrate configuration system capabilities
**Features**:
- Load parameters from JSON
- Compare exit strategies
- Show dynamic parameter adjustment
- Explain production benefits

## Configuration Files

### `/config/trading_config.json`
Central configuration with:
- MACD parameters (13/34/8)
- RSI parameters (14/30/70)
- Exit strategies (balanced, conservative, aggressive)
- Expected values and breakeven rates

### `/config/trading_config.py`
Configuration management class with:
- Type-safe parameter loading
- Validation methods
- Environment switching
- Dynamic updates

## Key Insights from Demo

### Exit Strategy Comparison
| Strategy | TP | SL | EV@50% | Breakeven |
|----------|----|----|--------|-----------|
| Balanced | 8% | 5% | +1.5% | 38.5% |
| Conservative | 6% | 8% | -1.0% | 57.1% |
| Aggressive | 10% | 3% | +3.5% | 23.1% |

**Clear Winner**: Balanced strategy has best expected value at realistic win rates.

### Usage Example
```python
from config.trading_config import get_config

config = get_config()
macd = config.get_macd_config()
exit_cfg = config.get_exit_config('balanced')

# Use in strategy
fast_ema = prices.ewm(span=macd.fast).mean()
```

## Production Benefits

### Before Configuration System
```python
# Scattered hardcoded values
def calculate_macd(prices, fast=13, slow=34, signal=8):
    # Parameters buried in code
```

### After Configuration System
```python
# Centralized, flexible parameters
config = get_config()
macd = config.get_macd_config()
def calculate_macd(prices, fast=macd.fast, slow=macd.slow, signal=macd.signal):
    # Parameters from central config
```

## Recommendations

1. **Default to Balanced Exits** (8% TP / 5% SL)
2. **Avoid Conservative Exits** (negative expected value)
3. **Use Configuration System** for all future parameter management
4. **Version Control Configs** to track parameter evolution

## Implementation Status
✅ Configuration files created
✅ Configuration manager implemented  
✅ Usage demonstration complete
⏳ **Issue #303**: Integration with existing codebase

## Related Issues
- Issue #303 - Configuration system implementation
- Issue #293 - Uses these validated parameters

## Usage
```bash
python config_usage_demo.py
```

This demonstrates the complete configuration system with parameter management, strategy comparison, and production benefits.