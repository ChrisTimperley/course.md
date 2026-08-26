from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.models.assignment import Assignment, AssignmentCheckpoint
from coursemd.core.models.course_event import CourseEvent
from coursemd.core.models.lab import Lab
from coursemd.integrations.canvas.assignments import (
    form_for_assignment,
    form_for_participation_event,
)
from coursemd.integrations.canvas.config import CanvasParticipationConfig
from coursemd.integrations.canvas.frontmatter import (
    update_course_config_with_participation_ids,
    update_lab_frontmatter_with_ids,
)
from coursemd.integrations.canvas.models import (
    canvas_assignment_submissions,
    canvas_lab_submission,
    canvas_participation_events,
)
from coursemd.integrations.canvas.resources import AssignmentCanvasClient
from coursemd.integrations.canvas.sync import (
    CanvasSyncEvent,
    sync_assignments_to_canvas,
    sync_labs_to_canvas,
    sync_participation_to_canvas,
)

LAB_CANVAS_ID = 456
PARTICIPATION_CANVAS_ID = 789
PARTICIPATION_GROUP_ID = 10


class DryRunAssignmentClient:
    dry_run = True

    def get_paginated(
        self,
        path: str,  # noqa: ARG002
        params: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return []


class ExistingAssignmentClient(DryRunAssignmentClient):
    def __init__(self, assignments: list[dict[str, Any]]) -> None:
        self.assignments = assignments

    def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        if path.endswith("/assignment_groups"):
            return [{"id": 10, "name": "Labs"}]
        if path.endswith("/assignments"):
            return self.assignments
        return []

    def is_assignment_released(
        self, course_id: str, assignment_id: int  # noqa: ARG002
    ) -> bool:
        return False

    def assignment_has_grades(
        self, course_id: str, assignment_id: int  # noqa: ARG002
    ) -> bool:
        return False


class ParticipationClient:
    dry_run = False

    def __init__(self) -> None:
        self.group_forms: list[dict[str, Any]] = []
        self.assignment_forms: list[dict[str, Any]] = []

    def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        if path.endswith("/assignment_groups"):
            return [
                {
                    "id": 10,
                    "name": "Engagement",
                    "group_weight": 5,
                    "rules": {"drop_lowest": 1},
                }
            ]
        return []

    def update_assignment_group(
        self,
        course_id: str,  # noqa: ARG002
        assignment_group_id: int,
        form: dict[str, Any],
    ) -> dict[str, Any]:
        assert assignment_group_id == PARTICIPATION_GROUP_ID
        self.group_forms.append(form)
        return {
            "id": 10,
            "name": "Engagement",
            "group_weight": form["group_weight"],
            "rules": json.loads(form["rules"]),
        }

    def create_assignment(
        self,
        course_id: str,  # noqa: ARG002
        form: dict[str, Any],
    ) -> dict[str, Any]:
        self.assignment_forms.append(form)
        return {
            "id": 789,
            "html_url": "https://canvas.example/assignments/789",
        }


class GradedParticipationClient(ParticipationClient):
    def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if path.endswith("/assignments"):
            return [
                {
                    "id": PARTICIPATION_CANVAS_ID,
                    "name": "Participation: 2026-01-12 — Course Introduction",
                    "html_url": "https://canvas.example/assignments/789",
                    "published": False,
                }
            ]
        return super().get_paginated(path, params)

    def is_assignment_released(
        self, course_id: str, assignment_id: int  # noqa: ARG002
    ) -> bool:
        return False

    def assignment_has_grades(
        self, course_id: str, assignment_id: int  # noqa: ARG002
    ) -> bool:
        return True

    def update_assignment(
        self,
        course_id: str,  # noqa: ARG002
        assignment_id: int,  # noqa: ARG002
        form: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        raise AssertionError("A graded assignment must never be updated.")


def test_assignment_uses_close_at_as_canvas_lock() -> None:
    assignment = Assignment(
        source_file=Path("assignments/hw1.md"),
        title="Homework 1",
        description="# Private Markdown handout\n\nDo not copy this body into Canvas.",
        release_date=dt.date(2026, 1, 12),
        due_date=dt.date(2026, 1, 16),
        link="/assignments/hw1/",
        due_at="2026-01-16T23:59:00-05:00",
        close_at="2026-01-20T23:59:00-05:00",
        integrations={"canvas": {"assignment_group": "Homework"}},
    )

    submission = canvas_assignment_submissions(assignment)[0]
    form = form_for_assignment(submission, assignment_group_id=10, publish_override=False)

    assert submission.close_at == "2026-01-20T23:59:00-05:00"
    assert form["assignment[due_at]"] == "2026-01-16T23:59:00-05:00"
    assert form["assignment[lock_at]"] == "2026-01-20T23:59:00-05:00"
    assert "Private Markdown handout" not in form["assignment[description]"]
    assert "See assignment instructions on the course website" in form[
        "assignment[description]"
    ]


def test_canvas_checkpoint_inherits_canonical_close_at() -> None:
    checkpoint = AssignmentCheckpoint.from_dict(
        {
            "date": "2026-01-14",
            "title": "Draft",
            "due_at": "2026-01-14T23:59:00-05:00",
            "close_at": "2026-01-18T23:59:00-05:00",
            "doc_anchor": "draft",
        },
        index=0,
    )
    assignment = Assignment(
        source_file=Path("assignments/hw1.md"),
        title="Homework 1",
        release_date=dt.date(2026, 1, 12),
        due_date=dt.date(2026, 1, 16),
        link="/assignments/hw1/",
        checkpoints=[checkpoint],
        integrations={"canvas": {"checkpoints": [{"doc_anchor": "draft"}]}},
    )

    submission = canvas_assignment_submissions(assignment)[0]

    assert submission.due_at == "2026-01-14T23:59:00-05:00"
    assert submission.close_at == "2026-01-18T23:59:00-05:00"


def test_assignment_sync_reports_events_without_printing(capsys) -> None:
    spec = Assignment(
        source_file=Path("assignments/hw1.md"),
        title="Homework 1",
        release_date=dt.date(2026, 1, 12),
        due_date=dt.date(2026, 1, 16),
        link="/assignments/hw1/",
        due_at="2026-01-16T23:59:00-05:00",
        group_assignment=False,
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


def test_assignment_sync_expands_canvas_checkpoint_submissions(capsys) -> None:
    spec = Assignment.load(Path("examples/hw3.md"))
    events: list[CanvasSyncEvent] = []

    results = sync_assignments_to_canvas(
        client=DryRunAssignmentClient(),  # type: ignore[arg-type]
        course_id="12345",
        specs=[spec],
        publish_override=False,
        group_category_id_override=1,
        reporter=events.append,
    )

    assert capsys.readouterr().out == ""
    assert [result["name"] for result in results] == [
        "C0: Scope Check",
        "C1: Hazard Analysis & Draft Launch Argument",
        "C2: Complete Launch Argument",
        "C3: Final Presentation",
    ]
    assert [result["doc_anchor"] for result in results] == [
        "task-c0-scope-check",
        "task-c1-hazard-analysis-and-draft-launch-argument",
        "task-c2-go-live-complete-launch-argument",
        "task-c3-final-presentation",
    ]
    assert [event.name for event in events if event.target == "assignment"] == [
        "C0: Scope Check",
        "C1: Hazard Analysis & Draft Launch Argument",
        "C2: Complete Launch Argument",
        "C3: Final Presentation",
    ]


def test_lab_canvas_submission_uses_lab_defaults_and_metadata() -> None:
    lab = Lab(
        source_file=Path("labs/lab01.md"),
        title="CI Guardrails",
        date=dt.date(2026, 9, 4),
        link="/labs/lab01/",
        description="Practice CI mechanics.",
        release_date=dt.date(2026, 8, 31),
        due_at="2026-09-04T23:59:00-04:00",
        integrations={
            "canvas": {
                "assignment_group": "Labs",
                "submission_form": [{"label": "Final commit URL"}],
            }
        },
    )

    submission = canvas_lab_submission(lab)

    assert submission.name == "CI Guardrails"
    assert submission.points_possible == 1.0
    assert submission.submission_types == ["online_url"]
    assert submission.canvas_assignment_group == "Labs"
    assert submission.due_at == "2026-09-04T23:59:00-04:00"
    assert submission.unlock_at == "2026-08-31T00:00:00-04:00"
    assert submission.source_file == Path("labs/lab01.md")


def test_lab_sync_uses_assignment_pipeline(capsys) -> None:
    lab = Lab(
        source_file=Path("labs/lab01.md"),
        title="CI Guardrails",
        date=dt.date(2026, 9, 4),
        link="/labs/lab01/",
        release_date=dt.date(2026, 8, 31),
        due_at="2026-09-04T23:59:00-04:00",
        integrations={"canvas": {"assignment_group": "Labs"}},
    )
    events: list[CanvasSyncEvent] = []

    results = sync_labs_to_canvas(
        client=DryRunAssignmentClient(),  # type: ignore[arg-type]
        course_id="12345",
        specs=[lab],
        publish_override=False,
        reporter=events.append,
    )

    assert capsys.readouterr().out == ""
    assert results == [
        {
            "action": "create",
            "name": "CI Guardrails",
            "id": None,
            "html_url": None,
            "source_file": "labs/lab01.md",
        }
    ]
    assert [(event.target, event.name) for event in events] == [
        ("assignment_group", "Labs"),
        ("assignment", "CI Guardrails"),
    ]


def test_lab_rename_updates_assignment_by_canvas_id() -> None:
    lab = Lab(
        source_file=Path("labs/lab01.md"),
        title="Renamed CI Guardrails",
        date=dt.date(2026, 9, 4),
        link="/labs/lab01/",
        release_date=dt.date(2026, 8, 31),
        due_at="2026-09-04T23:59:00-04:00",
        integrations={
            "canvas": {"assignment_group": "Labs", "id": LAB_CANVAS_ID}
        },
    )
    client = ExistingAssignmentClient(
        [
            {
                "id": LAB_CANVAS_ID,
                "name": "Old CI Guardrails",
                "html_url": "https://canvas.example/assignments/456",
            }
        ]
    )

    results = sync_labs_to_canvas(
        client=client,  # type: ignore[arg-type]
        course_id="12345",
        specs=[lab],
        publish_override=False,
    )

    assert results == [
        {
            "action": "update",
            "name": "Renamed CI Guardrails",
            "id": LAB_CANVAS_ID,
            "html_url": "https://canvas.example/assignments/456",
            "source_file": "labs/lab01.md",
        }
    ]


def test_lab_sync_rejects_missing_configured_canvas_id() -> None:
    lab = Lab(
        source_file=Path("labs/lab01.md"),
        title="Renamed CI Guardrails",
        date=dt.date(2026, 9, 4),
        link="/labs/lab01/",
        release_date=dt.date(2026, 8, 31),
        due_at="2026-09-04T23:59:00-04:00",
        integrations={
            "canvas": {"assignment_group": "Labs", "id": LAB_CANVAS_ID}
        },
    )
    client = ExistingAssignmentClient(
        [{"id": 999, "name": "Renamed CI Guardrails"}]
    )

    with pytest.raises(
        CoursemdValidationError,
        match=r"Canvas assignment id 456.*Refusing to match by name or create",
    ):
        sync_labs_to_canvas(
            client=client,  # type: ignore[arg-type]
            course_id="12345",
            specs=[lab],
            publish_override=False,
        )


def test_lab_sync_writes_canvas_id_to_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "labs" / "lab01.md"
    path.parent.mkdir()
    path.write_text(
        """---
kind: lab
title: CI Guardrails
date: 2026-09-04
integrations:
  canvas:
    assignment_group: Labs
---

Lab instructions.
""",
        encoding="utf-8",
    )

    update_lab_frontmatter_with_ids(
        [
            {
                "action": "created",
                "name": "CI Guardrails",
                "id": LAB_CANVAS_ID,
                "source_file": str(path),
            }
        ]
    )

    lab = Lab.load(path)
    assert lab is not None
    assert lab.integrations["canvas"]["id"] == LAB_CANVAS_ID


def test_lab_loads_canonical_release_and_due_times(tmp_path: Path) -> None:
    path = tmp_path / "lab01.md"
    path.write_text(
        """---
kind: lab
title: CI Guardrails
date: 2026-09-04
release_date: 2026-08-31
due_at: 2026-09-04T23:59:00-04:00
---

Lab instructions.
""",
        encoding="utf-8",
    )

    lab = Lab.load(path)

    assert lab is not None
    assert lab.release_date == dt.date(2026, 8, 31)
    assert lab.due_at == "2026-09-04T23:59:00-04:00"
    assert lab.reveal_on == dt.date(2026, 8, 31)


def test_lab_canvas_submission_rejects_canvas_specific_timing() -> None:
    lab = Lab(
        source_file=Path("labs/lab01.md"),
        title="CI Guardrails",
        date=dt.date(2026, 9, 4),
        link="/labs/lab01/",
        release_date=dt.date(2026, 8, 31),
        due_at="2026-09-04T23:59:00-04:00",
        integrations={"canvas": {"due_at": "2026-09-05T23:59:00-04:00"}},
    )

    with pytest.raises(CoursemdValidationError, match="timing must use top-level"):
        canvas_lab_submission(lab)


def test_lab_canvas_submission_rejects_canvas_specific_name() -> None:
    lab = Lab(
        source_file=Path("labs/lab01.md"),
        title="CI Guardrails",
        date=dt.date(2026, 9, 4),
        link="/labs/lab01/",
        release_date=dt.date(2026, 8, 31),
        due_at="2026-09-04T23:59:00-04:00",
        integrations={"canvas": {"name": "A different name"}},
    )

    with pytest.raises(CoursemdValidationError, match="names must use top-level 'title'"):
        canvas_lab_submission(lab)


def test_lab_rejects_due_at_on_a_different_date(tmp_path: Path) -> None:
    path = tmp_path / "lab01.md"
    path.write_text(
        """---
kind: lab
title: CI Guardrails
date: 2026-09-04
release_date: 2026-08-31
due_at: 2026-09-05T23:59:00-04:00
---
""",
        encoding="utf-8",
    )

    with pytest.raises(CoursemdValidationError, match="calendar date of 'due_at'"):
        Lab.load(path)


def test_participation_events_include_only_lectures_and_never_accept_submissions() -> None:
    events = [
        CourseEvent(
            kind="lecture",
            date=dt.date(2026, 1, 12),
            title="Course Introduction",
            integrations={"canvas": {"participation_id": 456}},
        ),
        CourseEvent(
            kind="midterm",
            date=dt.date(2026, 1, 14),
            title="Midterm I",
        ),
    ]

    specs = canvas_participation_events(
        events,
        CanvasParticipationConfig(),
        source_file=Path(".coursemd.yml"),
    )

    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "Participation (January 12th, 2026): Course Introduction"
    assert spec.canvas_id == LAB_CANVAS_ID
    assert spec.canvas_assignment_group == "Participation"
    assert spec.points_possible == 1.0
    assert spec.submission_types == ["none"]
    assert spec.due_at is None
    form = form_for_participation_event(spec, assignment_group_id=10, publish_override=False)
    assert form["assignment[points_possible]"] == "1.0"
    assert form["assignment[grading_type]"] == "points"
    assert form["assignment[submission_types][]"] == ["none"]
    assert "assignment[due_at]" not in form
    assert form["assignment[description]"] == ""


def test_participation_sync_applies_group_weight_and_drop_policy() -> None:
    policy = CanvasParticipationConfig(
        assignment_group="Engagement",
        group_weight=10,
        drop_lowest=4,
    )
    specs = canvas_participation_events(
        [
            CourseEvent(
                kind="lecture",
                date=dt.date(2026, 1, 12),
                title="Course Introduction",
            )
        ],
        policy,
        source_file=Path(".coursemd.yml"),
    )
    client = ParticipationClient()
    events: list[CanvasSyncEvent] = []

    results = sync_participation_to_canvas(
        client=client,  # type: ignore[arg-type]
        course_id="12345",
        specs=specs,
        policy=policy,
        publish_override=True,
        reporter=events.append,
    )

    assert client.group_forms == [
        {"group_weight": 10, "rules": '{"drop_lowest": 4}'}
    ]
    assert client.assignment_forms[0]["assignment[submission_types][]"] == ["none"]
    assert client.assignment_forms[0]["assignment[published]"] == "true"
    assert results[0]["event_date"] == "2026-01-12"
    assert results[0]["event_title"] == "Course Introduction"
    assert [(event.action, event.target) for event in events] == [
        ("update", "assignment_group"),
        ("create", "assignment"),
    ]


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (8, "8th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (24, "24th"),
    ],
)
def test_participation_title_uses_long_date_with_ordinal(
    day: int,
    expected: str,
) -> None:
    [spec] = canvas_participation_events(
        [
            CourseEvent(
                kind="lecture",
                date=dt.date(2026, 8, day),
                title="Course Introduction",
            )
        ],
        CanvasParticipationConfig(),
        source_file=Path(".coursemd.yml"),
    )

    assert spec.name == f"Participation (August {expected}, 2026): Course Introduction"


def test_participation_sync_matches_legacy_title_without_creating_duplicate() -> None:
    policy = CanvasParticipationConfig(assignment_group="Labs")
    specs = canvas_participation_events(
        [
            CourseEvent(
                kind="lecture",
                date=dt.date(2026, 1, 12),
                title="Course Introduction",
            )
        ],
        policy,
        source_file=Path(".coursemd.yml"),
    )
    client = ExistingAssignmentClient(
        [
            {
                "id": PARTICIPATION_CANVAS_ID,
                "name": "Participation: 2026-01-12 — Course Introduction",
                "published": False,
            }
        ]
    )
    events: list[CanvasSyncEvent] = []

    results = sync_participation_to_canvas(
        client=client,  # type: ignore[arg-type]
        course_id="12345",
        specs=specs,
        policy=policy,
        publish_override=False,
        reporter=events.append,
    )

    assert results[0]["action"] == "update"
    assert [(event.action, event.target, event.id) for event in events] == [
        ("update", "assignment", PARTICIPATION_CANVAS_ID)
    ]


def test_assignment_grade_guard_treats_zero_as_an_existing_grade(monkeypatch) -> None:
    client = AssignmentCanvasClient(
        base_url="https://canvas.example",
        token="test-token",  # noqa: S106
    )

    submissions = [{"score": None, "grade": None, "excused": False}]

    def participation_submissions(
        path: str,
        params: dict[str, Any] | None = None,  # noqa: ARG001
    ) -> list[dict[str, Any]]:
        assert path.endswith("/assignments/789/submissions")
        return submissions

    monkeypatch.setattr(client, "get_paginated", participation_submissions)

    assert client.assignment_has_grades("12345", PARTICIPATION_CANVAS_ID) is False
    submissions[0] = {"score": 0, "grade": "0", "excused": False}
    assert client.assignment_has_grades("12345", PARTICIPATION_CANVAS_ID) is True


def test_participation_rerun_never_updates_an_assignment_with_grades() -> None:
    policy = CanvasParticipationConfig(
        assignment_group="Engagement",
        group_weight=5,
        drop_lowest=1,
    )
    specs = canvas_participation_events(
        [
            CourseEvent(
                kind="lecture",
                date=dt.date(2026, 1, 12),
                title="Course Introduction",
                integrations={
                    "canvas": {"participation_id": PARTICIPATION_CANVAS_ID}
                },
            )
        ],
        policy,
        source_file=Path(".coursemd.yml"),
    )
    client = GradedParticipationClient()
    events: list[CanvasSyncEvent] = []

    results = sync_participation_to_canvas(
        client=client,  # type: ignore[arg-type]
        course_id="12345",
        specs=specs,
        policy=policy,
        publish_override=True,
        reporter=events.append,
    )

    assert client.group_forms == []
    assert client.assignment_forms == []
    assert results[0]["action"] == "skipped"
    assert events == [
        CanvasSyncEvent(
            action="skip",
            target="assignment",
            name="Participation (January 12th, 2026): Course Introduction",
            id=PARTICIPATION_CANVAS_ID,
            reason="has existing submissions or grades",
        )
    ]


def test_participation_sync_writes_canvas_id_to_course_event(tmp_path: Path) -> None:
    config_path = tmp_path / ".coursemd.yml"
    config_path.write_text(
        """schedule:
  start_date: 2026-01-12
  end_date: 2026-01-16
  events:
  - kind: lecture
    date: 2026-01-12
    title: Course Introduction
integrations:
  canvas:
    base_url: https://canvas.example.edu
    course_id: '12345'
""",
        encoding="utf-8",
    )

    update_course_config_with_participation_ids(
        [
            {
                "id": PARTICIPATION_CANVAS_ID,
                "source_file": str(config_path),
                "event_date": "2026-01-12",
                "event_title": "Course Introduction",
            }
        ]
    )

    event = CourseEvent.from_dict(
        yaml.safe_load(config_path.read_text(encoding="utf-8"))["schedule"]["events"][0]
    )
    assert event.integrations["canvas"]["participation_id"] == PARTICIPATION_CANVAS_ID
