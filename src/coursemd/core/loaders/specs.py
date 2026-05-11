"""Assignment collection loaders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from coursemd.core.loaders.assignments import DEFAULT_ASSIGNMENTS_URL_PATH
from coursemd.core.models.assignment import Assignment

if TYPE_CHECKING:
    from pathlib import Path


def load_assignments(
    files: list[Path],
    *,
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
) -> list[Assignment]:
    return sorted(
        [
            Assignment.load(path).with_assignment_url_path(assignment_url_path)
            for path in files
        ],
        key=lambda assignment: assignment.release_date,
    )
