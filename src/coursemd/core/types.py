"""Public type definitions for course data structures."""

from __future__ import annotations

import typing as t
from typing import TYPE_CHECKING

from coursemd.core.models.rubric import RubricCriterion, RubricSection, RubricTier

if TYPE_CHECKING:
    import datetime as dt


class EventDict(t.TypedDict, total=False):
    """Represents a course event."""

    kind: str
    title: str
    date: dt.date
    link: str | None


class BreakDict(t.TypedDict):
    """Represents a course break period."""

    name: str
    start: dt.date
    end: dt.date


__all__ = [
    "BreakDict",
    "EventDict",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
]
