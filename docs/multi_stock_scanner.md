# Multi-Stock Technical Scanner

## Overview

The Technical Agent has been enhanced with multi-stock scanning capabilities, allowing it to efficiently scan portfolios of stocks for MACD histogram entry signals. This is a key component of the new architecture pivot where the system focuses on simple rule-based decisions across multiple stocks.

## Implementation Details

### New Methods

#### `scan_stocks(stock_list, date, use_cache=True)`

An async method that scans multiple stocks for MACD histogram entry signals.

**Parameters:**

- `stock_list`: List of stock symbols to scan (e.g., ["AAPL", "NVDA", "TSLA"])
- `date`: Date to analyze in YYYY-MM-DD format
- `use_cache`: Whether to use cached market data (default: True)

**Returns:**

```json
{
    "scan_date": "2025-07-14",
    "market_open": true,
    "stocks_scanned": 7,
    "entries_found": 2,
    "entries": [
        {
            "symbol": "NVDA",
            "histogram_value": -0.03,
            "histogram_prev": -0.08,
            "improving": true,
            "signal_strength": 0.8,
            "price": 875.50,
            "volume_ratio": 1.2,
            "macd_line": -0.15,
            "signal_line": -0.12,
            "date": "2025-07-14"
        }
    ],
    "errors": [],
    "cache_hits": 5,
    "scan_time_seconds": 12.5,
    "summary": {
        "hit_rate": 28.6,
        "cache_hit_rate": 71.4,
        "avg_signal_strength": 0.7
    }
}
```

#### `scan_stocks_sync(stock_list, date, use_cache=True)`

A synchronous wrapper for the async `scan_stocks` method, useful for integration with existing synchronous code.

## Entry Criteria

The scanner identifies stocks that meet the following criteria:

1. **MACD Histogram < 0.05**: The histogram must be below 0.05 (allowing slight positive values for momentum crosses)
2. **Histogram Improving**: Current histogram value must be greater than the previous day's value
3. **Signal Strength**: Calculated based on the improvement rate (normalized 0-1)

## Features

### 1. Efficient Caching

- Uses `MarketDataCache` to store and retrieve market data
- Dramatically reduces API calls for repeated scans
- 24-hour cache expiry for market data

### 2. Batch Processing

- Processes multiple stocks in a single call
- Provides detailed timing and performance metrics
- Handles errors gracefully without stopping the entire scan

### 3. Enhanced Metrics

- Volume ratio (current vs 20-day average)
- MACD line and signal line values
- Signal strength calculation
- Summary statistics (hit rate, cache efficiency)

## Usage Examples

### Basic Usage

```python
from src.agents.tech_agent import TechAgent

# Initialize agent
ta_agent = TechAgent()

# Define stocks to scan
mag7_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

# Run scanner
results = await ta_agent.scan_stocks(mag7_stocks, "2025-07-14")

# Process results
for entry in results['entries']:
    print(f"{entry['symbol']}: Signal strength {entry['signal_strength']}")
```

### Synchronous Usage

```python
# Use sync wrapper for non-async code
results = ta_agent.scan_stocks_sync(mag7_stocks, "2025-07-14")
```

### Portfolio Scanning

```python
# Scan multiple portfolios
portfolios = {
    "Tech": ["AAPL", "MSFT", "GOOGL"],
    "Finance": ["JPM", "BAC", "GS"],
    "Healthcare": ["JNJ", "PFE", "UNH"]
}

all_signals = []
for name, stocks in portfolios.items():
    results = ta_agent.scan_stocks_sync(stocks, "2025-07-14")
    all_signals.extend(results['entries'])

# Sort by signal strength
all_signals.sort(key=lambda x: x['signal_strength'], reverse=True)
```

## Integration with Strategy Agent

The multi-stock scanner is designed to work with the new simplified strategy approach:

1. **Technical Analysis**: Scanner identifies stocks with MACD histogram entry signals
2. **Sentiment Analysis**: Sentiment Agent analyzes news for stocks with TA signals
3. **Dual Agreement**: Strategy Agent only trades when both TA and SA agree
4. **Portfolio Management**: System can manage multiple positions across different stocks

## Performance Considerations

### API Rate Limits

- Uses Yahoo Finance as primary source (fewer rate limits)
- Falls back to Alpha Vantage and FMP as needed
- Caching significantly reduces API calls

### Optimization Tips

1. Pre-cache data during off-hours for frequently scanned stocks
2. Use bulk date ranges to minimize API calls
3. Implement parallel processing for large portfolios
4. Monitor cache hit rates to optimize performance

## Future Enhancements

1. **Real-time Scanning**: Add support for intraday scanning
2. **Custom Indicators**: Allow scanning with different technical indicators
3. **Alert System**: Notify when new signals appear
4. **Portfolio Optimization**: Suggest position sizes based on signal strength
5. **Historical Analysis**: Track signal performance over time

## Testing

Run the test scripts to verify functionality:

```bash
# Basic test
python tests/test_multi_stock_scanner.py

# Comprehensive demo
python scripts/demo_multi_stock_scanner.py
```

## Troubleshooting

### No Data Available

- Check API keys are configured
- Verify market data cache is accessible
- Ensure date is a valid trading day

### Slow Performance

- Enable caching (`use_cache=True`)
- Pre-fetch data for frequently scanned stocks
- Reduce the lookback period if possible

### No Signals Found

- MACD histogram signals are relatively rare
- Try different dates or stocks
- Consider adjusting the threshold (currently 0.05)
