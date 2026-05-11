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
    require_release_date,
)
from coursemd.core.models.checkpoint import AssignmentCheckpoint
from coursemd.core.models.rubric import Rubric

if TYPE_CHECKING:
    import datetime as dt
    from pathlib import Path

    from coursemd.core.models.rubric import RubricCriterion


def _parse_submission_types(value: Any) -> list[str]:
    if value is None:
        return ["none"]
    if isinstance(value, str):
        submission_types = [value.strip()]
    elif isinstance(value, list):
        typed_values = cast("list[Any]", value)
        if any(not isinstance(item, str) for item in typed_values):
            raise TypeError("'submission_types' must be a string or list of strings.")
        submission_types = [item.strip() for item in cast("list[str]", typed_values)]
    else:
        raise TypeError("'submission_types' must be a string or list of strings.")
    if not submission_types or any(not item for item in submission_types):
        raise ValueError("'submission_types' must include at least one value.")
    return submission_types


def _parse_integrations(metadata: dict[str, Any]) -> dict[str, Any]:
    integrations_raw = metadata.get("integrations")
    if integrations_raw is None:
        return {}
    if not isinstance(integrations_raw, dict):
        raise TypeError("'integrations' must be an object/map.")
    return dict(cast("dict[str, Any]", integrations_raw))


@dataclass(frozen=True)
class SubmissionField:
    """A required submission field for an assignment."""

    label: str
    hint: str | None = None


def _parse_submission_form(value: Any) -> list[SubmissionField]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("'submission_form' must be a list of objects.")

    fields: list[SubmissionField] = []
    for index, item in enumerate(cast("list[Any]", value)):
        if not isinstance(item, dict):
            raise TypeError(f"submission_form[{index}] must be an object.")
        field_map = cast("dict[str, Any]", item)
        fields.append(
            SubmissionField(
                label=require_non_empty_string(
                    field_map.get("label"),
                    f"submission_form[{index}].label",
                ),
                hint=optional_string(field_map.get("hint")),
            )
        )
    return fields


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


def _parse_rubric_criteria_filter(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError("'rubric_criteria' must be a list of strings.")
    typed_values = cast("list[Any]", value)
    if any(not isinstance(item, str) for item in typed_values):
        raise TypeError("'rubric_criteria' must be a list of strings.")
    return [item.strip() for item in cast("list[str]", typed_values)]


@dataclass(frozen=True)
class Assignment:
    """Canonical assignment specification."""

    source_file: Path
    title: str
    release_date: dt.date
    due_date: dt.date
    link: str
    due_at: str | None = None
    kind: str = "assignment"
    description: str | None = None
    reveal_date: dt.date | None = None
    submission_types: list[str] = field(default_factory=lambda: ["none"])
    points_possible: float = 100.0
    published: bool = False
    position: int | None = None
    unlock_at: str | None = None
    group_assignment: bool = False
    submission_form: list[SubmissionField] = field(default_factory=list)
    rubric_criteria: list[RubricCriterion] = field(default_factory=list)
    checkpoints: list[AssignmentCheckpoint] = field(default_factory=list)
    doc_url: str | None = None
    doc_anchor: str | None = None
    notes: str | None = None
    integrations: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.title

    @property
    def reveal_on(self) -> dt.date:
        return self.reveal_date or self.release_date

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

            points_raw = metadata.get("points", 100)
            try:
                points_possible = float(cast("Any", 100 if points_raw is None else points_raw))
            except (TypeError, ValueError) as exc:
                raise ValueError("'points' must be numeric.") from exc

            position_raw = metadata.get("position")
            position = None
            if position_raw is not None:
                try:
                    position = int(cast("Any", position_raw))
                except (TypeError, ValueError) as exc:
                    raise ValueError("'position' must be an integer.") from exc

            rubric_section = optional_string(metadata.get("rubric_section"))
            rubric_criteria_filter = _parse_rubric_criteria_filter(
                metadata.get("rubric_criteria")
            )

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
                submission_types=_parse_submission_types(metadata.get("submission_types")),
                points_possible=points_possible,
                published=bool(metadata.get("published", False)),
                position=position,
                unlock_at=require_release_date(metadata.get("release_date"), "release_date"),
                group_assignment=bool(metadata.get("group_assignment", False)),
                submission_form=_parse_submission_form(metadata.get("submission_form")),
                rubric_criteria=Rubric.from_metadata(metadata).select_criteria(
                    rubric_section,
                    rubric_criteria_filter,
                ),
                checkpoints=_parse_checkpoints(
                    metadata.get("checkpoints"),
                    release_date=release_date,
                    due_date=due_date,
                ),
                doc_url=optional_string(metadata.get("doc_url")),
                doc_anchor=optional_string(metadata.get("doc_anchor")),
                notes=optional_string(metadata.get("notes")),
                integrations=_parse_integrations(metadata),
            )

