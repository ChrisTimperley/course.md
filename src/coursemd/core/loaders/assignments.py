"""Assignment frontmatter validation for schedule-facing metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coursemd.core.exceptions import wrap_validation_errors
from coursemd.core.loaders.dates import require_date

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.types import AssignmentDict, CheckpointDict

DEFAULT_ASSIGNMENTS_URL_PATH = "assignments"


def _require_non_empty_string(value: Any, source_file: Path, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{source_file}: '{field_name}' must be a non-empty string.")
    return text


@wrap_validation_errors
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
