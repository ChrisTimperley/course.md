"""Canvas-specific schedule enrichment helpers."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from coursemd.core.loaders.markdown import load_markdown_metadata

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.types import QuizDict


def inject_quiz_links(
    quizzes: list[QuizDict],
    quiz_files: list[Path],
    base_url: str,
    course_id: int | str,
) -> list[QuizDict]:
    """Inject Canvas quiz URLs into QuizDict entries that have a Canvas ID but no explicit link."""
    canvas_ids: dict[str, int] = {}
    for path in quiz_files:
        meta: dict[str, Any] = load_markdown_metadata(path)
        title = str(meta.get("title", "")).strip()
        canvas_map = (meta.get("integrations") or {}).get("canvas") or {}
        if not isinstance(canvas_map, dict):
            continue
        raw_id = canvas_map.get("id")
        if title and raw_id is not None:
            with contextlib.suppress(TypeError, ValueError):
                canvas_ids[title] = int(raw_id)

    base = base_url.rstrip("/")
    result: list[QuizDict] = []
    for quiz in quizzes:
        if "link" not in quiz:
            canvas_id = canvas_ids.get(quiz["title"])
            if canvas_id is not None:
                quiz = {**quiz, "link": f"{base}/courses/{course_id}/quizzes/{canvas_id}"}  # type: ignore[misc]  # noqa: PLW2901
        result.append(quiz)
    return result
