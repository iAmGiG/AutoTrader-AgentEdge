# Historical News Data Investigation Findings

**Date**: 2025-08-04  
**Issue**: #160  
**Status**: ✅ IMPLEMENTATION COMPLETE - Google Search Solution Deployed

**Updated**: 2025-08-04 - Google Custom Search API implementation successful with quota protection and organized cache system.

## Executive Summary

✅ **SOLUTION IMPLEMENTED**: Google Custom Search API successfully deployed with comprehensive quota protection and organized cache system.

**Final Implementation**:

- **Google Search Historical News**: Operational with 52/90 API calls used, 415+ articles cached
- **Cache Organization**: Automated date-based categorization (historical vs recent content)
- **Premium Sources**: Access to Barrons, WSJ, Bloomberg, Reuters, CNBC, MarketWatch
- **Quota Protection**: Prevents cost overruns, stays within free tier
- **Backtesting Integration**: Date-filtered news retrieval working

## Original Research Constraints

During initial investigation, we identified significant constraints with various sources:

1. **Yahoo Finance**: No historical URL parameters supported
2. **Wayback Machine**: Has snapshots but access is unstable
3. **FMP**: News endpoints are paywalled (only quotes work on free tier)
4. **NewsAPI**: Limited to 30 days history, poor ETF coverage
5. **Alpha Vantage**: Reserved for OHLCV data (25 calls/day limit)

## Detailed Findings

### Yahoo Finance Direct Access

- **Result**: ❌ Not Viable
- All date parameters (`?date=`, `?d=`, `?time=`, `?timestamp=`) redirect to current news
- No archive URLs exist (`/news/archive/`, `/news/2022/`)
- Pagination parameters also redirect to current content

### Wayback Machine (Internet Archive)

- **Result**: ⚠️ Partially Viable but Unstable
- CDX API shows snapshots exist:
  - `finance.yahoo.com/news`: 10+ snapshots
  - `finance.yahoo.com/topic/stock-market-news`: 10+ snapshots
  - `finance.yahoo.com/topic/earnings`: 10+ snapshots
  - Key dates covered: March 2022, June 2022, Sept 2022, March 2023
- **Issues**:
  - Connection errors when fetching actual content
  - Rate limiting concerns
  - HTML structure may differ from current scraper expectations

### Financial Modeling Prep (FMP)

- **Result**: ❌ Not Viable (Paywalled)
- Historical news endpoint exists but requires premium subscription
- Free tier only supports:
  - Real-time quotes for MAG7 stocks
  - Limited corporate actions data

### NewsAPI

- **Result**: ❌ Not Suitable
- Free tier: Only 30 days historical
- Poor coverage for financial tickers (especially ETFs like SPY)
- Inconsistent results for systematic backtesting

### Alpha Vantage

- **Result**: ❌ Reserved for Other Use
- Has news sentiment API
- Limited to 25 requests/day on free tier
- Currently reserved for OHLCV data

## Alternative Sources Discovered

### Viable Archives (via Wayback Machine)

1. **Reuters**: `reuters.com/markets` - Good snapshot coverage
2. **MarketWatch**: `marketwatch.com/latest-news` - Available snapshots
3. **CNBC**: `cnbc.com/markets` - Archived regularly
4. **Bloomberg**: `bloomberg.com/markets` - Has snapshots (but likely paywalled content)

## Recommended Implementation Strategy

Given the constraints, here's the pragmatic approach:

### Phase 1: Wayback Machine Implementation (Despite Limitations)

1. Implement robust error handling for connection issues
2. Use exponential backoff and retries
3. Cache aggressively (permanent storage for historical data)
4. Accept partial data coverage

### Phase 2: Alternative Source Integration

1. Add Reuters scraper via Wayback Machine
2. Add MarketWatch scraper via Wayback Machine
3. Combine multiple sources for better coverage

### Phase 3: Future-Proofing

1. Start collecting current news daily for future historical use
2. Build local historical dataset over time
3. Consider academic datasets (GDELT, EventRegistry) for research

## Implementation Blueprint

```python
class HistoricalNewsScraper:
    def __init__(self):
        self.sources = {
            'yahoo': YahooWaybackScraper(),
            'reuters': ReutersWaybackScraper(),
            'marketwatch': MarketWatchWaybackScraper()
        }
        self.cache = HistoricalNewsCache()
    
    def fetch_historical_news(self, start_date, end_date, sources=None):
        """
        Fetch from multiple sources with fallback logic.
        """
        all_news = []
        
        for source_name, scraper in self.sources.items():
            if sources and source_name not in sources:
                continue
                
            try:
                news = scraper.fetch_range(start_date, end_date)
                all_news.extend(news)
            except Exception as e:
                logger.warning(f"{source_name} failed: {e}")
                continue
        
        return self._deduplicate_news(all_news)
```

## Immediate Next Steps

1. **Accept Limitations**: Historical news will have gaps
2. **Implement Wayback Scraper**: Focus on Yahoo Finance first
3. **Aggressive Caching**: Store everything permanently
4. **Lower Expectations**: Aim for "some historical context" not "complete coverage"

## Alternative Approach for Backtesting

Since comprehensive historical news is not achievable with current resources:

1. **Run backtests without historical sentiment** initially
2. **Use current news collection** to build historical dataset going forward
3. **Consider simplified sentiment** (market volatility indicators instead of news)
4. **Focus on technical indicators** which have complete historical data

## Conclusion

✅ **IMPLEMENTATION SUCCESSFUL**: Google Custom Search API provides viable solution for historical news access.

**Achieved Results**:

1. **Operational News System**: 52 API calls captured 415+ articles from premium sources
2. **Organized Cache**: Automated categorization by publication date prevents temporal leakage
3. **Cost Protection**: Quota management keeps system within free tier limits
4. **Backtesting Ready**: Date-filtered news retrieval provides appropriate historical context

## Implementation Documentation

See detailed documentation for the implemented solution:

- **[Google Search Historical News](./google_search_historical_news.md)**: Complete implementation guide
- **[News Cache Organization](./news_cache_organization.md)**: Cache categorization and date filtering system
- **[Yahoo Finance Scraper](./yahoo_finance_scraper.md)**: Complementary current news source

**Status**: Historical news infrastructure is production-ready and integrated with backtesting pipeline.
