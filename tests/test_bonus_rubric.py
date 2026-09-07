from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any
from unittest.mock import Mock, call

import pytest

from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.models.assignment import Assignment
from coursemd.core.models.rubric import Rubric
from coursemd.integrations.canvas.models import canvas_assignment_submissions
from coursemd.integrations.canvas.resources import AssignmentCanvasClient
from coursemd.integrations.canvas.rubrics import form_for_rubric
from coursemd.integrations.canvas.sync import sync_assignments_to_canvas
from coursemd.integrations.mkdocs.macros import define_env

BASE_POINTS = 130
BONUS_POINTS = 20


@pytest.fixture
def metadata() -> dict[str, Any]:
    return {
        "rubric": {
            "type": "pass-fail",
            "sections": [
                {
                    "slug": "final",
                    "section": "Final checkpoint",
                    "points": BASE_POINTS,
                    "criteria": [
                        {"slug": "required", "points": BASE_POINTS, "desc": "Required work."},
                        {
                            "slug": "speed",
                            "name": "Fast CI",
                            "desc": "Complete CI is fast.",
                            "bonus": True,
                            "type": "tiered",
                            "points": 10,
                            "tiers": [
                                {"points": 10, "label": "Two minutes"},
                                {"points": 5, "label": "Three minutes"},
                                {"points": 0, "label": "No bonus"},
                            ],
                        },
                        {
                            "slug": "protection",
                            "desc": "Additional mistakes are caught.",
                            "bonus": True,
                            "type": "range",
                            "points": 10,
                        },
                    ],
                }
            ],
        }
    }


@pytest.fixture
def assignment(metadata: dict[str, Any]) -> Assignment:
    return Assignment(
        source_file=Path("assignments/bonus.md"),
        title="Bonus example",
        release_date=dt.date(2026, 9, 7),
        due_date=dt.date(2026, 9, 20),
        due_at="2026-09-20T23:59:00-04:00",
        link="/assignments/bonus/",
        rubric=Rubric.from_metadata(metadata),
        integrations={
            "canvas": {
                "points": BASE_POINTS,
                "rubric_section": "final",
                "assignment_group": "Homework",
            }
        },
    )


def test_bonus_points_are_separate_from_base_totals(metadata: dict[str, Any]) -> None:
    rubric = Rubric.from_metadata(metadata)
    section = rubric.sections[0]
    required, speed, protection = section.criteria

    assert required.bonus is False
    assert section.points == rubric.points == BASE_POINTS
    assert section.bonus_points == rubric.bonus_points == BONUS_POINTS
    assert sum(criterion.points for criterion in section.criteria) == BASE_POINTS + BONUS_POINTS
    assert [tier.points for tier in speed.tiers] == [10, 5, 0]
    assert protection.criterion_type == "range"
    flattened = rubric.flatten_criteria(prepend_section_name=True)
    assert [criterion.bonus for criterion in flattened] == [
        False,
        True,
        True,
    ]
    assert rubric.select_criteria("final", ["speed"]) == [speed]


@pytest.mark.parametrize("bonus", ["true", "false", 1, None])
def test_bonus_flag_requires_a_boolean(metadata: dict[str, Any], bonus: Any) -> None:
    metadata["rubric"]["sections"][0]["criteria"][1]["bonus"] = bonus
    with pytest.raises(TypeError, match=r"bonus.*must be a boolean"):
        Rubric.from_metadata(metadata)


def test_bonus_cannot_hide_an_incorrect_base_total(metadata: dict[str, Any]) -> None:
    metadata["rubric"]["sections"][0]["points"] = BASE_POINTS + BONUS_POINTS
    with pytest.raises(ValueError, match="base criteria total 130"):
        Rubric.from_metadata(metadata)


def test_canvas_validates_base_total_but_exports_all_criteria(assignment: Assignment) -> None:
    [submission] = canvas_assignment_submissions(assignment)
    assert submission.points_possible == BASE_POINTS
    form = form_for_rubric(assignment_id=42, criteria=submission.rubric_criteria, title="Final")
    assert form["skip_updating_points_possible"] == "true"
    assert form["rubric[skip_updating_points_possible]"] == "true"
    assert form["rubric[criteria][0][points]"] == str(BASE_POINTS)
    assert form["rubric[criteria][0][description]"] == "Required work."
    assert form["rubric[criteria][1][description]"] == "Bonus: Fast CI"
    assert form["rubric[criteria][1][long_description]"] == "Complete CI is fast."
    assert [form[f"rubric[criteria][1][ratings][{i}][points]"] for i in range(3)] == [
        "10",
        "5",
        "0",
    ]
    assert form["rubric[criteria][2][description]"] == "Bonus: Additional mistakes are caught."
    assert form["rubric[criteria][2][points]"] == "10"
    assert form["rubric[criteria][2][criterion_use_range]"] == "true"

    assignment.integrations["canvas"]["points"] = BASE_POINTS + BONUS_POINTS
    with pytest.raises(CoursemdValidationError, match="base criteria total 130"):
        canvas_assignment_submissions(assignment)


@pytest.mark.parametrize("legacy", [False, True])
def test_bonus_rendering_preserves_base_totals(metadata: dict[str, Any], legacy: bool) -> None:
    env = Mock()
    macros: dict[str, Any] = {}
    env.macro.side_effect = lambda function: macros.setdefault(function.__name__, function)
    define_env(env)
    raw = metadata["rubric"]
    if legacy:
        raw = raw["sections"]
        for criterion in raw[0]["criteria"]:
            criterion.setdefault("name", criterion["desc"])
            for tier in criterion.get("tiers", []):
                tier.setdefault("desc", "")
    rubric = Rubric.from_metadata({"rubric": raw})
    assert rubric.bonus_points == BONUS_POINTS
    rendered = macros["rubric_table"](raw)
    assert "The assignment is worth <strong>130 points</strong>" in rendered
    assert rendered.count("(+ 20 bonus pts)</span>") == 1 + len(rubric.sections)
    bonus_count = sum(criterion.bonus for criterion in rubric.flatten_criteria())
    assert rendered.count('class="rubric__bonus">Bonus:</span>') == bonus_count
    assert "150 pts" not in rendered
    assert "150 points" not in rendered
    if legacy:
        assert rendered.count('class="rubric-criterion rubric-criterion--bonus"') == bonus_count
    else:
        assert "rubric-checklist__item--tiered rubric-checklist__item--bonus" in rendered
        assert "rubric-checklist__item--range rubric-checklist__item--bonus" in rendered
        assert 'data-rubric-item="final.speed"' in rendered
        assert "Three minutes" in rendered


@pytest.fixture
def client() -> Mock:
    client = Mock(spec=AssignmentCanvasClient)
    client.dry_run = False
    client.get_paginated.side_effect = lambda path, **_kwargs: (
        [{"id": 10, "name": "Homework"}] if path.endswith("/assignment_groups") else []
    )
    client.create_assignment.return_value = {"id": 42, "name": "Bonus example"}
    client.update_assignment.return_value = {"id": 42, "name": "Bonus example"}
    client.get.return_value = {"points_possible": BASE_POINTS}
    client.is_assignment_released.return_value = False
    client.assignment_has_grades.return_value = False
    return client


def test_bonus_sync_creation_and_resync_verify_denominator(
    assignment: Assignment,
    client: Mock,
) -> None:
    expected_actions = ("create", "update")
    for expected_action in expected_actions:
        [result] = sync_assignments_to_canvas(client, "123", [assignment], False)
        assert result["action"] == expected_action
        client.get.assert_called_with("/courses/123/assignments/42")
        form = client.create_rubric.call_args.kwargs["form"]
        assert form["skip_updating_points_possible"] == "true"
        assert form["rubric[criteria][2][points]"] == "10"
        client.get_paginated.side_effect = lambda path, **_kwargs: (
            [{"id": 10, "name": "Homework"}]
            if path.endswith("/assignment_groups")
            else [{"id": 42, "name": "Bonus example"}]
        )
    assert client.create_assignment.call_count == 1
    assert client.update_assignment.call_count == 1
    assert client.create_rubric.call_count == client.get.call_count == len(expected_actions)
    for method in (client.create_assignment, client.update_assignment):
        assert method.call_args.kwargs["form"]["assignment[points_possible]"] == "130.0"


@pytest.mark.parametrize("restore_succeeds", [True, False])
def test_bonus_sync_restores_points_if_canvas_ignores_skip_flag(
    assignment: Assignment,
    client: Mock,
    restore_succeeds: bool,
) -> None:
    client.get.side_effect = [
        {"points_possible": BASE_POINTS + BONUS_POINTS},
        {"points_possible": BASE_POINTS if restore_succeeds else BASE_POINTS + BONUS_POINTS},
    ]
    if restore_succeeds:
        sync_assignments_to_canvas(client, "123", [assignment], False)
    else:
        with pytest.raises(RuntimeError, match="Restoring base points failed"):
            sync_assignments_to_canvas(client, "123", [assignment], False)
    client.update_assignment.assert_called_once_with(
        "123",
        assignment_id=42,
        form={"assignment[points_possible]": "130.0"},
    )
    assert client.get.call_args_list == [
        call("/courses/123/assignments/42"),
        call("/courses/123/assignments/42"),
    ]


@pytest.mark.parametrize("mode", ["dry-run", "released", "graded"])
def test_bonus_sync_preserves_existing_sync_guards(
    assignment: Assignment,
    client: Mock,
    mode: str,
) -> None:
    client.get_paginated.side_effect = lambda path, **_kwargs: (
        [{"id": 10, "name": "Homework"}]
        if path.endswith("/assignment_groups")
        else [{"id": 42, "name": "Bonus example"}]
    )
    client.dry_run = mode == "dry-run"
    client.is_assignment_released.return_value = mode == "released"
    client.assignment_has_grades.return_value = mode == "graded"
    sync_assignments_to_canvas(client, "123", [assignment], False)
    client.create_rubric.assert_not_called()
    client.update_assignment.assert_not_called()
    client.get.assert_not_called()
