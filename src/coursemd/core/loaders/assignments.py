"""Assignment frontmatter loaders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coursemd.core.loaders.dates import normalize_due_at, require_date, require_release_date
from coursemd.core.loaders.markdown import load_markdown_metadata
from coursemd.core.models.assignment import AssignmentSpec
from coursemd.core.rubric import select_rubric_criteria

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.types import AssignmentDict, CheckpointDict

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
        raise TypeError(
            f"{source_file}: '{assignment_name}' submission_form must be a list of objects."
        )

    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise TypeError(
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


def _optional_mapping(value: Any, source_file: Path, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{source_file}: '{field_name}' must be an object/map.")
    return value


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
                raise TypeError(f"{source_file}: checkpoints[{index}] must be an object.")
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


def parse_assignment_specs_from_file(source_file: Path) -> list[AssignmentSpec]:
    metadata = load_markdown_metadata(source_file)
    validate_schedule_assignment_metadata(source_file, metadata)

    assignments = metadata.get("assignments")
    if assignments is None or assignments == []:
        return []
    if not isinstance(assignments, list):
        raise TypeError(f"{source_file}: 'assignments' must be a list.")

    specs: list[AssignmentSpec] = []
    seen_names: set[str] = set()

    for item in assignments:
        if not isinstance(item, dict):
            raise TypeError(f"{source_file}: each item in assignments must be an object/map.")

        name = _require_non_empty_string(item.get("name"), source_file, "assignments[].name")
        if name in seen_names:
            raise ValueError(f"{source_file}: duplicate assignment name '{name}'.")
        seen_names.add(name)

        due_at = normalize_due_at(item.get("due_at"), source_file, name)

        integrations_raw = item.get("integrations")
        integrations: dict[str, Any] = {}
        if integrations_raw is not None:
            if not isinstance(integrations_raw, dict):
                raise TypeError(
                    f"{source_file}: '{name}.integrations' must be an object/map."
                )
            integrations = integrations_raw

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

        submission_form = _parse_submission_form(item.get("submission_form"), source_file, name)

        rubric_section: str | None = item.get("rubric_section") or None
        rubric_criteria_filter_raw = item.get("rubric_criteria")
        rubric_criteria_filter: list[str] | None = (
            rubric_criteria_filter_raw if isinstance(rubric_criteria_filter_raw, list) else None
        )
        rubric_criteria = select_rubric_criteria(metadata, rubric_section, rubric_criteria_filter)

        doc_url_raw = item.get("doc_url")
        doc_url = str(doc_url_raw).strip() if doc_url_raw is not None else None
        doc_anchor_raw = item.get("doc_anchor")
        doc_anchor = str(doc_anchor_raw).strip() or None if doc_anchor_raw is not None else None
        notes_raw = item.get("notes")
        notes = str(notes_raw).strip() or None if notes_raw is not None else None

        specs.append(
            AssignmentSpec(
                source_file=source_file,
                name=name,
                due_at=due_at,
                submission_types=submission_types,
                points_possible=points_possible,
                published=published,
                position=position,
                unlock_at=unlock_at,
                group_assignment=group_assignment,
                submission_form=submission_form,
                rubric_criteria=rubric_criteria,
                doc_url=doc_url,
                doc_anchor=doc_anchor,
                notes=notes,
                integrations=integrations,
            )
        )
    return specs


def default_assignment_files(repo_root: Path) -> list[Path]:
    docs_dir = repo_root / "website" / "docs" / "assignments"
    return sorted(path for path in docs_dir.glob("*.md") if path.name != "index.md")


def load_assignment_specs(files: list[Path]) -> list[AssignmentSpec]:
    specs: list[AssignmentSpec] = []
    for path in files:
        specs.extend(parse_assignment_specs_from_file(path))
    return specs
