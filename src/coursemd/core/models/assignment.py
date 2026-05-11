"""Assignment models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, cast

from coursemd.core.exceptions import wrap_validation_errors
from coursemd.core.loaders.assignments import DEFAULT_ASSIGNMENTS_URL_PATH, assignment_link_for
from coursemd.core.loaders.dates import normalize_due_at, require_date, require_release_date
from coursemd.core.loaders.markdown import load_markdown_post
from coursemd.core.models.rubric import Rubric

if TYPE_CHECKING:
    import datetime as dt
    from pathlib import Path

    from coursemd.core.models.rubric import RubricCriterion


def _require_non_empty_string(value: Any, source_file: Path, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{source_file}: '{field_name}' must be a non-empty string.")
    return text


def _parse_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_submission_types(value: Any, source_file: Path) -> list[str]:
    if value is None:
        return ["none"]
    if isinstance(value, str):
        submission_types = [value.strip()]
    elif isinstance(value, list):
        typed_values = cast("list[Any]", value)
        if any(not isinstance(item, str) for item in typed_values):
            raise TypeError(
                f"{source_file}: 'submission_types' must be a string or list of strings."
            )
        submission_types = [item.strip() for item in cast("list[str]", typed_values)]
    else:
        raise TypeError(
            f"{source_file}: 'submission_types' must be a string or list of strings."
        )
    if not submission_types or any(not item for item in submission_types):
        raise ValueError(f"{source_file}: 'submission_types' must include at least one value.")
    return submission_types


def _parse_integrations(metadata: dict[str, Any], source_file: Path) -> dict[str, Any]:
    integrations_raw = metadata.get("integrations")
    if integrations_raw is None:
        return {}
    if not isinstance(integrations_raw, dict):
        raise TypeError(f"{source_file}: 'integrations' must be an object/map.")
    return dict(cast("dict[str, Any]", integrations_raw))


@dataclass(frozen=True)
class SubmissionField:
    """A required submission field for an assignment."""

    label: str
    hint: str | None = None


def _parse_submission_form(value: Any, source_file: Path) -> list[SubmissionField]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{source_file}: 'submission_form' must be a list of objects.")

    fields: list[SubmissionField] = []
    for index, item in enumerate(cast("list[Any]", value)):
        if not isinstance(item, dict):
            raise TypeError(f"{source_file}: submission_form[{index}] must be an object.")
        field_map = cast("dict[str, Any]", item)
        fields.append(
            SubmissionField(
                label=_require_non_empty_string(
                    field_map.get("label"),
                    source_file,
                    f"submission_form[{index}].label",
                ),
                hint=_parse_optional_string(field_map.get("hint")),
            )
        )
    return fields


@dataclass(frozen=True)
class AssignmentCheckpoint:
    """A dated checkpoint associated with an assignment."""

    date: dt.date
    title: str
    description: str | None = None
    due_at: str | None = None
    doc_anchor: str | None = None

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        *,
        source_file: Path,
        index: int,
        release_date: dt.date,
        due_date: dt.date,
    ) -> AssignmentCheckpoint:
        checkpoint_date = require_date(
            value.get("date"),
            source_file,
            f"checkpoints[{index}].date",
        )
        checkpoint_title = _require_non_empty_string(
            value.get("title"),
            source_file,
            f"checkpoints[{index}].title",
        )
        if checkpoint_date < release_date or checkpoint_date > due_date:
            raise ValueError(
                f"{source_file}: checkpoints[{index}].date must fall between "
                f"'release_date' and 'due_date'."
            )

        checkpoint_due_at_raw = value.get("due_at")
        checkpoint_due_at = None
        if checkpoint_due_at_raw is not None:
            checkpoint_due_at = normalize_due_at(
                checkpoint_due_at_raw,
                source_file,
                f"checkpoints[{index}]",
            )
            checkpoint_due_date = require_date(
                checkpoint_due_at,
                source_file,
                f"checkpoints[{index}].due_at",
            )
            if checkpoint_due_date != checkpoint_date:
                raise ValueError(
                    f"{source_file}: checkpoints[{index}].due_at must fall on "
                    f"the same calendar date as checkpoints[{index}].date."
                )

        return cls(
            date=checkpoint_date,
            title=checkpoint_title,
            description=_parse_optional_string(value.get("description")),
            due_at=checkpoint_due_at,
            doc_anchor=_parse_optional_string(value.get("doc_anchor")),
        )


def _parse_checkpoints(
    value: Any,
    source_file: Path,
    release_date: dt.date,
    due_date: dt.date,
) -> list[AssignmentCheckpoint]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{source_file}: 'checkpoints' must be a list.")

    checkpoints: list[AssignmentCheckpoint] = []
    previous_date: dt.date | None = None
    for index, item in enumerate(cast("list[Any]", value)):
        if not isinstance(item, dict):
            raise TypeError(f"{source_file}: checkpoints[{index}] must be an object.")
        checkpoint = AssignmentCheckpoint.from_dict(
            cast("dict[str, Any]", item),
            source_file=source_file,
            index=index,
            release_date=release_date,
            due_date=due_date,
        )
        checkpoint_date = checkpoint.date
        if previous_date is not None and checkpoint_date < previous_date:
            raise ValueError(f"{source_file}: checkpoints must be ordered by ascending date.")

        checkpoints.append(checkpoint)
        previous_date = checkpoint_date

    return checkpoints


def _parse_rubric_criteria_filter(value: Any, source_file: Path) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError(f"{source_file}: 'rubric_criteria' must be a list of strings.")
    typed_values = cast("list[Any]", value)
    if any(not isinstance(item, str) for item in typed_values):
        raise TypeError(f"{source_file}: 'rubric_criteria' must be a list of strings.")
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
    @wrap_validation_errors
    def load(cls, filename: Path) -> Assignment:
        """Load a single assignment from a Markdown file."""

        post = load_markdown_post(filename)
        metadata = post.metadata

        title = _require_non_empty_string(metadata.get("title"), filename, "title")
        release_date = require_date(metadata.get("release_date"), filename, "release_date")

        due_date_raw = metadata.get("due_date")
        due_at_raw = metadata.get("due_at")
        due_at = None if due_at_raw is None else normalize_due_at(due_at_raw, filename, title)
        due_date_from_due_at = (
            None if due_at is None else require_date(due_at, filename, "due_at")
        )

        if due_date_raw is None and due_date_from_due_at is None:
            raise ValueError(f"{filename}: assignment must define 'due_date' or 'due_at'.")

        if due_date_raw is None:
            if due_date_from_due_at is None:
                raise ValueError(f"{filename}: assignment must define 'due_date' or 'due_at'.")
            due_date = due_date_from_due_at
        else:
            due_date = require_date(due_date_raw, filename, "due_date")
        if due_date_from_due_at is not None and due_date != due_date_from_due_at:
            raise ValueError(f"{filename}: 'due_date' must match the calendar date of 'due_at'.")
        if due_date < release_date:
            raise ValueError(f"{filename}: 'due_date' must not be earlier than 'release_date'.")

        reveal_date = None
        if metadata.get("reveal_date") is not None:
            reveal_date = require_date(metadata.get("reveal_date"), filename, "reveal_date")
            if reveal_date > due_date:
                raise ValueError(f"{filename}: 'reveal_date' must not be later than 'due_date'.")

        points_raw = metadata.get("points", 100)
        try:
            points_possible = float(cast("Any", 100 if points_raw is None else points_raw))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{filename}: 'points' must be numeric.") from exc

        position_raw = metadata.get("position")
        position = None
        if position_raw is not None:
            try:
                position = int(cast("Any", position_raw))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{filename}: 'position' must be an integer.") from exc

        rubric_section = _parse_optional_string(metadata.get("rubric_section"))
        rubric_criteria_filter = _parse_rubric_criteria_filter(
            metadata.get("rubric_criteria"),
            filename,
        )

        return cls(
            source_file=filename,
            title=title,
            release_date=release_date,
            due_date=due_date,
            link=assignment_link_for(filename, assignment_url_path=DEFAULT_ASSIGNMENTS_URL_PATH),
            due_at=due_at,
            kind=_parse_optional_string(metadata.get("kind")) or "assignment",
            description=str(post.content).strip() or None,
            reveal_date=reveal_date,
            submission_types=_parse_submission_types(metadata.get("submission_types"), filename),
            points_possible=points_possible,
            published=bool(metadata.get("published", False)),
            position=position,
            unlock_at=require_release_date(metadata.get("release_date"), filename, "release_date"),
            group_assignment=bool(metadata.get("group_assignment", False)),
            submission_form=_parse_submission_form(metadata.get("submission_form"), filename),
            rubric_criteria=Rubric.from_metadata(metadata).select_criteria(
                rubric_section,
                rubric_criteria_filter,
            ),
            checkpoints=_parse_checkpoints(
                metadata.get("checkpoints"),
                filename,
                release_date,
                due_date,
            ),
            doc_url=_parse_optional_string(metadata.get("doc_url")),
            doc_anchor=_parse_optional_string(metadata.get("doc_anchor")),
            notes=_parse_optional_string(metadata.get("notes")),
            integrations=_parse_integrations(metadata, filename),
        )

