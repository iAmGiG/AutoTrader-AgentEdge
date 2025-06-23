"""Simple MAS back-test utility.

Walk day-by-day through a date range, calling the ``CoordinatorAgent`` and
``StrategyAgent`` to simulate a naive trading strategy.  Basic equity and
trade statistics are printed on completion.

Usage:
    python backtest_mas.py SYMBOL START END

Example:
    python backtest_mas.py NVDA 2023-01-01 2024-12-31
"""

import asyncio
import sys
from typing import List, Dict

import pandas as pd

from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.strategy_agent import StrategyAgent
from src.tools.tools import YahooFinanceTool
from src.tools.date_utils import process_date_param


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    start = process_date_param(sys.argv[2]) if len(sys.argv) > 2 else "2023-01-01"
    end = process_date_param(sys.argv[3]) if len(sys.argv) > 3 else "2024-12-31"

    yf = YahooFinanceTool()
    prices = yf.fetch_stock_data(symbol, start, end)
    if prices.empty:
        print("No price data found")
        return
    prices = prices["Close"].dropna()

    coord = CoordinatorAgent()
    strat = StrategyAgent()

    equity = 100_000.0
    shares = 0
    equity_curve: List[Dict[str, float]] = []
    trades: List[Dict[str, float]] = []

    for ts, price in prices.items():
        date_str = ts.date().isoformat()
        sigs = asyncio.run(coord.get_signals(date_str, symbol))
        decision = strat.decide_trade(sigs)
        qty = decision.get("qty", 100)

        if decision.get("action") == "BUY" and equity >= price * qty:
            equity -= price * qty
            shares += qty
            trades.append({"date": date_str, "action": "BUY", "price": price, "qty": qty})
        elif decision.get("action") == "SELL" and shares > 0:
            equity += price * shares
            trades.append({"date": date_str, "action": "SELL", "price": price, "qty": shares})
            shares = 0

        equity_curve.append({"date": date_str, "equity": equity + shares * price})

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
