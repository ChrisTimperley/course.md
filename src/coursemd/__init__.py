"""Coursemd - A reusable package for data-driven course websites."""

__version__ = "0.1.0"

from coursemd.core.models import (
    AssignmentSpec,
    CourseRepository,
    QuestionSpec,
    QuizSpec,
    ReadingSpec,
)
from coursemd.core.rubric import (
    flatten_rubric_criteria,
    load_rubric_sections,
    select_rubric_criteria,
)
from coursemd.core.schedule import Schedule, ScheduleEntry
from coursemd.core.types import (
    AssignmentDict,
    BreakDict,
    CheckpointDict,
    EventDict,
    QuizDict,
    RubricCriterion,
    RubricSection,
    RubricTier,
)
from coursemd.core.utils import current_date, working_days

__all__ = [
    "AssignmentDict",
    "AssignmentSpec",
    "BreakDict",
    "CheckpointDict",
    "CourseRepository",
    "EventDict",
    "QuestionSpec",
    "QuizDict",
    "QuizSpec",
    "ReadingSpec",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
    "Schedule",
    "ScheduleEntry",
    "current_date",
    "flatten_rubric_criteria",
    "load_rubric_sections",
    "select_rubric_criteria",
    "working_days",
]
