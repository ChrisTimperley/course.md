"""Canvas-specific schedule enrichment helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from coursemd.integrations.canvas.models import canvas_quiz

if TYPE_CHECKING:
    from coursemd.core.models.quiz import Quiz


def inject_quiz_links(
    quizzes: list[Quiz],
    base_url: str,
    course_id: int | str,
) -> list[Quiz]:
    """Inject Canvas quiz URLs into quiz specs that have a Canvas ID but no explicit link."""
    base = base_url.rstrip("/")
    result: list[Quiz] = []
    for quiz in quizzes:
        canvas_id = canvas_quiz(quiz.integrations).id
        if quiz.link is None and canvas_id is not None:
            result.append(quiz.with_link(f"{base}/courses/{course_id}/quizzes/{canvas_id}"))
        else:
            result.append(quiz)
    return result
