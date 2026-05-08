"""Assignment models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from coursemd.models.integrations import AssignmentIntegrations
from coursemd.models.rubric import RubricCriterion


@dataclass(frozen=True)
class AssignmentSpec:
    """Canonical assignment sync specification.

    The model still exposes a few Canvas-oriented fields for compatibility with
    the existing CLI, while durable external IDs live under ``integrations``.
    """

    source_file: Path
    name: str
    due_at: str
    assignment_group: str
    submission_types: list[str]
    points_possible: float
    published: bool
    description_html: str
    position: int | None
    unlock_at: str | None
    group_assignment: bool
    submission_form: list[dict[str, Any]]
    rubric_criteria: list[RubricCriterion]
    integrations: AssignmentIntegrations = field(default_factory=AssignmentIntegrations)

    @property
    def canvas_id(self) -> int | None:
        """Compatibility alias for the nested Canvas assignment ID."""

        return self.integrations.canvas.assignment_id


CanvasAssignmentSpec = AssignmentSpec
