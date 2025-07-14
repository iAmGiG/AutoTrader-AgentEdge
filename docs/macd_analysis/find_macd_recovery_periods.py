#!/usr/bin/env python3
"""
Diagnostic script to find periods where MACD < 0 recovery pattern occurs.
This helps identify date ranges for testing that would actually generate trades.
"""
import sys
import os

# fmt: off
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# fmt: on

from datetime import timedelta
from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.tools.processors.indicator_library import macd


def find_macd_recovery_periods(symbol, start_date, end_date):
    """Find periods where MACD was < 0 yesterday and rising today."""
    print(f"\n🔍 Analyzing {symbol} from {start_date} to {end_date}")

    # Fetch market data
    market_tool = MarketDataTool()
    df = market_tool.fetch_market_data(symbol, start_date, end_date)

    if df.empty:
        print(f"❌ No data available for {symbol}")
        return []

    # Calculate MACD
    macd_line, signal_line, histogram = macd(df['Close'])

    # Find recovery patterns
    recovery_dates = []

    for i in range(1, len(macd_line)):
        macd_today = macd_line.iloc[i]
        macd_yesterday = macd_line.iloc[i - 1]

        # Check for MACD < 0 recovery pattern
        if macd_yesterday < 0 and macd_today > macd_yesterday:
            date = df.index[i]
            recovery_dates.append({
                'date': date,
                'macd_yesterday': macd_yesterday,
                'macd_today': macd_today,
                'macd_change': macd_today - macd_yesterday,
                'price': df.loc[date]['Close']
            })

    return recovery_dates


def main():
    # Test multiple symbols and periods
    test_cases = [
        # 2020 COVID crash and recovery
        ('SPY', '2020-02-15', '2020-04-30'),
        ('QQQ', '2020-02-15', '2020-04-30'),
        ('AAPL', '2020-02-15', '2020-04-30'),

        # 2022 tech correction
        ('META', '2022-01-01', '2022-12-31'),
        ('TSLA', '2022-01-01', '2022-12-31'),

        # 2018 December correction
        ('SPY', '2018-10-01', '2019-01-31'),

        # Recent periods
        ('NVDA', '2024-01-01', '2024-12-31'),
    ]

    all_recovery_periods = []

    for symbol, start, end in test_cases:
        recoveries = find_macd_recovery_periods(symbol, start, end)

        if recoveries:
            print(f"\n✅ Found {len(recoveries)} MACD recovery patterns for {symbol}:")
            for r in recoveries[:5]:  # Show first 5
                print(
                    f"   {r['date'].date()}: MACD {r['macd_yesterday']:.4f} → {r['macd_today']:.4f} (Price: ${r['price']:.2f})")

            # Find best multi-day recovery periods
            for i, r in enumerate(recoveries):
                # Look for consecutive days with recovery
                period_start = r['date']
                period_end = r['date']

                # Check next few days
                for j in range(i + 1, min(i + 5, len(recoveries))):
                    if (recoveries[j]['date'] - period_end).days <= 3:
                        period_end = recoveries[j]['date']

                if (period_end - period_start).days >= 3:
                    all_recovery_periods.append({
                        'symbol': symbol,
                        'start': period_start - timedelta(days=2),
                        'end': period_end + timedelta(days=2),
                        'recovery_days': (period_end - period_start).days + 1
                    })
        else:
            print(f"\n❌ No MACD recovery patterns found for {symbol}")

    # Print best periods for testing
    print("\n" + "=" * 60)
    print("🎯 RECOMMENDED TEST PERIODS (with MACD < 0 recoveries):")
    print("=" * 60)

    # Sort by recovery days
    best_periods = sorted(all_recovery_periods, key=lambda x: x['recovery_days'], reverse=True)[:10]

    for p in best_periods:
        print(
            f"\npython scripts/backtest_mas.py {p['symbol']} {p['start'].date()} {p['end'].date()}")
        print(f"  → {p['recovery_days']} recovery days in period")


if __name__ == "__main__":
    main()
