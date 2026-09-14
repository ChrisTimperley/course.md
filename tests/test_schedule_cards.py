from __future__ import annotations

import datetime as dt

from coursemd.core.models.course_event import CourseEvent, Handout
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


def test_lecture_card_links_to_handout_downloads_in_both_layouts() -> None:
    event = CourseEvent(
        kind="lecture",
        date=dt.date(2026, 1, 12),
        title="Course Introduction",
        learning_goals=("Explain flow & feedback.",),
        handouts=(Handout(title="Evidence & notes", link="/handouts/intro/evidence.pdf"),),
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

    expanded = render_schedule_cards(schedule, current_page_url="schedule/")
    flat = render_schedule_cards(schedule, current_page_url="schedule/", show_learning_goals=False)

    for rendered in (expanded, flat):
        assert 'href="../handouts/intro/evidence.pdf" download>' in rendered
        assert "Handout: Evidence &amp; notes <" in rendered
    assert '<span class="wevent__handouts">' in flat


def test_lecture_card_can_hide_learning_goals() -> None:
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

    rendered = render_schedule_cards(
        schedule,
        current_page_url="schedule/",
        show_learning_goals=False,
    )

    assert "wevent--expandable" not in rendered
    assert "Explain flow &amp; feedback." not in rendered
    assert "Learning goals" not in rendered
    assert 'href="../slides/course-introduction.html"' in rendered


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
