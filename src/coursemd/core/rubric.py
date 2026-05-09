"""Rubric parsing helpers shared by course tooling."""

from __future__ import annotations

from typing import Any, cast

from coursemd.core.models.rubric import RubricCriterion, RubricSection


def load_rubric_sections(metadata: dict[str, Any]) -> list[RubricSection]:
    """Return rubric sections from Markdown metadata."""
    rubric = metadata.get("rubric", []) or []
    if not isinstance(rubric, list):
        return []
    return [
        cast(RubricSection, section)
        for section in rubric
        if isinstance(section, dict)
    ]


def select_rubric_criteria(
    metadata: dict[str, Any],
    rubric_section: str | None,
    rubric_criteria_filter: list[str] | None = None,
) -> list[RubricCriterion]:
    """Select rubric criteria from one named section, optionally filtering by criterion name."""
    if not rubric_section:
        return []

    for section in load_rubric_sections(metadata):
        if section.get("section") != rubric_section:
            continue

        criteria = section.get("criteria", [])
        if not isinstance(criteria, list):
            return []

        filtered = [
            cast(RubricCriterion, criterion)
            for criterion in criteria
            if isinstance(criterion, dict)
        ]
        if rubric_criteria_filter:
            filtered = [
                criterion
                for criterion in filtered
                if criterion.get("name") in rubric_criteria_filter
            ]
        return filtered

    return []


def flatten_rubric_criteria(
    metadata: dict[str, Any],
    *,
    prepend_section_name: bool = False,
) -> list[RubricCriterion]:
    """Flatten a rubric into a list of criteria, optionally prefixing section names."""
    flattened: list[RubricCriterion] = []
    for section in load_rubric_sections(metadata):
        section_name = str(section.get("section", "")).strip()
        criteria = section.get("criteria", [])
        if not isinstance(criteria, list):
            continue
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            if prepend_section_name and section_name and criterion.get("name"):
                entry = cast(RubricCriterion, dict(criterion))
                entry["name"] = f"{section_name} -- {criterion['name']}"
                flattened.append(entry)
            else:
                flattened.append(criterion)
    return flattened
