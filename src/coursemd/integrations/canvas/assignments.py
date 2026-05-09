"""Canvas assignment payload builders."""

from __future__ import annotations

from typing import Any

from coursemd.core.models.assignment import AssignmentSpec


def form_for_assignment(
    spec: AssignmentSpec,
    assignment_group_id: int,
    publish_override: bool,
    group_category_id: int | None = None,
) -> dict[str, Any]:
    publish_value = True if publish_override else spec.published
    form: dict[str, Any] = {
        "assignment[name]": spec.name,
        "assignment[due_at]": spec.due_at,
        "assignment[lock_at]": spec.due_at,
        "assignment[points_possible]": str(spec.points_possible),
        "assignment[published]": "true" if publish_value else "false",
        "assignment[assignment_group_id]": str(assignment_group_id),
        "assignment[description]": spec.description_html,
        "assignment[submission_types][]": spec.submission_types,
    }
    if spec.position is not None:
        form["assignment[position]"] = str(spec.position)
    if spec.unlock_at is not None:
        form["assignment[unlock_at]"] = spec.unlock_at
    if spec.group_assignment and group_category_id is not None:
        form["assignment[group_category_id]"] = str(group_category_id)
    return form
