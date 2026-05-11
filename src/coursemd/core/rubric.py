"""Rubric parsing helpers shared by course tooling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coursemd.core.models.rubric import Rubric

if TYPE_CHECKING:
    from coursemd.core.models.rubric import RubricCriterion, RubricSection


def load_rubric_sections(metadata: dict[str, Any]) -> list[RubricSection]:
    """Return rubric sections from Markdown metadata."""
    return Rubric.from_metadata(metadata).sections


def select_rubric_criteria(
    metadata: dict[str, Any],
    rubric_section: str | None,
    rubric_criteria_filter: list[str] | None = None,
) -> list[RubricCriterion]:
    """Select rubric criteria from one named section, optionally filtering by criterion name."""
    return Rubric.from_metadata(metadata).select_criteria(rubric_section, rubric_criteria_filter)


def flatten_rubric_criteria(
    metadata: dict[str, Any],
    *,
    prepend_section_name: bool = False,
) -> list[RubricCriterion]:
    """Flatten a rubric into a list of criteria, optionally prefixing section names."""
    return Rubric.from_metadata(metadata).flatten_criteria(
        prepend_section_name=prepend_section_name,
    )
