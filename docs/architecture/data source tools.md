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

- Fetch historical & real-time stock price data
- Retrieve company fundamental data and overview
- Access forex and crypto data (with paid tier)

**Advantages:**

- Higher rate limits with paid tier
- Reliable official API
- Provides fundamental data (balance sheets, income statements)
- Offers forex and crypto support
- Provides economic indicators

#### D. YahooFinanceTool – Stock Prices and Options

**Purpose:**

- Fetch historical stock data with long backtesting periods
- Access options chain data
- Get data without API key requirements

**Advantages:**

- No API key required
- Often provides more historical data
- Includes options chain data
- Free and reliable for most use cases

#### E. MarketDataTool – Unified Market Data Access

**Purpose:**

- Provide a single interface for all market data sources
- Intelligently route requests to the appropriate provider
- Handle fallbacks if primary source fails

**Features:**

- Smart routing based on data type requested
- API limit awareness and management
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

- News includes sentiment scores out of the box
- Company-specific news filtering
- Sector-based news filtering

#### G. FinnHubTool – Financial and Economic Headlines

**Purpose:**

- Fetch specialized financial news headlines
- Access economic news and market updates
- Category-based news filtering

**Features:**

- Specialized financial focus
- Multiple categories (general, forex, crypto, merger)
- Company-specific filtering

#### H. NewsHeadlineTool – General News Access

**Purpose:**

- Retrieve headlines related to broader topics
- Access non-financial news that may impact markets
- General keyword-based searching

**Sources:**

- NewsAPI – Broad news coverage across many publications
- Mediastack – Alternative news aggregation

#### I. UnifiedNewsTool – Comprehensive News Aggregation

**Purpose:**

- Fetch news from multiple providers with one interface
- Deduplicate similar articles across sources
- Provide standardized formatting and sentiment analysis

**Features:**

- Fetches from all available news sources in parallel
- Uses async processing for performance
- Deduplicates similar headlines
- Adds sentiment analysis to all articles
- Provides consistent output format regardless of source

### Optional Tools

#### J. OptionsDataTool – Tracking Market Sentiment via Options

**Purpose:**

- Analyze implied volatility and option chain data
- Determine risk sentiment from options positioning

**Libraries:**

- cboe – CBOE market data (limited free access)
- quandl – Historical options data (some free datasets)

**Why:**

- Provides advanced indicators of market sentiment and risk
- Options data often precedes price movements

## 3. Agent Requirements and Tool Organization

Since the SentimentAgent and StrategyAgent are the simplest to implement first, the priority should be on the tools that these agents require for effective operation. This will ensure that they can produce meaningful outputs before expanding the agent ecosystem.

### Agent Tool Requirements

| Agent Type        | Required Tools                                                                                   |
|-------------------|--------------------------------------------------------------------------------------------------|
| **SentimentAgent** | UnifiedNewsTool, AlphaVantageNewsTool, FinnHubTool, NewsHeadlineTool, SECEdgarTool              |
| **StrategyAgent**  | MarketDataTool, AlphaVantageMarketTool, YahooFinanceTool, UnifiedNewsTool, FREDDataTool         |
| **TechAgent** | MarketDataTool, AlphaVantageMarketTool, YahooFinanceTool, FREDDataTool                         |
| **RiskAgent**      | SECEdgarTool, FREDDataTool, MarketDataTool                                                       |

### Unified Tool Access

The tools are registered in the central `tools.py` file, where they are:

1. Wrapped with `FunctionTool` from `autogen_core.tools`
2. Tagged with appropriate agent types
3. Made available through the `get_tools_for_agent()` function

Example registration:

```python
unified_news_tool = FunctionTool(
    func=fetch_unified_news,
    name="fetch_unified_news",
    description="Fetch news from multiple sources with deduplication and sentiment analysis"
)
unified_news_tool.agent_types = [SENTIMENT_AGENT, STRATEGY_AGENT]
```

### Tool Extension Pattern

To add new tools to the system:

1. Create the tool implementation in the appropriate subdirectory
2. Add any internal dependencies in the tool's own directory
3. Export the tool implementation via the directory's `__init__.py`
4. Register the tool functions in `tools.py` with appropriate agent types
5. Update documentation in this file to reflect the new capability

### Specialized vs Unified Tool Interfaces

We maintain two levels of tool interfaces:

1. **Specialized Tools**: Direct access to specific data sources
   - Example: `AlphaVantageMarketTool` for specific Alpha Vantage features
   - Example: `YahooFinanceTool` for Yahoo Finance-specific capabilities

2. **Unified Interfaces**: High-level abstractions over multiple sources
   - Example: `MarketDataTool` integrates multiple market data sources
   - Example: `UnifiedNewsTool` provides a single interface to all news sources

This two-level approach allows both specialized control when needed and simplified, consistent interfaces for most use cases.

### Specialized Tools Examples

#### Market Data

```python
# Direct Alpha Vantage access for fundamentals
alpha_tool = AlphaVantageMarketTool()
fundamentals = alpha_tool.fetch_company_overview("AAPL")

# Direct Yahoo Finance access for options
yahoo_tool = YahooFinanceTool()
options_chain = yahoo_tool.fetch_options_data("MSFT")
```

#### News Data

```python
# Direct Alpha Vantage news with sentiment
av_news = AlphaVantageNewsTool()
sentiment_news = av_news.fetch_news_sentiment("AAPL")

# FinnHub specialized economic news
finnhub = FinnHubTool()
economic_news = finnhub.fetch_economic_headlines()
```

### Unified Interfaces Examples

#### Market Data

```python
# Smart market data routing
market_tool = MarketDataTool()
market_data = market_tool.fetch_market_data("AAPL", data_type="price")
fundamental_data = market_tool.fetch_market_data("TSLA", data_type="fundamentals")
```

#### News Data

```python
# Comprehensive news from all sources
all_news = fetch_unified_news(
    ticker="AAPL",
    keywords="earnings",
    sources="alpha_vantage,finnhub,newsapi"
)
```

This unified approach maximizes both flexibility and consistency across the multi-agent system.
