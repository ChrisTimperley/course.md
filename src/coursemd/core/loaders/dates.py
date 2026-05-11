"""Date parsing and normalization helpers for course content."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


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
                return datetime.fromisoformat(candidate).date()
            except ValueError:
                return None
        try:
            return datetime.strptime(candidate, "%Y-%m-%d").date()  # noqa: DTZ007
        except ValueError:
            return None
    return None
