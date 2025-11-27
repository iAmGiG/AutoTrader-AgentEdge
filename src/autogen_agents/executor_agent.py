#!/usr/bin/env python3
"""
Minimal Executor Agent - Paper trading only
"""
from typing import Dict

from .base_agent import BaseAgent


class ExecutorAgent(BaseAgent):
    """
    Minimal executor for paper trading tests.
    No complex position management - just track trades.
    """

    def __init__(self, name="executor_agent", initial_capital=100000, **kwargs):
        super().__init__(name=name, **kwargs)
        self.capital = initial_capital
        self.positions = {}
        self.trade_history = []

    def execute_paper_trade(self, signal: Dict) -> Dict:
        """Simple paper trade execution."""
        # Just track: symbol, action, price, shares
        # Return: execution confirmation
        pass

    def generate_reply(self, messages, context=None) -> str:
        """AutoGen interface."""
        # Parse trade request
        # Execute paper trade
        # Return confirmation
        pass
