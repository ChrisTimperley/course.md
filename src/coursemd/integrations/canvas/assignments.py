"""Canvas assignment payload builders."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from coursemd.integrations.canvas.models import (
        CanvasAssignmentSubmission,
        CanvasParticipationEvent,
    )


def build_assignment_description_html(
    spec: CanvasAssignmentSubmission,
    site_base_url: str,
) -> str:
    doc_url = spec.doc_url or f"{site_base_url.rstrip('/')}{spec.link}"
    if spec.doc_anchor:
        doc_url = f"{doc_url.rstrip('#')}#{spec.doc_anchor}"

    html_parts = [
        (
            "<p><b>See assignment instructions on the course website:</b> "
            f'<a href="{escape(doc_url, quote=True)}">{escape(spec.name)}</a></p>'
        )
    ]
    if spec.notes:
        html_parts.append(f"<p>{escape(spec.notes)}</p>")

    if spec.submission_form:
        html_parts.append("<p>Please submit the following deliverables:</p><ul>")
        for field in spec.submission_form:
            label = escape(field.label)
            hint_html = f"<strong>:</strong> {escape(field.hint)}" if field.hint else ""
            html_parts.append(f"<li><strong>{label}</strong>{hint_html}</li>")
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def form_for_assignment(
    spec: CanvasAssignmentSubmission,
    assignment_group_id: int,
    publish_override: bool,
    group_category_id: int | None = None,
    site_base_url: str = "",
) -> dict[str, Any]:
    publish_value = True if publish_override else spec.published
    form: dict[str, Any] = {
        "assignment[name]": spec.name,
        "assignment[points_possible]": str(spec.points_possible),
        "assignment[published]": "true" if publish_value else "false",
        "assignment[assignment_group_id]": str(assignment_group_id),
        "assignment[description]": build_assignment_description_html(spec, site_base_url),
        "assignment[submission_types][]": spec.submission_types,
    }
    if spec.due_at is not None:
        form["assignment[due_at]"] = spec.due_at
        form["assignment[lock_at]"] = spec.close_at or spec.due_at
    if spec.position is not None:
        form["assignment[position]"] = str(spec.position)
    if spec.unlock_at is not None:
        form["assignment[unlock_at]"] = spec.unlock_at
    if spec.group_assignment and group_category_id is not None:
        form["assignment[group_category_id]"] = str(group_category_id)
    return form


def form_for_participation_event(
    spec: CanvasParticipationEvent,
    assignment_group_id: int,
    publish_override: bool,
) -> dict[str, Any]:
    """Build a no-submission, one-point assignment for staff-recorded participation."""

    publish_value = True if publish_override else spec.published
    form: dict[str, Any] = {
        "assignment[name]": spec.name,
        "assignment[points_possible]": "1.0",
        "assignment[grading_type]": "points",
        "assignment[published]": "true" if publish_value else "false",
        "assignment[assignment_group_id]": str(assignment_group_id),
        "assignment[description]": "",
        "assignment[submission_types][]": ["none"],
    }
    if spec.position is not None:
        form["assignment[position]"] = str(spec.position)
    return form
