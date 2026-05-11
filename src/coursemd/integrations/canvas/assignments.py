"""Canvas assignment payload builders."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Any

from coursemd.core.loaders.assignments import DEFAULT_ASSIGNMENTS_URL_PATH

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.models.assignment import AssignmentSpec


def _default_docs_url(
    source_file: Path,
    site_base_url: str,
    assignment_url_path: str,
) -> str:
    return f"{site_base_url.rstrip('/')}/{assignment_url_path.strip('/')}/{source_file.stem}/"


def build_assignment_description_html(
    spec: AssignmentSpec,
    site_base_url: str,
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
) -> str:
    doc_url = spec.doc_url or _default_docs_url(
        spec.source_file, site_base_url, assignment_url_path
    )
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
            label = escape(str(field.get("label", "")))
            hint = field.get("hint", "")
            hint_html = f"<strong>:</strong> {escape(str(hint))}" if hint else ""
            html_parts.append(f"<li><strong>{label}</strong>{hint_html}</li>")
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def form_for_assignment(
    spec: AssignmentSpec,
    assignment_group_id: int,
    publish_override: bool,
    group_category_id: int | None = None,
    site_base_url: str = "",
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
) -> dict[str, Any]:
    publish_value = True if publish_override else spec.published
    form: dict[str, Any] = {
        "assignment[name]": spec.name,
        "assignment[due_at]": spec.due_at,
        "assignment[lock_at]": spec.due_at,
        "assignment[points_possible]": str(spec.points_possible),
        "assignment[published]": "true" if publish_value else "false",
        "assignment[assignment_group_id]": str(assignment_group_id),
        "assignment[description]": build_assignment_description_html(
            spec, site_base_url, assignment_url_path
        ),
        "assignment[submission_types][]": spec.submission_types,
    }
    if spec.position is not None:
        form["assignment[position]"] = str(spec.position)
    if spec.unlock_at is not None:
        form["assignment[unlock_at]"] = spec.unlock_at
    if spec.group_assignment and group_category_id is not None:
        form["assignment[group_category_id]"] = str(group_category_id)
    return form
