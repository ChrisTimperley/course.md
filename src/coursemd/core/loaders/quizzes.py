"""Quiz frontmatter loaders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from coursemd.core.exceptions import wrap_validation_errors
from coursemd.core.loaders.markdown import load_markdown_post
from coursemd.core.loaders.validation import (
    bind_validation,
    optional_string,
)
from coursemd.core.models.quiz import Quiz, QuizQuestion, Reading

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


@wrap_validation_errors
def parse_quiz_file(source_file: Path) -> Quiz:
    validate = bind_validation(source_file)
    post = load_markdown_post(source_file)
    meta = post.metadata
    title = validate.require_non_empty_string(meta.get("title"), "title")

    integrations_raw = meta.get("integrations")
    integrations: dict[str, Any] = {}
    if integrations_raw is not None:
        if not isinstance(integrations_raw, dict):
            raise TypeError("'integrations' must be an object/map.")
        integrations = dict(integrations_raw)

    due_at = validate.normalize_due_at(meta.get("due_at"), title)
    points = meta.get("points")
    if points is not None:
        try:
            points = float(points)
        except (TypeError, ValueError) as exc:
            raise ValueError("'points' must be numeric.") from exc
    published = bool(meta.get("published", False))
    unlock_at = validate.require_release_date(meta.get("release_date"), "release_date")
    description = optional_string(meta.get("description"))
    readings = Reading.load(meta.get("readings"))

    questions_raw = meta.get("questions")
    if questions_raw is None:
        raise ValueError("'questions' is required.")
    if not isinstance(questions_raw, list):
        raise TypeError("'questions' must be a list.")
    if not questions_raw:
        raise ValueError("'questions' must contain at least one item.")

    questions = QuizQuestion.from_list(cast("list[Any]", questions_raw))

    return Quiz(
        source_file=source_file,
        title=title,
        due_at=due_at,
        points=points,
        published=published,
        unlock_at=unlock_at,
        description=description,
        readings=readings,
        questions=questions,
        integrations=integrations,
    )


def default_quiz_files(repo_root: Path) -> list[Path]:
    quizzes_dir = repo_root / "website" / "docs" / "quizzes"
    if not quizzes_dir.exists():
        return []
    return sorted(path for path in quizzes_dir.glob("*.md") if path.name != "index.md")


def load_quiz_specs(files: list[Path]) -> list[Quiz]:
    specs: list[Quiz] = []
    for path in files:
        metadata = load_markdown_post(path).metadata
        questions = metadata.get("questions")
        if questions is None or questions == []:
            continue
        specs.append(parse_quiz_file(path))
    return specs
