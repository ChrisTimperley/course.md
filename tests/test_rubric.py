from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.models.assignment import Assignment
from coursemd.core.models.rubric import Rubric
from coursemd.integrations.canvas.models import canvas_assignment_submissions
from coursemd.integrations.canvas.rubrics import form_for_rubric
from coursemd.integrations.mkdocs.macros import define_env


def _pass_fail_metadata(*, section_points: int = 10) -> dict[str, Any]:
    return {
        "rubric": {
            "type": "pass-fail",
            "sections": [
                {
                    "slug": "setup",
                    "section": "Setup",
                    "points": section_points,
                    "criteria": [
                        {
                            "slug": "clean-start",
                            "points": 10,
                            "desc": "The project starts from a clean checkout.",
                        }
                    ],
                }
            ],
        }
    }


def test_pass_fail_rubric_parses_slugs_and_derives_ratings() -> None:
    rubric = Rubric.from_metadata(_pass_fail_metadata())

    section = rubric.sections[0]
    criterion = section.criteria[0]
    assert rubric.rubric_type == "pass-fail"
    assert section.slug == "setup"
    assert criterion.slug == "clean-start"
    assert criterion.name == "The project starts from a clean checkout."
    assert [(tier.label, tier.points) for tier in criterion.tiers] == [
        ("Pass", 10),
        ("Fail", 0),
    ]
    assert rubric.select_criteria("setup", ["clean-start"]) == [criterion]


def test_pass_fail_criterion_slug_survives_reordering() -> None:
    metadata = _pass_fail_metadata(section_points=15)
    criteria = metadata["rubric"]["sections"][0]["criteria"]
    criteria.append(
        {
            "slug": "verification",
            "points": 5,
            "desc": "The verification command reports failures.",
        }
    )

    original = Rubric.from_metadata(metadata)
    criteria.reverse()
    reordered = Rubric.from_metadata(metadata)

    assert original.select_criteria("setup", ["clean-start"])[0].desc == (
        reordered.select_criteria("setup", ["clean-start"])[0].desc
    )


def test_typed_rubric_allows_per_criterion_scoring_modes() -> None:
    metadata = _pass_fail_metadata(section_points=40)
    criteria = metadata["rubric"]["sections"][0]["criteria"]
    criteria.extend(
        [
            {
                "slug": "heldout-cases",
                "type": "range",
                "points": 20,
                "desc": "The implementation succeeds across held-out cases.",
            },
            {
                "slug": "design-quality",
                "type": "tiered",
                "points": 10,
                "desc": "The design is coherent and maintainable.",
                "tiers": [
                    {"points": 10, "label": "Strong", "desc": "Meets the specification."},
                    {"points": 5, "label": "Developing", "desc": "Has minor gaps."},
                    {"points": 0, "label": "Insufficient", "desc": "Has major gaps."},
                ],
            },
        ]
    )

    rubric = Rubric.from_metadata(metadata)
    pass_fail, point_range, tiered = rubric.sections[0].criteria

    assert rubric.typed is True
    assert pass_fail.criterion_type == "pass-fail"
    assert point_range.criterion_type == "range"
    assert [(tier.label, tier.points) for tier in point_range.tiers] == [
        ("Full credit", 20),
        ("Minimum credit", 0),
    ]
    assert tiered.criterion_type == "tiered"
    assert [tier.points for tier in tiered.tiers] == [10, 5, 0]


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        (_pass_fail_metadata(section_points=15), "criteria total 10"),
        (
            {
                "rubric": {
                    "type": "pass-fail",
                    "sections": [
                        {
                            "slug": "Setup",
                            "section": "Setup",
                            "points": 10,
                            "criteria": [],
                        }
                    ],
                }
            },
            "lowercase kebab-case slug",
        ),
        (
            {
                "rubric": {
                    "type": "pass-fail",
                    "sections": [
                        {
                            "slug": "setup",
                            "section": "Setup",
                            "points": 20,
                            "criteria": [
                                {
                                    "slug": "clean-start",
                                    "points": 10,
                                    "desc": "The project starts cleanly.",
                                },
                                {
                                    "slug": "clean-start",
                                    "points": 10,
                                    "desc": "The project still starts cleanly.",
                                },
                            ],
                        }
                    ],
                }
            },
            "Duplicate rubric criterion slug 'clean-start'",
        ),
    ],
)
def test_pass_fail_rubric_rejects_invalid_structure(metadata: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Rubric.from_metadata(metadata)


def test_canvas_submission_selects_rubric_by_slug_and_checks_points() -> None:
    rubric = Rubric.from_metadata(_pass_fail_metadata())
    assignment = Assignment(
        source_file=Path("assignments/hw1.md"),
        title="Homework 1",
        release_date=dt.date(2026, 1, 12),
        due_date=dt.date(2026, 1, 16),
        due_at="2026-01-16T23:59:00-05:00",
        link="/assignments/hw1/",
        rubric=rubric,
        integrations={
            "canvas": {
                "points": 10,
                "rubric_section": "setup",
            }
        },
    )

    submission = canvas_assignment_submissions(assignment)[0]

    assert [criterion.slug for criterion in submission.rubric_criteria] == ["clean-start"]

    assignment.integrations["canvas"]["points"] = 9
    with pytest.raises(CoursemdValidationError, match="criteria total 10"):
        canvas_assignment_submissions(assignment)


def test_canvas_form_contains_derived_pass_fail_ratings() -> None:
    rubric = Rubric.from_metadata(_pass_fail_metadata())
    criterion = rubric.sections[0].criteria[0]

    form = form_for_rubric(
        assignment_id=42,
        criteria=[criterion],
        title="Homework 1",
    )

    assert form["rubric[criteria][0][description]"] == criterion.desc
    assert form["rubric[criteria][0][long_description]"] == ""
    assert form["rubric[criteria][0][ratings][0][description]"] == "Pass"
    assert form["rubric[criteria][0][ratings][0][points]"] == "10"
    assert form["rubric[criteria][0][ratings][1][description]"] == "Fail"
    assert form["rubric[criteria][0][ratings][1][points]"] == "0"
    assert form["rubric[criteria][0][criterion_use_range]"] == "false"


def test_canvas_form_enables_range_scoring() -> None:
    metadata = _pass_fail_metadata(section_points=20)
    criterion = metadata["rubric"]["sections"][0]["criteria"][0]
    criterion.update(
        {
            "slug": "heldout-cases",
            "type": "range",
            "points": 20,
            "desc": "The implementation succeeds across held-out cases.",
        }
    )
    parsed = Rubric.from_metadata(metadata).sections[0].criteria[0]

    form = form_for_rubric(assignment_id=42, criteria=[parsed], title="Homework 1")

    assert form["rubric[criteria][0][criterion_use_range]"] == "true"
    assert form["rubric[criteria][0][ratings][0][points]"] == "20"
    assert form["rubric[criteria][0][ratings][1][points]"] == "0"


class _MacroEnvironment:
    def __init__(self) -> None:
        self.macros: dict[str, Callable[..., str]] = {}
        self.variables: dict[str, Any] = {}
        self.conf: dict[str, Any] = {}

    def macro(self, function: Callable[..., str]) -> Callable[..., str]:
        self.macros[function.__name__] = function
        return function


def test_pass_fail_rubric_renders_as_compact_slugged_checklist() -> None:
    env = _MacroEnvironment()
    define_env(env)

    rendered = env.macros["rubric_table"](_pass_fail_metadata()["rubric"])

    assert "The assignment is worth <strong>10 points</strong>." in rendered
    assert 'data-rubric-section="setup"' in rendered
    assert 'data-rubric-item="setup.clean-start"' in rendered
    assert 'type="checkbox"' in rendered
    assert 'for="rubric-check-setup-clean-start"' in rendered
    assert "The project starts from a clean checkout." in rendered
    assert "10 pts" in rendered
    assert "<details" not in rendered


def test_mixed_typed_rubric_renders_range_and_tiered_items() -> None:
    env = _MacroEnvironment()
    define_env(env)
    metadata = _pass_fail_metadata(section_points=30)
    criteria = metadata["rubric"]["sections"][0]["criteria"]
    criteria.append(
        {
            "slug": "heldout-cases",
            "type": "range",
            "points": 10,
            "desc": "The implementation succeeds across held-out cases.",
        }
    )
    criteria.append(
        {
            "slug": "design-quality",
            "type": "tiered",
            "points": 10,
            "desc": "The design is coherent and maintainable.",
            "tiers": [
                {"points": 10, "label": "Strong", "desc": "Meets the specification."},
                {"points": 0, "label": "Insufficient", "desc": "Has major gaps."},
            ],
        }
    )

    rendered = env.macros["rubric_table"](metadata["rubric"])

    assert 'data-rubric-type="range"' in rendered
    assert "0&ndash;10 pts" in rendered
    assert 'data-rubric-type="tiered"' in rendered
    assert "Scoring levels" in rendered
    assert "Strong" in rendered


def test_legacy_tiered_rubric_keeps_expandable_rendering() -> None:
    env = _MacroEnvironment()
    define_env(env)
    rubric = [
        {
            "section": "Implementation",
            "points": 10,
            "criteria": [
                {
                    "name": "Correctness",
                    "points": 10,
                    "desc": "The implementation behaves correctly.",
                    "tiers": [
                        {"points": 10, "label": "Complete", "desc": "All cases pass."},
                        {"points": 0, "label": "Missing", "desc": "Cases fail."},
                    ],
                }
            ],
        }
    ]

    rendered = env.macros["rubric_table"](rubric)

    assert "The assignment is worth <strong>10 points</strong>." in rendered
    assert '<details class="rubric-criterion">' in rendered
    assert "Complete" in rendered
    assert "rubric-checklist" not in rendered
