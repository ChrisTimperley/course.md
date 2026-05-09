"""MkDocs backend adapter for coursemd."""

from __future__ import annotations

from typing import Any

__all__ = ["CoursemdPlugin"]


def __getattr__(name: str) -> Any:
    if name != "CoursemdPlugin":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from coursemd.integrations.mkdocs.plugin import CoursemdPlugin

    return CoursemdPlugin
