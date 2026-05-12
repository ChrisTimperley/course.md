"""Repository-level loaders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import yaml  # type: ignore[import-untyped]
from dotenv import load_dotenv

from coursemd.core.exceptions import CoursemdValidationError, wrap_validation_errors
from coursemd.core.loaders.specs import load_assignments
from coursemd.core.loaders.validation import bind_validation

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.models.assignment import Assignment
    from coursemd.core.types import BreakDict, EventDict


@wrap_validation_errors
def validate_schedule_data(source_file: Path, value: Any) -> dict[str, Any]:
    """Validate and normalize schedule.yaml content."""
    validate = bind_validation(source_file)

    schedule = validate.require_mapping(value, "schedule")
    course_raw = validate.require_mapping(schedule.get("course"), "course")
    start_date = validate.require_date(course_raw.get("start_date"), "course.start_date")
    end_date = validate.require_date(course_raw.get("end_date"), "course.end_date")
    if end_date < start_date:
        raise ValueError("'course.end_date' must not be earlier than 'course.start_date'.")

    course = dict(course_raw)
    course["title"] = validate.require_non_empty_string(course_raw.get("title"), "course.title")
    course["start_date"] = start_date
    course["end_date"] = end_date
    events_raw = schedule.get("events", [])
    if not isinstance(events_raw, list):
        raise TypeError("'events' must be a list.")
    events: list[EventDict] = []
    for index, event_raw in enumerate(events_raw):
        event = validate.require_mapping(event_raw, f"events[{index}]")
        kind = validate.require_non_empty_string(event.get("kind"), f"events[{index}].kind").lower()
        event_date = validate.require_date(event.get("date"), f"events[{index}].date")

        normalized_event = dict(event)
        normalized_event["kind"] = kind
        normalized_event["date"] = event_date
        normalized_event["title"] = validate.require_non_empty_string(
            event.get("title"),
            f"events[{index}].title",
        )
        if "link" in event and event.get("link") is not None:
            normalized_event["link"] = validate.require_non_empty_string(
                event.get("link"),
                f"events[{index}].link",
            )
        events.append(cast("EventDict", normalized_event))

    breaks_raw = schedule.get("breaks", [])
    if not isinstance(breaks_raw, list):
        raise TypeError("'breaks' must be a list.")
    breaks: list[BreakDict] = []
    for index, break_raw in enumerate(breaks_raw):
        break_map = validate.require_mapping(break_raw, f"breaks[{index}]")
        start = validate.require_date(break_map.get("start"), f"breaks[{index}].start")
        end = validate.require_date(break_map.get("end"), f"breaks[{index}].end")
        if end < start:
            raise ValueError(f"breaks[{index}].end must not be earlier than breaks[{index}].start.")
        breaks.append(
            {
                "name": validate.require_non_empty_string(
                    break_map.get("name"),
                    f"breaks[{index}].name",
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
            raise ValueError(f"breaks[{index}] overlaps breaks[{previous_index}].")
        previous_index = index
        previous_break = break_

    normalized = dict(schedule)
    normalized["course"] = course
    normalized["events"] = events
    normalized["breaks"] = breaks
    return normalized


def load_repository_env(repo_root: Path, filename: str = ".env", *, override: bool = False) -> Path:
    """Load a repository-local dotenv file if present and return its path."""

    env_path = repo_root / filename
    load_dotenv(env_path, override=override)
    return env_path


def load_data_files(files: list[Path]) -> dict[str, Any]:
    """Load YAML data files keyed by their stem."""

    loaded: dict[str, Any] = {}
    for path in files:
        try:
            with path.open("r", encoding="utf-8") as handle:
                document = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise CoursemdValidationError(f"invalid YAML: {exc}", source_path=path) from exc
        if path.stem == "schedule":
            loaded[path.stem] = validate_schedule_data(path, document)
        else:
            loaded[path.stem] = document or {}
    return loaded


def load_schedule_assignments(
    files: list[Path],
    *,
    assignment_url_path: str,
) -> list[Assignment]:
    """Load assignment metadata for schedule rendering."""

    return load_assignments(files, assignment_url_path=assignment_url_path)



