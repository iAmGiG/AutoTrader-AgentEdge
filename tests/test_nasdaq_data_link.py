#!/usr/bin/env python3
"""Test NASDAQ Data Link functionality."""
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

print("Testing NASDAQ Data Link...")

# Test import
try:
    from src.tools.data_sources.market.nasdaq_data_link_tool import NasdaqDataLinkTool
    print("✅ NasdaqDataLinkTool imported successfully")
except ImportError as e:
    print(f"❌ Failed to import NasdaqDataLinkTool: {e}")
    sys.exit(1)

# Test initialization
try:
    tool = NasdaqDataLinkTool()
    print("✅ NasdaqDataLinkTool initialized")
except Exception as e:
    print(f"❌ Failed to initialize: {e}")
    sys.exit(1)

# Test data fetch
try:
    print("\nFetching AAPL data for October 2022...")
    df = tool.fetch_stock_data("AAPL", "2022-10-01", "2022-10-31")

    if df is not None and not df.empty:
        print(f"✅ Data retrieved: {len(df)} days")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        print(
            f"   Sample close prices: ${df['Close'].iloc[0]:.2f} to ${df['Close'].iloc[-1]:.2f}")
    else:
        print("❌ No data returned")
except Exception as e:
    print(f"❌ Error fetching data: {type(e).__name__}: {e}")

# Test as fallback in MarketDataTool
print("\n" + "="*60)
print("Testing NASDAQ as fallback in MarketDataTool...")
try:
    from src.tools.data_sources.market.market_data_tool import MarketDataTool

    # Force NASDAQ as primary source
    tool = MarketDataTool(config={"data_source": "nasdaq"})
    df = tool.fetch_market_data("AAPL", "2022-10-01", "2022-10-31")

    if df is not None and not df.empty:
        print(f"✅ MarketDataTool with NASDAQ: {len(df)} days retrieved")
    else:
        print("❌ MarketDataTool returned no data")

except Exception as e:
    print(f"❌ MarketDataTool error: {e}")
