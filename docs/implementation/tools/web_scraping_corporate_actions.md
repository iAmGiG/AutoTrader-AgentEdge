# Web Scraping Corporate Actions Data

## Overview

After testing multiple financial data APIs (FMP, Finnhub, Yahoo Finance, Nasdaq Link), we discovered that **corporate actions data (earnings dates, dividend information, insider transactions) is largely premium-locked across major financial APIs**. This document outlines potential web scraping approaches to obtain this data from free sources.

## Current API Situation

### Tested APIs and Results:
- **FMP (Financial Modeling Prep)**: Corporate actions require premium subscription (403 Forbidden)
- **Finnhub**: Corporate actions require premium subscription (403 Forbidden)  
- **Yahoo Finance**: Free but aggressively rate limited, basic data only
- **Nasdaq Link**: Authentication issues, likely premium features

### What Works (Free Tier):
- **FMP**: Basic stock prices, company profiles ✅
- **Yahoo Finance**: Basic stock prices, limited corporate events (with caching/throttling) ✅
- **Alpha Vantage**: Market data, news sentiment ✅

## Potential Web Scraping Targets

### 1. SEC EDGAR Database
**Target**: https://www.sec.gov/edgar/searchedgar/companysearch.html
**Data Available**: 
- Earnings announcements (8-K filings)
- Dividend declarations (8-K filings)
- Insider transactions (Forms 3, 4, 5)

**Advantages**:
- Official SEC data, highly reliable
- Comprehensive coverage of US public companies
- Free and public access

**Challenges**:
- Complex filing documents (need to parse XML/HTML)
- Rate limiting on SEC servers
- Requires understanding of SEC form types
- Data may be delayed (filing deadlines)

**Implementation Approach**:
```python
# Example structure
class SECEdgarScraper:
    def fetch_recent_8k_filings(self, ticker, days_back=30):
        # Search for recent 8-K filings for earnings/dividends
        pass
    
    def parse_earnings_announcement(self, filing_url):
        # Extract earnings date and estimates from 8-K
        pass
    
    def fetch_insider_transactions(self, ticker, days_back=90):
        # Search for Forms 3, 4, 5
        pass
```

### 2. Yahoo Finance (Enhanced Scraping)
**Target**: https://finance.yahoo.com/calendar/earnings, https://finance.yahoo.com/calendar/dividend
**Data Available**:
- Earnings calendar
- Dividend calendar
- Historical data

**Advantages**:
- Well-structured HTML
- Comprehensive coverage
- Regular updates

**Challenges**:
- Anti-bot measures (Cloudflare, rate limiting)
- Need to handle JavaScript rendering
- Terms of service considerations

**Implementation Approach**:
```python
# Example structure
class YahooFinanceScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible research tool)'
        })
    
    def scrape_earnings_calendar(self, start_date, end_date):
        # Scrape earnings calendar pages
        pass
    
    def scrape_dividend_calendar(self, start_date, end_date):
        # Scrape dividend calendar pages  
        pass
```

### 3. Financial News Sites
**Targets**: 
- MarketWatch earnings calendar
- CNN Business earnings calendar
- Seeking Alpha earnings calendar

**Advantages**:
- Multiple sources for cross-validation
- Often have good mobile/API-like endpoints
- Less strict anti-bot measures

**Challenges**:
- Varying data quality
- Different formats across sites
- May require multiple scrapers

### 4. Company Investor Relations Pages
**Target**: Direct company websites (e.g., Apple Investor Relations)
**Data Available**:
- Earnings announcements
- Dividend declarations
- Event calendars

**Advantages**:
- Direct from source
- High accuracy
- Less likely to have anti-bot measures

**Challenges**:
- Need to scrape hundreds/thousands of different sites
- Highly variable formats
- Scalability issues

## Recommended Implementation Strategy

### Phase 1: SEC EDGAR Focus
1. **Start with SEC EDGAR** as the most reliable source
2. Focus on 8-K filings for earnings and dividend announcements
3. Use official SEC RSS feeds where available
4. Implement respectful rate limiting (1-2 requests per second)

### Phase 2: Yahoo Finance Supplement
1. Implement Yahoo Finance calendar scraping as backup
2. Use rotating user agents and proxy rotation if needed
3. Focus on upcoming events (next 30-60 days)
4. Cache results to minimize requests

### Phase 3: Multi-Source Validation
1. Cross-reference data from multiple sources
2. Implement confidence scoring based on source agreement
3. Flag discrepancies for manual review

## Technical Implementation Considerations

### Tools and Libraries:
```python
# Required packages
import requests
import beautifulsoup4
import selenium  # For JavaScript-heavy sites
import pandas as pd
import lxml
import fake-useragent  # For rotating user agents
```

### Rate Limiting and Ethics:
```python
import time
import random

class RespectfulScraper:
    def __init__(self, min_delay=1.0, max_delay=3.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
    
    def make_request(self, url):
        # Add random delay between requests
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
        
        # Make request with appropriate headers
        return requests.get(url, headers=self.get_headers())
```

### Data Validation:
```python
class CorporateActionsValidator:
    def validate_earnings_date(self, date, symbol):
        # Check if date is reasonable (business day, future, etc.)
        pass
    
    def cross_reference_sources(self, data_source1, data_source2):
        # Compare data from different sources
        pass
```

## Legal and Ethical Considerations

### Terms of Service:
- **Always review ToS** before scraping any website
- **Respect robots.txt** files
- **Use reasonable rate limits** to avoid overwhelming servers

### Best Practices:
- Identify your bot with a proper User-Agent
- Implement exponential backoff on errors
- Cache results to minimize repeat requests
- Consider reaching out to sites for API access first

### Alternative Approaches:
- **Contact data providers** for academic/research pricing
- **Partner with financial data companies** for access
- **Use official RSS feeds** where available (SEC has some)

## Integration with RH2MAS

### Tool Structure:
```python
# New tool in src/tools/data_sources/scraped/
class CorporateActionsScraper:
    def __init__(self):
        self.sec_scraper = SECEdgarScraper()
        self.yahoo_scraper = YahooFinanceScraper()
    
    def fetch_earnings_calendar(self, start_date, end_date):
        # Try multiple sources and merge results
        pass
    
    def fetch_dividend_calendar(self, start_date, end_date):
        # Try multiple sources and merge results
        pass
```

### Tool Hierarchy Update:
```python
# Updated hierarchy in tools.py
# 1. PRIMARY: Scraped corporate actions (free, comprehensive)
#    - scraped_earnings_calendar, scraped_dividend_calendar
# 2. BACKUP: Yahoo Finance API (free, rate limited)  
#    - yahoo_corporate_events
# 3. EXPERIMENTAL: Premium APIs (when subscriptions available)
#    - fmp_earnings_calendar, finnhub_earnings_calendar
```

## Expected Challenges and Solutions

### Challenge 1: Anti-Bot Measures
**Solution**: Use Selenium with headless browsers, rotate user agents, implement delays

### Challenge 2: Data Quality/Consistency  
**Solution**: Multi-source validation, confidence scoring, manual review processes

### Challenge 3: Maintenance Overhead
**Solution**: Automated testing, error monitoring, fallback mechanisms

### Challenge 4: Legal/ToS Issues
**Solution**: Conservative approach, legal review, partnership exploration

## Estimated Development Timeline

### Week 1-2: SEC EDGAR Implementation
- Parse 8-K filings for earnings announcements
- Extract insider transaction data
- Basic rate limiting and error handling

### Week 3-4: Yahoo Finance Scraping
- Earnings and dividend calendar scraping
- Anti-bot evasion techniques
- Data normalization and integration

### Week 5-6: Data Validation and Integration
- Cross-source validation
- Integration with existing RH2MAS tools
- Testing and optimization

## Success Metrics

### Data Quality:
- 95%+ accuracy vs known events
- Coverage of major S&P 500 companies
- Timely updates (within 24 hours of announcements)

### Reliability:
- 99%+ uptime for data collection
- Graceful handling of source failures
- Automatic recovery from rate limiting

### Performance:
- Daily updates for 500+ companies
- Response time <5 seconds for typical queries
- Minimal impact on target sites

## Conclusion

Web scraping represents the most viable path for obtaining comprehensive, free corporate actions data. While it requires more development effort than API integration, it can provide the data coverage needed without premium subscription costs.

The recommended approach prioritizes reliable sources (SEC EDGAR) while supplementing with more accessible but less reliable sources (Yahoo Finance). Proper implementation with ethical scraping practices can provide a robust alternative to premium financial data APIs.