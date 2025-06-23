from datetime import datetime
from typing import Dict

from .base_agent import BaseAgent


class StrategyAgent(BaseAgent):
    """Implements a basic MACD + sentiment trading strategy."""

    def __init__(self, name: str = "StrategyAgent", memory_system=None):
        super().__init__(name=name, tools=[], memory_system=memory_system)
        self.position = 0  # 0 = flat, 1 = long
        self.entry_price = None
        self.trade_log = []

    def generate_reply(self, messages, context=None):
        """Stub implementation required by BaseAgent."""
        raise NotImplementedError("StrategyAgent does not support conversations")

    def decide_trade(self, aggregated: Dict, price: float, trade_date: str) -> Dict:
        """Return a BUY/SELL/HOLD decision based on MACD crossovers and sentiment."""
        macd_y = aggregated["technical"].get("macd_yest")
        macd_t = aggregated["technical"].get("macd_today")
        sentiment = aggregated["sentiment"].get("score", 0)

        action = "HOLD"

        # ----- ENTRY -----
        if self.position == 0:
            if (
                macd_y is not None
                and macd_y < 0
                and macd_t is not None
                and macd_t > macd_y
                and sentiment > 0
            ):
                action = "BUY"
                self.position = 1
                self.entry_price = price

        # ----- EXIT -----
        elif self.position == 1:
            if (
                (macd_y is not None and macd_y < 0 and macd_t < macd_y)
                or (macd_y is not None and macd_y > 0 and macd_t < 0)
            ):
                action = "SELL"
                self.position = 0

        self.trade_log.append(
            {
                "date": trade_date,
                "action": action,
                "price": price,
                "macd_t": macd_t,
                "macd_y": macd_y,
                "sent": sentiment,
            }
        )

        return {
            "action": action,
            "qty": 100 if action == "BUY" else 0,
            "reason": "macd_sent_rule_v1",
        }
