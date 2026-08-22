"""Rubric type definitions."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Any, Literal, cast

RubricType = Literal["tiered", "pass-fail", "range"]
_RUBRIC_TYPES: set[str] = {"tiered", "pass-fail", "range"}
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MINIMUM_TIERS = 2


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
    slug: str | None = None
    criterion_type: RubricType = "tiered"
    min_points: int = 0


@dataclass(frozen=True)
class RubricSection:
    """Represents a top-level section of a rubric."""

    section: str
    points: int = 0
    criteria: list[RubricCriterion] = field(default_factory=list)
    slug: str | None = None


@dataclass(frozen=True)
class Rubric:
    """A complete rubric parsed from assignment metadata."""

    sections: list[RubricSection]
    rubric_type: RubricType = "tiered"
    typed: bool = False

    @staticmethod
    def _slug(value: Any, field_name: str, *, required: bool) -> str | None:
        if value is None:
            if required:
                raise ValueError(f"'{field_name}' is required for typed rubrics.")
            return None
        slug = str(value).strip()
        if not _SLUG_PATTERN.fullmatch(slug):
            raise ValueError(
                f"'{field_name}' must be a lowercase kebab-case slug (for example, 'clean-start')."
            )
        return slug

    @staticmethod
    def _points(value: Any, field_name: str) -> int:
        try:
            points = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"'{field_name}' must be an integer.") from exc
        if points <= 0:
            raise ValueError(f"'{field_name}' must be greater than zero.")
        return points

    @staticmethod
    def _criterion_type(value: Any, field_name: str) -> RubricType:
        criterion_type = str(value).strip()
        if criterion_type not in _RUBRIC_TYPES:
            supported = ", ".join(sorted(_RUBRIC_TYPES))
            raise ValueError(
                f"Unknown rubric type '{criterion_type}' in '{field_name}'; "
                f"expected one of: {supported}."
            )
        return cast("RubricType", criterion_type)

    @classmethod
    def _tiered_criterion(cls, item: dict[str, Any]) -> RubricCriterion:
        tiers_raw = item.get("tiers", [])
        tiers: list[RubricTier] = (
            [
                RubricTier(
                    points=int(t.get("points", 0)),
                    label=str(t.get("label", "")),
                    desc=str(t.get("desc", "")),
                )
                for t in tiers_raw
                if isinstance(t, dict)
            ]
            if isinstance(tiers_raw, list)
            else []
        )
        return RubricCriterion(
            name=str(item.get("name", "")),
            points=int(item.get("points", 0)),
            desc=str(item.get("desc", "")),
            tiers=tiers,
            slug=cls._slug(item.get("slug"), "rubric.criteria.slug", required=False),
        )

    @classmethod
    def _typed_criterion(
        cls,
        item: dict[str, Any],
        *,
        default_type: RubricType,
    ) -> RubricCriterion:
        slug = cls._slug(item.get("slug"), "rubric.criteria.slug", required=True)
        points = cls._points(item.get("points"), f"rubric criterion '{slug}' points")
        desc = str(item.get("desc", "")).strip()
        if not desc:
            raise ValueError(f"Rubric criterion '{slug}' requires a description.")
        name = str(item.get("name", "")).strip() or desc
        criterion_type = cls._criterion_type(
            item.get("type", default_type),
            f"rubric criterion '{slug}' type",
        )

        if criterion_type == "pass-fail":
            if item.get("tiers") is not None or item.get("min_points") is not None:
                raise ValueError(
                    f"Pass-fail rubric criterion '{slug}' derives its ratings; "
                    "remove 'tiers' and 'min_points'."
                )
            tiers = [
                RubricTier(points=points, label="Pass"),
                RubricTier(points=0, label="Fail"),
            ]
            min_points = 0
        elif criterion_type == "range":
            if item.get("tiers") is not None:
                raise ValueError(
                    f"Range rubric criterion '{slug}' derives its endpoints; remove 'tiers'."
                )
            try:
                min_points = int(item.get("min_points", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Rubric criterion '{slug}' min_points must be an integer."
                ) from exc
            if min_points < 0 or min_points >= points:
                raise ValueError(
                    f"Rubric criterion '{slug}' min_points must be at least zero "
                    f"and less than its {points}-point maximum."
                )
            tiers = [
                RubricTier(points=points, label="Full credit"),
                RubricTier(points=min_points, label="Minimum credit"),
            ]
        else:
            if item.get("min_points") is not None:
                raise ValueError(f"Tiered rubric criterion '{slug}' does not use 'min_points'.")
            tiers_raw = item.get("tiers")
            if not isinstance(tiers_raw, list) or len(tiers_raw) < _MINIMUM_TIERS:
                raise ValueError(f"Tiered rubric criterion '{slug}' requires at least two tiers.")
            tiers = []
            for tier_index, tier in enumerate(tiers_raw):
                if not isinstance(tier, dict):
                    raise TypeError(
                        f"Rubric criterion '{slug}' tier {tier_index} must be an object."
                    )
                try:
                    tier_points = int(tier.get("points", 0))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Rubric criterion '{slug}' tier {tier_index} points must be an integer."
                    ) from exc
                if tier_points < 0 or tier_points > points:
                    raise ValueError(
                        f"Rubric criterion '{slug}' tier points must be between 0 and {points}."
                    )
                label = str(tier.get("label", "")).strip()
                if not label:
                    raise ValueError(
                        f"Rubric criterion '{slug}' tier {tier_index} requires a label."
                    )
                tiers.append(
                    RubricTier(
                        points=tier_points,
                        label=label,
                        desc=str(tier.get("desc", "")).strip(),
                    )
                )
            tier_points_set = {tier.points for tier in tiers}
            if len(tier_points_set) != len(tiers):
                raise ValueError(f"Rubric criterion '{slug}' has duplicate tier points.")
            if points not in tier_points_set or 0 not in tier_points_set:
                raise ValueError(
                    f"Tiered rubric criterion '{slug}' must include {points}-point "
                    "and 0-point tiers."
                )
            min_points = 0

        return RubricCriterion(
            name=name,
            points=points,
            desc=desc,
            tiers=tiers,
            slug=slug,
            criterion_type=criterion_type,
            min_points=min_points,
        )

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> Rubric:
        """Parse a Rubric from raw Markdown frontmatter metadata."""
        raw = metadata.get("rubric", []) or []
        typed = isinstance(raw, dict)
        if typed:
            rubric_map = cast("dict[str, Any]", raw)
            rubric_type = cls._criterion_type(rubric_map.get("type", "tiered"), "rubric.type")
            sections_raw = rubric_map.get("sections", [])
            if not isinstance(sections_raw, list):
                raise ValueError("'rubric.sections' must be a list.")
            raw = sections_raw
        elif isinstance(raw, list):
            rubric_type = "tiered"
        else:
            raise ValueError("'rubric' must be a list or an object with type and sections.")

        sections: list[RubricSection] = []
        section_slugs: set[str] = set()
        for section_index, item in enumerate(raw):
            if not isinstance(item, dict):
                if typed:
                    raise ValueError(f"rubric.sections[{section_index}] must be an object.")
                continue
            criteria_raw = item.get("criteria", [])
            if not isinstance(criteria_raw, list):
                if typed:
                    raise ValueError(f"rubric.sections[{section_index}].criteria must be a list.")
                continue
            section_slug = cls._slug(
                item.get("slug"),
                "rubric.sections.slug",
                required=typed,
            )
            if section_slug is not None:
                if section_slug in section_slugs:
                    raise ValueError(f"Duplicate rubric section slug '{section_slug}'.")
                section_slugs.add(section_slug)
            criteria: list[RubricCriterion] = []
            criterion_slugs: set[str] = set()
            for criterion_index, c in enumerate(criteria_raw):
                if not isinstance(c, dict):
                    if typed:
                        raise ValueError(
                            f"rubric.sections[{section_index}].criteria[{criterion_index}] "
                            "must be an object."
                        )
                    continue
                criterion = (
                    cls._typed_criterion(c, default_type=rubric_type)
                    if typed
                    else cls._tiered_criterion(c)
                )
                if criterion.slug is not None:
                    if criterion.slug in criterion_slugs:
                        raise ValueError(
                            f"Duplicate rubric criterion slug '{criterion.slug}' "
                            f"in section '{section_slug or item.get('section', '')}'."
                        )
                    criterion_slugs.add(criterion.slug)
                criteria.append(criterion)

            section_points = (
                cls._points(item.get("points"), f"rubric section '{section_slug}' points")
                if typed
                else int(item.get("points", 0))
            )
            if typed:
                criteria_points = sum(criterion.points for criterion in criteria)
                if section_points != criteria_points:
                    raise ValueError(
                        f"Rubric section '{section_slug}' declares {section_points} points, "
                        f"but its criteria total {criteria_points}."
                    )
            section_name = str(item.get("section", "")).strip()
            if typed and not section_name:
                raise ValueError(
                    f"rubric section '{section_slug}' requires a display name in 'section'."
                )
            sections.append(
                RubricSection(
                    section=section_name,
                    points=section_points,
                    criteria=criteria,
                    slug=section_slug,
                )
            )
        return cls(sections=sections, rubric_type=rubric_type, typed=typed)

    def select_criteria(
        self,
        section_name: str | None,
        criteria_filter: list[str] | None = None,
    ) -> list[RubricCriterion]:
        """Return criteria from the named section, optionally filtered by name."""
        if not section_name:
            return []
        for section in self.sections:
            if section_name not in {section.section, section.slug}:
                continue
            if criteria_filter:
                return [
                    criterion
                    for criterion in section.criteria
                    if criterion.name in criteria_filter or criterion.slug in criteria_filter
                ]
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
