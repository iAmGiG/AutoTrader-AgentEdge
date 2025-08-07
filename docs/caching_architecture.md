# RH2MAS Caching Architecture: Cross-Source Data Integration

## 🗂️ Cache Structure Overview

The RH2MAS system uses a **source-segregated, date-range-aware** caching strategy that allows tools to find data regardless of the original source.

```
.cache/
├── market_data/                    # Legacy FMP cache (6,000+ points)
│   └── AAPL_2022-01-01_2022-12-31.json
├── polygon/                        # New Polygon.io cache
│   ├── prices/
│   │   └── AAPL_2025-04-09_to_2025-04-16_day.json
│   ├── news/
│   │   └── AAPL_news_2025-04-09_2025-04-16_100.json
│   └── events/
│       └── AAPL_dividends_2025-04-01_2025-06-30.json
└── news/
    ├── google_search/              # Google Search API cache
    │   └── AAPL_stock_crash_2025-04-09.json
    ├── hybrid_historical/          # Multi-source news cache
    │   └── finviz_2025-04-09.json
    └── yahoo_scraper/              # Yahoo scraper cache
        └── AAPL_headlines_2025-04-09.json
```

## 🔄 How Cross-Source Data Retrieval Works

### 1. **Source-Specific Caching**

Each data source manages its own cache with **standardized naming conventions**:

#### Market Data Sources

```python
# Polygon.io cache key format
cache_key = f"{ticker}_{start_date}_to_{end_date}_{timespan}"
# Example: "AAPL_2025-04-09_to_2025-04-16_day.json"

# FMP cache key format  
cache_key = f"{ticker}_{start_date}_{end_date}"
# Example: "AAPL_2022-01-01_2022-12-31.json"

# Yahoo Finance cache key format
cache_key = f"{ticker}_{period}_{interval}"
# Example: "AAPL_1y_1d.json"
```

#### News Sources

```python
# Google Search cache key format
cache_key = f"{query_hash}_{date_range}"
# Example: "AAPL_stock_crash_2025-04-09.json"

# Yahoo scraper cache key format
cache_key = f"{ticker}_headlines_{date}"
# Example: "AAPL_headlines_2025-04-09.json"
```

### 2. **Date Range Resolution Strategy**

When tools request data for a date range, the system uses a **hierarchical lookup**:

```python
def find_data_for_range(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Find data across multiple cache sources for a date range.
    
    Priority order:
    1. Exact cache hit (same date range)
    2. Superset cache hit (cached range includes requested range) 
    3. Multiple cache combination (combine partial ranges)
    4. API fetch with caching
    """
    
    # 1. Try exact cache hit first
    exact_cache = try_exact_cache_hit(ticker, start_date, end_date)
    if exact_cache is not None:
        return exact_cache
    
    # 2. Try superset cache (cached data includes requested range)
    superset_cache = try_superset_cache(ticker, start_date, end_date)
    if superset_cache is not None:
        return filter_date_range(superset_cache, start_date, end_date)
    
    # 3. Try combining multiple partial caches
    combined_cache = try_combine_partial_caches(ticker, start_date, end_date)
    if combined_cache is not None:
        return combined_cache
    
    # 4. Fetch from API and cache
    return fetch_and_cache(ticker, start_date, end_date)
```

### 3. **Data Format Standardization**

All cached market data follows the **same JSON structure** regardless of source:

```json
[
  {
    "date": "2025-04-09 00:00:00",
    "open": 171.95,
    "high": 200.61,
    "low": 171.89, 
    "close": 198.85,
    "volume": 184261774.0,
    "vwap": 187.9565,        // Polygon-specific (null for other sources)
    "transactions": 2212956  // Polygon-specific (null for other sources)
  }
]
```

### 4. **Tool Integration Pattern**

The **MarketDataTool** acts as a **unified interface** that abstracts away the source complexity:

```python
class MarketDataTool:
    def fetch_market_data(self, symbol: str, start_date: str, end_date: str):
        # Check all available cache sources in priority order
        data_sources = [
            self.polygon_tool,    # Highest quality (VWAP, transactions)
            self.fmp_tool,        # Cached historical data
            self.yahoo_tool,      # Fallback for older data
            self.alpha_vantage_tool  # Final fallback
        ]
        
        for source in data_sources:
            try:
                data = source.get_data(symbol, start_date, end_date)
                if not data.empty:
                    return data
            except Exception:
                continue  # Try next source
        
        return pd.DataFrame()  # Empty if all sources fail
```

## 🎯 **Practical Example: AAPL April 2025**

Let's trace how the system finds AAPL data for April 9-16, 2025:

### Step 1: Tool Request

```python
# Backtest system requests data
data = fetch_market_data("AAPL", "2025-04-09", "2025-04-16")
```

### Step 2: Cache Lookup Sequence

```python
# 1. Check Polygon cache (newest, highest priority)
polygon_cache = ".cache/polygon/prices/AAPL_2025-04-09_to_2025-04-16_day.json"
if exists(polygon_cache):
    return load_json(polygon_cache)  # ✅ CACHE HIT!

# 2. Check if larger Polygon cache exists
polygon_monthly = ".cache/polygon/prices/AAPL_2025-04-01_to_2025-04-30_day.json"  
if exists(polygon_monthly):
    data = load_json(polygon_monthly)
    return filter_dates(data, "2025-04-09", "2025-04-16")  # ✅ SUBSET HIT!

# 3. Check FMP cache (fallback)
fmp_cache = ".cache/market_data/AAPL_2025-01-01_2025-12-31.json"
if exists(fmp_cache):
    return filter_dates(load_json(fmp_cache), "2025-04-09", "2025-04-16")

# 4. API fetch as last resort
```

### Step 3: Data Format Consistency

```python
# Regardless of source, all tools return the same format:
{
    "ticker": "AAPL",
    "data": [
        {"date": "2025-04-09", "open": 171.95, "high": 200.61, ...},
        {"date": "2025-04-10", "open": 189.06, "high": 194.78, ...}
    ],
    "source": "polygon",  # or "fmp", "yahoo", etc.
    "cached": true
}
```

## 🔗 **News Data Integration**

News data follows a **similar but more complex pattern** due to multiple sources:

### News Source Priority

```python
NEWS_SOURCE_PRIORITY = [
    GoogleSearchNewsTool,      # Highest quality, premium sources
    YahooNewsScraperTool,      # Real-time scraping
    FinVizHistoricalScraper,   # Historical snapshots
    NewsAPITool,               # Fallback for recent news
    AlphaVantageNewsTool       # Basic news feed
]
```

### News Cache Resolution

```python
def get_news_for_period(ticker: str, start_date: str, end_date: str):
    """
    Aggregate news from multiple cached sources for a date range.
    """
    all_news = []
    
    for source in NEWS_SOURCE_PRIORITY:
        cached_news = source.get_cached_news(ticker, start_date, end_date)
        if not cached_news.empty:
            cached_news['source'] = source.name
            all_news.append(cached_news)
    
    # Combine and deduplicate
    combined_news = pd.concat(all_news, ignore_index=True)
    return deduplicate_news(combined_news)
```

## ✅ **Key Benefits of This Architecture**

### 1. **Source Transparency**

- Tools don't need to know which source provided the data
- Backtest system gets consistent data format regardless of origin
- Easy to add new data sources without breaking existing tools

### 2. **Intelligent Fallbacks**  

- If Polygon data unavailable → Falls back to FMP cache
- If specific date range missing → Uses superset and filters
- If all caches miss → Fetches from API

### 3. **Optimized Performance**

- **Cache hits are instantaneous** (no API calls)
- **Superset filtering** avoids redundant API requests
- **Multiple source aggregation** provides comprehensive coverage

### 4. **Date Range Intelligence**

```python
# Request: April 9-16, 2025
# Available: April 1-30, 2025 (cached)
# System automatically filters cached month to requested week
# Result: No API call needed, instant response
```

## 🎯 **Real-World Scenario**

**User runs backtest for AAPL April 9-16, 2025:**

1. **Cache Hit**: Polygon data exists → Returns in 0.001s
2. **Tool Integration**: Backtest system gets consistent OHLCV format
3. **Source Agnostic**: Backtest doesn't know/care it came from Polygon
4. **Future Requests**: Same data range returns instantly from cache

**If news sentiment is needed:**

1. **Multi-source aggregation**: Combines Google Search + Yahoo scraper + FinViz
2. **Deduplication**: Removes duplicate articles across sources  
3. **Date filtering**: Only includes news from April 9-16 period
4. **Consistent format**: All sources normalized to same schema

## 🚀 **Bottom Line**

The caching system is **source-agnostic from the tool perspective** but **source-aware at the cache layer**. This means:

- ✅ **Tools don't care** where data came from
- ✅ **Cache optimization** is source-specific for performance
- ✅ **Date range resolution** works across all sources
- ✅ **New sources integrate seamlessly** without breaking existing tools
- ✅ **Fallback strategies** ensure data availability

**Result**: You get the best available data for any date range, with intelligent caching and seamless source integration! 🎉
