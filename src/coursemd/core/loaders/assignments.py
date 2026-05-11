"""Assignment loading helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_ASSIGNMENTS_URL_PATH = "assignments"


def assignment_link_for(
    source_file: Path,
    *,
    assignment_url_path: str = DEFAULT_ASSIGNMENTS_URL_PATH,
) -> str:
    """Build the published site path for an assignment page."""

    return f"/{assignment_url_path.strip('/')}/{source_file.stem}/"
