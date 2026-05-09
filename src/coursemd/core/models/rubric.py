"""Rubric type definitions."""

from __future__ import annotations

from typing import TypedDict


class RubricTier(TypedDict):
    """Represents a single scoring tier within a rubric criterion."""

    points: int
    label: str
    desc: str


class RubricCriterion(TypedDict, total=False):
    """Represents a single gradeable criterion within a rubric section."""

    name: str
    points: int
    desc: str
    tiers: list[RubricTier]


class RubricSection(TypedDict, total=False):
    """Represents a top-level section of a rubric."""

    section: str
    points: int
    criteria: list[RubricCriterion]
