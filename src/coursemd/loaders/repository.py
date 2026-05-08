"""Repository-level loaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from coursemd.loaders.assignments import (
    load_assignment_specs,
    validate_schedule_assignment_metadata,
)
from coursemd.loaders.dates import require_date
from coursemd.loaders.markdown import load_markdown_metadata
from coursemd.loaders.quizzes import load_quiz_specs, validate_schedule_quiz_metadata
from coursemd.models.repository import CourseRepository
from coursemd.types import AssignmentDict, BreakDict, EventDict, QuizDict


def _require_mapping(value: Any, source_file: Path, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{source_file}: '{label}' must be an object/map.")
    return value


def _require_non_empty_string(value: Any, source_file: Path, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{source_file}: '{field_name}' must be a non-empty string.")
    return text


def validate_schedule_data(source_file: Path, value: Any) -> dict[str, Any]:
    """Validate and normalize schedule.yaml content."""

    schedule = _require_mapping(value, source_file, "schedule")
    course_raw = _require_mapping(schedule.get("course"), source_file, "course")
    start_date = require_date(course_raw.get("start_date"), source_file, "course.start_date")
    end_date = require_date(course_raw.get("end_date"), source_file, "course.end_date")
    if end_date < start_date:
        raise ValueError(
            f"{source_file}: 'course.end_date' must not be earlier than 'course.start_date'."
        )

    course = dict(course_raw)
    course["title"] = _require_non_empty_string(
        course_raw.get("title"), source_file, "course.title"
    )
    course["start_date"] = start_date
    course["end_date"] = end_date
    if "canvas_course_id" in course_raw:
        canvas_course_id = course_raw.get("canvas_course_id")
        if (
            canvas_course_id is None
            or isinstance(canvas_course_id, bool)
            or not str(canvas_course_id).strip()
        ):
            raise ValueError(
                f"{source_file}: 'course.canvas_course_id' must be a non-empty "
                "string or integer when provided."
            )

    events_raw = schedule.get("events", [])
    if not isinstance(events_raw, list):
        raise ValueError(f"{source_file}: 'events' must be a list.")
    events: list[EventDict] = []
    for index, event_raw in enumerate(events_raw):
        event = _require_mapping(event_raw, source_file, f"events[{index}]")
        kind = _require_non_empty_string(
            event.get("kind"), source_file, f"events[{index}].kind"
        ).lower()
        event_date = require_date(event.get("date"), source_file, f"events[{index}].date")

        normalized_event = dict(event)
        normalized_event["kind"] = kind
        normalized_event["date"] = event_date
        normalized_event["title"] = _require_non_empty_string(
            event.get("title"),
            source_file,
            f"events[{index}].title",
        )
        if "link" in event and event.get("link") is not None:
            normalized_event["link"] = _require_non_empty_string(
                event.get("link"),
                source_file,
                f"events[{index}].link",
            )
        events.append(cast("EventDict", normalized_event))

    breaks_raw = schedule.get("breaks", [])
    if not isinstance(breaks_raw, list):
        raise ValueError(f"{source_file}: 'breaks' must be a list.")
    breaks: list[BreakDict] = []
    for index, break_raw in enumerate(breaks_raw):
        break_map = _require_mapping(break_raw, source_file, f"breaks[{index}]")
        start = require_date(break_map.get("start"), source_file, f"breaks[{index}].start")
        end = require_date(break_map.get("end"), source_file, f"breaks[{index}].end")
        if end < start:
            raise ValueError(
                f"{source_file}: breaks[{index}].end must not be earlier than "
                f"breaks[{index}].start."
            )
        breaks.append(
            {
                "name": _require_non_empty_string(
                    break_map.get("name"), source_file, f"breaks[{index}].name"
                ),
                "start": start,
                "end": end,
            }
        )

    sorted_breaks = sorted(enumerate(breaks), key=lambda item: item[1]["start"])
    previous_index: int | None = None
    previous_break: BreakDict | None = None
    for index, break_ in sorted_breaks:
        if previous_break is not None and break_["start"] <= previous_break["end"]:
            raise ValueError(f"{source_file}: breaks[{index}] overlaps breaks[{previous_index}].")
        previous_index = index
        previous_break = break_

    normalized = dict(schedule)
    normalized["course"] = course
    normalized["events"] = events
    normalized["breaks"] = breaks
    return normalized


def load_repository_env(repo_root: Path, filename: str = ".env", *, override: bool = False) -> Path:
    """Load a repository-local dotenv file if present and return its path."""

    from dotenv import load_dotenv

    env_path = repo_root / filename
    load_dotenv(env_path, override=override)
    return env_path


def load_data_files(files: list[Path]) -> dict[str, Any]:
    """Load YAML data files keyed by their stem."""

    loaded: dict[str, Any] = {}
    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
            if path.stem == "schedule":
                loaded[path.stem] = validate_schedule_data(path, document)
            else:
                loaded[path.stem] = document or {}
    return loaded


def load_schedule_assignments(
    files: list[Path],
    *,
    assignment_url_path: str,
) -> list[AssignmentDict]:
    """Load assignment metadata for schedule rendering."""

    assignments: list[AssignmentDict] = []
    for path in files:
        metadata = load_markdown_metadata(path)
        if str(metadata.get("kind", "")).strip() != "homework":
            continue
        assignments.append(
            validate_schedule_assignment_metadata(
                path,
                metadata,
                assignment_url_path=assignment_url_path,
            )
        )

    return sorted(assignments, key=lambda item: item["release_date"])


def load_schedule_quizzes(
    files: list[Path],
    *,
    canvas_base_url: str,
    canvas_course_id: int | str | None,
) -> list[QuizDict]:
    """Load quiz metadata for schedule rendering."""

    quizzes: list[QuizDict] = []
    for path in files:
        metadata = load_markdown_metadata(path)
        quizzes.append(
            validate_schedule_quiz_metadata(
                path,
                metadata,
                canvas_base_url=canvas_base_url,
                canvas_course_id=canvas_course_id,
            )
        )

    return sorted(quizzes, key=lambda item: item["release_date"])


def load_course_repository(
    *,
    repo_root: Path,
    data_files: list[Path],
    assignment_files: list[Path],
    quiz_files: list[Path],
    site_base_url: str,
    assignment_url_path: str = "assignments",
    canvas_base_url: str = "",
    require_canvas_fields: bool = False,
) -> CourseRepository:
    """Load the configured repository as one object graph."""

    data = load_data_files(data_files)
    schedule_map = cast("dict[str, Any]", data.get("schedule", {}))
    course_map = cast("dict[str, Any]", schedule_map.get("course", {}))

    return CourseRepository(
        repo_root=repo_root,
        data=data,
        assignments=load_assignment_specs(
            assignment_files,
            site_base_url=site_base_url,
            assignment_url_path=assignment_url_path,
            require_canvas_fields=require_canvas_fields,
        ),
        quizzes=load_quiz_specs(
            quiz_files,
            require_canvas_fields=require_canvas_fields,
        ),
        schedule_assignments=load_schedule_assignments(
            assignment_files,
            assignment_url_path=assignment_url_path,
        ),
        schedule_quizzes=load_schedule_quizzes(
            quiz_files,
            canvas_base_url=canvas_base_url,
            canvas_course_id=course_map.get("canvas_course_id"),
        ),
    )
