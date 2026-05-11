"""Quiz frontmatter loaders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from coursemd.core.loaders.dates import normalize_due_at, require_date, require_release_date
from coursemd.core.loaders.markdown import load_markdown_post
from coursemd.core.models.integrations import CanvasQuizIntegration, QuizIntegrations
from coursemd.core.models.quiz import QuestionSpec, QuizSpec, ReadingSpec

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.types import QuizDict

QUESTION_TYPE_MAP = {
    "multiple_choice": "multiple_choice_question",
    "true_false": "true_false_question",
    "multiple_answers": "multiple_answers_question",
    "short_answer": "short_answer_question",
    "essay": "essay_question",
    "matching": "matching_question",
}

QUIZ_TYPE_MAP = {
    "reading": "assignment",
    "reflection": "graded_survey",
    "phase": "assignment",
}


def _require_non_empty_string(value: Any, source_file: Path, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{source_file}: '{field_name}' must be a non-empty string.")
    return text


def _optional_mapping(value: Any, source_file: Path, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{source_file}: '{field_name}' must be an object/map.")
    return value


def parse_readings(value: Any, source_file: Path, quiz_type: str) -> list[ReadingSpec]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{source_file}: 'readings' must be a list.")
    if quiz_type != "reading" and value:
        raise ValueError(
            f"{source_file}: 'readings' is only supported for quizzes with type='reading'."
        )

    readings: list[ReadingSpec] = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise TypeError(
                f"{source_file}: readings[{i}] must be an object with 'title' and 'url'."
            )
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title:
            raise ValueError(f"{source_file}: readings[{i}].title is required.")
        if not url:
            raise ValueError(f"{source_file}: readings[{i}].url is required.")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{source_file}: readings[{i}].url must be an absolute http(s) URL.")
        readings.append(ReadingSpec(title=title, url=url))
    return readings


def validate_schedule_quiz_metadata(
    source_file: Path,
    metadata: dict[str, Any],
    *,
    canvas_base_url: str,
    canvas_course_id: int | str | None,
) -> QuizDict:
    """Validate and normalize quiz metadata used in the rendered schedule."""

    title = _require_non_empty_string(metadata.get("title"), source_file, "title")
    release_date = require_date(metadata.get("release_date"), source_file, "release_date")
    due_at = normalize_due_at(metadata.get("due_at"), source_file, title)
    due_date = require_date(due_at, source_file, "due_at")
    if due_date < release_date:
        raise ValueError(f"{source_file}: 'due_at' must not fall before 'release_date'.")

    quiz: QuizDict = {
        "title": title,
        "release_date": release_date,
        "due_date": due_date,
    }

    link = metadata.get("link")
    if link is not None:
        link_text = str(link).strip()
        if not link_text:
            raise ValueError(f"{source_file}: 'link' must be a non-empty string when provided.")
        quiz["link"] = link_text
    else:
        integrations = _optional_mapping(metadata.get("integrations"), source_file, "integrations")
        canvas_integration = _optional_mapping(
            integrations.get("canvas"),
            source_file,
            "integrations.canvas",
        )
        canvas_id = canvas_integration.get("id")
        if canvas_course_id and canvas_id is not None:
            quiz["link"] = (
                f"{canvas_base_url.rstrip('/')}/courses/{canvas_course_id}/quizzes/{canvas_id}"
            )

    quiz_type = str(metadata.get("type", "")).strip().lower()
    readings = parse_readings(metadata.get("readings"), source_file, quiz_type)
    if readings:
        quiz["readings"] = [{"title": reading.title, "url": reading.url} for reading in readings]

    return quiz


def parse_quiz_file(source_file: Path) -> QuizSpec:
    post = load_markdown_post(source_file)
    meta = post.metadata

    title = _require_non_empty_string(meta.get("title"), source_file, "title")

    qtype = str(meta.get("type", "")).strip().lower()
    if qtype not in QUIZ_TYPE_MAP:
        raise ValueError(
            f"{source_file}: 'type' must be one of: {', '.join(QUIZ_TYPE_MAP)}. Got '{qtype}'."
        )

    integrations = _optional_mapping(meta.get("integrations"), source_file, "integrations")
    canvas_integration_map = _optional_mapping(
        integrations.get("canvas"),
        source_file,
        "integrations.canvas",
    )
    quiz_type_override = canvas_integration_map.get("quiz_type")
    canvas_quiz_type = str(quiz_type_override) if quiz_type_override else QUIZ_TYPE_MAP[qtype]

    due_at = normalize_due_at(meta.get("due_at"), source_file, title)
    assignment_group = str(
        canvas_integration_map.get("assignment_group") or f"{qtype.title()} Quizzes"
    )
    points = meta.get("points")
    if points is not None:
        try:
            points = float(points)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source_file}: 'points' must be numeric.") from exc
    published = bool(meta.get("published", False))
    unlock_at = require_release_date(meta.get("release_date"), source_file, "release_date")
    description = str(meta.get("description", "")).strip() or None
    readings = parse_readings(meta.get("readings"), source_file, qtype)
    canvas_id = canvas_integration_map.get("id")
    if canvas_id is not None:
        try:
            canvas_id = int(canvas_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{source_file}: 'integrations.canvas.id' must be an integer."
            ) from exc

    questions_raw = meta.get("questions")
    if questions_raw is None:
        raise ValueError(f"{source_file}: 'questions' is required.")
    if not isinstance(questions_raw, list):
        raise TypeError(f"{source_file}: 'questions' must be a list.")
    if not questions_raw:
        raise ValueError(f"{source_file}: 'questions' must contain at least one item.")

    question_specs: list[QuestionSpec] = []
    seen_positions: set[int] = set()
    for i, question in enumerate(questions_raw):
        if not isinstance(question, dict):
            raise TypeError(f"{source_file}: each question must be an object.")
        qtype_inner = str(question.get("question_type", "")).strip().lower()
        if qtype_inner not in QUESTION_TYPE_MAP:
            raise ValueError(
                f"{source_file}: question {i + 1} has invalid question_type '{qtype_inner}'. "
                f"Must be one of: {', '.join(QUESTION_TYPE_MAP)}."
            )
        qtext = question.get("question_text", "")
        if not str(qtext).strip():
            raise ValueError(f"{source_file}: question {i + 1} must have question_text.")
        try:
            pts = float(question.get("points_possible", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{source_file}: question {i + 1} points_possible must be numeric."
            ) from exc
        try:
            pos = int(question.get("position", i + 1))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{source_file}: question {i + 1} position must be an integer."
            ) from exc
        if pos < 1:
            raise ValueError(f"{source_file}: question {i + 1} position must be at least 1.")
        if pos in seen_positions:
            raise ValueError(f"{source_file}: question positions must be unique within a quiz.")
        seen_positions.add(pos)
        answers_raw = question.get("answers", [])
        if not isinstance(answers_raw, list):
            raise TypeError(f"{source_file}: question {i + 1} answers must be a list.")
        distractors = question.get("distractors")
        if isinstance(distractors, list):
            distractors = [str(d) for d in distractors]
        elif distractors is None:
            distractors = None
        else:
            raise TypeError(f"{source_file}: question {i + 1} distractors must be a list.")

        answer_required_types = (
            "multiple_choice",
            "true_false",
            "multiple_answers",
            "matching",
            "short_answer",
        )
        if (
            qtype_inner in answer_required_types
            and not answers_raw
            and qtype_inner != "short_answer"
        ):
            raise ValueError(
                f"{source_file}: question {i + 1} ({qtype_inner}) must have answers."
            )

        if qtype_inner in {"multiple_choice", "true_false", "multiple_answers"}:
            correct_answers = 0
            for answer_index, answer in enumerate(answers_raw):
                if not isinstance(answer, dict):
                    raise TypeError(
                        f"{source_file}: question {i + 1} answers[{answer_index}] "
                        "must be an object."
                    )
                answer_text = str(answer.get("text", "")).strip()
                if not answer_text:
                    raise ValueError(
                        f"{source_file}: question {i + 1} answers[{answer_index}].text is required."
                    )
                if not isinstance(answer.get("correct"), bool):
                    raise TypeError(
                        f"{source_file}: question {i + 1} answers[{answer_index}].correct "
                        f"must be a boolean."
                    )
                if answer["correct"]:
                    correct_answers += 1
            if correct_answers == 0:
                raise ValueError(
                    f"{source_file}: question {i + 1} must mark at least one answer correct."
                )
            if qtype_inner in {"multiple_choice", "true_false"} and correct_answers != 1:
                raise ValueError(
                    f"{source_file}: question {i + 1} ({qtype_inner}) must mark "
                    "exactly one answer correct."
                )

        if qtype_inner == "matching":
            for answer_index, answer in enumerate(answers_raw):
                if not isinstance(answer, dict):
                    raise TypeError(
                        f"{source_file}: question {i + 1} answers[{answer_index}] "
                        "must be an object."
                    )
                left = str(answer.get("left", "")).strip()
                right = str(answer.get("right", "")).strip()
                if not left or not right:
                    raise ValueError(
                        f"{source_file}: question {i + 1} matching answers must include "
                        f"non-empty 'left' and 'right' fields."
                    )

        if qtype_inner == "short_answer":
            for answer_index, answer in enumerate(answers_raw):
                if isinstance(answer, str):
                    if not answer.strip():
                        raise ValueError(
                            f"{source_file}: question {i + 1} answers[{answer_index}] "
                            "must not be blank."
                        )
                    continue
                if not isinstance(answer, dict):
                    raise TypeError(
                        f"{source_file}: question {i + 1} answers[{answer_index}] "
                        "must be a string or object."
                    )
                answer_text = str(answer.get("text", "")).strip()
                if not answer_text:
                    raise ValueError(
                        f"{source_file}: question {i + 1} answers[{answer_index}].text is required."
                    )

        question_specs.append(
            QuestionSpec(
                question_type=qtype_inner,
                question_text=str(qtext),
                points_possible=pts,
                position=pos,
                answers=answers_raw if isinstance(answers_raw, list) else [],
                distractors=distractors,
            )
        )

    return QuizSpec(
        source_file=source_file,
        title=title,
        source_type=qtype,
        due_at=due_at,
        points=points,
        published=published,
        unlock_at=unlock_at,
        description=description,
        readings=readings,
        questions=question_specs,
        integrations=QuizIntegrations(
            canvas=CanvasQuizIntegration(
                id=canvas_id,
                assignment_group=assignment_group,
                quiz_type=canvas_quiz_type,
            )
        ),
    )


def default_quiz_files(repo_root: Path) -> list[Path]:
    quizzes_dir = repo_root / "website" / "docs" / "quizzes"
    if not quizzes_dir.exists():
        return []
    return sorted(path for path in quizzes_dir.glob("*.md") if path.name != "index.md")


def load_quiz_specs(
    files: list[Path],
    *,
    require_canvas_fields: bool = True,
) -> list[QuizSpec]:
    specs: list[QuizSpec] = []
    for path in files:
        if not require_canvas_fields:
            metadata = load_markdown_post(path).metadata
            questions = metadata.get("questions")
            if questions is None or questions == []:
                continue
        specs.append(parse_quiz_file(path))
    return specs
