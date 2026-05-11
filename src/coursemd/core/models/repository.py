"""Repository-level course model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from coursemd.core.loaders.quizzes import load_quiz_specs
from coursemd.core.loaders.repository import load_data_files
from coursemd.core.loaders.specs import load_assignment_specs

if TYPE_CHECKING:
    from pathlib import Path

    from coursemd.core.config import CourseConfig, CoursePathsConfig
    from coursemd.core.integration_config import IntegrationConfig
    from coursemd.core.models.assignment import AssignmentSpec
    from coursemd.core.models.quiz import QuizSpec

T = TypeVar("T", bound="IntegrationConfig")


def _default_data_files(config: CourseConfig) -> list[Path]:
    if not config.paths.data_dir.is_dir():
        return []
    return sorted(
        path
        for path in config.paths.data_dir.iterdir()
        if path.is_file() and path.suffix in {".yaml", ".yml"}
    )


def _default_assignment_files(config: CourseConfig) -> list[Path]:
    if not config.paths.assignments_dir.is_dir():
        return []
    return sorted(
        path for path in config.paths.assignments_dir.glob("*.md") if path.name != "index.md"
    )


def _default_quiz_files(config: CourseConfig) -> list[Path]:
    if not config.paths.quizzes_dir.is_dir():
        return []
    return sorted(
        path for path in config.paths.quizzes_dir.glob("*.md") if path.name != "index.md"
    )


@dataclass(frozen=True)
class CourseRepository:
    """A loaded course repository as a coherent object graph."""

    config: CourseConfig
    data: dict[str, Any] = field(default_factory=dict)
    assignments: list[AssignmentSpec] = field(default_factory=list)
    quizzes: list[QuizSpec] = field(default_factory=list)

    @property
    def repo_root(self) -> Path:
        return self.config.repo_root

    @property
    def timezone(self) -> str:
        return self.config.timezone

    @property
    def paths(self) -> CoursePathsConfig:
        return self.config.paths

    def get_integration(self, name: str, config_type: type[T]) -> T | None:
        return self.config.get_integration(name, config_type)

    @classmethod
    def build(
        cls,
        config: CourseConfig,
        *,
        data_files: list[Path] | None = None,
        assignment_files: list[Path] | None = None,
        quiz_files: list[Path] | None = None,
    ) -> CourseRepository:
        """Build a repository from a config, discovering files from configured paths."""
        resolved_data_files = data_files if data_files is not None else _default_data_files(config)
        resolved_assignment_files = (
            assignment_files if assignment_files is not None else _default_assignment_files(config)
        )
        resolved_quiz_files = (
            quiz_files if quiz_files is not None else _default_quiz_files(config)
        )

        return cls(
            config=config,
            data=load_data_files(resolved_data_files),
            assignments=load_assignment_specs(resolved_assignment_files),
            quizzes=load_quiz_specs(resolved_quiz_files),
        )
