"""Integration-specific state nested under canonical course models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanvasAssignmentIntegration:
    """Canvas state for an assignment-like item."""

    assignment_id: int | None = None
    assignment_group: str | None = None


@dataclass(frozen=True)
class CanvasQuizIntegration:
    """Canvas state for a quiz-like item."""

    quiz_id: int | None = None
    assignment_group: str | None = None


@dataclass(frozen=True)
class AssignmentIntegrations:
    """External integration state for an assignment."""

    canvas: CanvasAssignmentIntegration = CanvasAssignmentIntegration()


@dataclass(frozen=True)
class QuizIntegrations:
    """External integration state for a quiz."""

    canvas: CanvasQuizIntegration = CanvasQuizIntegration()
