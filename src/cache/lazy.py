"""
A shared cache instance that is built on first use (#600).

The module-level caches (cache_adapter, unified_broker_cache) used to be built at
import, which created .cache/trading_data.db in the working directory of anything that
imported src.trading. A LazyInstance stands in for them: importers keep using the same
name, and the database is opened on the first attribute access.
"""

import threading
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")


class LazyInstance(Generic[T]):
    """Stands in for a shared instance; builds it with ``factory`` on first use."""

    def __init__(self, factory: Callable[[], T]):
        self._factory = factory
        self._instance: Optional[T] = None
        self._lock = threading.Lock()

    def get(self) -> T:
        """The shared instance, built on the first call."""
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._factory()
        return self._instance

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):  # copy/pickle probes must not build the instance
            raise AttributeError(name)
        return getattr(self.get(), name)

    def __repr__(self) -> str:
        state = "built" if self._instance is not None else "not built"
        return f"<LazyInstance of {getattr(self._factory, '__name__', self._factory)} ({state})>"
