"""Quiz frontmatter loaders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coursemd.core.exceptions import wrap_validation_errors
from coursemd.core.loaders.validation import bind_validation
from coursemd.core.models.quiz import Reading

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.types import QuizDict


@wrap_validation_errors
def validate_schedule_quiz_metadata(
    source_file: Path,
    metadata: dict[str, Any],
) -> QuizDict:
    """Validate and normalize quiz metadata used in the rendered schedule."""
    validate = bind_validation(source_file)

    title = validate.require_non_empty_string(metadata.get("title"), "title")
    release_date = validate.require_date(metadata.get("release_date"), "release_date")
    due_at = validate.normalize_due_at(metadata.get("due_at"), title)
    due_date = validate.require_date(due_at, "due_at")
    if due_date < release_date:
        raise ValueError("'due_at' must not fall before 'release_date'.")

    quiz: QuizDict = {
        "title": title,
        "release_date": release_date,
        "due_date": due_date,
    }

    link = metadata.get("link")
    if link is not None:
        link_text = str(link).strip()
        if not link_text:
            raise ValueError("'link' must be a non-empty string when provided.")
        quiz["link"] = link_text

    readings = Reading.load(metadata.get("readings"))
    if readings:
        quiz["readings"] = [
            {"title": reading.title, "url": reading.url} for reading in readings
        ]

    return quiz


def default_quiz_files(repo_root: Path) -> list[Path]:
    quizzes_dir = repo_root / "website" / "docs" / "quizzes"
    if not quizzes_dir.exists():
        return []
    return sorted(path for path in quizzes_dir.glob("*.md") if path.name != "index.md")
