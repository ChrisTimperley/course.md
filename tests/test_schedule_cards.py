from __future__ import annotations

import datetime as dt

from coursemd.core.models.course_event import CourseEvent
from coursemd.core.schedule import Schedule, ScheduleEntry
from coursemd.integrations.mkdocs.schedule_cards import render_schedule_cards


def test_lecture_card_expands_learning_goals_and_links_to_slides() -> None:
    event = CourseEvent(
        kind="lecture",
        date=dt.date(2026, 1, 12),
        title="Course Introduction",
        link="/slides/course-introduction.html",
        learning_goals=("Explain flow & feedback.",),
    )
    schedule = Schedule(
        entries=[
            ScheduleEntry(
                date=event.date,
                events=[event],
                break_=None,
                assignment_released=None,
                assignment_due=None,
                quiz_released=None,
                quiz_due=None,
            )
        ]
    )

    rendered = render_schedule_cards(schedule, current_page_url="schedule/")

    assert 'class="wevent wevent--lecture wevent--expandable"' in rendered
    assert '<details class="wevent__details">' in rendered
    assert "Explain flow &amp; feedback." in rendered
    assert 'href="../slides/course-introduction.html"' in rendered
    assert ">Open slides <" in rendered


def test_lecture_card_links_to_preview_spec() -> None:
    event = CourseEvent(
        kind="lecture",
        date=dt.date(2026, 1, 12),
        title="Course Introduction",
        learning_goals=("Explain flow & feedback.",),
    )
    schedule = Schedule(
        entries=[
            ScheduleEntry(
                date=event.date,
                events=[event],
                break_=None,
                assignment_released=None,
                assignment_due=None,
                quiz_released=None,
                quiz_due=None,
            )
        ]
    )

    rendered = render_schedule_cards(
        schedule,
        preview_spec_links={event.date: "/specs/00-course-introduction/"},
        current_page_url="schedule/",
    )

    assert 'class="wevent__spec-link"' in rendered
    assert 'href="../specs/00-course-introduction/"' in rendered
    assert ">View lecture spec<" in rendered
