"""MkDocs backend adapter for coursemd."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["CoursemdPlugin", "DraftsPlugin"]

_LAZY = {
    "CoursemdPlugin": "coursemd.integrations.mkdocs.plugin",
    "DraftsPlugin": "coursemd.integrations.mkdocs.drafts",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_path), name)
