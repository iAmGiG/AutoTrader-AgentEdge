#!/usr/bin/env python3
"""Diagnose MACD conditions to find good test periods.

This script analyzes historical data to find periods where MACD < 0
and then starts recovering, which are the entry conditions for our strategy.
"""
import pandas as pd
from src.tools.processors.indicator_library import macd
from src.tools.data_sources.market.market_data_tool import MarketDataTool
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


def find_macd_opportunities(symbol: str, start: str, end: str):
    """Find periods where MACD is negative and recovering."""
    print(f"\n🔍 Analyzing {symbol} from {start} to {end}")

    # Fetch market data using Yahoo Finance (no rate limits)
    market_tool = MarketDataTool(config={"data_source": "yahoo"})
    data = market_tool.fetch_market_data(symbol, start, end)

    if data is None or data.empty:
        print(f"❌ No data available for {symbol}")
        return

    print(f"✅ Fetched {len(data)} days of data")

    # Calculate MACD
    macd_line, signal_line, histogram = macd(data['Close'])

    # Create DataFrame with MACD values
    macd_data = pd.DataFrame({
        'MACD': macd_line,
        'Signal': signal_line,
        'Histogram': histogram
    }, index=data.index)

    # Find opportunities
    opportunities = []

    for i in range(1, len(macd_data)):
        macd_today = macd_data.iloc[i]['MACD']
        macd_yesterday = macd_data.iloc[i-1]['MACD']

        # Check entry conditions
        if macd_yesterday < 0 and macd_today > macd_yesterday:
            opportunities.append({
                'date': macd_data.index[i].strftime('%Y-%m-%d'),
                'macd_yesterday': round(macd_yesterday, 2),
                'macd_today': round(macd_today, 2),
                'improvement': round(macd_today - macd_yesterday, 2),
                'price': data.iloc[i]['Close']
            })

    print(f"\n📊 Found {len(opportunities)} potential entry points:")

    if opportunities:
        # Show first 10
        for i, opp in enumerate(opportunities[:10]):
            print(f"  {opp['date']}: MACD {opp['macd_yesterday']} → {opp['macd_today']} "
                  f"(+{opp['improvement']}) @ ${opp['price']:.2f}")

        if len(opportunities) > 10:
            print(f"  ... and {len(opportunities) - 10} more")

    return opportunities


def main():
    """Analyze multiple symbols and periods."""

    # Test periods known for volatility
    test_cases = [
        # Symbol, Start, End, Description
        ("SPY", "2020-03-01", "2020-04-30", "COVID Crash"),
        ("NVDA", "2022-10-01", "2022-11-30", "2022 Tech Correction"),
        ("AAPL", "2018-12-01", "2019-01-31", "2018 Q4 Correction"),
        ("TSLA", "2022-05-01", "2022-06-30", "Growth Stock Selloff"),
        ("QQQ", "2023-03-01", "2023-04-30", "Banking Crisis"),
    ]

    all_opportunities = []

    for symbol, start, end, description in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {description}")
        opportunities = find_macd_opportunities(symbol, start, end)

        if opportunities:
            all_opportunities.append({
                'symbol': symbol,
                'period': f"{start} to {end}",
                'description': description,
                'count': len(opportunities),
                'first_date': opportunities[0]['date'],
                'last_date': opportunities[-1]['date']
            })

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY: Best Periods for Testing")
    print("="*60)

    # Sort by opportunity count
    all_opportunities.sort(key=lambda x: x['count'], reverse=True)

    for opp in all_opportunities:
        print(f"\n{opp['description']} ({opp['symbol']})")
        print(f"  Period: {opp['period']}")
        print(f"  Opportunities: {opp['count']}")
        print(f"  Date range: {opp['first_date']} to {opp['last_date']}")

    if all_opportunities:
        best = all_opportunities[0]
        print(f"\n🎯 BEST PERIOD: {best['description']}")
        print(
            f"   Run: python scripts/compare_strategies.py {best['symbol']} {best['period'].split(' to ')[0]} {best['period'].split(' to ')[1]}")


if __name__ == "__main__":
    main()
