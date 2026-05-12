"""Path configuration for course repositories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class CoursePathsConfig:
    data_dir: Path
    assignments_dir: Path
    quizzes_dir: Path
    env_file: str = ".env"
