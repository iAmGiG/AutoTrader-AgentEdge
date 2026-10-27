"""
Dry run for the scheduled routines (#601): broker calls that would change orders are
logged and not sent.

DryRunOrderManager wraps an order manager. Reads (``get_*`` methods) pass through;
every other method returns a result with status ``DRY_RUN_STATUS``, which callers treat
as "not submitted". It blocks by default, so a write method added to the order manager
later is blocked too.
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

DRY_RUN_STATUS = "dry_run"
DRY_RUN_MESSAGE = "dry run: not sent"
_READ_PREFIX = "get_"
_PLAIN_VALUES = (str, int, float, bool, type(None))


class DryRunOrderManager:
    """An order manager that sends nothing: reads pass through, other calls are logged."""

    def __init__(self, order_manager: Any):
        self._order_manager = order_manager
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        attr = getattr(self._order_manager, name)
        if callable(attr):
            return attr if name.startswith(_READ_PREFIX) else self._blocked(name)
        if isinstance(attr, _PLAIN_VALUES):
            return attr
        # A client or other object would let a caller send orders around the guard
        raise AttributeError(f"{name} is not available in a dry run")

    def _blocked(self, name: str):
        def not_sent(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            self.calls.append((name, {"args": args, **kwargs}))
            logger.info("DRY RUN: %s(%s) not sent", name, _describe(args, kwargs))
            return {
                "status": DRY_RUN_STATUS,
                "message": DRY_RUN_MESSAGE,
                "order_id": None,
                "symbol": kwargs.get("symbol"),
            }

        return not_sent


def _describe(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> str:
    parts = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
    return ", ".join(parts)
