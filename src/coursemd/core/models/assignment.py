"""Assignment models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.models.rubric import RubricCriterion


@dataclass(frozen=True)
class AssignmentSpec:
    """Canonical assignment specification."""

    source_file: Path
    name: str
    due_at: str
    submission_types: list[str]
    points_possible: float
    published: bool
    position: int | None
    unlock_at: str | None
    group_assignment: bool
    submission_form: list[dict[str, Any]]
    rubric_criteria: list[RubricCriterion]
    doc_url: str | None = None
    doc_anchor: str | None = None
    notes: str | None = None
    integrations: dict[str, Any] = field(default_factory=dict)
