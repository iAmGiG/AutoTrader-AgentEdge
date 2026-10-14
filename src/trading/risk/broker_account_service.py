"""
BrokerAccountService - real account data for SimpleRiskManager.

Reads portfolio value, buying power and positions through a broker order manager,
so risk checks use the actual account instead of demo values.
"""

from typing import Any, Dict, List


class BrokerAccountService:
    """
    Async account lookups backed by an order manager's broker calls.

    The order manager must provide ``get_account_status()`` (a dict with
    ``portfolio_value`` and ``buying_power``) and ``get_positions()`` (dicts with
    ``symbol``, ``qty`` and ``market_value``), as AlpacaOrderManager does. Failures
    propagate so the risk check can fail closed.
    """

    def __init__(self, order_manager):
        self._order_manager = order_manager

    async def get_portfolio_value(self, user_id: str = "default") -> float:
        return float(self._order_manager.get_account_status()["portfolio_value"])

    async def get_buying_power(self, user_id: str = "default") -> float:
        return float(self._order_manager.get_account_status()["buying_power"])

    async def get_positions(self, user_id: str = "default") -> List[Dict[str, Any]]:
        return self._order_manager.get_positions()
