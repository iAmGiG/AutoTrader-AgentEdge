# Yahoo Finance News Scraper Documentation

**Created**: 2025-08-01  
**Status**: Production Ready  
**GitHub Issues**: #151-159 (Completed), #160 (Pending)

## Overview

The Yahoo Finance News Scraper is a web scraping tool that serves as the **primary news source** for the RH2MAS sentiment agent. It replaces rate-limited API tools by directly scraping Yahoo Finance news pages using multiple HTML parsing strategies for resilience.

## Key Features

### Multi-Strategy HTML Parsing
The scraper uses 4 different selector strategies to handle Yahoo's changing HTML structure:

1. **Strategy 1**: `li[data-test-locator="story-item"]` (current Yahoo structure)
2. **Strategy 2**: `div[data-test-locator="story-item"]` (alternative structure)
3. **Strategy 3**: Generic `.story-item` selectors
4. **Strategy 4**: Fallback `article` and `div[class*="story"]`

### Intelligent Caching System
- **Location**: `.cache/news/yahoo_finance/`
- **TTL**: 5-minute expiration with automatic cleanup
- **Metadata tracking**: Timestamps, item counts, hit/miss statistics
- **Deduplication**: URL-based duplicate removal across categories

### Rate Limiting & Error Handling
- **Delay**: 2.5 seconds between requests to prevent IP bans
- **User Agent Rotation**: 3 different browser user agents
- **Graceful Degradation**: Returns empty DataFrame on failures
- **Comprehensive Logging**: Debug information for troubleshooting

## Architecture

### Core Classes

#### `YahooFinanceNewsScraper`
Main scraper class with multi-strategy HTML parsing.

```python
scraper = YahooFinanceNewsScraper(cache_manager)
news_df = scraper.fetch_news(category="stock-market-news", use_cache=True)
```

#### `YahooNewsCache`
Cache management with TTL and metadata tracking.

```python
cache = YahooNewsCache(cache_dir="./.cache/news/yahoo_finance")
cache.set(category, dataframe, ttl_minutes=5)
cached_data = cache.get(category, ttl_minutes=5)
```

#### `HtmlClient`
HTTP client with rate limiting and user agent rotation.

```python
client = HtmlClient(rate_limit_delay=2.5)
soup = client.load_document(url)
```

### Integration Points

#### AutoGen FunctionTool
```python
from src.tools.data_sources.news.yahoo_scraper_tool import yahoo_finance_scraper_tool

# Tool is automatically registered with sentiment agent
result = yahoo_finance_scraper_tool.func(
    keywords=['NVDA', 'earnings'],
    count=10,
    categories=['stock-market-news', 'earnings']
)
```

#### Sentiment Agent Integration
Located in `src/tools/tools.py`:

```python
_sentiment_tools_raw = [
    unified_news_tool,           # Existing unified tool
    yahoo_finance_scraper_tool,  # Primary news source
    sec_search_tool,            # SEC regulatory info
]
```

## Supported Categories

| Category | Yahoo URL Path | Description |
|----------|----------------|-------------|
| `stock-market-news` | `/topic/stock-market-news/` | General market news |
| `economic-news` | `/topic/economic-news/` | Economic indicators & policy |
| `earnings` | `/topic/earnings/` | Corporate earnings reports |
| `crypto` | `/topic/crypto/` | Cryptocurrency news |
| `latest` | `/news/` | Latest financial news |

## API Reference

### Primary Function

```python
def fetch_yahoo_finance_news(
    keywords: List[str] = None,
    count: int = 10,
    categories: List[str] = None,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Fetch Yahoo Finance news - drop-in replacement for banned yfin tool.
    
    Args:
        keywords: Keywords to filter news (optional)
        count: Number of headlines to return
        categories: News categories to fetch from
        use_cache: Whether to use caching
    
    Returns:
        DataFrame with normalized news data
    """
```

### Schema Compatibility

The scraper returns DataFrames compatible with the existing sentiment pipeline:

| Column | Type | Description |
|--------|------|-------------|
| `title` | str | News headline |
| `summary` | str | Article summary/description |
| `url` | str | Full article URL |
| `published_date` | datetime | Publication timestamp |
| `source` | str | Always "Yahoo Finance" |
| `relevance_score` | float | Always 1.0 |
| `Data_Source` | str | Always "YahooScraper" |
| `category` | str | News category |
| `sentiment_ready` | bool | Always True |

## Cache Structure

```
.cache/news/yahoo_finance/
├── metadata.json                           # Cache metadata with TTL
├── stock-market-news_20250801_1645.json   # Market news cache
├── earnings_20250801_1645.json            # Earnings news cache
└── crypto_20250801_1645.json              # Crypto news cache
```

### Metadata Format

```json
{
  "stock-market-news_20250801_1645": {
    "category": "stock-market-news",
    "cached_at": "2025-08-01T16:47:14.026621",
    "expires_at": "2025-08-01T16:52:14.026628",
    "item_count": 20
  }
}
```

## Usage Examples

### Basic News Fetching

```python
from src.tools.data_sources.news.yahoo_scraper_tool import fetch_yahoo_finance_news

# Fetch general market news
news_df = fetch_yahoo_finance_news(
    categories=['stock-market-news'],
    count=10
)

# Fetch news for specific stock
nvidia_news = fetch_yahoo_finance_news(
    keywords=['NVDA', 'NVIDIA'],
    categories=['stock-market-news', 'earnings'],
    count=5
)
```

### Cache Management

```python
from src.tools.data_sources.news.yahoo_scraper_tool import YahooNewsCache

cache = YahooNewsCache()

# Get cache statistics
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")

# Manual cleanup
cache.cleanup_expired()
```

### Direct Scraper Usage

```python
from src.tools.data_sources.news.yahoo_scraper_tool import YahooFinanceNewsScraper

scraper = YahooFinanceNewsScraper()
earnings_news = scraper.fetch_news('earnings', use_cache=False)
```

## Testing

### Unit Tests
Location: `tests/unit/tools/data_sources/test_yahoo_scraper.py`

```bash
# Run unit tests
python -m pytest tests/unit/tools/data_sources/test_yahoo_scraper.py -v

# Run with live tests (sparingly)
RUN_LIVE_TESTS=1 python -m pytest tests/unit/tools/data_sources/test_yahoo_scraper.py -v
```

### Test Categories
- Basic news fetching functionality
- Cache system operation
- Data normalization for sentiment pipeline
- AutoGen FunctionTool integration
- Sentiment agent tool registration
- Error handling with invalid inputs
- Cache cleanup functionality

## Troubleshooting

### Common Issues

#### No Headlines Found
**Symptoms**: Empty DataFrame returned
**Causes**: 
- Yahoo changed HTML structure
- Rate limiting triggered
- Network connectivity issues

**Solutions**:
1. Check logs for HTML parsing strategy used
2. Verify network connectivity to finance.yahoo.com
3. Increase rate limiting delay
4. Update selector strategies if needed

#### Cache Not Working
**Symptoms**: Fresh requests on every call
**Causes**:
- Permissions issues in cache directory
- TTL expired
- Cache corruption

**Solutions**:
1. Check `.cache/news/yahoo_finance/` permissions
2. Verify metadata.json format
3. Clear cache directory if corrupted

#### Rate Limiting
**Symptoms**: HTTP 429 errors, empty results
**Causes**:
- Too frequent requests
- Yahoo anti-bot measures

**Solutions**:
1. Increase `rate_limit_delay` to 5+ seconds
2. Use cache more aggressively
3. Limit concurrent scraping operations

### Debugging

Enable detailed logging:

```python
import logging
logging.getLogger('src.tools.data_sources.news.yahoo_scraper_tool').setLevel(logging.DEBUG)
```

## Performance Characteristics

### Benchmarks
- **Categories**: 4 categories scraped in ~15 seconds
- **Cache Hit Rate**: ~70% in typical usage
- **Rate Limiting**: 2.5s delay prevents IP bans
- **Memory Usage**: ~10MB per 100 articles cached

### Optimization Recommendations
1. Use caching (enabled by default)
2. Limit categories to those actually needed
3. Set appropriate `count` limits
4. Monitor cache statistics for tuning

## Future Enhancements

### Issue #160: Historical News Data
**Status**: Created but not implemented
**Scope**: Add ability to scrape historical news data for backtesting

**Proposed Implementation**:
- Wayback Machine integration
- Date-based URL construction
- Historical cache separate from current news
- Backtesting pipeline integration

### Potential Improvements
1. RSS feed fallback for redundancy
2. Additional financial news site support
3. Real-time news streaming
4. Sentiment scoring integration
5. News article full-text extraction

## Dependencies

### Required Packages
- `requests` - HTTP client (replaced aiohttp)
- `beautifulsoup4` - HTML parsing
- `pandas` - Data manipulation
- `autogen_core.tools` - FunctionTool integration

### File Dependencies
- `src/tools/tools.py` - Agent tool registration
- `.cache/news/yahoo_finance/` - Cache directory (created automatically)

## Maintenance

### Regular Tasks
1. Monitor cache hit rates and adjust TTL
2. Check logs for HTML parsing failures
3. Update selectors if Yahoo changes structure
4. Monitor rate limiting effectiveness

### Version History
- **v1.0** (2025-08-01): Initial production release
- Multi-strategy HTML parsing
- Cache system with TTL
- AutoGen integration
- Sentiment agent integration

## Security Considerations

### Data Privacy
- No sensitive data stored in cache
- URLs and headlines only (public information)
- No user tracking or personal information

### Network Security
- Standard HTTP requests only
- No executable content processed
- Rate limiting prevents abuse
- User agent rotation for anonymity

## Support

For issues related to the Yahoo Finance scraper:

1. Check troubleshooting section above
2. Verify test suite passes: `pytest tests/unit/tools/data_sources/test_yahoo_scraper.py`
3. Review logs for HTML parsing strategy failures
4. Check GitHub issues #151-160 for related discussions

**Maintainer Note**: This tool is critical infrastructure for the sentiment agent. Changes should be tested thoroughly and backward compatibility maintained.