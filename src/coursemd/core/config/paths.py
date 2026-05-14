"""Path configuration for course repositories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Self

from coursemd.core.config_helpers import optional_mapping, require_string, resolve_relative_path

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class CoursePathsConfig:
    DEFAULT_DATA_DIR: ClassVar[str] = "data"
    DEFAULT_ASSIGNMENTS_DIR: ClassVar[str] = "assignments"
    DEFAULT_QUIZZES_DIR: ClassVar[str] = "quizzes"
    DEFAULT_ENV_FILE: ClassVar[str] = ".env"

    data_dir: Path
    assignments_dir: Path
    quizzes_dir: Path
    env_file: str = DEFAULT_ENV_FILE

    @classmethod
    def default(cls, *, repo_root: Path) -> Self:
        return cls.from_dict({}, repo_root=repo_root)

    @classmethod
    def parse(cls, raw_value: Any, *, repo_root: Path) -> Self:
        return cls.from_dict(optional_mapping(raw_value, label="paths"), repo_root=repo_root)

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, repo_root: Path) -> Self:
        data_dir = value.get("data", cls.DEFAULT_DATA_DIR)
        assignments_dir = value.get("assignments", cls.DEFAULT_ASSIGNMENTS_DIR)
        quizzes_dir = value.get("quizzes", cls.DEFAULT_QUIZZES_DIR)
        env_file = value.get("environment", cls.DEFAULT_ENV_FILE)

        if data_dir is None:
            data_dir = cls.DEFAULT_DATA_DIR
        if assignments_dir is None:
            assignments_dir = cls.DEFAULT_ASSIGNMENTS_DIR
        if quizzes_dir is None:
            quizzes_dir = cls.DEFAULT_QUIZZES_DIR
        if env_file is None:
            env_file = cls.DEFAULT_ENV_FILE

        return cls(
            data_dir=resolve_relative_path(repo_root, data_dir, label="paths.data"),
            assignments_dir=resolve_relative_path(
                repo_root,
                assignments_dir,
                label="paths.assignments",
            ),
            quizzes_dir=resolve_relative_path(repo_root, quizzes_dir, label="paths.quizzes"),
            env_file=require_string(env_file, label="paths.environment"),
        )
