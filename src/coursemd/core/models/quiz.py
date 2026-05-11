"""Quiz models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class QuestionSpec:
    """A quiz question in the course repository model."""

    question_type: str
    question_text: str
    points_possible: float
    position: int
    answers: list[dict[str, Any]]
    distractors: list[str] | None = None


@dataclass(frozen=True)
class ReadingSpec:
    """A required reading associated with a quiz."""

    title: str
    url: str


@dataclass(frozen=True)
class QuizSpec:
    """Canonical quiz specification."""

    source_file: Path
    title: str
    source_type: str
    due_at: str
    points: float | None
    published: bool
    unlock_at: str | None
    description: str | None
    readings: list[ReadingSpec] = field(default_factory=list)
    questions: list[QuestionSpec] = field(default_factory=list)
    integrations: dict[str, Any] = field(default_factory=dict)
