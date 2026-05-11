"""Canvas-specific integration models and data extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    "CanvasAssignmentIntegration",
    "CanvasQuizIntegration",
    "canvas_assignment",
    "canvas_quiz",
]
