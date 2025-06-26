"""Simple MAS back-test utility.

Walk day-by-day through a date range, calling the ``CoordinatorAgent`` and
``StrategyAgent`` to simulate a naive trading strategy.  Basic equity and
trade statistics are printed on completion.

Usage:
    python backtest_mas.py SYMBOL START END

Example:
    python backtest_mas.py NVDA 2023-01-01 2024-12-31
"""
import sys
import os
# Add src to Python path so imports work - MUST BE BEFORE OTHER IMPORTS
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from src.tools.date_utils import process_date_param
from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.agents.strategy_agent import StrategyAgent
from src.agents.coordinator_agent import CoordinatorAgent
import pandas as pd
from typing import List, Dict
import asyncio


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    start = process_date_param(sys.argv[2]) if len(
        sys.argv) > 2 else "2025-05-01"
    end = process_date_param(sys.argv[3]) if len(
        sys.argv) > 3 else "2025-05-02"

    # Use MarketDataTool with Alpha Vantage as the preferred source
    # This avoids Yahoo Finance IP blocks and uses our available API
    print(f"Fetching market data for {symbol} from {start} to {end}")
    market_tool = MarketDataTool({"data_source": "alpha_vantage"})
    prices = market_tool.fetch_market_data(symbol, start, end)
    
    if prices.empty:
        print("No price data found from Alpha Vantage")
        print("Trying FMP as backup...")
        market_tool = MarketDataTool({"data_source": "fmp"})
        prices = market_tool.fetch_market_data(symbol, start, end)
    
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

    for ts, price in prices.items():
        date_str = ts.date().isoformat()
        print(f"\n--- Processing {date_str} ---")
        print(f"Price: ${price:.2f}")
        
        sigs = asyncio.run(coord.get_signals(date_str, symbol))
        print(f"Signals received: sentiment={sigs.get('sentiment', {})}, technical={sigs.get('technical', {})}")
        
        decision = strat.decide_trade(
            sigs, price=float(price), trade_date=date_str)
        print(f"Decision: {decision}")
        
        qty = decision.get("qty", 100)

        if decision.get("action") == "BUY" and equity >= price * qty:
            equity -= price * qty
            shares += qty
            trades.append({"date": date_str, "action": "BUY",
                          "price": price, "qty": qty})
        elif decision.get("action") == "SELL" and shares > 0:
            equity += price * shares
            trades.append({"date": date_str, "action": "SELL",
                          "price": price, "qty": shares})
            shares = 0

        equity_curve.append(
            {"date": date_str, "equity": equity + shares * price})

    final_value = equity + shares * prices.iloc[-1]
    print(f"Back-test {symbol}: start={start} end={end}")
    print(f"Final equity: ${final_value:,.2f}")
    if trades:
        print("Trades:")
        print(pd.DataFrame(trades))
    else:
        print("No trades executed")


if __name__ == "__main__":
    main()
