"""Undo module-level side effects of tests that import code against stubs.

monkeypatch restores the names it patched, but not what was built from them: modules
imported while a stub was installed stay bound to it, and get_config() keeps the instance
it created. sandboxed_modules() snapshots sys.modules and the config singleton and restores
both on exit, evicting only project modules first imported inside the block (re-importing
third-party C extensions such as numpy is not safe).
"""

import contextlib
import sys

PROJECT_PREFIXES = ("src.", "config_defaults.", "config.")


def _is_project_module(name: str, extra_names) -> bool:
    return (
        name in ("src", "config_defaults", "config")
        or name.startswith(PROJECT_PREFIXES)
        or (name in extra_names)
    )


@contextlib.contextmanager
def sandboxed_modules(*extra_names: str):
    """Restore sys.modules and config_defaults.trading_config._config_instance on exit.

    Args:
        extra_names: Additional module names to evict if they were added inside the block
            (e.g. modules loaded directly from a file under a test-only name).
    """
    import config_defaults.trading_config as trading_config

    saved = dict(sys.modules)
    saved_config = trading_config._config_instance
    try:
        yield
    finally:
        for name in list(sys.modules):
            if name not in saved and _is_project_module(name, extra_names):
                del sys.modules[name]
        for name, module in saved.items():
            if sys.modules.get(name) is not module:
                sys.modules[name] = module
        trading_config._config_instance = saved_config
