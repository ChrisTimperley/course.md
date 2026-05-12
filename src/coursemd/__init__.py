"""Coursemd - A reusable package for data-driven course websites."""

__version__ = "0.1.0"

from coursemd.core.models import (
    Assignment,
    CourseRepository,
    Quiz,
    QuizQuestion,
    Reading,
    Rubric,
)
from coursemd.core.schedule import Schedule, ScheduleEntry
from coursemd.core.types import (
    BreakDict,
    EventDict,
    RubricCriterion,
    RubricSection,
    RubricTier,
)
from coursemd.core.utils import current_date, working_days

__all__ = [
    "Assignment",
    "BreakDict",
    "CourseRepository",
    "EventDict",
    "Quiz",
    "QuizQuestion",
    "Reading",
    "Rubric",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
    "Schedule",
    "ScheduleEntry",
    "current_date",
    "working_days",
]
