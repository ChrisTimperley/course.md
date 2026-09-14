"""Core schedule data model."""

import datetime as dt
import typing as t
from dataclasses import dataclass

from coursemd.core.models.assignment import Assignment
from coursemd.core.models.course_break import CourseBreak
from coursemd.core.models.course_event import CourseEvent
from coursemd.core.models.quiz import Quiz
from coursemd.core.utils import current_date, working_days


@dataclass(frozen=True)
class ScheduleEntry:
    """Stores information for a single day in the course schedule."""

    date: dt.date
    events: list[CourseEvent]
    break_: CourseBreak | None
    assignment_released: Assignment | None
    assignment_due: Assignment | None
    quiz_released: Quiz | None
    quiz_due: Quiz | None


@dataclass(frozen=True)
class Schedule:
    """Represents a complete course schedule."""

    entries: t.Sequence[ScheduleEntry]

    @classmethod
    def build(
        cls,
        earliest_date: dt.date,
        latest_date: dt.date,
        events: list[CourseEvent],
        breaks: list[CourseBreak],
        assignments: list[Assignment],
        quizzes: list[Quiz],
        show_upcoming_lectures: bool = False,
        show_upcoming_exams: bool = False,
        show_all_content: bool = False,
    ) -> t.Self:
        """
        Build a schedule from course data.

        Args:
            earliest_date: Start date of the course
            latest_date: End date of the course
            events: List of course events (lectures, recitations, exams)
            breaks: List of break periods
            assignments: List of assignments
            quizzes: List of quizzes
            show_upcoming_lectures: Whether to include every upcoming lecture
            show_upcoming_exams: Whether to include every upcoming exam or midterm
            show_all_content: Whether to include unreleased events, assignments, and quizzes

        Returns:
            A Schedule object with all entries populated
        """
        now = current_date()

        def break_at_date(d: dt.date) -> CourseBreak | None:
            """Find if there's a break on the given date."""
            for break_ in breaks:
                if break_.contains(d):
                    return break_
            return None

        def preview_next(
            events_by_date: dict[dt.date, list[CourseEvent]],
        ) -> dict[dt.date, list[CourseEvent]]:
            """Keep previous events, the next event, released events, and optional previews.

            Upcoming events with an explicit release date (e.g., labs) are shown once
            released and hidden until then, independently of the next-event preview.
            """
            filtered: dict[dt.date, list[CourseEvent]] = {}
            found_next_upcoming = False

            def is_previewed(event: CourseEvent) -> bool:
                kind = event.kind.strip().lower()
                return (show_upcoming_lectures and kind == "lecture") or (
                    show_upcoming_exams and kind in {"exam", "midterm"}
                )

            for d in sorted(events_by_date):
                events_on_date = events_by_date[d]
                if d <= now:
                    filtered[d] = events_on_date
                    continue

                undated = [event for event in events_on_date if event.release_date is None]
                show_undated = bool(undated) and not found_next_upcoming
                found_next_upcoming = found_next_upcoming or show_undated

                visible_events = [
                    event
                    for event in events_on_date
                    if (event.release_date is not None and event.release_date <= now)
                    or (event.release_date is None and (show_undated or is_previewed(event)))
                ]
                if visible_events:
                    filtered[d] = visible_events

            return filtered

        # Build event dictionaries
        events_by_date: dict[dt.date, list[CourseEvent]] = {}
        for event in events:
            events_by_date.setdefault(event.date, []).append(event)
        date_to_events = events_by_date if show_all_content else preview_next(events_by_date)

        # Build assignment dictionaries
        date_to_assignment_release = {
            assignment.release_date: assignment
            for assignment in assignments
            if show_all_content or assignment.reveal_on <= now
        }
        date_to_assignment_due = {
            assignment.due_date: assignment
            for assignment in assignments
            if show_all_content or assignment.release_date <= now
        }

        # Build quiz dictionaries
        date_to_quiz_release = {
            quiz.release_date: quiz
            for quiz in quizzes
            if show_all_content or quiz.release_date <= now
        }
        date_to_quiz_due = {
            quiz.due_date: quiz for quiz in quizzes if show_all_content or quiz.release_date <= now
        }

        # Build schedule entries
        entries: list[ScheduleEntry] = []
        for date in working_days(earliest_date, latest_date):
            entry = ScheduleEntry(
                date=date,
                events=date_to_events.get(date, []),
                break_=break_at_date(date),
                assignment_released=date_to_assignment_release.get(date),
                assignment_due=date_to_assignment_due.get(date),
                quiz_released=date_to_quiz_release.get(date),
                quiz_due=date_to_quiz_due.get(date),
            )
            entries.append(entry)

        return cls(entries)
