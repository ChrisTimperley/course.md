"""Course break model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import datetime as dt


@dataclass(frozen=True)
class CourseBreak:
    """Represents a break period in the course schedule."""

    name: str
    start: dt.date
    end: dt.date

    def contains(self, date: dt.date) -> bool:
        return self.start <= date <= self.end
