from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from coursemd.core.models.assignment import Assignment
from coursemd.core.models.course_event import CourseEvent
from coursemd.integrations.mkdocs.macros import define_env


class _MacroEnvironment:
    def __init__(self) -> None:
        self.macros: dict[str, Callable[..., str]] = {}
        self.variables: dict[str, Any] = {}
        self.conf: dict[str, Any] = {}

    def macro(self, function: Callable[..., str]) -> Callable[..., str]:
        self.macros[function.__name__] = function
        return function


def test_schedule_macros_show_lectures_and_exams_publicly_and_everything_in_preview(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-11")
    schedule = {
        "course": {
            "start_date": dt.date(2026, 1, 12),
            "end_date": dt.date(2026, 1, 16),
        },
        "events": [
            CourseEvent(
                kind="lecture",
                date=dt.date(2026, 1, 12),
                title="First lecture",
            ),
            CourseEvent(
                kind="lab",
                date=dt.date(2026, 1, 13),
                title="Future lab",
            ),
            CourseEvent(
                kind="lecture",
                date=dt.date(2026, 1, 14),
                title="Future lecture",
            ),
            CourseEvent(
                kind="midterm",
                date=dt.date(2026, 1, 15),
                title="Midterm I",
            ),
        ],
        "assignments": [
            Assignment(
                source_file=Path("assignments/future.md"),
                title="Future homework",
                release_date=dt.date(2026, 1, 15),
                due_date=dt.date(2026, 1, 16),
                link="/assignments/future/",
            )
        ],
    }

    public_env = _MacroEnvironment()
    public_env.variables["coursemd_preview"] = False
    define_env(public_env)
    preview_env = _MacroEnvironment()
    preview_env.variables["coursemd_preview"] = True
    define_env(preview_env)

    for macro_name in ("schedule_cards", "this_week_card"):
        public = public_env.macros[macro_name](
            schedule,
            show_upcoming_lectures=True,
            show_upcoming_exams=True,
        )

        assert "First lecture" in public
        assert "Future lecture" in public
        assert "Midterm I" in public
        assert "Future lab" not in public
        assert "Future homework" not in public

        preview = preview_env.macros[macro_name](
            schedule,
            show_upcoming_lectures=True,
            show_upcoming_exams=True,
        )

        assert "First lecture" in preview
        assert "Future lecture" in preview
        assert "Midterm I" in preview
        assert "Future lab" in preview
        assert "Future homework" in preview


def test_canvas_submission_resolves_checkpoint_anchor() -> None:
    env = _MacroEnvironment()
    env.conf = {
        "extra": {
            "canvas_base_url": "https://canvas.example.edu",
            "canvas_course_id": 12345,
        }
    }
    env.variables["page"] = SimpleNamespace(
        meta={
            "integrations": {
                "canvas": {
                    "checkpoints": [
                        {
                            "name": "HW1A: Baseline",
                            "doc_anchor": "checkpoint-a",
                            "canvas_id": 456,
                            "submission_form": [{"label": "Final commit URL"}],
                        },
                        {
                            "name": "HW1B: Repairs",
                            "doc_anchor": "checkpoint-b",
                        },
                    ]
                }
            }
        }
    )
    define_env(env)

    canvas_submission = env.macros["canvas_submission"]
    full = canvas_submission("checkpoint-a")
    compact = canvas_submission("checkpoint-a", show_form=False)
    pre_sync = canvas_submission("checkpoint-b", show_form=False)
    numeric = canvas_submission(789)

    assert "courses/12345/assignments/456" in full
    assert "Final commit URL" in full
    assert "courses/12345/assignments/456" in compact
    assert "Final commit URL" not in compact
    assert 'class="canvas-submission__link"' in compact
    assert "Open HW1A in Canvas" in compact
    assert "Open HW1B in Canvas" in pre_sync
    assert "assignments/None" not in pre_sync
    assert "courses/12345/assignments/789" in numeric


def test_submission_checklists_renders_complete_section_from_metadata() -> None:
    env = _MacroEnvironment()
    env.conf = {
        "extra": {
            "canvas_base_url": "https://canvas.example.edu",
            "canvas_course_id": 12345,
        }
    }
    metadata = {
        "submission": {
            "intro": "Complete each checklist.",
            "timezone": "ET",
            "ai_disclosure": "Name the AI tools used, or write **No AI tools used.**",
        },
        "checkpoints": [
            {
                "title": "Checkpoint A",
                "doc_anchor": "checkpoint-a",
                "due_at": "2026-08-30T23:59:00-04:00",
                "deliverables": ["Preserve the submitted revision.", "Submit its URL."],
            }
        ],
        "integrations": {
            "canvas": {
                "checkpoints": [
                    {
                        "name": "HW1A: Baseline",
                        "doc_anchor": "checkpoint-a",
                        "canvas_id": 456,
                    }
                ]
            }
        },
    }
    env.variables["page"] = SimpleNamespace(meta=metadata)
    define_env(env)

    rendered = env.macros["submission_checklists"](metadata)

    assert rendered.startswith("## Submission and Deliverables { #checkpoint-a }")
    assert "Complete each checklist." in rendered
    assert "### HW1A: Baseline" not in rendered
    assert "**Due Sunday, August 30 at 11:59 pm ET.**" in rendered
    assert "* [ ] Preserve the submitted revision." in rendered
    assert "* [ ] Submit its URL." in rendered
    assert "courses/12345/assignments/456" in rendered
    assert "Open HW1A in Canvas" in rendered
    assert '!!! info "AI-use disclosure"' in rendered
    assert "No AI tools used." in rendered


def test_submission_checklists_separates_multiple_checkpoints() -> None:
    env = _MacroEnvironment()
    env.conf = {
        "extra": {
            "canvas_base_url": "https://canvas.example.edu",
            "canvas_course_id": 12345,
        }
    }
    metadata = {
        "checkpoints": [
            {
                "title": "Checkpoint A",
                "doc_anchor": "checkpoint-a",
                "due_at": "2026-08-30T23:59:00-04:00",
                "deliverables": ["Submit the baseline."],
            },
            {
                "title": "Checkpoint B",
                "doc_anchor": "checkpoint-b",
                "due_at": "2026-09-06T23:59:00-04:00",
                "deliverables": ["Submit the repairs."],
            },
        ],
        "integrations": {
            "canvas": {
                "checkpoints": [
                    {"name": "HW1A: Baseline", "doc_anchor": "checkpoint-a"},
                    {"name": "HW1B: Repairs", "doc_anchor": "checkpoint-b"},
                ]
            }
        },
    }
    env.variables["page"] = SimpleNamespace(meta=metadata)
    define_env(env)

    rendered = env.macros["submission_checklists"](metadata)

    assert rendered.startswith("## Submission and Deliverables\n")
    assert "### HW1A: Baseline { #checkpoint-a }" in rendered
    assert "### HW1B: Repairs { #checkpoint-b }" in rendered
