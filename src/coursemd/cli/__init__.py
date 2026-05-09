"""CLI package exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_APP_EXPORTS = {
    "AppState",
    "app",
    "main",
    "main_callback",
}

__all__ = sorted(
    _APP_EXPORTS
    | {
        "typer",
    }
)


def main(*args: Any, **kwargs: Any) -> int:
    module = import_module("coursemd.cli.bootstrap")
    bootstrap_main = getattr(module, "main")
    return int(bootstrap_main(*args, **kwargs))


def __getattr__(name: str) -> Any:
    if name == "typer":
        return import_module("typer")
    if name in _APP_EXPORTS:
        module = import_module("coursemd.cli.bootstrap")
        return getattr(module, name)
    raise AttributeError(f"module 'coursemd.cli' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _APP_EXPORTS)
