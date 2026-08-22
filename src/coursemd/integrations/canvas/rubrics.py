"""Canvas rubric payload builders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from coursemd.core.models.rubric import RubricCriterion


def form_for_rubric(
    *,
    assignment_id: int,
    criteria: Sequence[RubricCriterion],
    title: str,
) -> dict[str, Any]:
    form: dict[str, Any] = {
        "rubric[title]": title,
        "rubric_association[association_type]": "Assignment",
        "rubric_association[association_id]": str(assignment_id),
        "rubric_association[use_for_grading]": "true",
        "rubric_association[purpose]": "grading",
    }
    for ci, criterion in enumerate(criteria):
        criterion_prefix = f"rubric[criteria][{ci}]"
        form[f"{criterion_prefix}[description]"] = criterion.name
        form[f"{criterion_prefix}[long_description]"] = (
            criterion.desc if criterion.desc != criterion.name else ""
        )
        form[f"{criterion_prefix}[points]"] = str(criterion.points)
        form[f"{criterion_prefix}[criterion_use_range]"] = str(
            criterion.criterion_type == "range"
        ).lower()
        for ri, tier in enumerate(criterion.tiers):
            rating_prefix = f"{criterion_prefix}[ratings][{ri}]"
            form[f"{rating_prefix}[description]"] = tier.label
            form[f"{rating_prefix}[long_description]"] = tier.desc
            form[f"{rating_prefix}[points]"] = str(tier.points)
    return form
