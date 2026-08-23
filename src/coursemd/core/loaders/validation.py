"""Shared validation helpers for content loaders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.loaders.dates import parse_date
from coursemd.core.utils import get_timezone

T = TypeVar("T")


@dataclass(frozen=True)
class BoundValidation:
    """Validation helpers bound to a specific source path."""

    source_path: Path

    def _call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        try:
            return func(*args, **kwargs)
        except CoursemdValidationError as exc:
            if exc.source_path is not None:
                raise
            raise CoursemdValidationError(exc.message, source_path=self.source_path) from exc

    def require_non_empty_string(self, value: Any, field_name: str) -> str:
        return self._call(require_non_empty_string, value, field_name)

    def require_mapping(self, value: Any, label: str) -> dict[str, Any]:
        return self._call(require_mapping, value, label)

    def require_date(self, value: Any, field_name: str) -> date:
        return self._call(require_date, value, field_name)

    def require_due_at(self, value: Any, context: str) -> datetime:
        return self._call(require_due_at, value, context)

    def normalize_due_at(self, value: Any, context: str) -> str:
        return self._call(normalize_due_at, value, context)

    def require_close_at(self, value: Any, context: str) -> datetime:
        return self._call(require_close_at, value, context)

    def normalize_close_at(self, value: Any, context: str) -> str:
        return self._call(normalize_close_at, value, context)

    def require_release_date(self, value: Any, field_name: str = "release_date") -> str:
        return self._call(require_release_date, value, field_name)


def bind_validation(source_path: Path) -> BoundValidation:
    return BoundValidation(source_path)


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def require_non_empty_string(value: Any, field_name: str) -> str:
    text = optional_string(value)
    if text is None:
        raise CoursemdValidationError(f"'{field_name}' must be a non-empty string.")
    return text


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CoursemdValidationError(f"'{label}' must be an object/map.")
    return cast("dict[str, Any]", value)


def require_date(value: Any, field_name: str) -> date:
    """Parse a required date-like field or raise a clear validation error."""

    parsed = parse_date(value)
    if parsed is None:
        raise CoursemdValidationError(
            f"'{field_name}' must be a valid date or ISO-8601 timestamp."
        )
    return parsed


def require_due_at(value: Any, context: str) -> datetime:
    """Parse a due timestamp and require an explicit timezone."""

    if isinstance(value, datetime):
        due_at = value
    elif isinstance(value, date):
        raise CoursemdValidationError(
            f"'{context}' due_at must include time + timezone (received date only)."
        )
    elif isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            due_at = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise CoursemdValidationError(
                f"'{context}' due_at must be ISO-8601 "
                f"(example: 2026-03-13T23:59:00-04:00)."
            ) from exc
    else:
        raise CoursemdValidationError(
            f"'{context}' due_at has unsupported type: {type(value).__name__}"
        )

    if due_at.tzinfo is None:
        raise CoursemdValidationError(
            f"'{context}' due_at must include timezone offset "
            f"(example: 2026-03-13T23:59:00-04:00)."
        )
    return due_at


def normalize_due_at(value: Any, context: str) -> str:
    """Normalize a due timestamp and require an explicit timezone."""

    due_at = require_due_at(value, context)
    return due_at.isoformat()


def require_close_at(value: Any, context: str) -> datetime:
    """Parse a last-accepted timestamp and require an explicit timezone."""

    if isinstance(value, datetime):
        close_at = value
    elif isinstance(value, date):
        raise CoursemdValidationError(
            f"'{context}' close_at must include time + timezone (received date only)."
        )
    elif isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            close_at = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise CoursemdValidationError(
                f"'{context}' close_at must be ISO-8601 "
                f"(example: 2026-03-17T23:59:00-04:00)."
            ) from exc
    else:
        raise CoursemdValidationError(
            f"'{context}' close_at has unsupported type: {type(value).__name__}"
        )

    if close_at.tzinfo is None:
        raise CoursemdValidationError(
            f"'{context}' close_at must include timezone offset "
            f"(example: 2026-03-17T23:59:00-04:00)."
        )
    return close_at


def normalize_close_at(value: Any, context: str) -> str:
    """Normalize a last-accepted timestamp and require an explicit timezone."""

    return require_close_at(value, context).isoformat()


def normalize_release_date(value: Any) -> str | None:
    """Normalize a release date into an ISO timestamp."""

    course_timezone = get_timezone()
    if value is None:
        return None
    if isinstance(value, datetime):
        release_at = value
    elif isinstance(value, date):
        release_at = datetime.combine(value, datetime.min.time(), tzinfo=course_timezone)
    elif isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if "T" in candidate or " " in candidate:
            try:
                release_at = datetime.fromisoformat(candidate)
            except ValueError:
                return None
        else:
            try:
                parsed_date = datetime.strptime(candidate, "%Y-%m-%d").date()  # noqa: DTZ007
                release_at = datetime.combine(
                    parsed_date,
                    datetime.min.time(),
                    tzinfo=course_timezone,
                )
            except ValueError:
                return None
    else:
        return None
    if release_at.tzinfo is None:
        release_at = release_at.replace(tzinfo=course_timezone)
    return release_at.isoformat()


def require_release_date(value: Any, field_name: str = "release_date") -> str:
    """Normalize a required release date or raise a clear validation error."""

    normalized = normalize_release_date(value)
    if normalized is None:
        raise CoursemdValidationError(
            f"'{field_name}' must be a valid date or ISO-8601 timestamp."
        )
    return normalized
