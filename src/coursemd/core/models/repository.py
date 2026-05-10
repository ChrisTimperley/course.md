"""Repository-level course model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from coursemd.core.models.assignment import AssignmentSpec
from coursemd.core.models.quiz import QuizSpec
from coursemd.core.types import AssignmentDict, QuizDict

if TYPE_CHECKING:
    from coursemd.core.config import CourseConfig


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

    repo_root: Path
    data: dict[str, Any] = field(default_factory=dict)
    assignments: list[AssignmentSpec] = field(default_factory=list)
    quizzes: list[QuizSpec] = field(default_factory=list)
    schedule_assignments: list[AssignmentDict] = field(default_factory=list)
    schedule_quizzes: list[QuizDict] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        config: CourseConfig,
        *,
        data_files: list[Path] | None = None,
        assignment_files: list[Path] | None = None,
        quiz_files: list[Path] | None = None,
        site_base_url: str | None = None,
        require_canvas_fields: bool = False,
    ) -> CourseRepository:
        """Build a repository from a config, discovering files from configured paths."""
        from coursemd.core.loaders.assignments import load_assignment_specs
        from coursemd.core.loaders.quizzes import load_quiz_specs
        from coursemd.core.loaders.repository import (
            load_data_files,
            load_schedule_assignments,
            load_schedule_quizzes,
        )
        from coursemd.integrations.canvas.config import CanvasConfig
        from coursemd.integrations.mkdocs.config import MkdocsIntegrationConfig

        mkdocs_cfg = MkdocsIntegrationConfig.require(config)
        canvas_cfg = CanvasConfig.get(config)
        resolved_site_base_url = site_base_url or mkdocs_cfg.base_url
        assignment_url_path = mkdocs_cfg.assignments_url_path
        canvas_base_url = canvas_cfg.base_url if canvas_cfg is not None else ""

        resolved_data_files = data_files if data_files is not None else _default_data_files(config)
        resolved_assignment_files = (
            assignment_files if assignment_files is not None else _default_assignment_files(config)
        )
        resolved_quiz_files = (
            quiz_files if quiz_files is not None else _default_quiz_files(config)
        )

        data = load_data_files(resolved_data_files)
        schedule_map = cast("dict[str, Any]", data.get("schedule", {}))
        course_map = cast("dict[str, Any]", schedule_map.get("course", {}))

        return cls(
            repo_root=config.repo_root,
            data=data,
            assignments=load_assignment_specs(
                resolved_assignment_files,
                site_base_url=resolved_site_base_url,
                assignment_url_path=assignment_url_path,
                require_canvas_fields=require_canvas_fields,
            ),
            quizzes=load_quiz_specs(
                resolved_quiz_files,
                require_canvas_fields=require_canvas_fields,
            ),
            schedule_assignments=load_schedule_assignments(
                resolved_assignment_files,
                assignment_url_path=assignment_url_path,
            ),
            schedule_quizzes=load_schedule_quizzes(
                resolved_quiz_files,
                canvas_base_url=canvas_base_url,
                canvas_course_id=course_map.get("canvas_course_id"),
            ),
        )
