"""Quiz models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, ClassVar, cast
from urllib.parse import urlparse

from coursemd.core.loaders.markdown import load_markdown_post
from coursemd.core.loaders.validation import bind_validation, optional_string

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class QuizQuestion:
    """A quiz question in the course repository model."""

    VALID_QUESTION_TYPES: ClassVar[frozenset[str]] = frozenset({
        "multiple_choice",
        "true_false",
        "multiple_answers",
        "short_answer",
        "essay",
        "matching",
    })

    question_type: str
    question_text: str
    points_possible: float
    position: int
    answers: list[Any]
    distractors: list[str] | None = None

    @classmethod
    def from_dict(cls, question: dict[str, Any]) -> QuizQuestion:
        question_type = str(question.get("question_type", "")).strip().lower()
        if question_type not in cls.VALID_QUESTION_TYPES:
            raise ValueError(
                f"invalid question_type '{question_type}'. "
                f"Must be one of: {', '.join(sorted(cls.VALID_QUESTION_TYPES))}."
            )

        question_text = str(question.get("question_text", ""))
        if not question_text.strip():
            raise ValueError("question_text is required.")

        try:
            points_possible = float(question.get("points_possible", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("points_possible must be numeric.") from exc

        try:
            position = int(question.get("position", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("position must be an integer.") from exc
        if position < 1:
            raise ValueError("position must be at least 1.")

        answers_raw = question.get("answers", [])
        if not isinstance(answers_raw, list):
            raise TypeError("answers must be a list.")

        distractors = cls._parse_distractors(question.get("distractors"))
        cls._validate_answers(question_type, cast("list[Any]", answers_raw))

        return cls(
            question_type=question_type,
            question_text=question_text,
            points_possible=points_possible,
            position=position,
            answers=cast("list[Any]", answers_raw),
            distractors=distractors,
        )

    @classmethod
    def from_list(cls, raw_questions: list[Any]) -> list[QuizQuestion]:
        questions: list[QuizQuestion] = []
        seen_positions: set[int] = set()
        for i, raw_question in enumerate(raw_questions):
            if not isinstance(raw_question, dict):
                raise TypeError(f"questions[{i}] must be an object.")
            question_dict = dict(cast("dict[str, Any]", raw_question))
            question_dict.setdefault("position", i + 1)
            try:
                question = cls.from_dict(question_dict)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"questions[{i}]: {exc}") from exc
            if question.position in seen_positions:
                raise ValueError("question positions must be unique within a quiz.")
            seen_positions.add(question.position)
            questions.append(question)
        return questions

    @staticmethod
    def _parse_distractors(value: Any) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise TypeError("distractors must be a list.")
        return [str(distractor) for distractor in value]

    @classmethod
    def _validate_answers(cls, question_type: str, answers: list[Any]) -> None:
        if question_type in {"multiple_choice", "true_false", "multiple_answers"}:
            cls._validate_choice_answers(question_type, answers)
        elif question_type == "matching":
            cls._validate_matching_answers(answers)
        elif question_type == "short_answer":
            cls._validate_short_answers(answers)

    @staticmethod
    def _validate_choice_answers(question_type: str, answers: list[Any]) -> None:
        if not answers:
            raise ValueError(f"{question_type} questions must have answers.")

        correct_answers = 0
        for i, answer in enumerate(answers):
            if not isinstance(answer, dict):
                raise TypeError(f"answers[{i}] must be an object.")
            answer_text = str(answer.get("text", "")).strip()
            if not answer_text:
                raise ValueError(f"answers[{i}].text is required.")
            if not isinstance(answer.get("correct"), bool):
                raise TypeError(f"answers[{i}].correct must be a boolean.")
            if answer["correct"]:
                correct_answers += 1

        if correct_answers == 0:
            raise ValueError("must mark at least one answer correct.")
        if question_type in {"multiple_choice", "true_false"} and correct_answers != 1:
            raise ValueError(f"{question_type} questions must mark exactly one answer correct.")

    @staticmethod
    def _validate_matching_answers(answers: list[Any]) -> None:
        if not answers:
            raise ValueError("matching questions must have answers.")

        for i, answer in enumerate(answers):
            if not isinstance(answer, dict):
                raise TypeError(f"answers[{i}] must be an object.")
            left = str(answer.get("left", "")).strip()
            right = str(answer.get("right", "")).strip()
            if not left or not right:
                raise ValueError(
                    "matching answers must include non-empty 'left' and 'right' fields."
                )

    @staticmethod
    def _validate_short_answers(answers: list[Any]) -> None:
        for i, answer in enumerate(answers):
            if isinstance(answer, str):
                if not answer.strip():
                    raise ValueError(f"answers[{i}] must not be blank.")
                continue
            if not isinstance(answer, dict):
                raise TypeError(f"answers[{i}] must be a string or object.")
            answer_text = str(answer.get("text", "")).strip()
            if not answer_text:
                raise ValueError(f"answers[{i}].text is required.")


@dataclass(frozen=True)
class Reading:
    """A required reading associated with a quiz."""

    title: str
    url: str

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> Reading:
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title:
            raise ValueError("title is required.")
        if not url:
            raise ValueError("url is required.")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL.")
        return cls(title=title, url=url)

    @classmethod
    def from_list(cls, value: list[Any]) -> list[Reading]:
        readings: list[Reading] = []
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                raise TypeError(f"readings[{i}] must be an object with 'title' and 'url'.")
            try:
                reading = cls.from_dict(cast("dict[str, Any]", item))
            except ValueError as exc:
                raise ValueError(f"readings[{i}]: {exc}") from exc
            readings.append(reading)
        return readings

    @classmethod
    def load(cls, value: Any) -> list[Reading]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("'readings' must be a list.")
        return cls.from_list(cast("list[Any]", value))


@dataclass(frozen=True)
class Quiz:
    """Canonical quiz specification."""

    source_file: Path
    title: str
    due_at: str
    points: float | None
    published: bool
    unlock_at: str | None
    description: str | None
    link: str | None = None
    readings: list[Reading] = field(default_factory=list)
    questions: list[QuizQuestion] = field(default_factory=list)
    integrations: dict[str, Any] = field(default_factory=dict)

    @property
    def release_date(self) -> date:
        if self.unlock_at is None:
            raise ValueError(f"{self.source_file}: release_date is required.")
        return datetime.fromisoformat(self.unlock_at).date()

    @property
    def due_date(self) -> date:
        return datetime.fromisoformat(self.due_at).date()

    def with_link(self, link: str) -> Quiz:
        return replace(self, link=link)

    @classmethod
    def load(cls, path: Path) -> Quiz:
        validate = bind_validation(path)
        post = load_markdown_post(path)
        meta = post.metadata
        title = validate.require_non_empty_string(meta.get("title"), "title")

        integrations_raw = meta.get("integrations")
        integrations: dict[str, Any] = {}
        if integrations_raw is not None:
            if not isinstance(integrations_raw, dict):
                raise TypeError("'integrations' must be an object/map.")
            integrations = dict(cast("dict[str, Any]", integrations_raw))

        due_at = validate.normalize_due_at(meta.get("due_at"), title)
        points = meta.get("points")
        if points is not None:
            try:
                points = float(points)
            except (TypeError, ValueError) as exc:
                raise ValueError("'points' must be numeric.") from exc
        published = bool(meta.get("published", False))
        unlock_at = validate.require_release_date(meta.get("release_date"), "release_date")
        if datetime.fromisoformat(due_at).date() < datetime.fromisoformat(unlock_at).date():
            raise ValueError("'due_at' must not fall before 'release_date'.")
        description = optional_string(meta.get("description"))
        link = optional_string(meta.get("link"))
        readings = Reading.load(meta.get("readings"))

        questions_raw = meta.get("questions")
        if questions_raw is None:
            raise ValueError("'questions' is required.")
        if not isinstance(questions_raw, list):
            raise TypeError("'questions' must be a list.")
        if not questions_raw:
            raise ValueError("'questions' must contain at least one item.")

        return cls(
            source_file=path,
            title=title,
            due_at=due_at,
            points=points,
            published=published,
            unlock_at=unlock_at,
            description=description,
            link=link,
            readings=readings,
            questions=QuizQuestion.from_list(cast("list[Any]", questions_raw)),
            integrations=integrations,
        )

    @classmethod
    def load_all(cls, files: list[Path]) -> list[Quiz]:
        quizzes: list[Quiz] = []
        for path in files:
            try:
                quiz = cls.load(path)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}: {exc}") from exc
            quizzes.append(quiz)
        return quizzes
