"""Quiz models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from coursemd.models.integrations import QuizIntegrations


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
    """Canonical quiz sync specification."""

    source_file: Path
    title: str
    source_type: str
    quiz_type: str
    due_at: str
    assignment_group: str
    points: float | None
    published: bool
    unlock_at: str | None
    description: str | None
    readings: list[ReadingSpec] = field(default_factory=list)
    questions: list[QuestionSpec] = field(default_factory=list)
    integrations: QuizIntegrations = field(default_factory=QuizIntegrations)

    @property
    def canvas_id(self) -> int | None:
        """Compatibility alias for the nested Canvas quiz ID."""

        return self.integrations.canvas.quiz_id


CanvasQuizSpec = QuizSpec
