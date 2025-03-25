# Defining the Unified DataFrame System

To ensure all tools integrate seamlessly, we’ll adopt **Pandas DataFrames** as the uniform structure across the system. Below is an outline of how the data from different tools will be stored, processed, and merged into DataFrames.

## **General Structure**

Each tool will output its data as a **DataFrame**, where each row represents a unique time interval, market event, or article, depending on the data type. Columns in these DataFrames will contain various features extracted from the raw data.

### **Market Data Tools**

- **Columns:** `Timestamp`, `Ticker`, `Open`, `High`, `Low`, `Close`, `Volume`, `Moving Averages`, etc.
- **Purpose:** Store market price data with time-series analysis features.

### **News Data Tools**

- **Columns:** `Timestamp`, `Headline`, `Article Text`, `Source`, `Sentiment Score`, etc.
- **Purpose:** Store news articles, their sentiments, and relevant metadata.

### **Meta-Tokens & Aggregated Data**

- **Columns:** `Timestamp`, `Ticker`, `Market Sentiment`, `Article Sentiment`, `Combined Sentiment Score`, etc.
- **Purpose:** Store processed information from multiple tools, such as sentiment, market volatility, and other aggregated data points.

---

## **Data Flow and Unification Process**

### **Step 1: Fetch Data**

- Each tool fetches its respective data (market prices, news articles, etc.) and returns it as a Pandas DataFrame.

### **Step 2: Data Processing**

- **Market Data:** Calculate moving averages, volatility indicators, etc.
- **News Data:** Perform sentiment analysis (e.g., positive/negative/neutral classification).

### **Step 3: Merging DataFrames**

- Use **timestamps** for time-based alignment or **tickers** for stock market data.
- Each row of the final DataFrame represents a **unique time slice**, combining market data, news sentiment, and meta-information.

---

## **List of Tools That Need Adjustment**

### **1. NewsHeadlineTool**

**Current Output:** List of dictionaries (raw news articles).  
**Needed Adjustment:** Convert the output into a DataFrame with structured columns.

#### **New Structure:**

| Timestamp  | Headline                          | Source  | Sentiment Score |
|------------|----------------------------------|--------|-----------------|
| 2024-01-01 | "Meta to expand its AI research" | NewsAPI | 0.75            |
| 2024-01-01 | "Stock market hits new highs"    | Finnhub | 0.65            |

---

### **2. MarketDataTool**

**Current Output:** Pandas DataFrame with market data (Open, Close, Volume, etc.).  
**Needed Adjustment:** Ensure standardized DataFrame format, including **moving averages, volatility, and additional indicators**.

#### **New Structure:**

| Timestamp  | Ticker | Open  | High  | Low  | Close | Volume | MA_50 | MA_200 | Volatility |
|------------|--------|-------|-------|------|-------|--------|-------|--------|------------|
| 2024-01-01 | AAPL   | 150.0 | 155.0 | 149.0| 153.0 | 1.5M   | 152.0 | 148.0  | 0.01       |

---

### **3. SentimentAgent**

**Current Output:** Sentiment signals from news data (raw text/dictionary).  
**Needed Adjustment:** Convert sentiment data into a structured DataFrame.

#### **New Structure:**

| Timestamp  | Headline                          | Sentiment Score |
|------------|----------------------------------|-----------------|
| 2024-01-01 | "Meta to expand its AI research" | 0.75            |
| 2024-01-01 | "Stock market hits new highs"    | 0.65            |

---

### **4. StrategyAgent (Future)**

**Current Output:** Not fully implemented yet.  
**Needed Adjustment:** Merge **market and sentiment data** into a **single DataFrame** for decision-making.

#### **New Structure:**

| Timestamp  | Ticker | Market Sentiment | Article Sentiment | Combined Sentiment | MA_50 | MA_200 | Volatility |
|------------|--------|------------------|-------------------|--------------------|-------|--------|------------|
| 2024-01-01 | AAPL   | 0.75             | 0.85              | 0.80               | 152.0 | 148.0  | 0.01       |

---

### **5. Decision Engine (Future)**

**Needed Adjustment:**  

- Handle **multiple data streams** and generate **actionable insights**.
- Compute **meta-tokens** and decide actions based on **combined sentiment, market conditions, and indicators**.

#### **New Structure:**

| Timestamp  | Decision   | Risk Profile | Action |
|------------|------------|--------------|--------|
| 2024-01-01 | Buy        | Low Risk     | Buy    |

---

## **Summary of Tools Requiring Adjustments**

| Tool              | Adjustment Needed |
|------------------|-----------------|
| **NewsHeadlineTool** | Convert output into a DataFrame with timestamp, headline, source, and sentiment score. |
| **MarketDataTool**   | Ensure output includes volatility, moving averages, and other key market indicators. |
| **SentimentAgent**   | Convert processed sentiment data into a structured DataFrame. |
| **StrategyAgent**    | Merge market and sentiment data into a unified DataFrame for decision-making. |
| **Decision Engine**  | Process merged DataFrame and generate meta-tokens for decision-making. |

---

## **Summary**

To streamline data processing across the system, all tools will **output Pandas DataFrames** with a consistent structure. The key modifications include:

1. **Standardizing the NewsHeadlineTool and SentimentAgent outputs** as structured DataFrames.
2. **Enhancing the MarketDataTool** by adding additional market indicators.
3. **Designing the StrategyAgent and Decision Engine** to merge and analyze market + sentiment data for better decision-making.

Once these changes are implemented, the system will have **seamless integration** across all data sources, ensuring a robust and unified data processing pipeline.

### Summary

- All tools will use Pandas DataFrames for data processing.
- Market and sentiment data will be merged based on timestamps/tickers.
- Several tools require adjustments, mainly to standardize output formats.
- Future tools (StrategyAgent & Decision Engine) will integrate data for decision-making.
