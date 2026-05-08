"""Canvas adapter for course repositories."""

from coursemd.adapters.canvas.assignments import form_for_assignment
from coursemd.adapters.canvas.client import DEFAULT_CANVAS_BASE_URL, CanvasApiClient
from coursemd.adapters.canvas.frontmatter import (
    update_assignment_frontmatter_with_ids,
    update_quiz_frontmatter_with_canvas_id,
)
from coursemd.adapters.canvas.quizzes import (
    build_canvas_answers,
    build_quiz_description,
    form_for_quiz,
    question_payload_for_canvas,
    total_quiz_points,
)
from coursemd.adapters.canvas.resources import AssignmentCanvasClient, QuizCanvasClient
from coursemd.adapters.canvas.rubrics import form_for_rubric
from coursemd.adapters.canvas.sync import (
    CanvasSyncEvent,
    CanvasSyncReporter,
    resolve_group_category_id,
    sync_assignments_to_canvas,
    sync_quiz_questions,
    sync_quizzes_to_canvas,
)

__all__ = [
    "AssignmentCanvasClient",
    "CanvasApiClient",
    "CanvasSyncEvent",
    "CanvasSyncReporter",
    "DEFAULT_CANVAS_BASE_URL",
    "QuizCanvasClient",
    "build_canvas_answers",
    "build_quiz_description",
    "form_for_assignment",
    "form_for_quiz",
    "form_for_rubric",
    "question_payload_for_canvas",
    "resolve_group_category_id",
    "sync_assignments_to_canvas",
    "sync_quiz_questions",
    "sync_quizzes_to_canvas",
    "total_quiz_points",
    "update_assignment_frontmatter_with_ids",
    "update_quiz_frontmatter_with_canvas_id",
]
