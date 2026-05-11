"""Typed domain models for course repositories."""

from coursemd.core.models.assignment import AssignmentSpec
from coursemd.core.models.quiz import QuestionSpec, QuizSpec, ReadingSpec
from coursemd.core.models.repository import CourseRepository
from coursemd.core.models.rubric import Rubric, RubricCriterion, RubricSection, RubricTier

__all__ = [
    "AssignmentSpec",
    "CourseRepository",
    "QuestionSpec",
    "QuizSpec",
    "ReadingSpec",
    "Rubric",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
]
