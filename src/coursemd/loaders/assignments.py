"""Assignment frontmatter loaders."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from coursemd.loaders.dates import normalize_due_at, require_date, require_release_date
from coursemd.loaders.markdown import load_markdown_metadata
from coursemd.models.assignment import AssignmentSpec
from coursemd.models.integrations import AssignmentIntegrations, CanvasAssignmentIntegration
from coursemd.rubric import select_rubric_criteria
from coursemd.types import AssignmentDict, CheckpointDict

DEFAULT_ASSIGNMENTS_URL_PATH = "assignments"


def _require_non_empty_string(value: Any, source_file: Path, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{source_file}: '{field_name}' must be a non-empty string.")
    return text


def _parse_submission_form(
    value: Any,
    source_file: Path,
    assignment_name: str,
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(
            f"{source_file}: '{assignment_name}' submission_form must be a list of objects."
        )

    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(
                f"{source_file}: '{assignment_name}' submission_form[{index}] must be an object."
            )
        label = _require_non_empty_string(
            item.get("label"),
            source_file,
            f"{assignment_name} submission_form[{index}].label",
        )
        entry = dict(item)
        entry["label"] = label
        hint = item.get("hint")
        if hint is not None:
            entry["hint"] = str(hint).strip()
        parsed.append(entry)
    return parsed


def validate_schedule_assignment_metadata(
    source_file: Path,
    metadata: dict[str, Any],
    *,
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
) -> AssignmentDict:
    """Validate and normalize assignment metadata used in the rendered schedule."""

    title = _require_non_empty_string(metadata.get("title"), source_file, "title")
    release_date = require_date(metadata.get("release_date"), source_file, "release_date")
    due_date = require_date(metadata.get("due_date"), source_file, "due_date")
    if due_date < release_date:
        raise ValueError(f"{source_file}: 'due_date' must not be earlier than 'release_date'.")

    assignment: AssignmentDict = {
        "title": title,
        "release_date": release_date,
        "due_date": due_date,
        "link": f"/{assignment_url_path.strip('/')}/{source_file.stem}/",
    }

    reveal_date_raw = metadata.get("reveal_date")
    if reveal_date_raw is not None:
        reveal_date = require_date(reveal_date_raw, source_file, "reveal_date")
        if reveal_date > due_date:
            raise ValueError(f"{source_file}: 'reveal_date' must not be later than 'due_date'.")
        assignment["reveal_date"] = reveal_date

    checkpoints_raw = metadata.get("checkpoints")
    if checkpoints_raw is not None:
        if not isinstance(checkpoints_raw, list):
            raise ValueError(f"{source_file}: 'checkpoints' must be a list.")

        checkpoints: list[CheckpointDict] = []
        previous_date = None
        for index, checkpoint_raw in enumerate(checkpoints_raw):
            if not isinstance(checkpoint_raw, dict):
                raise ValueError(f"{source_file}: checkpoints[{index}] must be an object.")
            checkpoint_date = require_date(
                checkpoint_raw.get("date"),
                source_file,
                f"checkpoints[{index}].date",
            )
            checkpoint_title = _require_non_empty_string(
                checkpoint_raw.get("title"),
                source_file,
                f"checkpoints[{index}].title",
            )
            if checkpoint_date < release_date or checkpoint_date > due_date:
                raise ValueError(
                    f"{source_file}: checkpoints[{index}].date must fall between "
                    f"'release_date' and 'due_date'."
                )
            if previous_date is not None and checkpoint_date < previous_date:
                raise ValueError(f"{source_file}: checkpoints must be ordered by ascending date.")
            checkpoint: CheckpointDict = {
                "date": checkpoint_date,
                "title": checkpoint_title,
            }
            description = checkpoint_raw.get("description")
            if description is not None:
                description_text = str(description).strip()
                if description_text:
                    checkpoint["description"] = description_text
            checkpoints.append(checkpoint)
            previous_date = checkpoint_date

        if checkpoints:
            assignment["checkpoints"] = checkpoints

    return assignment


def default_docs_url(
    source_file: Path,
    site_base_url: str,
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
) -> str:
    stem = source_file.stem
    return f"{site_base_url.rstrip('/')}/{assignment_url_path.strip('/')}/{stem}/"


def build_assignment_description_html(
    source_file: Path,
    assignment_name: str,
    assignment_cfg: dict[str, Any],
    site_base_url: str,
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
    submission_form: list[dict[str, Any]] | None = None,
) -> str:
    if "description_html" in assignment_cfg:
        return str(assignment_cfg["description_html"])

    doc_url = str(
        assignment_cfg.get("doc_url")
        or default_docs_url(
            source_file,
            site_base_url,
            assignment_url_path=assignment_url_path,
        )
    )
    doc_anchor = assignment_cfg.get("doc_anchor")
    if doc_anchor:
        doc_url = f"{doc_url.rstrip('#')}#{doc_anchor}"

    notes = assignment_cfg.get("notes")
    html_parts = [
        (
            "<p><b>See assignment instructions on the course website:</b> "
            f'<a href="{escape(doc_url, quote=True)}">{escape(assignment_name)}</a></p>'
        )
    ]
    if notes:
        html_parts.append(f"<p>{escape(str(notes))}</p>")

    if submission_form:
        html_parts.append("<p>Please submit the following deliverables:</p><ul>")
        for field in submission_form:
            label = escape(str(field.get("label", "")))
            hint = field.get("hint", "")
            hint_html = f"<strong>:</strong> {escape(str(hint))}" if hint else ""
            html_parts.append(f"<li><strong>{label}</strong>{hint_html}</li>")
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def parse_assignment_specs_from_file(
    source_file: Path,
    site_base_url: str,
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
    *,
    require_canvas_fields: bool = True,
) -> list[AssignmentSpec]:
    metadata = load_markdown_metadata(source_file)
    schedule_metadata = validate_schedule_assignment_metadata(
        source_file,
        metadata,
        assignment_url_path=assignment_url_path,
    )

    assignments = metadata.get("canvas_assignments")
    if assignments is None:
        if not require_canvas_fields:
            return []
        raise ValueError(f"{source_file}: missing 'canvas_assignments' frontmatter list.")
    if not isinstance(assignments, list):
        raise ValueError(f"{source_file}: 'canvas_assignments' must be a list.")
    if not assignments:
        if not require_canvas_fields:
            return []
        raise ValueError(f"{source_file}: 'canvas_assignments' must contain at least one item.")

    phase_title = schedule_metadata["title"]
    specs: list[AssignmentSpec] = []
    seen_names: set[str] = set()

    for item in assignments:
        if not isinstance(item, dict):
            raise ValueError(
                f"{source_file}: each item in canvas_assignments must be an object/map."
            )

        name = _require_non_empty_string(item.get("name"), source_file, "canvas_assignments[].name")
        if name in seen_names:
            raise ValueError(f"{source_file}: duplicate canvas assignment name '{name}'.")
        seen_names.add(name)

        due_at = normalize_due_at(item.get("due_at"), source_file, name)
        group_name = str(item.get("assignment_group") or phase_title).strip()
        if not group_name:
            raise ValueError(
                f"{source_file}: '{name}' assignment_group must be a non-empty string."
            )

        submission_types_raw = item.get("submission_types", ["none"])
        if isinstance(submission_types_raw, str):
            submission_types = [submission_types_raw.strip()]
        elif isinstance(submission_types_raw, list) and all(
            isinstance(v, str) for v in submission_types_raw
        ):
            submission_types = [value.strip() for value in submission_types_raw]
        else:
            raise ValueError(
                f"{source_file}: '{name}' submission_types must be a string or list of strings."
            )
        if not submission_types or any(not submission_type for submission_type in submission_types):
            raise ValueError(f"{source_file}: '{name}' must include at least one submission type.")

        points_raw = item.get("points", item.get("points_possible", 100))
        try:
            points_possible = float(100 if points_raw is None else points_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source_file}: '{name}' points must be numeric.") from exc
        published = bool(item.get("published", False))
        position = item.get("position")
        if position is not None:
            try:
                position = int(position)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{source_file}: '{name}' position must be an integer.") from exc

        unlock_at = require_release_date(metadata.get("release_date"), source_file, "release_date")
        group_assignment = bool(
            item.get("group_assignment", metadata.get("group_assignment", False))
        )
        canvas_id = item.get("canvas_id")
        if canvas_id is not None:
            try:
                canvas_id = int(canvas_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{source_file}: '{name}' canvas_id must be an integer.") from exc

        submission_form = _parse_submission_form(item.get("submission_form"), source_file, name)

        rubric_section: str | None = item.get("rubric_section") or None
        rubric_criteria_filter_raw = item.get("rubric_criteria")
        rubric_criteria_filter: list[str] | None = (
            rubric_criteria_filter_raw if isinstance(rubric_criteria_filter_raw, list) else None
        )
        rubric_criteria = select_rubric_criteria(metadata, rubric_section, rubric_criteria_filter)

        specs.append(
            AssignmentSpec(
                source_file=source_file,
                name=name,
                due_at=due_at,
                assignment_group=group_name,
                submission_types=submission_types,
                points_possible=points_possible,
                published=published,
                description_html=build_assignment_description_html(
                    source_file=source_file,
                    assignment_name=name,
                    assignment_cfg=item,
                    site_base_url=site_base_url,
                    assignment_url_path=assignment_url_path,
                    submission_form=submission_form,
                ),
                position=position,
                unlock_at=unlock_at,
                group_assignment=group_assignment,
                submission_form=submission_form,
                rubric_criteria=rubric_criteria,
                integrations=AssignmentIntegrations(
                    canvas=CanvasAssignmentIntegration(
                        assignment_id=canvas_id,
                        assignment_group=group_name,
                    )
                ),
            )
        )
    return specs


def default_assignment_files(repo_root: Path) -> list[Path]:
    docs_dir = repo_root / "website" / "docs" / "assignments"
    return sorted(path for path in docs_dir.glob("*.md") if path.name != "index.md")


def load_assignment_specs(
    files: list[Path],
    site_base_url: str,
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
    *,
    require_canvas_fields: bool = True,
) -> list[AssignmentSpec]:
    specs: list[AssignmentSpec] = []
    for path in files:
        specs.extend(
            parse_assignment_specs_from_file(
                path,
                site_base_url,
                assignment_url_path=assignment_url_path,
                require_canvas_fields=require_canvas_fields,
            )
        )
    return specs
