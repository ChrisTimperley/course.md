"""Schedule configuration for course repositories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from coursemd.core.config_helpers import CONFIG_FILENAME, require_mapping
from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.loaders.dates import parse_date
from coursemd.core.models.course_break import CourseBreak
from coursemd.core.models.course_event import CourseEvent
from coursemd.core.schedule import Schedule

if TYPE_CHECKING:
    import datetime as dt

    from coursemd.core.models.repository import CourseRepository


def _require_date(value: Any, *, label: str) -> dt.date:
    parsed = parse_date(value)
    if parsed is None:
        raise CoursemdValidationError(
            f"{label} must be a valid date or ISO-8601 timestamp in {CONFIG_FILENAME}."
        )
    return parsed


@dataclass(frozen=True)
class ScheduleConfig:
    start_date: dt.date
    end_date: dt.date
    events: list[CourseEvent]
    breaks: list[CourseBreak]

    @classmethod
    def parse(cls, raw_value: Any) -> Self:
        schedule_map = require_mapping(raw_value, label="schedule")
        start_date = _require_date(schedule_map.get("start_date"), label="schedule.start_date")
        end_date = _require_date(schedule_map.get("end_date"), label="schedule.end_date")
        if end_date < start_date:
            raise CoursemdValidationError(
                f"schedule.end_date must not be earlier than schedule.start_date in "
                f"{CONFIG_FILENAME}."
            )

        events = CourseEvent.from_list(schedule_map.get("events", []))

        breaks_raw = schedule_map.get("breaks", [])
        if not isinstance(breaks_raw, list):
            raise CoursemdValidationError(f"schedule.breaks must be a list in {CONFIG_FILENAME}.")

        breaks: list[CourseBreak] = []
        for index, raw_break in enumerate(breaks_raw):
            break_map = require_mapping(raw_break, label=f"schedule.breaks[{index}]")
            start = _require_date(
                break_map.get("start"),
                label=f"schedule.breaks[{index}].start",
            )
            end = _require_date(
                break_map.get("end"),
                label=f"schedule.breaks[{index}].end",
            )
            if end < start:
                raise CoursemdValidationError(
                    f"schedule.breaks[{index}].end must not be earlier than "
                    f"schedule.breaks[{index}].start in {CONFIG_FILENAME}."
                )
            name = break_map.get("name")
            if not isinstance(name, str) or not name.strip():
                raise CoursemdValidationError(
                    f"schedule.breaks[{index}].name must be a non-empty string in "
                    f"{CONFIG_FILENAME}."
                )
            breaks.append(CourseBreak(name=name.strip(), start=start, end=end))

        sorted_breaks = sorted(enumerate(breaks), key=lambda item: item[1].start)
        previous_index: int | None = None
        previous_break: CourseBreak | None = None
        for index, break_ in sorted_breaks:
            if previous_break is not None and break_.start <= previous_break.end:
                raise CoursemdValidationError(
                    f"schedule.breaks[{index}] overlaps schedule.breaks[{previous_index}] "
                    f"in {CONFIG_FILENAME}."
                )
            previous_index = index
            previous_break = break_

        return cls(start_date=start_date, end_date=end_date, events=events, breaks=breaks)

    def build(self, repository: CourseRepository) -> Schedule:
        return Schedule.build(
            earliest_date=self.start_date,
            latest_date=self.end_date,
            events=self.events,
            breaks=self.breaks,
            assignments=repository.assignments,
            quizzes=repository.quizzes,
        )
