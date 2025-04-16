#!/usr/bin/env python3
"""
Super simple proof of concept for fetching stock data and analyzing it.

This avoids AutoGen's tool system completely to get a working demo.
"""

import sys
import os
import json
import pandas as pd
import datetime
import traceback

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath('.'))

# Import configuration
from config.config_loader import ConfigLoader

# Import the Yahoo Finance tool directly
from src.tools.data_sources.yahoo_finance_tool import YahooFinanceTool

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import openai
        import yfinance
        print("✓ All dependencies verified")
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Make sure you're in the correct conda environment.")
        print("Try: conda activate AutoGen")
        return False

def fetch_stock_data(ticker="AAPL", days=7):
    """
    Fetch stock data using Yahoo Finance.
    
    Args:
        ticker: Stock symbol to fetch
        days: Number of days to fetch
        
    Returns:
        DataFrame with stock data
    """
    print(f"Fetching {days} days of data for {ticker}...")
    
    # Calculate start date
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Fetch data
    try:
        tool = YahooFinanceTool()
        data = tool.fetch_stock_data(ticker, start_date, end_date)
        
        if data is not None and not data.empty:
            print(f"✓ Fetch successful: {len(data)} rows")
            print("\nFirst few rows:")
            print(data.head(3))
            return data
        else:
            print("✗ Fetch returned empty DataFrame")
            return None
    except Exception as e:
        print(f"✗ Error fetching data: {e}")
        traceback.print_exc()
        return None

def fetch_news(keyword="AAPL", count=5):
    """
    Simple function to fetch news headlines.
    
    This is just a placeholder that returns hardcoded news to demonstrate the concept.
    """
    print(f"Fetching {count} news articles for {keyword}...")
    
    # Mock news data
    mock_news = pd.DataFrame({
        'title': [
            f"{keyword} reports record quarterly earnings", 
            f"Analysts bullish on {keyword} outlook",
            f"New products expected from {keyword} next month",
            f"Market reaction to {keyword} announcement",
            f"{keyword} expands operations globally"
        ],
        'date': pd.date_range(end=datetime.datetime.now(), periods=5, freq='D'),
        'source': ['Bloomberg', 'CNBC', 'Reuters', 'WSJ', 'Yahoo Finance'],
        'url': [f"https://example.com/news/{i}" for i in range(1, 6)]
    })
    
    print("\nSample news headlines:")
    for i, row in mock_news.head(3).iterrows():
        print(f"- {row['title']} ({row['source']})")
    
    return mock_news.head(count)

def analyze_data(market_data, news_data, ticker):
    """
    Use OpenAI to analyze market data and news.
    """
    if market_data is None or len(market_data) == 0:
        return f"No market data available for {ticker}"
        
    # Load OpenAI key
    loader = ConfigLoader()
    openai_key = loader.get("open_ai_key")
    model_name = loader.get("open_model") or "gpt-4o"
    
    print(f"\nAnalyzing data using {model_name}...")
    
    try:
        # Import OpenAI
        import openai
        client = openai.OpenAI(api_key=openai_key)
        
        # Calculate basic metrics for market data
        if len(market_data) > 1:
            first_price = market_data['Close'].iloc[0]
            last_price = market_data['Close'].iloc[-1]
            percent_change = ((last_price - first_price) / first_price) * 100
            
            # Calculate daily changes
            market_data['Daily_Change'] = market_data['Close'].pct_change() * 100
            daily_changes = market_data['Daily_Change'].dropna().tolist()
            
            # Calculate volatility
            volatility = market_data['Daily_Change'].std()
            
            # Prepare market data points
            market_points = {
                "ticker": ticker,
                "period": f"{len(market_data)} days",
                "first_price": round(first_price, 2),
                "last_price": round(last_price, 2),
                "percent_change": round(percent_change, 2),
                "volatility": round(volatility, 2),
                "days_up": sum(1 for x in daily_changes if x > 0),
                "days_down": sum(1 for x in daily_changes if x < 0)
            }
        else:
            market_points = {
                "ticker": ticker,
                "period": "1 day",
                "price": round(market_data['Close'].iloc[0], 2),
                "volume": int(market_data['Volume'].iloc[0])
            }
        
        # Prepare news data
        news_points = []
        for _, row in news_data.iterrows():
            news_points.append({
                "title": row['title'],
                "source": row['source'],
                "date": row['date'].strftime("%Y-%m-%d")
            })
        
        # Create the prompt with both market and news data
        prompt = f"""
        You are a financial analyst. Analyze the following data for {ticker} and provide insights:
        
        MARKET DATA:
        {json.dumps(market_points, indent=2)}
        
        NEWS HEADLINES:
        {json.dumps(news_points, indent=2)}
        
        Please provide:
        1. A summary of the stock's recent performance
        2. Key observations about price movements
        3. Analysis of how recent news might be affecting the stock
        4. A brief outlook based on both technical and news indicators
        
        Keep your response concise and focused on the data provided.
        """
        
        # Call OpenAI API
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a financial analyst specializing in stock market analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return completion.choices[0].message.content
        
    except Exception as e:
        traceback.print_exc()
        return f"Error analyzing data: {str(e)}"

def main():
    """Main entry point for the proof of concept."""
    print("\n===== Simple Stock Data Analysis Proof of Concept =====")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Get ticker from command line or use default
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    
    print("\n----- Step 1: Fetch Market Data -----")
    market_data = fetch_stock_data(ticker=ticker, days=14)
    
    print("\n----- Step 2: Fetch News Data -----")
    news_data = fetch_news(keyword=ticker, count=5)
    
    if market_data is not None and not market_data.empty:
        print("\n----- Step 3: Data Analysis -----")
        analysis = analyze_data(market_data, news_data, ticker)
        
        print("\n===== Analysis =====")
        print(analysis)
    else:
        print(f"\n✗ Failed to fetch any data for {ticker}")
    
    print("\n===== Proof of Concept Complete =====")
    print("Run the script with a ticker symbol to analyze different stocks:")
    print("./run_simple_agent.sh MSFT")

if __name__ == "__main__":
    main()