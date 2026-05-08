"""Coursemd - A reusable package for data-driven course websites."""

__version__ = "0.1.0"

from coursemd.models import AssignmentSpec, CourseRepository, QuestionSpec, QuizSpec, ReadingSpec
from coursemd.rubric import flatten_rubric_criteria, load_rubric_sections, select_rubric_criteria
from coursemd.schedule import Schedule, ScheduleEntry
from coursemd.types import (
    AssignmentDict,
    BreakDict,
    CheckpointDict,
    EventDict,
    QuizDict,
    RubricCriterion,
    RubricSection,
    RubricTier,
)
from coursemd.utils import current_date, working_days

__all__ = [
    "Schedule",
    "ScheduleEntry",
    "AssignmentSpec",
    "CourseRepository",
    "QuestionSpec",
    "QuizSpec",
    "ReadingSpec",
    "flatten_rubric_criteria",
    "load_rubric_sections",
    "select_rubric_criteria",
    "AssignmentDict",
    "BreakDict",
    "CheckpointDict",
    "EventDict",
    "QuizDict",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
    "current_date",
    "working_days",
]
