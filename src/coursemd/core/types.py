"""Public type definitions for course data structures."""

from __future__ import annotations

import datetime as dt
import typing as t

from coursemd.core.models.rubric import RubricCriterion, RubricSection, RubricTier


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


class CheckpointDict(t.TypedDict):
    """Represents a checkpoint within an assignment."""

    date: dt.date
    title: str
    description: t.NotRequired[str]


class AssignmentDict(t.TypedDict, total=False):
    """Represents a course assignment for schedule rendering."""

    title: str
    release_date: dt.date
    due_date: dt.date
    link: str | None
    reveal_date: dt.date
    checkpoints: list[CheckpointDict]


class ReadingDict(t.TypedDict):
    """Represents a reading linked to a quiz."""

    title: str
    url: str


class QuizDict(t.TypedDict, total=False):
    """Represents a course quiz for schedule rendering."""

    title: str
    release_date: dt.date
    due_date: dt.date
    link: str | None
    readings: list[ReadingDict]


__all__ = [
    "AssignmentDict",
    "BreakDict",
    "CheckpointDict",
    "EventDict",
    "QuizDict",
    "ReadingDict",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
]
