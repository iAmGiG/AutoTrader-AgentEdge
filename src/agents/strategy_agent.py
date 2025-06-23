from typing import Dict
from .base_agent import BaseAgent


class StrategyAgent(BaseAgent):
    """
    Implements a hard-coded MACD + sentiment trading strategy.

    Entry:
      - If flat AND yesterday’s MACD < 0 AND today’s MACD > yesterday’s MACD
        AND sentiment > 0 → BUY

    Exit:
      - If long AND (yesterday’s MACD < 0 AND today’s MACD < yesterday’s MACD)
        OR (yesterday’s MACD > 0 AND today’s MACD < 0) → SELL

    Otherwise: HOLD
    """

    def __init__(self, name: str = "StrategyAgent", memory_system=None):
        super().__init__(name=name, tools=[], memory_system=memory_system)
        self.position = 0       # 0 = flat, 1 = long
        self.entry_price = None
        self.trade_log = []

    def generate_reply(self, messages, context=None):
        """Stub required by BaseAgent; this agent does not chat."""
        raise NotImplementedError("StrategyAgent does not support chat-based interactions")

    def decide_trade(self, aggregated: Dict, price: float, trade_date: str) -> Dict:
        """Return a BUY/SELL/HOLD decision based on MACD crossovers and sentiment."""
        macd_y = aggregated.get("technical", {}).get("macd_yest")
        macd_t = aggregated.get("technical", {}).get("macd_today")
        sentiment = aggregated.get("sentiment", {}).get("score", 0)

        action = "HOLD"

        # Entry rule
        if self.position == 0:
            if (
                macd_y is not None and macd_y < 0 and
                macd_t is not None and macd_t > macd_y and
                sentiment > 0
            ):
                action = "BUY"
                self.position = 1
                self.entry_price = price

        # Exit rule
        elif self.position == 1:
            if (
                (macd_y is not None and macd_y < 0 and macd_t < macd_y) or
                (macd_y is not None and macd_y > 0 and macd_t < 0)
            ):
                action = "SELL"
                self.position = 0

        # Log trade decision
        self.trade_log.append({
            "date":       trade_date,
            "action":     action,
            "price":      price,
            "macd_today": macd_t,
            "macd_yest":  macd_y,
            "sentiment":  sentiment,
        })

        return {
            "action": action,
            "qty":    100 if action == "BUY" else 0,
            "reason": "macd_sent_rule_v1"
        }
