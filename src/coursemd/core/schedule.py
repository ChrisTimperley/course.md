"""Core schedule data model."""

import datetime as dt
import typing as t
from dataclasses import dataclass

from coursemd.core.models.assignment import Assignment
from coursemd.core.models.quiz import Quiz
from coursemd.core.types import BreakDict, EventDict
from coursemd.core.utils import current_date, working_days


@dataclass(frozen=True)
class ScheduleEntry:
    """Stores information for a single day in the course schedule."""

    date: dt.date
    events: list[EventDict]
    break_: BreakDict | None
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
        events: list[EventDict],
        breaks: list[BreakDict],
        assignments: list[Assignment],
        quizzes: list[Quiz],
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

        Returns:
            A Schedule object with all entries populated
        """
        now = current_date()

        def break_at_date(d: dt.date) -> BreakDict | None:
            """Find if there's a break on the given date."""
            for break_ in breaks:
                if break_["start"] <= d <= break_["end"]:
                    return break_
            return None

        def preview_next(
            events_by_date: dict[dt.date, list[EventDict]],
        ) -> dict[dt.date, list[EventDict]]:
            """Keep all previous events and the next upcoming event, hide future ones."""
            filtered: dict[dt.date, list[EventDict]] = {}

            # We keep all previous events as well as the next upcoming event
            # We ignore all other future events
            for d in sorted(events_by_date):
                filtered[d] = events_by_date[d]
                if d > now:
                    break

            return filtered

        # Build event dictionaries
        events_by_date: dict[dt.date, list[EventDict]] = {}
        for event in events:
            events_by_date.setdefault(event["date"], []).append(event)
        date_to_events = preview_next(events_by_date)

        # Build assignment dictionaries
        date_to_assignment_release = {
            assignment.release_date: assignment
            for assignment in assignments
            if assignment.reveal_on <= now
        }
        date_to_assignment_due = {
            assignment.due_date: assignment
            for assignment in assignments
            if assignment.release_date <= now
        }

        # Build quiz dictionaries
        date_to_quiz_release = {
            quiz.release_date: quiz for quiz in quizzes if quiz.release_date <= now
        }
        date_to_quiz_due = {
            quiz.due_date: quiz for quiz in quizzes if quiz.release_date <= now
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
