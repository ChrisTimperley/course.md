"""Typed domain models for course repositories."""

from coursemd.models.assignment import AssignmentSpec, CanvasAssignmentSpec
from coursemd.models.integrations import (
    AssignmentIntegrations,
    CanvasAssignmentIntegration,
    CanvasQuizIntegration,
    QuizIntegrations,
)
from coursemd.models.quiz import CanvasQuizSpec, QuestionSpec, QuizSpec, ReadingSpec
from coursemd.models.repository import CourseRepository
from coursemd.models.rubric import RubricCriterion, RubricSection, RubricTier

__all__ = [
    "AssignmentIntegrations",
    "AssignmentSpec",
    "CanvasAssignmentIntegration",
    "CanvasAssignmentSpec",
    "CanvasQuizIntegration",
    "CanvasQuizSpec",
    "CourseRepository",
    "QuestionSpec",
    "QuizIntegrations",
    "QuizSpec",
    "ReadingSpec",
    "RubricCriterion",
    "RubricSection",
    "RubricTier",
]
