# News Cache Organization System

## Overview

The News Cache Organization system uses a monthly consolidation structure with intelligent deduplication and date filtering to ensure backtesting receives historically appropriate content without temporal data leakage.

## Current Cache Structure (Monthly System)

### Directory Organization

```
.cache/news_monthly/              # Primary cache (49 files total)
├── AAPL/
│   ├── 2024-03.json             # All March 2024 articles
│   ├── 2024-06.json             # All June 2024 articles
│   └── ...
├── TSLA/
│   ├── 2025-06.json
│   └── ...
└── [Other tickers...]
```

### Monthly File Format

```json
{
  "month": "2024-06",
  "ticker": "AAPL",
  "consolidated_at": "2025-08-19T23:14:20.505693",
  "results": [
    {
      "title": "Apple beats earnings expectations",
      "summary": "...",
      "url": "https://...",
      "published_date": "2024-06-15 00:00:00",
      "article_date": "2024-06-15",  // Used for date filtering
      "relevance_score": 0.55,
      "ticker": "AAPL"
    }
  ],
  "articles_count": 22,
  "duplicates_removed": 498,
  "methodology": "monthly_consolidation_with_deduplication"
}
```

## Cache Lookup Logic

When an agent requests news for a specific date:

### 1. Monthly File Loading
```python
# Request: AAPL news for 2024-06-15
cache_file = ".cache/news_monthly/AAPL/2024-06.json"
```

### 2. Date Filtering (Prevent Future Spill)
```python
# Load all articles for the month
monthly_data = load_json(cache_file)
articles = monthly_data['results']

# Filter to only articles up to requested date
end_date = "2024-06-15"
filtered_articles = [
    article for article in articles 
    if article['article_date'] <= end_date
]
```

### 3. Return Filtered DataFrame
- Agent receives only articles up to the requested date
- Articles from June 16-30 remain hidden
- Prevents temporal leakage in backtesting

## New Search and Append Logic

When new searches are performed:

### 1. API Search
```python
# Google Search API call for specific date range
results = google_search_api.search(ticker, start_date, end_date)
```

### 2. Relevance Filtering
```python
# Only cache articles with relevance_score > 0.0
relevant_articles = [a for a in results if a['relevance_score'] > 0.0]
```

### 3. Set-Based Deduplication
```python
# Load existing monthly cache
existing_articles = load_monthly_cache(ticker, month)
existing_titles = {normalize_title(a['title']) for a in existing_articles}

# Only append truly new articles
new_articles = []
for article in relevant_articles:
    normalized_title = normalize_title(article['title'])
    if normalized_title not in existing_titles:
        new_articles.append(article)
        existing_titles.add(normalized_title)
```

### 4. Append to Monthly Cache
```python
# Combine and sort by date
all_articles = existing_articles + new_articles
all_articles.sort(key=lambda x: x['article_date'])

# Save back to monthly cache
save_monthly_cache(ticker, month, all_articles)
```

## Key Statistics

### Consolidation Results
- **Original files**: 537 messy cache files with 180+ character names
- **After consolidation**: 49 clean monthly files
- **Deduplication rate**: 81.5% (1,143 duplicates removed from 1,403 articles)
- **Final unique articles**: 260 relevant articles

### Benefits of Monthly Structure
1. **Simpler lookups**: One file per month vs multiple weekly/daily files
2. **Better deduplication**: Same article won't appear across multiple files
3. **Date safety**: Filtering prevents future data leakage
4. **Efficient caching**: Append operations with automatic deduplication

## Data Integrity Measures

### Date Validation
- Articles with future dates relative to request are rejected
- Publication dates extracted from article snippets when available
- Fallback to request date if no publication date found

### Title-Only Sentiment
- V1/V3/V4 agents use title-only sentiment analysis
- Prevents date smuggling through summary text
- Mimics realistic trader behavior (scanning headlines)

### Relevance Scoring
- Articles scored by relevance to ticker (0.0 to 1.0)
- Only articles with score > 0.0 are cached
- Categories: company_specific (1.0), sector_relevant (0.7), macro_economic (0.5), market_wide (0.3)

## Implementation Files

- **Cache Script**: `scripts/create_monthly_cache.py`
- **Google Search API**: `src/tools/data_sources/news/google_search_api.py`
- **Cache Directory**: `.cache/news_monthly/`

## Future Enhancements

### Considered but Not Implemented
1. **Database storage**: Would solve many issues but keeping it simple with JSON
2. **Weekly sub-sections**: Monthly is sufficient granularity
3. **Title obfuscation**: Would prevent V4 from using training knowledge of specific companies

### Known Limitations
- V4 can potentially recognize companies from headlines (not fully obfuscated)
- 2024 data still contains some 2025 contamination from Google Search
- Cache relies on Google Search API accuracy for date extraction