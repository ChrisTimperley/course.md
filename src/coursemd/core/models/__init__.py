"""Typed domain models for course repositories."""

from coursemd.core.models.assignment import AssignmentSpec
from coursemd.core.models.integrations import (
    AssignmentIntegrations,
    CanvasAssignmentIntegration,
    CanvasQuizIntegration,
    QuizIntegrations,
)
from coursemd.core.models.quiz import QuestionSpec, QuizSpec, ReadingSpec
from coursemd.core.models.repository import CourseRepository
from coursemd.core.models.rubric import RubricCriterion, RubricSection, RubricTier

__all__ = [
    "AssignmentIntegrations",
    "AssignmentSpec",
    "CanvasAssignmentIntegration",
    "CanvasQuizIntegration",
    "CourseRepository",
    "QuestionSpec",
    "QuizIntegrations",
    "QuizSpec",
    "ReadingSpec",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
]
