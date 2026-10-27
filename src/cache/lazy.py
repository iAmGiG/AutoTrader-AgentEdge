"""
A shared cache instance that is built on first use (#600).

The module-level caches (cache_adapter, unified_broker_cache) used to be built at
import, which created .cache/trading_data.db in the working directory of anything that
imported src.trading. A LazyInstance stands in for them: importers keep using the same
name, and the database is opened on the first attribute access.
"""

import threading
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


_OWN = frozenset({"_factory", "_instance", "_lock"})


class LazyInstance(Generic[T]):
    """
    Stands in for a shared instance; builds it with ``factory`` on first use.

    Reads, writes and deletes of attributes go to the instance (so
    ``monkeypatch.setattr(cache_adapter, "cache", fake)`` patches the real adapter);
    only the stand-in's own ``_factory``, ``_instance`` and ``_lock`` stay on it.
    """

    def __init__(self, factory: Callable[[], T]):
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_instance", None)
        object.__setattr__(self, "_lock", threading.Lock())

    def get(self) -> T:
        """The shared instance, built on the first call."""
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    object.__setattr__(self, "_instance", self._factory())
        return self._instance

    def __getattr__(self, name: str) -> Any:
        # Only reached for names not on the stand-in. Its own names missing means it was
        # never initialised (copy/pickle); dunder probes must not build the instance.
        if name in _OWN or name.startswith("__"):
            raise AttributeError(name)
        return getattr(self.get(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _OWN:
            object.__setattr__(self, name, value)
        else:
            setattr(self.get(), name, value)

    def __delattr__(self, name: str) -> None:
        if name in _OWN:
            object.__delattr__(self, name)
        else:
            delattr(self.get(), name)

    def __repr__(self) -> str:
        state = "built" if self._instance is not None else "not built"
        return f"<LazyInstance of {getattr(self._factory, '__name__', self._factory)} ({state})>"
