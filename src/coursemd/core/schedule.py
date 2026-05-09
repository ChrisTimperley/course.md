"""Schedule rendering logic for course websites."""

import datetime as dt
import html
import typing as t
from dataclasses import dataclass

from coursemd.core.types import AssignmentDict, BreakDict, EventDict, QuizDict
from coursemd.core.utils import current_date, working_days, working_days_between


@dataclass(frozen=True)
class ScheduleEntry:
    """Stores information for a single day in the course schedule."""

    date: dt.date
    events: list[EventDict]
    break_: BreakDict | None
    assignment_released: AssignmentDict | None
    assignment_due: AssignmentDict | None
    quiz_released: QuizDict | None
    quiz_due: QuizDict | None

    def _render_what(self) -> str:
        """Render the 'what' column (event or break)."""
        output = ""

        if self.events:
            rendered_events: list[str] = []
            for event in self.events:
                title = html.escape(str(event["title"]))
                kind = str(event.get("kind", "")).strip().lower()
                attributes = {"class": "label"}
                if link := event.get("link"):
                    attributes["href"] = html.escape(str(link), quote=True)

                if kind == "lecture":
                    title = f"Lecture: {title}"
                    attributes["class"] = "label label-gold"
                    attributes["target"] = "_blank"
                elif kind == "workshop":
                    title = f"Workshop: {title}"
                    attributes["class"] = "label label-green"
                    attributes["target"] = "_blank"
                elif kind == "recitation":
                    title = f"Recitation: {title}"
                    attributes["class"] = "label label-blue"
                elif kind == "midterm":
                    title = title or "Midterm"
                    attributes["class"] = "label label-red"
                elif kind:
                    title = f"{html.escape(kind.replace('_', ' ').title())}: {title}"

                html_attributes = " ".join(f'{k}="{v}"' for k, v in attributes.items())
                rendered_events.append(f"<a {html_attributes}>{title}</a>")
            output = "<br>".join(rendered_events)
        elif self.break_:
            output = f'<a class="label label-break">Break: {html.escape(self.break_["name"])}</a>'

        return f'<td class="what">{output}</td>'

    def _render_assignment(self) -> str:
        """Render the assignment column."""
        if assignment := self.assignment_released:
            start_date = assignment["release_date"]
            end_date = assignment["due_date"]
            num_working_days = working_days_between(start_date, end_date)

            # Assignment title and due date
            html = f"<b>{assignment['title']}</b><br>Due {end_date.strftime('%A, %B %d')} @ 11:59pm"

            # Render checkpoints if present
            if checkpoints := assignment.get("checkpoints"):
                html += '<ul class="checkpoints">'
                for checkpoint in checkpoints:
                    cp_date = checkpoint["date"]
                    cp_title = checkpoint["title"]
                    date_str = cp_date.strftime("%a %b ") + str(cp_date.day)

                    html += "<li>"
                    html += '<span class="checkpoint-badge">🚩</span>'
                    html += '<span class="checkpoint-info">'
                    html += f'<span class="checkpoint-date">{date_str}</span>'
                    html += f'<span class="checkpoint-title">{cp_title}</span>'
                    html += "</span>"
                    html += "</li>"
                html += "</ul>"
            else:
                # Add spacing when there are no checkpoints
                html += "<br>"

            # Handout button at the bottom
            attributes = {
                "class": "label label-red",
                "href": assignment.get("link", ""),
            }
            html_attributes = " ".join(f'{k}="{v}"' for k, v in attributes.items())
            html += f"<a {html_attributes}>Handout</a>"

            return f'<td class="assignment" rowspan="{num_working_days}">{html}</td>'

        return '<td class="assignment"></td>'

    def _render_when(self) -> str:
        """Render the date column."""
        html_when = self.date.strftime("%a %b ") + str(self.date.day)
        return f'<td class="when">{html_when}</td>'

    def _render_quiz(self) -> str:
        """Render the quiz column."""
        if quiz := self.quiz_released:
            start_date = quiz["release_date"]
            end_date = quiz["due_date"]
            num_working_days = working_days_between(start_date, end_date)

            due_text = end_date.strftime("%A, %B %d")
            out = (
                f"<b>{html.escape(quiz['title'])}</b><br>"
                f'<span class="quiz-due">Due {due_text} @ 11:59pm</span>'
            )

            if readings := quiz.get("readings"):
                out += (
                    '<div class="quiz-readings-wrap">'
                    '<span class="quiz-readings-label">Readings</span>'
                    '<ul class="quiz-readings">'
                )
                for r in readings:
                    title_esc = html.escape(r["title"])
                    url_esc = html.escape(r["url"], quote=True)
                    out += (
                        '<li><span class="reading-badge">📖</span>'
                        f'<a href="{url_esc}" target="_blank" '
                        f'rel="noopener noreferrer">{title_esc}</a></li>'
                    )
                out += "</ul></div>"

            attributes = {
                "class": "label label-purple",
                "href": quiz.get("link", ""),
            }
            html_attributes = " ".join(f'{k}="{v}"' for k, v in attributes.items())
            out += f"<br><a {html_attributes}>Take Quiz</a>"

            return f'<td class="quiz" rowspan="{num_working_days}">{out}</td>'

        return '<td class="quiz"></td>'

    def render(self, skip_quiz: bool = False, skip_assignment: bool = False) -> str:
        """
        Render a complete table row for this schedule entry.

        Args:
            skip_quiz: If True, don't render the quiz column (used for rowspan)
            skip_assignment: If True, don't render the assignment column (used for rowspan)

        Returns:
            HTML string for the table row
        """
        html_what = self._render_what()
        html_when = self._render_when()

        # Only render quiz/assignment cells if not skipping
        html_quiz = "" if skip_quiz else self._render_quiz()
        html_assignment = "" if skip_assignment else self._render_assignment()

        html = f"<tr>{html_when}{html_what}{html_quiz}{html_assignment}</tr>"
        return html


@dataclass
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
        assignments: list[AssignmentDict],
        quizzes: list[QuizDict],
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
            assignment["release_date"]: assignment
            for assignment in assignments
            if assignment.get("reveal_date", assignment["release_date"]) <= now
        }
        date_to_assignment_due = {
            assignment["due_date"]: assignment
            for assignment in assignments
            if assignment["release_date"] <= now
        }

        # Build quiz dictionaries
        date_to_quiz_release = {
            quiz["release_date"]: quiz for quiz in quizzes if quiz["release_date"] <= now
        }
        date_to_quiz_due = {
            quiz["due_date"]: quiz for quiz in quizzes if quiz["release_date"] <= now
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

    def render(self) -> str:
        """
        Render the complete schedule as an HTML table.

        Returns:
            HTML string for the complete schedule table
        """
        if not self.entries:
            return "<p><em>No events yet.</em></p>"

        html = (
            '<div id="schedule"><table><thead><tr><th>Date</th><th>Event</th>'
            "<th>Quiz</th><th>Assignment</th></tr></thead><tbody>"
        )

        # Track spanning cells
        quiz_span_remaining = 0
        assignment_span_remaining = 0

        for entry in self.entries:
            # Determine if we should skip columns due to previous rowspan
            skip_quiz = quiz_span_remaining > 0
            skip_assignment = assignment_span_remaining > 0

            # Calculate new spans if items are released
            if entry.quiz_released:
                quiz_span_remaining = working_days_between(
                    entry.quiz_released["release_date"], entry.quiz_released["due_date"]
                )
            if entry.assignment_released:
                assignment_span_remaining = working_days_between(
                    entry.assignment_released["release_date"], entry.assignment_released["due_date"]
                )

            # Render the entry
            html += entry.render(skip_quiz=skip_quiz, skip_assignment=skip_assignment)

            # Decrement span counters
            if quiz_span_remaining > 0:
                quiz_span_remaining -= 1
            if assignment_span_remaining > 0:
                assignment_span_remaining -= 1

        html += "</tbody></table></div>"
        return html
