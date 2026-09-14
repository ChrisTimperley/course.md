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


def _events_by_date(schedule: Schedule) -> dict[dt.date, list[CourseEvent]]:
    return {entry.date: entry.events for entry in schedule.entries}


def _build(events: list[CourseEvent]) -> Schedule:
    return Schedule.build(
        earliest_date=dt.date(2026, 1, 12),
        latest_date=dt.date(2026, 1, 16),
        events=events,
        breaks=[],
        assignments=[],
        quizzes=[],
        show_upcoming_lectures=True,
    )


def test_schedule_shows_released_lab_beyond_next_event(monkeypatch) -> None:
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-12")
    today_lecture = _event("lecture", dt.date(2026, 1, 12), "Today lecture")
    next_lecture = _event("lecture", dt.date(2026, 1, 14), "Next lecture")
    released_lab = CourseEvent(
        kind="lab",
        date=dt.date(2026, 1, 16),
        title="Released lab",
        release_date=dt.date(2026, 1, 12),
    )

    events_by_date = _events_by_date(_build([today_lecture, next_lecture, released_lab]))

    assert events_by_date[next_lecture.date] == [next_lecture]
    assert events_by_date[released_lab.date] == [released_lab]


def test_schedule_hides_unreleased_lab_even_when_next_event(monkeypatch) -> None:
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-12")
    unreleased_lab = CourseEvent(
        kind="lab",
        date=dt.date(2026, 1, 13),
        title="Unreleased lab",
        release_date=dt.date(2026, 1, 13),
    )
    future_lab = _event("lab", dt.date(2026, 1, 15), "Future lab")

    events_by_date = _events_by_date(_build([unreleased_lab, future_lab]))

    assert events_by_date[unreleased_lab.date] == []
    assert events_by_date[future_lab.date] == [future_lab]
