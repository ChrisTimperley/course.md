"""Coursemd - A reusable package for data-driven course websites."""

__version__ = "0.1.0"

from coursemd.core.config import ScheduleConfig
from coursemd.core.models import (
    Assignment,
    CourseBreak,
    CourseRepository,
    Quiz,
    QuizQuestion,
    Reading,
    Rubric,
)
from coursemd.core.schedule import Schedule, ScheduleEntry
from coursemd.core.types import (
    EventDict,
    RubricCriterion,
    RubricSection,
    RubricTier,
)
from coursemd.core.utils import current_date, working_days

__all__ = [
    "Assignment",
    "CourseBreak",
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
    "ScheduleConfig",
    "ScheduleEntry",
    "current_date",
    "working_days",
]
