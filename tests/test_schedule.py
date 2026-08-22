from __future__ import annotations

import datetime as dt

from coursemd.core.models.course_event import CourseEvent
from coursemd.core.schedule import Schedule


def _event(kind: str, date: dt.date, title: str) -> CourseEvent:
    return CourseEvent(kind=kind, date=date, title=title)


def test_schedule_can_show_all_upcoming_lectures(monkeypatch) -> None:
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-11")
    first_lecture = _event("lecture", dt.date(2026, 1, 12), "First lecture")
    future_lab = _event("lab", dt.date(2026, 1, 13), "Future lab")
    future_lecture = _event("lecture", dt.date(2026, 1, 14), "Future lecture")

    schedule = Schedule.build(
        earliest_date=dt.date(2026, 1, 12),
        latest_date=dt.date(2026, 1, 16),
        events=[first_lecture, future_lab, future_lecture],
        breaks=[],
        assignments=[],
        quizzes=[],
        show_upcoming_lectures=True,
    )

    events_by_date = {entry.date: entry.events for entry in schedule.entries}
    assert events_by_date[first_lecture.date] == [first_lecture]
    assert events_by_date[future_lab.date] == []
    assert events_by_date[future_lecture.date] == [future_lecture]


def test_schedule_hides_later_upcoming_lectures_by_default(monkeypatch) -> None:
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-11")
    first_lecture = _event("lecture", dt.date(2026, 1, 12), "First lecture")
    future_lecture = _event("lecture", dt.date(2026, 1, 14), "Future lecture")

    schedule = Schedule.build(
        earliest_date=dt.date(2026, 1, 12),
        latest_date=dt.date(2026, 1, 16),
        events=[first_lecture, future_lecture],
        breaks=[],
        assignments=[],
        quizzes=[],
    )

    events_by_date = {entry.date: entry.events for entry in schedule.entries}
    assert events_by_date[first_lecture.date] == [first_lecture]
    assert events_by_date[future_lecture.date] == []
