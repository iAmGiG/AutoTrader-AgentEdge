#!/usr/bin/env python3
"""Test different market data sources to see which are working."""
from src.tools.data_sources.market.market_data_tool import MarketDataTool
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


def test_data_source(source: str, symbol: str, start: str, end: str):
    """Test a specific data source."""
    print(f"\n{'='*60}")
    print(f"Testing {source.upper()} for {symbol} ({start} to {end})")
    print('='*60)

    try:
        tool = MarketDataTool(data_source=source)
        df = tool.fetch_market_data(symbol, start, end)

        if df is not None and not df.empty:
            print(f"✅ SUCCESS: Retrieved {len(df)} days of data")
            print(f"   Date range: {df.index[0]} to {df.index[-1]}")
            print(f"   Columns: {list(df.columns)}")
            print(
                f"   Sample prices: ${df['Close'].iloc[0]:.2f} to ${df['Close'].iloc[-1]:.2f}")
            return True
        else:
            print(f"❌ FAILED: No data returned")
            return False

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {str(e)}")
        return False


def main():
    """Test all available data sources."""
    # Test parameters
    symbol = "AAPL"
    start = "2024-01-01"
    end = "2024-01-31"

    print("🔍 Testing Market Data Sources")
    print(f"Symbol: {symbol}, Period: {start} to {end}")

    # Test each source
    sources = ["yahoo", "alpha_vantage", "fmp", "nasdaq"]
    results = {}

    for source in sources:
        results[source] = test_data_source(source, symbol, start, end)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)

    working_sources = [s for s, worked in results.items() if worked]
    failed_sources = [s for s, worked in results.items() if not worked]

    if working_sources:
        print(f"\n✅ Working sources: {', '.join(working_sources)}")
        print(
            f"\n🎯 RECOMMENDATION: Use '{working_sources[0]}' as primary data source")
        print(
            f"   Update scripts to use: MarketDataTool(data_source='{working_sources[0]}')")

    if failed_sources:
        print(f"\n❌ Failed sources: {', '.join(failed_sources)}")

    # Test fallback chain
    if len(working_sources) > 1:
        print(f"\n🔄 Fallback chain test...")
        # Force a fallback by using a non-existent symbol
        tool = MarketDataTool(data_source=working_sources[0])
        test_df = tool.fetch_market_data("INVALID_SYMBOL_XYZ", start, end)
        if test_df is not None and test_df.empty:
            print("   Fallback chain working correctly")


if __name__ == "__main__":
    main()
