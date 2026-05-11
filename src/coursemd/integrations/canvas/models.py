"""Canvas-specific integration models and data extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from coursemd.core.models.assignment import Assignment


@dataclass(frozen=True)
class CanvasAssignment:
    """An assignment with Canvas integration data unpacked from integrations.canvas."""

    assignment: Assignment
    canvas_id: int | None = None
    canvas_assignment_group: str | None = None

    @classmethod
    def from_assignment(cls, assignment: Assignment) -> CanvasAssignment:
        canvas_map = assignment.integrations.get("canvas") or {}
        if not isinstance(canvas_map, dict):
            canvas_map = {}
        canvas_id = canvas_map.get("id")
        if canvas_id is not None:
            try:
                canvas_id = int(canvas_id)
            except (TypeError, ValueError):
                canvas_id = None
        canvas_group = str(canvas_map.get("assignment_group") or "").strip() or None
        return cls(
            assignment=assignment,
            canvas_id=canvas_id,
            canvas_assignment_group=canvas_group,
        )


@dataclass(frozen=True)
class CanvasAssignmentIntegration:
    """Canvas state extracted from an assignment's integrations dict."""

    id: int | None = None
    assignment_group: str | None = None


@dataclass(frozen=True)
class CanvasQuizIntegration:
    """Canvas state extracted from a quiz's integrations dict."""

    id: int | None = None
    assignment_group: str | None = None
    quiz_type: str | None = None


def canvas_assignment(integrations: dict[str, Any]) -> CanvasAssignmentIntegration:
    """Extract Canvas integration data from an assignment's raw integrations dict."""
    canvas_map = integrations.get("canvas") or {}
    if not isinstance(canvas_map, dict):
        canvas_map = {}
    canvas_id = canvas_map.get("id")
    if canvas_id is not None:
        try:
            canvas_id = int(canvas_id)
        except (TypeError, ValueError):
            canvas_id = None
    group = str(canvas_map.get("assignment_group") or "").strip() or None
    return CanvasAssignmentIntegration(id=canvas_id, assignment_group=group)


def canvas_quiz(
    integrations: dict[str, Any],
    source_type: str,
    quiz_type_map: dict[str, str],
) -> CanvasQuizIntegration:
    """Extract Canvas integration data from a quiz's raw integrations dict.

    quiz_type_map should be the Canvas QUIZ_TYPE_MAP from the quizzes module.
    """
    canvas_map = integrations.get("canvas") or {}
    if not isinstance(canvas_map, dict):
        canvas_map = {}
    canvas_id = canvas_map.get("id")
    if canvas_id is not None:
        try:
            canvas_id = int(canvas_id)
        except (TypeError, ValueError):
            canvas_id = None
    group = str(canvas_map.get("assignment_group") or "").strip() or None
    quiz_type_override = canvas_map.get("quiz_type")
    default_quiz_type = quiz_type_map.get(source_type, "assignment")
    quiz_type = str(quiz_type_override) if quiz_type_override else default_quiz_type
    return CanvasQuizIntegration(id=canvas_id, assignment_group=group, quiz_type=quiz_type)


__all__ = [
    "CanvasAssignment",
    "CanvasAssignmentIntegration",
    "CanvasQuizIntegration",
    "canvas_assignment",
    "canvas_quiz",
]
