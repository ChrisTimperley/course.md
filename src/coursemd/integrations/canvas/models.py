"""Canvas-specific integration models and data extraction helpers."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.loaders.validation import (
    normalize_close_at,
    normalize_due_at,
    optional_string,
    require_non_empty_string,
    require_release_date,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from coursemd.core.models.assignment import Assignment
    from coursemd.core.models.checkpoint import AssignmentCheckpoint
    from coursemd.core.models.course_event import CourseEvent
    from coursemd.core.models.lab import Lab
    from coursemd.core.models.rubric import RubricCriterion
    from coursemd.integrations.canvas.config import CanvasParticipationConfig


def _canvas_map(integrations: dict[str, Any]) -> dict[str, Any]:
    canvas = integrations.get("canvas") or {}
    if not isinstance(canvas, dict):
        return {}
    return dict(cast("dict[str, Any]", canvas))


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any, field_name: str) -> float:
    try:
        return float(cast("Any", value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{field_name}' must be numeric.") from exc


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


def _parse_position(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(cast("Any", value))
    except (TypeError, ValueError) as exc:
        raise ValueError("'position' must be an integer.") from exc


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
class CanvasSubmissionField:
    """A Canvas-facing field students should include in a submission."""

    label: str
    hint: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanvasSubmissionField:
        label = require_non_empty_string(data.get("label"), "submission_form.label")
        hint = optional_string(data.get("hint"))
        return cls(
            label=label,
            hint=hint,
        )

    @classmethod
    def from_list(cls, data: list[Any]) -> list[CanvasSubmissionField]:
        fields: list[CanvasSubmissionField] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise TypeError(f"submission_form[{index}] must be an object.")
            field_map = cast("dict[str, Any]", item)
            field = CanvasSubmissionField.from_dict(field_map)
            fields.append(field)
        return fields


def _parse_submission_form(value: Any) -> list[CanvasSubmissionField]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("'submission_form' must be a list of objects.")
    return CanvasSubmissionField.from_list(cast("list[Any]", value))


def _find_checkpoint(
    assignment: Assignment,
    item: dict[str, Any],
) -> AssignmentCheckpoint | None:
    anchor = optional_string(item.get("doc_anchor"))
    name = optional_string(item.get("name")) or optional_string(item.get("title"))
    for checkpoint in assignment.checkpoints:
        if anchor and checkpoint.doc_anchor == anchor:
            return checkpoint
        if name and checkpoint.title == name:
            return checkpoint
    return None


@dataclass(frozen=True)
class CanvasAssignmentSubmission:
    """One Canvas assignment/submission target derived from a course.md assignment."""

    assignment: Assignment | Lab
    name: str
    due_at: str | None
    points_possible: float
    close_at: str | None = None
    canvas_id: int | None = None
    canvas_assignment_group: str | None = None
    submission_types: list[str] = field(default_factory=lambda: ["none"])
    published: bool = False
    position: int | None = None
    unlock_at: str | None = None
    group_assignment: bool = False
    submission_form: list[CanvasSubmissionField] = field(default_factory=list)
    rubric_criteria: list[RubricCriterion] = field(default_factory=list)
    doc_url: str | None = None
    doc_anchor: str | None = None
    notes: str | None = None

    @property
    def source_file(self) -> Path:
        return self.assignment.source_file

    @property
    def link(self) -> str:
        return self.assignment.link

    @property
    def description(self) -> str | None:
        return self.assignment.description


@dataclass(frozen=True)
class CanvasAssignment:
    """Canvas assignment/submission data unpacked from integrations.canvas."""

    assignment: Assignment
    canvas_id: int | None = None
    canvas_assignment_group: str | None = None
    submissions: list[CanvasAssignmentSubmission] = field(default_factory=list)

    def __iter__(self) -> Iterator[CanvasAssignmentSubmission]:
        return iter(self.submissions)

    @classmethod
    def from_assignment(cls, assignment: Assignment) -> CanvasAssignment:
        canvas_map = _canvas_map(assignment.integrations)
        canvas_id = _parse_int(canvas_map.get("id") or canvas_map.get("canvas_id"))
        canvas_group = optional_string(canvas_map.get("assignment_group"))
        submissions = _submissions_from_assignment(assignment, canvas_map)
        return cls(
            assignment=assignment,
            canvas_id=canvas_id,
            canvas_assignment_group=canvas_group,
            submissions=submissions,
        )


@dataclass(frozen=True)
class CanvasParticipationEvent:
    """A one-point, staff-graded Canvas assignment for a lecture."""

    event: CourseEvent
    source_file: Path
    canvas_assignment_group: str
    canvas_id: int | None = None
    published: bool = False
    position: int | None = None
    points_possible: float = 1.0
    due_at: str | None = None
    close_at: str | None = None
    unlock_at: str | None = None
    submission_types: list[str] = field(default_factory=lambda: ["none"])
    group_assignment: bool = False
    doc_anchor: str | None = None
    rubric_criteria: list[RubricCriterion] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"Participation: {self.event.date.isoformat()} — {self.event.title}"


def canvas_participation_events(
    events: list[CourseEvent],
    config: CanvasParticipationConfig,
    *,
    source_file: Path,
) -> list[CanvasParticipationEvent]:
    """Return chronological Canvas participation targets for lecture events."""

    lectures = sorted(
        (event for event in events if event.kind == "lecture"),
        key=lambda event: (event.date, event.title),
    )
    participation_events: list[CanvasParticipationEvent] = []
    for position, event in enumerate(lectures, start=1):
        canvas_map = _canvas_map(event.integrations)
        participation_events.append(
            CanvasParticipationEvent(
                event=event,
                source_file=source_file,
                canvas_assignment_group=config.assignment_group,
                canvas_id=_parse_int(canvas_map.get("participation_id")),
                position=position,
            )
        )
    return participation_events


@dataclass(frozen=True)
class CanvasQuizIntegration:
    """Canvas state extracted from a quiz's integrations dict."""

    id: int | None = None
    assignment_group: str | None = None
    quiz_type: str | None = None


def _rubric_criteria(
    assignment: Assignment,
    source: dict[str, Any],
) -> list[RubricCriterion]:
    rubric_section = optional_string(source.get("rubric_section"))
    rubric_criteria_filter = _parse_rubric_criteria_filter(source.get("rubric_criteria"))
    criteria = assignment.rubric.select_criteria(rubric_section, rubric_criteria_filter)
    if assignment.rubric.typed and rubric_section is not None and not criteria:
        raise CoursemdValidationError(
            f"Typed rubric section '{rubric_section}' was not found or selected no criteria.",
            source_path=assignment.source_file,
        )
    return criteria


def _unlock_at(assignment: Assignment, source: dict[str, Any]) -> str | None:
    if source.get("unlock_at") is not None:
        return require_release_date(source.get("unlock_at"), "unlock_at")
    return require_release_date(assignment.release_date, "release_date")


def _submission_from_canvas_map(
    assignment: Assignment,
    source: dict[str, Any],
    *,
    checkpoint: AssignmentCheckpoint | None = None,
    default_points: float | None = None,
) -> CanvasAssignmentSubmission:
    title = optional_string(source.get("name")) or optional_string(source.get("title"))
    name = title or (checkpoint.title if checkpoint is not None else assignment.name)
    due_at: str | None
    due_at_raw = source.get("due_at")
    if due_at_raw is not None:
        due_at = normalize_due_at(due_at_raw, name)
    elif checkpoint is not None:
        due_at = checkpoint.due_at.isoformat()
    else:
        due_at = assignment.due_at

    close_at: str | None
    close_at_raw = source.get("close_at")
    if close_at_raw is not None:
        close_at = normalize_close_at(close_at_raw, name)
    elif checkpoint is not None and checkpoint.close_at is not None:
        close_at = checkpoint.close_at.isoformat()
    else:
        close_at = assignment.close_at

    if (
        close_at is not None
        and due_at is not None
        and dt.datetime.fromisoformat(close_at) < dt.datetime.fromisoformat(due_at)
    ):
        raise CoursemdValidationError(
            f"Canvas assignment '{name}' close_at must not be earlier than due_at.",
            source_path=assignment.source_file,
        )

    points_raw = source.get("points", source.get("points_possible", default_points))
    points_possible = 100.0 if points_raw is None else _parse_float(points_raw, "points")

    doc_anchor = (
        optional_string(source.get("doc_anchor"))
        or (checkpoint.doc_anchor if checkpoint is not None else None)
        or assignment.doc_anchor
    )
    rubric_criteria = _rubric_criteria(assignment, source)
    if assignment.rubric.typed and rubric_criteria:
        rubric_points = sum(criterion.points for criterion in rubric_criteria)
        if points_possible != rubric_points:
            raise CoursemdValidationError(
                f"Canvas assignment '{name}' declares {points_possible:g} points, "
                f"but its typed rubric criteria total {rubric_points}.",
                source_path=assignment.source_file,
            )

    return CanvasAssignmentSubmission(
        assignment=assignment,
        name=name,
        due_at=due_at,
        points_possible=points_possible,
        close_at=close_at,
        canvas_id=_parse_int(source.get("id") or source.get("canvas_id")),
        canvas_assignment_group=optional_string(source.get("assignment_group")),
        submission_types=_parse_submission_types(source.get("submission_types")),
        published=_parse_bool(source.get("published")),
        position=_parse_position(source.get("position")),
        unlock_at=_unlock_at(assignment, source),
        group_assignment=_parse_bool(
            source.get("group_assignment"),
            default=assignment.group_assignment,
        ),
        submission_form=_parse_submission_form(source.get("submission_form")),
        rubric_criteria=rubric_criteria,
        doc_url=optional_string(source.get("doc_url")) or assignment.doc_url,
        doc_anchor=doc_anchor,
        notes=optional_string(source.get("notes")) or assignment.notes,
    )


def _submissions_from_assignment(
    assignment: Assignment,
    canvas_map: dict[str, Any],
) -> list[CanvasAssignmentSubmission]:
    checkpoints = canvas_map.get("checkpoints")
    if isinstance(checkpoints, list) and checkpoints:
        submissions: list[CanvasAssignmentSubmission] = []
        for index, item in enumerate(cast("list[Any]", checkpoints)):
            if not isinstance(item, dict):
                raise TypeError(f"integrations.canvas.checkpoints[{index}] must be an object.")
            source = dict(cast("dict[str, Any]", item))
            has_global_group = canvas_map.get("assignment_group") is not None
            if has_global_group and source.get("assignment_group") is None:
                source["assignment_group"] = canvas_map.get("assignment_group")
            checkpoint = _find_checkpoint(assignment, source)
            submissions.append(
                _submission_from_canvas_map(
                    assignment,
                    source,
                    checkpoint=checkpoint,
                    default_points=0.0,
                )
            )
        return submissions

    return [_submission_from_canvas_map(assignment, canvas_map)]


def canvas_assignment_submissions(assignment: Assignment) -> list[CanvasAssignmentSubmission]:
    """Return the Canvas submission targets for a course.md assignment."""

    return CanvasAssignment.from_assignment(assignment).submissions


def canvas_lab_submission(lab: Lab) -> CanvasAssignmentSubmission:
    """Return the Canvas assignment target for a course.md lab."""
    canvas_map = _canvas_map(lab.integrations)
    if canvas_map.get("name") is not None:
        raise CoursemdValidationError(
            "Lab names must use top-level 'title'; remove integrations.canvas.name.",
            source_path=lab.source_file,
        )
    legacy_timing_fields = sorted({"due_at", "unlock_at"} & canvas_map.keys())
    if legacy_timing_fields:
        fields = ", ".join(f"integrations.canvas.{field}" for field in legacy_timing_fields)
        raise CoursemdValidationError(
            f"Lab timing must use top-level 'release_date' and 'due_at'; remove {fields}.",
            source_path=lab.source_file,
        )
    if lab.release_date is None or lab.due_at is None:
        raise CoursemdValidationError(
            "Canvas lab sync requires top-level 'release_date' and 'due_at'.",
            source_path=lab.source_file,
        )
    unlock_at = require_release_date(lab.release_date, "release_date")
    points_raw = canvas_map.get("points", canvas_map.get("points_possible", 1.0))

    return CanvasAssignmentSubmission(
        assignment=lab,
        name=lab.name,
        due_at=lab.due_at,
        points_possible=_parse_float(points_raw, "points"),
        close_at=lab.due_at,
        canvas_id=_parse_int(canvas_map.get("id") or canvas_map.get("canvas_id")),
        canvas_assignment_group=optional_string(canvas_map.get("assignment_group")),
        submission_types=_parse_submission_types(
            canvas_map.get("submission_types", ["online_url"])
        ),
        published=_parse_bool(canvas_map.get("published")),
        position=_parse_position(canvas_map.get("position")),
        unlock_at=unlock_at,
        group_assignment=_parse_bool(canvas_map.get("group_assignment")),
        submission_form=_parse_submission_form(canvas_map.get("submission_form")),
        doc_url=optional_string(canvas_map.get("doc_url")),
        doc_anchor=optional_string(canvas_map.get("doc_anchor")),
        notes=optional_string(canvas_map.get("notes")),
    )


def canvas_quiz(integrations: dict[str, Any]) -> CanvasQuizIntegration:
    """Extract Canvas integration data from a quiz's raw integrations dict."""
    canvas_map = _canvas_map(integrations)
    canvas_id = _parse_int(canvas_map.get("id") or canvas_map.get("canvas_id"))
    group = optional_string(canvas_map.get("assignment_group"))
    quiz_type_override = canvas_map.get("quiz_type")
    quiz_type = str(quiz_type_override) if quiz_type_override else None
    return CanvasQuizIntegration(id=canvas_id, assignment_group=group, quiz_type=quiz_type)


__all__ = [
    "CanvasAssignment",
    "CanvasAssignmentSubmission",
    "CanvasParticipationEvent",
    "CanvasQuizIntegration",
    "CanvasSubmissionField",
    "canvas_assignment_submissions",
    "canvas_lab_submission",
    "canvas_participation_events",
    "canvas_quiz",
]
