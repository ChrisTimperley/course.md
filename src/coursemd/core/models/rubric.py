"""Rubric type definitions."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RubricTier:
    """Represents a single scoring tier within a rubric criterion."""

    points: int
    label: str
    desc: str = ""


@dataclass(frozen=True)
class RubricCriterion:
    """Represents a single gradeable criterion within a rubric section."""

    name: str
    points: int = 0
    desc: str = ""
    tiers: list[RubricTier] = field(default_factory=list)


@dataclass(frozen=True)
class RubricSection:
    """Represents a top-level section of a rubric."""

    section: str
    points: int = 0
    criteria: list[RubricCriterion] = field(default_factory=list)


@dataclass(frozen=True)
class Rubric:
    """A complete rubric parsed from assignment metadata."""

    sections: list[RubricSection]

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> Rubric:
        """Parse a Rubric from raw Markdown frontmatter metadata."""
        raw = metadata.get("rubric", []) or []
        if not isinstance(raw, list):
            return cls(sections=[])
        sections: list[RubricSection] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            criteria_raw = item.get("criteria", [])
            if not isinstance(criteria_raw, list):
                continue
            criteria: list[RubricCriterion] = []
            for c in criteria_raw:
                if not isinstance(c, dict):
                    continue
                tiers_raw = c.get("tiers", [])
                tiers: list[RubricTier] = [
                    RubricTier(
                        points=int(t.get("points", 0)),
                        label=str(t.get("label", "")),
                        desc=str(t.get("desc", "")),
                    )
                    for t in tiers_raw
                    if isinstance(t, dict)
                ] if isinstance(tiers_raw, list) else []
                criteria.append(RubricCriterion(
                    name=str(c.get("name", "")),
                    points=int(c.get("points", 0)),
                    desc=str(c.get("desc", "")),
                    tiers=tiers,
                ))
            sections.append(RubricSection(
                section=str(item.get("section", "")).strip(),
                points=int(item.get("points", 0)),
                criteria=criteria,
            ))
        return cls(sections=sections)

    def select_criteria(
        self,
        section_name: str | None,
        criteria_filter: list[str] | None = None,
    ) -> list[RubricCriterion]:
        """Return criteria from the named section, optionally filtered by name."""
        if not section_name:
            return []
        for section in self.sections:
            if section.section != section_name:
                continue
            if criteria_filter:
                return [c for c in section.criteria if c.name in criteria_filter]
            return list(section.criteria)
        return []

    def flatten_criteria(self, *, prepend_section_name: bool = False) -> list[RubricCriterion]:
        """Return all criteria across all sections, optionally prefixing section names."""
        flattened: list[RubricCriterion] = []
        for section in self.sections:
            for criterion in section.criteria:
                if prepend_section_name and section.section and criterion.name:
                    prefixed_name = f"{section.section} -- {criterion.name}"
                    flattened.append(dataclasses.replace(criterion, name=prefixed_name))
                else:
                    flattened.append(criterion)
        return flattened
