"""Assignment models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, cast

from coursemd.core.exceptions import validation_error_boundary
from coursemd.core.loaders.assignments import DEFAULT_ASSIGNMENTS_URL_PATH, assignment_link_for
from coursemd.core.loaders.markdown import load_markdown_post
from coursemd.core.loaders.validation import (
    normalize_due_at,
    optional_string,
    require_date,
    require_non_empty_string,
)
from coursemd.core.models.checkpoint import AssignmentCheckpoint
from coursemd.core.models.rubric import Rubric

if TYPE_CHECKING:
    import datetime as dt
    from pathlib import Path


def _parse_integrations(metadata: dict[str, Any]) -> dict[str, Any]:
    integrations_raw = metadata.get("integrations")
    if integrations_raw is None:
        return {}
    if not isinstance(integrations_raw, dict):
        raise TypeError("'integrations' must be an object/map.")
    return dict(cast("dict[str, Any]", integrations_raw))


def _parse_checkpoints(
    value: Any,
    *,
    release_date: dt.date,
    due_date: dt.date,
) -> list[AssignmentCheckpoint]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("'checkpoints' must be a list of objects.")
    return AssignmentCheckpoint.from_list(
        cast("list[dict[str, Any]]", value),
        release_date=release_date,
        due_date=due_date,
    )


def _parse_float(value: Any, field_name: str) -> float:
    try:
        return float(cast("Any", value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{field_name}' must be numeric.") from exc


@dataclass(frozen=True)
class AssignmentGradeTier:
    """A course grading tier for an assignment."""

    name: str
    min_score: float
    points: float


@dataclass(frozen=True)
class AssignmentGrading:
    """Raw-score grading policy for an assignment."""

    raw_max: float
    tiers: list[AssignmentGradeTier] = field(default_factory=list)


def _parse_grading(value: Any) -> AssignmentGrading | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("'grading' must be an object/map.")
    grading_map = cast("dict[str, Any]", value)
    raw_max = _parse_float(grading_map.get("raw_max"), "grading.raw_max")

    tiers_raw = grading_map.get("tiers", [])
    if tiers_raw is None:
        tiers_raw = []
    if not isinstance(tiers_raw, list):
        raise TypeError("'grading.tiers' must be a list of objects.")

    tiers: list[AssignmentGradeTier] = []
    for index, item in enumerate(cast("list[Any]", tiers_raw)):
        if not isinstance(item, dict):
            raise TypeError(f"grading.tiers[{index}] must be an object.")
        tier_map = cast("dict[str, Any]", item)
        tiers.append(
            AssignmentGradeTier(
                name=require_non_empty_string(
                    tier_map.get("name"),
                    f"grading.tiers[{index}].name",
                ),
                min_score=_parse_float(
                    tier_map.get("min_score"),
                    f"grading.tiers[{index}].min_score",
                ),
                points=_parse_float(
                    tier_map.get("points"),
                    f"grading.tiers[{index}].points",
                ),
            )
        )
    return AssignmentGrading(raw_max=raw_max, tiers=tiers)


def _parse_legacy_points(value: Any) -> float | None:
    if value is None:
        return None
    return _parse_float(value, "points")


def _parse_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "1", "on"}:
            return True
        if text in {"false", "no", "0", "off"}:
            return False
    return bool(value)


def _parse_meta(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("'meta' must be an object/map.")
    return dict(cast("dict[str, Any]", value))


def _parse_rubric(value: dict[str, Any]) -> Rubric:
    return Rubric.from_metadata(value)


@dataclass(frozen=True)
class Assignment:
    """Canonical homework/assignment page specification."""

    source_file: Path
    title: str
    release_date: dt.date
    due_date: dt.date
    link: str
    due_at: str | None = None
    kind: str = "assignment"
    description: str | None = None
    reveal_date: dt.date | None = None
    group_assignment: bool = False
    points: float | None = None
    grading: AssignmentGrading | None = None
    rubric: Rubric = field(default_factory=lambda: Rubric(sections=[]))
    checkpoints: list[AssignmentCheckpoint] = field(default_factory=list)
    doc_url: str | None = None
    doc_anchor: str | None = None
    notes: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    integrations: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.title

    @property
    def reveal_on(self) -> dt.date:
        return self.reveal_date or self.release_date

    @property
    def points_possible(self) -> float:
        """Best generic raw-score total for integrations that need a default."""

        if self.points is not None:
            return self.points
        if self.grading is not None:
            return self.grading.raw_max
        return 100.0

    def with_assignment_url_path(self, assignment_url_path: str) -> Assignment:
        return replace(
            self,
            link=assignment_link_for(
                self.source_file,
                assignment_url_path=assignment_url_path,
            ),
        )

    @classmethod
    def load(cls, filename: Path) -> Assignment:
        """Load a single assignment from a Markdown file."""

        with validation_error_boundary(filename):
            post = load_markdown_post(filename)
            metadata = post.metadata

            title = require_non_empty_string(metadata.get("title"), "title")
            release_date = require_date(metadata.get("release_date"), "release_date")

            due_date_raw = metadata.get("due_date")
            due_at_raw = metadata.get("due_at")
            due_at = None if due_at_raw is None else normalize_due_at(due_at_raw, title)
            due_date_from_due_at = None if due_at is None else require_date(due_at, "due_at")

            if due_date_raw is None and due_date_from_due_at is None:
                raise ValueError("assignment must define 'due_date' or 'due_at'.")

            if due_date_raw is None:
                if due_date_from_due_at is None:
                    raise ValueError("assignment must define 'due_date' or 'due_at'.")
                due_date = due_date_from_due_at
            else:
                due_date = require_date(due_date_raw, "due_date")
            if due_date_from_due_at is not None and due_date != due_date_from_due_at:
                raise ValueError("'due_date' must match the calendar date of 'due_at'.")
            if due_date < release_date:
                raise ValueError("'due_date' must not be earlier than 'release_date'.")

            reveal_date = None
            if metadata.get("reveal_date") is not None:
                reveal_date = require_date(metadata.get("reveal_date"), "reveal_date")
                if reveal_date > due_date:
                    raise ValueError("'reveal_date' must not be later than 'due_date'.")

            return cls(
                source_file=filename,
                title=title,
                release_date=release_date,
                due_date=due_date,
                link=assignment_link_for(
                    filename,
                    assignment_url_path=DEFAULT_ASSIGNMENTS_URL_PATH,
                ),
                due_at=due_at,
                kind=optional_string(metadata.get("kind")) or "assignment",
                description=str(post.content).strip() or None,
                reveal_date=reveal_date,
                group_assignment=_parse_bool(metadata.get("group_assignment")),
                points=_parse_legacy_points(metadata.get("points")),
                grading=_parse_grading(metadata.get("grading")),
                rubric=_parse_rubric(metadata),
                checkpoints=_parse_checkpoints(
                    metadata.get("checkpoints"),
                    release_date=release_date,
                    due_date=due_date,
                ),
                doc_url=optional_string(metadata.get("doc_url")),
                doc_anchor=optional_string(metadata.get("doc_anchor")),
                notes=optional_string(metadata.get("notes")),
                meta=_parse_meta(metadata.get("meta")),
                integrations=_parse_integrations(metadata),
            )


__all__ = (
    "Assignment",
    "AssignmentCheckpoint",
    "AssignmentGradeTier",
    "AssignmentGrading",
)
