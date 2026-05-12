"""Configuration discovery and loading for coursemd repositories."""

from __future__ import annotations

from coursemd.core.config.course import CourseConfig
from coursemd.core.config.paths import CoursePathsConfig
from coursemd.core.config.schedule import ScheduleConfig

__all__ = [
    "CourseConfig",
    "CoursePathsConfig",
    "ScheduleConfig",
]
