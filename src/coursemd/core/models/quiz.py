"""Quiz models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class QuizQuestion:
    """A quiz question in the course repository model."""

    question_type: str
    question_text: str
    points_possible: float
    position: int
    answers: list[dict[str, Any]]
    distractors: list[str] | None = None


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
    readings: list[Reading] = field(default_factory=list)
    questions: list[QuizQuestion] = field(default_factory=list)
    integrations: dict[str, Any] = field(default_factory=dict)
