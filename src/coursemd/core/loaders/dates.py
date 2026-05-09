"""Date parsing and normalization helpers for course content."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from coursemd.core.utils import DEFAULT_TIMEZONE, get_timezone

EASTERN = ZoneInfo(DEFAULT_TIMEZONE)


def parse_date(value: Any) -> date | None:
    """Parse a date from a date, datetime, YYYY-MM-DD string, or ISO timestamp."""

    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if "T" in candidate or " " in candidate:
            try:
                return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date()
            except ValueError:
                return None
        try:
            return datetime.strptime(candidate, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def require_date(value: Any, source_file: Path, field_name: str) -> date:
    """Parse a required date-like field or raise a clear validation error."""

    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(
            f"{source_file}: '{field_name}' must be a valid date or ISO-8601 timestamp."
        )
    return parsed


def normalize_due_at(value: Any, source_file: Path, context: str) -> str:
    """Normalize a due timestamp and require an explicit timezone."""

    if isinstance(value, datetime):
        due_at = value
    elif isinstance(value, date):
        raise ValueError(
            f"{source_file}: '{context}' due_at must include time + timezone (received date only)."
        )
    elif isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            due_at = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(
                f"{source_file}: '{context}' due_at must be ISO-8601 "
                f"(example: 2026-03-13T23:59:00-04:00)."
            ) from exc
    else:
        raise ValueError(
            f"{source_file}: '{context}' due_at has unsupported type: {type(value).__name__}"
        )

    if due_at.tzinfo is None:
        raise ValueError(
            f"{source_file}: '{context}' due_at must include timezone offset "
            f"(example: 2026-03-13T23:59:00-04:00)."
        )
    return due_at.isoformat()


def normalize_release_date(value: Any, source_file: Path) -> str | None:
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
                release_at = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            try:
                parsed_date = datetime.strptime(candidate, "%Y-%m-%d").date()
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


def require_release_date(value: Any, source_file: Path, field_name: str = "release_date") -> str:
    """Normalize a required release date or raise a clear validation error."""

    normalized = normalize_release_date(value, source_file)
    if normalized is None:
        raise ValueError(
            f"{source_file}: '{field_name}' must be a valid date or ISO-8601 timestamp."
        )
    return normalized
