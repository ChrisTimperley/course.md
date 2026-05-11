from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from coursemd.core.models.assignment import Assignment
from coursemd.integrations.canvas.sync import CanvasSyncEvent, sync_assignments_to_canvas


class DryRunAssignmentClient:
    dry_run = True

    def get_paginated(
        self,
        path: str,  # noqa: ARG002
        params: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return []


def test_assignment_sync_reports_events_without_printing(capsys) -> None:
    spec = Assignment(
        source_file=Path("assignments/hw1.md"),
        title="Homework 1",
        release_date=dt.date(2026, 1, 12),
        due_date=dt.date(2026, 1, 16),
        link="/assignments/hw1/",
        due_at="2026-01-16T23:59:00-05:00",
        submission_types=["none"],
        points_possible=100,
        published=False,
        position=None,
        unlock_at=None,
        group_assignment=False,
        submission_form=[],
        rubric_criteria=[],
        integrations={"canvas": {"assignment_group": "Homework"}},
    )
    events: list[CanvasSyncEvent] = []

    results = sync_assignments_to_canvas(
        client=DryRunAssignmentClient(),  # type: ignore[arg-type]
        course_id="12345",
        specs=[spec],
        publish_override=False,
        reporter=events.append,
    )

    assert capsys.readouterr().out == ""
    assert results == [
        {
            "action": "create",
            "name": "Homework 1",
            "id": None,
            "html_url": None,
            "source_file": "assignments/hw1.md",
        }
    ]
    assert events == [
        CanvasSyncEvent(
            action="create",
            target="assignment_group",
            name="Homework",
            dry_run=True,
        ),
        CanvasSyncEvent(
            action="create",
            target="assignment",
            name="Homework 1",
            dry_run=True,
        ),
    ]
