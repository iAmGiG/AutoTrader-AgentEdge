# Technical Agent Documentation

**Last Updated**: 2025-07-11

## Overview

The Technical Agent (`TechAgent`) is responsible for analyzing market data using technical indicators and providing trading signals based on price patterns and momentum indicators.

## Key Components

### 1. Technical Indicators

The agent uses various technical indicators from the `indicator_library`:

| Indicator | Purpose | Key Values |
|-----------|---------|------------|
| **MACD** | Momentum and trend | MACD line, Signal line, Histogram |
| **RSI** | Overbought/Oversold | 0-100 scale |
| **Bollinger Bands** | Volatility | Upper/Middle/Lower bands |
| **EMA/SMA** | Moving averages | Various periods |
| **Supertrend** | Trend direction | Price levels |

### 2. MACD Implementation (Critical)

**IMPORTANT**: As of 2025-07-11, the MACD calculation has been corrected:

```python
# CORRECT implementation (current):
macd_df["MACD"] = macd_df["MACD_line"]  # Use MACD line for signals

# INCORRECT implementation (previous):
macd_df["MACD"] = macd_df["MACD_line"] - macd_df["MACD_signal"]  # This was the histogram!
```

#### MACD Components:
- **MACD Line**: EMA(12) - EMA(26) - The primary signal line
- **Signal Line**: EMA(9) of MACD line - Used for crossover signals
- **Histogram**: MACD line - Signal line - Shows convergence/divergence

#### Why This Matters:
The strategy agent expects the MACD value to be the MACD line itself, not the histogram. Using the histogram led to incorrect trading signals because:
1. Histogram values are much smaller in magnitude
2. Histogram represents the difference between MACD and signal, not the trend itself
3. Standard MACD trading strategies use the MACD line value

### 3. Data Flow

1. **Input**: Market data (OHLCV) from various sources
2. **Processing**: 
   - Calculate requested indicators
   - Always includes MACD for downstream consistency
   - Formats data for LLM analysis
3. **Output**: Technical analysis with signal strength assessment

### 4. LLM Integration

The agent uses GPT-4 to:
- Interpret technical patterns
- Identify support/resistance levels
- Assess signal strength
- Provide narrative analysis of market conditions

### 5. Key Methods

#### `generate_reply(messages, context)`
Main entry point for technical analysis requests.

#### `_execute_tool(tool_name, tool_args)`
Handles tool execution, particularly `analyze_technicals` which:
- Fetches market data
- Calculates indicators (always includes MACD)
- Returns formatted analysis

## Configuration

```python
TECHNICAL_LLM_CONFIG = {
    "temperature": 0.1,  # Low temperature for consistent analysis
    "max_tokens": 2048,
}
```

## Integration with Strategy

The Technical Agent provides data that the Strategy Agent uses for trading decisions:

```python
# Strategy expects:
technical_data = {
    'macd_today': 0.5,      # MACD line value (NOT histogram)
    'macd_yest': 0.3,       # Previous MACD line value
    'analysis': {...},      # Detailed technical analysis
    'pattern': 'bullish',   # Identified patterns
    'signal_strength': 0.7  # Confidence in signal
}
```

## Common Issues and Solutions

### Issue 1: MACD Values Seem Wrong
**Symptom**: MACD values are very small (near 0) when stock is trending
**Cause**: Using histogram instead of MACD line
**Solution**: Ensure `MACD = MACD_line` not `MACD_line - MACD_signal`

### Issue 2: Missing MACD Data
**Symptom**: Strategy complains about missing MACD
**Cause**: Not enough historical data for calculation
**Solution**: MACD requires 26+ days of data minimum

## Testing

To verify MACD calculations:
```python
# Test with known data
from src.tools.processors.indicator_library import macd
import pandas as pd

# Create test data
test_prices = pd.Series([100, 101, 102, ...])  # 30+ values
result = macd(test_prices)

# Verify
assert 'MACD_line' in result.columns
assert 'MACD_signal' in result.columns
assert result['MACD_line'].iloc[-1] != result['MACD_hist'].iloc[-1]
```

## Future Improvements

1. Add more sophisticated pattern recognition
2. Implement multi-timeframe analysis
3. Add volume-based indicators
4. Enhance LLM prompts for better pattern detection