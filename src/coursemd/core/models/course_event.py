"""Course event model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.loaders.dates import parse_date

if TYPE_CHECKING:
    import datetime as dt


@dataclass(frozen=True)
class CourseEvent:
    """Represents an event in the course schedule."""

    kind: str
    date: dt.date
    title: str
    link: str | None = None
    speakers: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: Any) -> Self:
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise CoursemdValidationError("event must be a mapping.")
        return cls.from_dict(value)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        kind = value.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            raise CoursemdValidationError("event kind must be a non-empty string.")

        parsed_date = parse_date(value.get("date"))
        if parsed_date is None:
            raise CoursemdValidationError("event date must be a valid date or ISO-8601 timestamp.")

        title = value.get("title")
        if not isinstance(title, str) or not title.strip():
            raise CoursemdValidationError("event title must be a non-empty string.")

        link = value.get("link")
        if link is not None and (not isinstance(link, str) or not link.strip()):
            raise CoursemdValidationError("event link must be a non-empty string.")

        speakers_raw = value.get("speakers", [])
        if speakers_raw is None:
            speakers_raw = []
        if not isinstance(speakers_raw, list):
            raise CoursemdValidationError("event speakers must be a list.")

        speakers: list[str] = []
        for speaker in speakers_raw:
            if not isinstance(speaker, str) or not speaker.strip():
                raise CoursemdValidationError("event speakers must be non-empty strings.")
            speakers.append(speaker.strip())

        return cls(
            kind=kind.strip().lower(),
            date=parsed_date,
            title=title.strip(),
            link=link.strip() if isinstance(link, str) else None,
            speakers=tuple(speakers),
        )

    @classmethod
    def from_list(cls, value: list[Any] | None) -> list[Self]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise CoursemdValidationError("events must be a list.")
        return [cls.parse(item) for item in value]
