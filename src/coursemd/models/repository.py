"""Repository-level course model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from coursemd.models.assignment import AssignmentSpec
from coursemd.models.quiz import QuizSpec
from coursemd.types import AssignmentDict, QuizDict


@dataclass(frozen=True)
class CourseRepository:
    """A loaded course repository as a coherent object graph."""

    repo_root: Path
    data: dict[str, Any] = field(default_factory=dict)
    assignments: list[AssignmentSpec] = field(default_factory=list)
    quizzes: list[QuizSpec] = field(default_factory=list)
    schedule_assignments: list[AssignmentDict] = field(default_factory=list)
    schedule_quizzes: list[QuizDict] = field(default_factory=list)
