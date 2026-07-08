"""HTML rendering for course schedules as weekly cards in MkDocs.

This is an alternative presentation to :mod:`coursemd.integrations.mkdocs.schedule`
(which renders a flat day-by-day table).  Instead of one row per working day, the
schedule is grouped into weekly cards: each card lists that week's events (lectures,
labs, breaks) and the homework released that week.
"""

import datetime as dt
import html

from coursemd.core.models.assignment import Assignment
from coursemd.core.models.course_event import CourseEvent
from coursemd.core.schedule import Schedule, ScheduleEntry
from coursemd.core.utils import current_date

# Map an event kind to the CSS modifier used for its colour dot / accent.
# Kinds not listed fall back to ``other``.
_KIND_MODIFIERS = {
    "lecture": "lecture",
    "workshop": "workshop",
    "recitation": "recitation",
    "lab": "lab",
    "midterm": "exam",
    "exam": "exam",
}

# Kinds whose title is prefixed with a human-readable label (e.g. "Lecture: ...").
_KIND_LABELS = {
    "lecture": "Lecture",
    "workshop": "Workshop",
    "recitation": "Recitation",
    "lab": "Lab",
}

# Kinds that link out to external material (open in a new tab).
_EXTERNAL_KINDS = {"lecture", "workshop"}


def _week_start(day: dt.date) -> dt.date:
    """Return the Monday of the week containing ``day``."""
    return day - dt.timedelta(days=day.weekday())


def _format_range(start: dt.date, end: dt.date) -> str:
    """Format a date range, collapsing a single day and omitting a shared month."""
    left = start.strftime("%b ") + str(start.day)
    if start == end:
        return left
    right = str(end.day) if start.month == end.month else end.strftime("%b ") + str(end.day)
    return f"{left} – {right}"  # noqa: RUF001 (en dash is intentional for ranges)


def _render_event(event: CourseEvent) -> str:
    kind = event.kind.strip().lower()
    modifier = _KIND_MODIFIERS.get(kind, "other")

    title = html.escape(event.title)
    if label := _KIND_LABELS.get(kind):
        title = f"{label}: {title}"
    elif kind in {"midterm", "exam"}:
        title = title or kind.title()
    elif kind:
        title = f"{html.escape(kind.replace('_', ' ').title())}: {title}"

    day_label = event.date.strftime("%a ") + str(event.date.day)

    if event.link:
        href = html.escape(event.link, quote=True)
        target = ' target="_blank" rel="noopener noreferrer"' if kind in _EXTERNAL_KINDS else ""
        body = f'<a class="wevent__title" href="{href}"{target}>{title}</a>'
    else:
        body = f'<span class="wevent__title">{title}</span>'

    return (
        f'<li class="wevent wevent--{modifier}">'
        f'<span class="wevent__day">{day_label}</span>'
        f"{body}"
        f"</li>"
    )


def _render_break_day(entry: ScheduleEntry) -> str:
    """Render a single break day as a dated row, like the event rows."""
    assert entry.break_ is not None
    day_label = entry.date.strftime("%a ") + str(entry.date.day)
    name = f"No Class: {html.escape(entry.break_.name)}"
    return (
        '<li class="wevent wevent--break">'
        f'<span class="wevent__day">{day_label}</span>'
        f'<span class="wevent__title">{name}</span>'
        "</li>"
    )


def _render_homework_row(assignment: Assignment) -> str:
    """Render a homework as a dated row placed on its due date (usually Sunday)."""
    due = assignment.due_date
    day_label = due.strftime("%a ") + str(due.day)
    title = f"Due: {html.escape(assignment.title)}"
    if assignment.link:
        href = html.escape(assignment.link, quote=True)
        body = f'<a class="wevent__title" href="{href}">{title}</a>'
    else:
        body = f'<span class="wevent__title">{title}</span>'
    return (
        '<li class="wevent wevent--homework">'
        f'<span class="wevent__day">{day_label}</span>'
        f"{body}"
        "</li>"
    )


def _render_week(
    *,
    week_start: dt.date,
    week_number: int,
    entries: list[ScheduleEntry],
    homework: list[Assignment],
    today_week_start: dt.date,
) -> str:
    rows: list[str] = []
    for entry in entries:
        if entry.events:
            rows.extend(_render_event(event) for event in entry.events)
        elif entry.break_ is not None:
            rows.append(_render_break_day(entry))

    # Homework is due on the weekend, so it follows the week's Mon-Fri events.
    rows.extend(_render_homework_row(a) for a in sorted(homework, key=lambda a: a.due_date))

    # Skip weeks with nothing to show (e.g. unrevealed future weeks).
    if not rows:
        return ""

    if week_start == today_week_start:
        status_class = " week-card--current"
        status = '<span class="week-card__status">You are here</span>'
    elif week_start > today_week_start:
        status_class = " week-card--upcoming"
        status = ""
    else:
        status_class = " week-card--past"
        status = ""

    date_range = _format_range(entries[0].date, entries[-1].date)

    return (
        f'<section class="week-card{status_class}">'
        '<header class="week-card__head">'
        f'<span class="week-card__num">Week {week_number}</span>'
        f'<span class="week-card__dates">{date_range}</span>'
        f"{status}"
        "</header>"
        f'<ul class="week-card__events">{"".join(rows)}</ul>'
        "</section>"
    )


def render_schedule_cards(schedule: Schedule) -> str:
    """Render a Schedule as a stack of weekly cards."""
    if not schedule.entries:
        return "<p><em>No events yet.</em></p>"

    # Group entries by the Monday of their week, preserving chronological order.
    weeks: dict[dt.date, list[ScheduleEntry]] = {}
    for entry in schedule.entries:
        weeks.setdefault(_week_start(entry.date), []).append(entry)

    # Group released homework by the week it is due in (the week of its due date).
    homework_by_week: dict[dt.date, list[Assignment]] = {}
    seen: set[int] = set()
    for entry in schedule.entries:
        assignment = entry.assignment_released
        if assignment is None or id(assignment) in seen:
            continue
        seen.add(id(assignment))
        homework_by_week.setdefault(_week_start(assignment.due_date), []).append(assignment)

    first_week_start = min(weeks)
    today_week_start = _week_start(current_date())

    cards: list[str] = []
    for week_start in sorted(weeks):
        week_number = ((week_start - first_week_start).days // 7) + 1
        cards.append(
            _render_week(
                week_start=week_start,
                week_number=week_number,
                entries=weeks[week_start],
                homework=homework_by_week.get(week_start, []),
                today_week_start=today_week_start,
            )
        )

    return f'<div id="schedule" class="schedule-cards">{"".join(cards)}</div>'
