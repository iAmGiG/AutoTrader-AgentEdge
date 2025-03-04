# Data Sources Tools for RH2MAS

- Focusing on individual tools for integrating financial data sources, we will define the essential tools, their responsibilities, and the libraries required for efficient data retrieval and processing.

1. Overview of Data Source Tools
Each tool is responsible for fetching, processing, and formatting data from different financial sources (SEC filings, market data, volatility indices, news sentiment, etc.). These tools should provide:

    - A standardized interface (fetch_data(params) -> DataFrame)
    - Efficient API handling (batch processing where applicable)
    - Caching or persistence support (when necessary)

Tools Required:

## Tools Required

| Tool Name            | Data Type                        | Source API / Library                                  | Purpose                                                      |
|----------------------|--------------------------------|------------------------------------------------------|--------------------------------------------------------------|
| **SECEdgarTool**     | Risk filings (10-K, 8-K, etc.) | `requests`, `beautifulsoup4`, `sec-edgar-downloader` | Extract company risk disclosures for sentiment/risk profiling |
| **MarketDataTool**   | Market prices, VIX, indices    | `yfinance`, `alpha_vantage`, `twelvedata`           | Fetch stock/index data for trend analysis                   |
| **NewsHeadlineTool** | News headlines, sentiment      | `newsapi`, `finnhub`, `mediastack`                   | Monitor news events and rank impact                         |
| **MacroDataTool**    | GDP, inflation, rates          | `fredapi`, `pandas-datareader`                       | Extract macro indicators to assess economic climate        |
| **OptionsDataTool** (Optional) | Implied volatility, options chains | `cboe`, `quandl` (limited free data) | Analyze options market for risk sentiment |

2. Detailed Breakdown of Each Tool
A. SECEdgarTool – Extracting Risk Disclosures from SEC Filings
Purpose:

    - Retrieve company disclosures from EDGAR (10-K, 8-K, 10-Q reports).
    - Extract and summarize risk factors.
Libraries Needed:

    - requests – To send HTTP requests to the SEC API.
    - beautifulsoup4 – For parsing HTML filings.
    - sec-edgar-downloader – Prebuilt package for downloading structured filings.
Why?

    - sec-edgar-downloader simplifies structured retrieval, avoiding manual parsing.
    - beautifulsoup4 helps extract relevant text from HTML documents.
    - requests allows direct API calls for faster metadata retrieval.

3. MarketDataTool – Stock Prices, Volatility Indices
Purpose:

    - Fetch historical & real-time stock/index data.
    - Track market sentiment via VIX.
Libraries Needed:

    - yfinance – Free API for stock & index data.
    - alpha_vantage – Alternative free API (rate-limited).
    - twelvedata – Provides alternative market data if needed.
Why?

    - yfinance offers free, efficient access to stock prices.
    - alpha_vantage has fundamental indicators but limits requests.
    - twelvedata supports additional data types like futures & crypto.

4. NewsHeadlineTool – Fetching and Analyzing Market News
Purpose:

    - Retrieve headlines related to financial markets.
    - Apply sentiment analysis to assess impact.
Libraries Needed:

    - requests – To make API calls.
    - newsapi – Free news aggregator API.
    - finnhub – Real-time financial news feed.
    - mediastack – Low-cost news alternative.
Why?

    - newsapi has broad news coverage but limited financial filtering.
    - finnhub specializes in finance-related news with sentiment scores.
    - mediastack is cheaper than Finnhub but requires manual processing.

5. MacroDataTool – Fetching Economic Indicators
Purpose:

    - Retrieve economic indicators like inflation, GDP, interest rates.
Libraries Needed:

    - fredapi – Fetches economic data from FRED (Federal Reserve).
    - pandas-datareader – Alternative source for macro data.
Why?

    - fredapi allows direct querying of macroeconomic indicators.
    - pandas-datareader integrates well with Pandas for historical analysis.

6. OptionsDataTool – Tracking Market Sentiment via Options

Purpose:

    - Analyze implied volatility and option chain data.
    - Determine risk sentiment from options positioning.
Libraries Needed:

    - cboe – CBOE market data (limited free access).
    - quandl – Historical options data (some free datasets).

Why?

    - cboe offers live market data but with limited free tiers.
    - quandl provides structured datasets with limited historical options data.

### sentiment and strategy agent tools in focus

Since the SentimentAgent and StrategyAgent are the simplest to implement first, the priority should be on the tools that these agents require for effective operation. This will ensure that they can produce meaningful outputs before expanding the agent ecosystem.

1. Tools Needed for Sentiment & Strategy Agents

# Tools Overview

| Tool               | Purpose                                      | Required By       | API/Library                               |
|--------------------|----------------------------------------------|-------------------|-------------------------------------------|
| **NewsHeadlineTool** | Retrieve financial news & assess sentiment | Sentiment Agent  | `newsapi`, `finnhub`, `mediastack`       |
| **MarketDataTool**  | Fetch stock/index/VIX data for trend analysis | Strategy Agent   | `yfinance`, `alpha_vantage`              |
| **SECEdgarTool**    | Extract company risk factors from SEC filings | Sentiment Agent  | `sec-edgar-downloader`, `beautifulsoup4` |

These three tools will allow the SentimentAgent to analyze textual market signals (news & risk disclosures) and the StrategyAgent to derive insights from historical & real-time market trends.

2. Priority 1: NewsHeadlineTool (Market Sentiment Extraction)

Purpose:

- Fetches news headlines from financial news sources.
- Processes text sentiment using NLP models.
- Identifies market-moving events (earnings, economic reports, geopolitical events).

## Libraries Needed

| Library      | Purpose                                                       |
|-------------|---------------------------------------------------------------|
| `requests`  | To call APIs (NewsAPI, Finnhub, Mediastack)                   |
| `newsapi`   | General news headlines (but limited financial focus)          |
| `finnhub`   | Financial news with sentiment scoring (preferred)             |
| `nltk` or `TextBlob` | Basic sentiment analysis if API lacks built-in scores |

example:

```python
import requests

class NewsHeadlineTool:
    def __init__(self, api_key, source="finnhub"):
        self.api_key = api_key
        self.source = source

    def fetch_news(self, keyword="market", count=5):
        if self.source == "finnhub":
            url = f"https://finnhub.io/api/v1/news?category=general&token={self.api_key}"
        elif self.source == "newsapi":
            url = f"https://newsapi.org/v2/everything?q={keyword}&apiKey={self.api_key}"
        else:
            raise ValueError("Unsupported news source")
        
        response = requests.get(url).json()
        return response[:count] if self.source == "finnhub" else response["articles"][:count]

# Example Usage
news_tool = NewsHeadlineTool("YOUR_API_KEY", source="finnhub")
articles = news_tool.fetch_news("inflation", count=3)
for article in articles:
    print(article["headline"] if "headline" in article else article["title"])
```

Why Finnhub?

- Provides pre-scored sentiment for articles.
- Focuses on financial news, unlike newsapi, which requires filtering.

3. Priority 2: MarketDataTool (Market Trends & Volatility)

Purpose:

- Retrieves historical and real-time stock/index prices.
- Fetches volatility indicators (VIX) for trend confirmation.
- Essential for StrategyAgent to adjust market positioning.

# Libraries Needed

| Library         | Purpose                                      |
|---------------|----------------------------------------------|
| `yfinance`    | Free, fast stock/index data (incl. VIX)     |
| `alpha_vantage` | Alternative API for stock/indicator data  |
| `pandas`      | For time-series manipulation                |

example:

```python
import yfinance as yf
import pandas as pd

class MarketDataTool:
    def fetch_stock_data(self, ticker, start_date="2023-01-01", end_date="2024-01-01"):
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]

    def fetch_vix_data(self, start_date="2023-01-01", end_date="2024-01-01"):
        vix = yf.Ticker("^VIX")
        df = vix.history(start=start_date, end=end_date)
        return df[['Close']]  # VIX represents market volatility

# Example Usage
market_tool = MarketDataTool()
spy_data = market_tool.fetch_stock_data("SPY")
vix_data = market_tool.fetch_vix_data()
print(spy_data.head(), vix_data.head())
```

Why yfinance?

- Free & reliable API for stock and index data.
- Direct support for VIX, which is critical for risk sentiment.

4. Priority 3: SECEdgarTool (Extracting Risk Disclosures)

Purpose

- Scrapes SEC filings (10-K, 8-K reports) for risk disclosures.
- Helps SentimentAgent evaluate risk-related language.
- Converts raw text into structured risk scores.

# Libraries Needed

| Library                 | Purpose                                      |
|-------------------------|----------------------------------------------|
| `sec-edgar-downloader`  | Simplifies SEC filing retrieval             |
| `beautifulsoup4`        | Parses HTML reports for relevant text       |
| `nltk` or `TextBlob`    | Processes text for risk factor detection    |

example:

```python
from sec_edgar_downloader import Downloader
from bs4 import BeautifulSoup
import os

class SECEdgarTool:
    def __init__(self, download_dir="sec_filings"):
        self.downloader = Downloader(download_dir)

    def fetch_filings(self, ticker, form_type="10-K", num_filings=1):
        self.downloader.get(form_type, ticker, amount=num_filings)
        file_path = os.path.join("sec_filings", ticker, form_type)
        return self.extract_risk_factors(file_path)

    def extract_risk_factors(self, file_path):
        risk_sections = []
        for filename in os.listdir(file_path):
            if filename.endswith(".txt"):  # SEC filings are text-heavy
                with open(os.path.join(file_path, filename), "r", encoding="utf-8") as f:
                    soup = BeautifulSoup(f.read(), "html.parser")
                    risk_sections.append(soup.get_text())
        return risk_sections

# Example Usage
edgar_tool = SECEdgarTool()
risks = edgar_tool.fetch_filings("AAPL", "10-K")
print(risks[0][:500])  # Show first 500 characters of the risk section
```

Why sec-edgar-downloader?

- Automates SEC retrieval (no manual parsing).
- Works with batch downloads.
