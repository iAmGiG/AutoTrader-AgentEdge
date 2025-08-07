# MAG7 Data Collection Services

This directory contains services for systematic collection of historical market data and news for MAG7 stocks during the Q2 2025 volatility period.

## 🎯 Purpose

Collect comprehensive data for MAG7 backtesting using superior Q2 2025 bear market periods instead of inaccessible October 2022 data:

- **AAPL**: -33.4% decline (April 9 - May 7, 2025)
- **TSLA**: -53.8% decline (December 20, 2024 - August 6, 2025)  
- **NVDA**: -36.9% decline (February 21 - June 12, 2025)
- **META**: -34.2% decline (February 25 - June 29, 2025)

## 📁 Files

### Core Services

- **`market_data_collector.py`** - Polygon.io market data collection with rate limiting
- **`news_data_collector.py`** - Google Search API news collection with quota management
- **`mag7_test_collection.py`** - Orchestrated collection for test week validation

### Testing & Validation

- **`test_market_collection.py`** - Quick tests for market data collection
- **`validate_cache_integration.py`** - Validates cache compatibility with existing tools

### Configuration

- **`config/collection_config.yaml`** - Service configuration and target periods

## 🚀 Quick Start

### 1. Test Single Ticker Collection

```bash
python scripts/services/test_market_collection.py --single
```

### 2. Test Three Ticker Collection (with rate limiting)

```bash
python scripts/services/test_market_collection.py --three
```

### 3. Full Test Week Collection (Market Data Only)

```bash
python scripts/services/mag7_test_collection.py --market-only
```

### 4. Validate Cache Integration

```bash
python scripts/services/validate_cache_integration.py
```

## 📊 Collection Status

### ✅ Completed Tests

- Single ticker collection: **PASSED** (6 days AAPL data)
- Cache structure validation: **PASSED**  
- Tool integration validation: **PASSED**
- Data format compatibility: **PASSED**

### 🎯 Ready for Full Collection

System validated and ready for comprehensive MAG7 data collection.

## 🔧 Technical Details

### Market Data (Polygon.io)

- **Rate Limit**: 65 seconds between requests (conservative for free tier)
- **Cache**: `.cache/polygon/prices/` with JSON format
- **Data**: OHLCV + VWAP + transaction count
- **Compatibility**: Direct integration with existing backtest tools

### News Data (Google Search API)  

- **Rate Limit**: 15 minutes between searches
- **Daily Quota**: 90/100 searches (leaves 10 for manual use)
- **Cache**: `.cache/news/google_search/`
- **Search Patterns**: Ticker-specific crash and volatility terms

### Rate Limiting Strategy

- **Market Data**: 7 tickers × 65s = ~7.6 minutes for one date range
- **News Data**: 7 tickers × 15min = ~1.75 hours for comprehensive coverage
- **Conservative Approach**: Prevents API quota exceeded errors

## 📈 Data Format

### Market Data JSON Structure

```json
[
  {
    "date": "2025-04-09 00:00:00",
    "open": 171.95,
    "high": 200.61, 
    "low": 171.89,
    "close": 198.85,
    "volume": 184261774.0,
    "vwap": 187.9565,
    "transactions": 2212956
  }
]
```

### News Data Integration

- Leverages existing `hybrid_historical_news_tool`
- Compatible with sentiment analysis pipeline
- Cached in Google Search format for reuse

## 🎯 Collection Targets

### Test Week (Validation)

- **Period**: April 9-16, 2025 (Peak volatility start)
- **Purpose**: Validate system before full collection
- **Status**: ✅ Market data collection validated

### Full Q2 2025 Collection

- **Pre-crash**: April 1-8, 2025
- **Peak volatility**: April 9 - May 7, 2025 (Priority 1)  
- **Recovery**: May 8 - June 30, 2025

## 🛠️ Error Handling

### Automatic Recovery

- Resume capability for interrupted collections
- Status tracking in `.cache/mag7_collection/`
- Retry logic with exponential backoff
- Quota exhaustion detection

### Monitoring

- Real-time progress reporting
- Rate limit compliance tracking
- Data quality validation
- Integration testing

## 🔄 Next Steps

1. **Full Week Collection**: Run complete test week (market + news)
2. **Scale to Full Q2**: Expand to complete Q2 2025 period
3. **Integration Testing**: Validate with full backtest pipeline
4. **Performance Analysis**: Compare Q2 2025 vs historical periods

## 💡 Key Benefits

- **Superior Test Periods**: Q2 2025 crashes more extreme than October 2022
- **Free Tier Compatible**: Works within Polygon.io and Google API limits
- **Existing Tool Integration**: Compatible with current backtest system
- **Systematic Collection**: Automated, resumable, rate-limit compliant
- **Comprehensive Coverage**: Both market data and sentiment-ready news

Ready for systematic MAG7 data collection! 🚀
