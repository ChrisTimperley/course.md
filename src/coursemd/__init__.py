"""Coursemd - A reusable package for data-driven course websites."""

__version__ = "0.1.0"

from coursemd.core.models import (
    Assignment,
    CourseRepository,
    QuestionSpec,
    QuizSpec,
    ReadingSpec,
    Rubric,
)
from coursemd.core.schedule import Schedule, ScheduleEntry
from coursemd.core.types import (
    BreakDict,
    EventDict,
    QuizDict,
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
    "QuestionSpec",
    "QuizDict",
    "QuizSpec",
    "ReadingSpec",
    "Rubric",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
    "Schedule",
    "ScheduleEntry",
    "current_date",
    "working_days",
]
