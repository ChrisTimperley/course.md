"""Canvas quiz payload builders."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any

from coursemd.integrations.canvas.models import canvas_quiz

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.models.quiz import QuestionSpec, QuizSpec

QUESTION_TYPE_MAP: dict[str, str] = {
    "multiple_choice": "multiple_choice_question",
    "true_false": "true_false_question",
    "multiple_answers": "multiple_answers_question",
    "short_answer": "short_answer_question",
    "essay": "essay_question",
    "matching": "matching_question",
}

QUIZ_TYPE_MAP: dict[str, str] = {
    "reading": "assignment",
    "reflection": "graded_survey",
    "phase": "assignment",
}


def _ensure_html(text: str) -> str:
    """Wrap plain text in <p> if it doesn't already look like HTML."""

    if not text or not text.strip():
        return "<p></p>"
    stripped = text.strip()
    if stripped.startswith("<") and stripped.endswith(">"):
        return text
    return f"<p>{text}</p>"


def build_quiz_description(spec: QuizSpec) -> str:
    parts: list[str] = []
    if spec.source_type == "reading" and spec.readings:
        items = "".join(
            (
                '<li><a href="'
                + html.escape(reading.url, quote=True)
                + '" target="_blank" rel="noopener noreferrer">'
                + html.escape(reading.title)
                + "</a></li>"
            )
            for reading in spec.readings
        )
        parts.append(
            "<p><strong>Before taking this quiz</strong>, complete the following readings:</p>"
            f"<ul>{items}</ul>"
            "<p>Questions may reference details from these readings and this week's "
            "course materials.</p>"
        )
    if spec.description:
        parts.append(_ensure_html(spec.description))
    return "".join(parts)


def build_canvas_answers(question: QuestionSpec, source_file: Path) -> list[dict[str, Any]]:
    qt = question.question_type
    canvas_answers: list[dict[str, Any]]
    if qt == "matching":
        canvas_answers = []
        distractors = question.distractors or []
        all_rights = [
            answer.get("right", "") for answer in question.answers if isinstance(answer, dict)
        ]
        for answer in question.answers:
            if not isinstance(answer, dict) or "left" not in answer or "right" not in answer:
                continue
            left = str(answer["left"])
            right = str(answer["right"])
            incorrect = [candidate for candidate in all_rights if candidate != right] + distractors
            canvas_answers.append(
                {
                    "answer_match_left": left,
                    "answer_match_right": right,
                    "matching_answer_incorrect_matches": "\n".join(incorrect) if incorrect else "",
                }
            )
        return canvas_answers

    if qt in ("multiple_choice", "true_false", "multiple_answers"):
        canvas_answers = []
        for answer in question.answers:
            if not isinstance(answer, dict) or "text" not in answer:
                raise ValueError(
                    f"{source_file}: {qt} question must have answers with 'text' and 'correct'."
                )
            weight = 100 if answer.get("correct", False) else 0
            canvas_answers.append(
                {
                    "answer_text": str(answer["text"]),
                    "answer_weight": weight,
                }
            )
        return canvas_answers

    if qt == "short_answer":
        canvas_answers = []
        for answer in question.answers:
            if isinstance(answer, dict) and "text" in answer:
                canvas_answers.append(
                    {
                        "answer_text": str(answer["text"]),
                        "answer_weight": 100,
                    }
                )
            elif isinstance(answer, str):
                canvas_answers.append(
                    {
                        "answer_text": str(answer),
                        "answer_weight": 100,
                    }
                )
        return canvas_answers

    if qt == "essay":
        return []

    raise ValueError(f"{source_file}: unsupported question_type '{qt}'")


def total_quiz_points(spec: QuizSpec) -> float:
    total_points = spec.points
    if total_points is None:
        total_points = sum(question.points_possible for question in spec.questions)
    return total_points


def form_for_quiz(
    spec: QuizSpec,
    assignment_group_id: int,
    publish_override: bool,
) -> dict[str, Any]:
    publish_value = publish_override or spec.published
    canvas = canvas_quiz(spec.integrations, spec.source_type, QUIZ_TYPE_MAP)
    form: dict[str, Any] = {
        "quiz[title]": spec.title,
        "quiz[quiz_type]": canvas.quiz_type or "assignment",
        "quiz[shuffle_answers]": "true",
        "quiz[due_at]": spec.due_at,
        "quiz[lock_at]": spec.due_at,
        "quiz[assignment_group_id]": str(assignment_group_id),
        "quiz[points_possible]": str(total_quiz_points(spec)),
        "quiz[published]": "true" if publish_value else "false",
        "quiz[description]": build_quiz_description(spec),
        "quiz[notify_of_update]": "false",
    }
    if spec.unlock_at:
        form["quiz[unlock_at]"] = spec.unlock_at
    return form


def question_payload_for_canvas(spec: QuestionSpec, source_file: Path) -> dict[str, Any]:
    canvas_type = QUESTION_TYPE_MAP[spec.question_type]
    payload: dict[str, Any] = {
        "question_name": f"Q{spec.position}",
        "question_text": _ensure_html(spec.question_text),
        "question_type": canvas_type,
        "position": spec.position,
        "points_possible": spec.points_possible,
    }
    if spec.question_type != "essay":
        payload["answers"] = build_canvas_answers(spec, source_file)
    return payload
