# Data Sources Tools for RH2MAS

- Focusing on individual tools for integrating financial data sources, we will define the essential tools, their responsibilities, and the libraries required for efficient data retrieval and processing.

## 1. Overview of Data Source Tools

Each tool is responsible for fetching, processing, and formatting data from different financial sources (SEC filings, market data, volatility indices, news sentiment, etc.). These tools should provide:

- A standardized interface (fetch_data(params) -> DataFrame)
- Efficient API handling (batch processing where applicable)
- Caching or persistence support (when necessary)

## Directory Structure

The tools are organized into a hierarchical structure based on their domain:

```bash
src/tools/
  |-- data_sources/        # External data access layer
  |   |-- market/          # Market price data tools
  |   |   |-- alpha_vantage_market.py
  |   |   |-- yahoo_finance_tool.py
  |   |   |-- market_data_tool.py  # Unified interface
  |   |
  |   |-- news/            # News and sentiment tools
  |   |   |-- alpha_vantage_news.py
  |   |   |-- finnhub_tool.py
  |   |   |-- news_headline_tool.py
  |   |   |-- unified_news_tool.py  # Unified interface
  |   |
  |   |-- government/      # Government data sources
  |       |-- sec_edgar_tool.py
  |       |-- FRED_data_tool.py
  |
  |-- processors/          # Data processing utilities
      |-- data_normalizer.py
      |-- sentiment_analyzer.py
```

## Tools Required

| Tool Name            | Data Type                        | Source API / Library                                  | Purpose                                                      |
|----------------------|--------------------------------|------------------------------------------------------|--------------------------------------------------------------|
| **SECEdgarTool**     | Risk filings (10-K, 8-K, etc.) | `requests`, `beautifulsoup4`, `sec-edgar-downloader` | Extract company risk disclosures for sentiment/risk profiling |
| **MarketDataTool**   | Market prices, VIX, indices    | `yfinance`, `alpha_vantage`, `twelvedata`           | Fetch stock/index data for trend analysis                   |
| **AlphaVantageMarketTool** | Stock prices, fundamentals | `alpha_vantage` | Specialized market data from Alpha Vantage API |
| **YahooFinanceTool** | Stock prices, options data | `yfinance` | Historical data and option chains from Yahoo Finance |
| **AlphaVantageNewsTool** | News sentiment | `alpha_vantage` | Financial news with sentiment scores |
| **NewsHeadlineTool** | News headlines, sentiment      | `newsapi`, `finnhub`, `mediastack`                   | Monitor news events and rank impact                         |
| **FinnHubTool** | Financial headlines | `finnhub` | Financial and economic headlines |
| **UnifiedNewsTool** | Comprehensive news | Multiple sources | Unified interface for all news sources with deduplication |
| **FREDDataTool**    | GDP, inflation, rates          | `fredapi`, `pandas-datareader`                       | Extract macro indicators to assess economic climate        |
| **OptionsDataTool** (Optional) | Implied volatility, options chains | `cboe`, `quandl` (limited free data) | Analyze options market for risk sentiment |

## 2. Detailed Breakdown of Each Tool

### Government Data Sources

#### A. SECEdgarTool – Extracting Risk Disclosures from SEC Filings

**Purpose:**

- Retrieve company disclosures from EDGAR (10-K, 8-K, 10-Q reports)
- Extract and summarize risk factors

**Libraries:**

- `requests` – To send HTTP requests to the SEC API
- `beautifulsoup4` – For parsing HTML filings
- `sec-edgar-downloader` – Prebuilt package for downloading structured filings

**Why:**

- sec-edgar-downloader simplifies structured retrieval, avoiding manual parsing
- beautifulsoup4 helps extract relevant text from HTML documents
- requests allows direct API calls for faster metadata retrieval

#### B. FREDDataTool – Fetching Economic Indicators

**Purpose:**

- Retrieve economic indicators like inflation, GDP, interest rates
- Fetch yield curve data and interest rate indicators

**Libraries:**

- `fredapi` – Fetches economic data from FRED (Federal Reserve)
- `pandas-datareader` – Alternative source for macro data

**Why:**

- fredapi allows direct querying of macroeconomic indicators
- pandas-datareader integrates well with Pandas for historical analysis

### Market Data Sources

#### C. AlphaVantageMarketTool – Stock Prices and Fundamentals

**Purpose:**

- Fetch historical stock data
- Access company fundamentals
- Specialized interface for Alpha Vantage API

**Features:**

- Dynamic date processing (supports relative dates like "-30d")
- Automatic timezone localization
- Column name standardization
- Split from original AlphaVantageTool for better separation of concerns

#### D. YahooFinanceTool – Free Stock Data with Rate Limiting

**Purpose:**

- Fetch historical OHLCV data
- Get company info and financials
- Handle rate limiting gracefully

**Features:**

- Built-in rate limiting protection
- Comprehensive data including splits and dividends
- Free tier with reasonable limits

#### E. MarketDataTool – Unified Market Data Interface

**Purpose:**

- Provide a single interface for multiple data providers
- Automatic fallback between sources
- Handle API failures gracefully

**Features:**

- Supports Alpha Vantage, Yahoo Finance, FMP, and Nasdaq Data Link
- Environment variable configuration
- Consistent DataFrame output format
- Fallback capabilities between providers
  - If Yahoo Finance is rate limited, the tool automatically retries using Alpha Vantage
  - If both fail, it falls back to FMP and finally Nasdaq Data Link
  - FMP's free tier only supports basic historical price endpoints

### News Data Sources

#### F. AlphaVantageNewsTool – Financial News with Sentiment

**Purpose:**

- Fetch financial news with pre-calculated sentiment scores
- Filter news by ticker symbols or topics
- Access top gainers/losers market data

**Features:**

- Split from original AlphaVantageTool for better organization
- Pre-calculated sentiment scores from Alpha Vantage
- Support for topic filtering
- Market movers data (top gainers/losers)

#### G. FinnHubTool – Financial Headlines for Sentiment Analysis

**Purpose:**

- Fetch financial news headlines from various categories
- Optimized for free tier API usage
- Company-specific news retrieval

**Features:**

- Multiple news categories (general, forex, crypto, economic, etc.)
- Company news endpoint for ticker-specific headlines
- Designed for headline sentiment analysis
- Free tier friendly with reasonable rate limits

#### H. NewsHeadlineTool – General News API Integration

**Purpose:**

- Fetch general market news from NewsAPI
- Keyword-based searching
- Date range filtering

**Features:**

- NewsAPI integration for broad news coverage
- Keyword and source filtering
- Historical news search capabilities

#### I. UnifiedNewsTool – Comprehensive News Aggregation

**Purpose:**

- Unified interface for all news sources
- Deduplication across providers
- Sentiment analysis integration
- Relevance scoring for better filtering

**Features:**

- Fetches from AlphaVantage, Finnhub, and NewsAPI
- Unified output format with standardized fields
- Built-in sentiment analysis using TextBlob
- Relevance scoring based on keyword and ticker matches
- Smart deduplication to avoid duplicate articles
- Search guidance when results are inadequate
- MVC architecture with Pydantic models for data validation

## 3. Processing Utilities

### Data Normalizer

**Purpose:**

- Standardize data formats across different sources
- Ensure consistent column naming
- Handle timezone conversions

**Features:**

- Normalize market data to common schema
- Normalize news data for sentiment analysis
- Support for various data source formats

### Sentiment Analyzer

**Purpose:**

- Analyze text sentiment using TextBlob
- Support for financial-specific sentiment analysis
- Batch processing capabilities

**Features:**

- TextBlob integration for basic sentiment
- Financial lexicon support
- Relevance scoring for news articles

## 4. Tool Integration in the Multi-Agent System

### Agent-Tool Assignments

| Agent Type        | Tools Used                                                                                          |
|-------------------|-----------------------------------------------------------------------------------------------------|
| **SentimentAgent** | UnifiedNewsTool, AlphaVantageNewsTool, FinnHubTool, NewsHeadlineTool, SECEdgarTool              |
| **StrategyAgent**  | MarketDataTool, AlphaVantageMarketTool, YahooFinanceTool, UnifiedNewsTool, FREDDataTool         |
| **TechAgent** | MarketDataTool, AlphaVantageMarketTool, YahooFinanceTool, FREDDataTool                         |
| **RiskAgent**      | SECEdgarTool, FREDDataTool, MarketDataTool                                                       |

### Unified Tool Access

The tools are registered in the central `tools.py` file, where they are:

1. Wrapped with `FunctionTool` from `autogen_core.tools`
2. Tagged with appropriate agent types
3. Organized into collections for each agent type

This architecture ensures:

- Clear separation of concerns
- Easy addition of new data sources
- Consistent data formatting across agents
- Efficient resource usage through proper tool allocation