"""
In-House Backtesting Framework

Lightweight backtesting engine built around validated VoterAgent logic.
Refactored from experiment_293_macd_vs_voting.py (reproduces its 0.856 in-sample Sharpe).
"""

from .backtest_engine import BacktestEngine
from .portfolio import Portfolio
from .results import BacktestResults

__all__ = ["BacktestEngine", "Portfolio", "BacktestResults"]
