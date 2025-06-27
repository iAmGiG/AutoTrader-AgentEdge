"""Simple MAS back-test utility.

Walk day-by-day through a date range, calling the ``CoordinatorAgent`` and
``StrategyAgent`` to simulate a naive trading strategy.  Basic equity and
trade statistics are printed on completion.

Usage:
    python backtest_mas.py SYMBOL START END

Example:
    python backtest_mas.py NVDA 2023-01-01 2024-12-31
"""
import traceback
import asyncio
from typing import List, Dict, Optional
import pandas as pd
from src.tools.cache import MarketDataCache
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.strategy_agent import StrategyAgent
from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.tools.date_utils import process_date_param
import sys
import os
# Add src to Python path so imports work - MUST BE BEFORE OTHER IMPORTS
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

# Define cache directory for output files
CACHE_DIR = os.path.join(os.path.dirname(
    __file__), '..', '.cache', 'backtests')
os.makedirs(CACHE_DIR, exist_ok=True)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    start = process_date_param(sys.argv[2]) if len(
        sys.argv) > 2 else "2025-05-01"
    end = process_date_param(sys.argv[3]) if len(
        sys.argv) > 3 else "2025-05-06"

    # Initialize cache
    cache = MarketDataCache()

    # Try to get data from cache first
    print(f"Checking cache for {symbol} from {start} to {end}")
    prices = cache.get(symbol, start, end, "alpha_vantage")

    if prices is None or prices.empty:
        # Use MarketDataTool with Alpha Vantage as the preferred source
        # This avoids Yahoo Finance IP blocks and uses our available API
        print(
            f"Cache miss - fetching market data for {symbol} from {start} to {end}")
        market_tool = MarketDataTool({"data_source": "alpha_vantage"})
        prices = market_tool.fetch_market_data(symbol, start, end)

        # Cache the data if successful
        if not prices.empty:
            cache.set(symbol, start, end, "alpha_vantage", prices)
        else:
            print("No price data found from Alpha Vantage")
            print("Trying FMP as backup...")

            # Check cache for FMP data
            prices = cache.get(symbol, start, end, "fmp")

            if prices is None or prices.empty:
                market_tool = MarketDataTool({"data_source": "fmp"})
                prices = market_tool.fetch_market_data(symbol, start, end)

                # Cache FMP data if successful
                if not prices.empty:
                    cache.set(symbol, start, end, "fmp", prices)

    if prices.empty:
        print("No price data found from any source")
        return

    print(f"Successfully fetched {len(prices)} days of price data")
    print(f"Price data columns: {list(prices.columns)}")

    # Work with the close prices only
    prices = prices["Close"].dropna()
    print(f"Using {len(prices)} days of close prices")

    coord = CoordinatorAgent()
    strat = StrategyAgent()

    equity = 100_000.0
    shares = 0
    equity_curve: List[Dict[str, float]] = []
    trades: List[Dict[str, float]] = []

    # Track statistics
    total_days = len(prices)
    successful_days = 0
    failed_days = 0
    skipped_days = 0

    for i, (ts, price) in enumerate(prices.items()):
        date_str = ts.date().isoformat()

        # Progress indicator
        print(f"\n--- Processing {i+1}/{total_days} days: {date_str} ---")
        print(f"Price: ${price:.2f}")

        try:
            # Get signals from coordinator
            sigs = asyncio.run(coord.get_signals(date_str, symbol))

            # Validate signals - skip if incomplete
            sentiment_data = sigs.get('sentiment', {})
            technical_data = sigs.get('technical', {})

            # Check for None values or missing data
            if not sigs.get('ok', False):
                print(
                    f"⚠️  Skipping {date_str}: Error in signals - {sigs.get('error', 'Unknown error')}")
                skipped_days += 1
                continue

            if not sentiment_data or sentiment_data.get('score') is None:
                print(f"⚠️  Skipping {date_str}: Missing sentiment data")
                skipped_days += 1
                continue

            if not technical_data or technical_data.get('macd_today') is None:
                print(f"⚠️  Skipping {date_str}: Missing technical data")
                skipped_days += 1
                continue

            print(
                f"Signals received: sentiment={sentiment_data}, technical={technical_data}")

            # Make trading decision
            decision = strat.decide_trade(
                sigs, price=float(price), trade_date=date_str)
            print(f"Decision: {decision}")

            qty = decision.get("qty", 100)

            # Execute trades
            if decision.get("action") == "BUY" and equity >= price * qty:
                equity -= price * qty
                shares += qty
                trades.append({
                    "date": date_str,
                    "action": "BUY",
                    "price": float(price),
                    "qty": qty,
                    "sentiment": sentiment_data.get('score', 0),
                    "macd_today": technical_data.get('macd_today', 0)
                })
                print(f"✅ Executed BUY: {qty} shares @ ${price:.2f}")

            elif decision.get("action") == "SELL" and shares > 0:
                sell_value = price * shares
                equity += sell_value
                trades.append({
                    "date": date_str,
                    "action": "SELL",
                    "price": float(price),
                    "qty": shares,
                    "sentiment": sentiment_data.get('score', 0),
                    "macd_today": technical_data.get('macd_today', 0)
                })
                print(
                    f"✅ Executed SELL: {shares} shares @ ${price:.2f} = ${sell_value:.2f}")
                shares = 0

            # Update equity curve
            current_value = equity + shares * price
            equity_curve.append({
                "date": date_str,
                "equity": current_value,
                "shares": shares,
                "price": float(price)
            })

            # Update strategy agent's equity curve
            strat.update_equity_curve(date_str, current_value, float(price))

            successful_days += 1

        except Exception as e:
            print(f"   Error processing {date_str}: {str(e)}")
            print(f"   Exception type: {type(e).__name__}")
            traceback.print_exc()
            failed_days += 1

            # Still update equity curve with current holdings
            current_value = equity + shares * price
            equity_curve.append({
                "date": date_str,
                "equity": current_value,
                "shares": shares,
                "price": float(price),
                "error": True
            })

            # Update strategy agent's equity curve even on error
            strat.update_equity_curve(date_str, current_value, float(price))
            continue

    # Calculate final statistics
    final_value = equity + shares * prices.iloc[-1]
    initial_value = 100_000.0
    total_return = (final_value - initial_value) / initial_value * 100

    print("\n" + "="*60)
    print(f"BACKTEST SUMMARY: {symbol}")
    print(f"Period: {start} to {end}")
    print("="*60)

    print(f"\nProcessing Statistics:")
    print(f"  Total days: {total_days}")
    print(
        f"  Successful: {successful_days} ({successful_days/total_days*100:.1f}%)")
    print(f"  Failed: {failed_days} ({failed_days/total_days*100:.1f}%)")
    print(f"  Skipped: {skipped_days} ({skipped_days/total_days*100:.1f}%)")

    print(f"\nPerformance:")
    print(f"  Initial equity: ${initial_value:,.2f}")
    print(f"  Final equity: ${final_value:,.2f}")
    print(f"  Total return: {total_return:+.2f}%")
    print(f"  Final shares held: {shares}")

    if trades:
        print(f"\nTrade Summary:")
        print(f"  Total trades: {len(trades)}")
        trades_df = pd.DataFrame(trades)
        buys = trades_df[trades_df['action'] == 'BUY']
        sells = trades_df[trades_df['action'] == 'SELL']
        print(f"  Buys: {len(buys)}")
        print(f"  Sells: {len(sells)}")

        print("\nDetailed Trades:")
        print(trades_df.to_string(index=False))

        # Save trades to CSV
        csv_filename = os.path.join(
            CACHE_DIR, f"{symbol}_trades_{start}_{end}.csv")
        trades_df.to_csv(csv_filename, index=False)
        print(f"\n✅ Trades saved to: {csv_filename}")
    else:
        print("\n No trades executed")

    # Save equity curve to CSV
    if equity_curve:
        equity_df = pd.DataFrame(equity_curve)
        equity_filename = os.path.join(
            CACHE_DIR, f"{symbol}_equity_{start}_{end}.csv")
        equity_df.to_csv(equity_filename, index=False)
        print(f"✅ Equity curve saved to: {equity_filename}")

    # Calculate and display comprehensive metrics
    metrics = strat.calculate_metrics(initial_capital=initial_value)
    strat.print_metrics_summary(metrics)

    # Save metrics to CSV
    metrics_df = pd.DataFrame([metrics])
    metrics_filename = os.path.join(
        CACHE_DIR, f"{symbol}_metrics_{start}_{end}.csv")
    metrics_df.to_csv(metrics_filename, index=False)
    print(f"\n✅ Metrics saved to: {metrics_filename}")


if __name__ == "__main__":
    main()
