"""Course repository configuration loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Self, TypeVar

import yaml

from coursemd.core.config.paths import CoursePathsConfig
from coursemd.core.config.schedule import ScheduleConfig
from coursemd.core.config_helpers import (
    CONFIG_FILENAME,
    require_mapping,
    require_timezone,
    resolve_relative_path,
)
from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.integration_config import IntegrationConfig, IntegrationConfigContext
from coursemd.core.models.staff import StaffMember
from coursemd.core.utils import DEFAULT_TIMEZONE as COURSE_DEFAULT_TIMEZONE
from coursemd.integrations import load_builtin_integration_configs

T = TypeVar("T", bound=IntegrationConfig)


@dataclass(frozen=True)
class CourseConfig:
    DEFAULT_DATA_DIR: ClassVar[str] = "data"
    DEFAULT_ASSIGNMENTS_DIR: ClassVar[str] = "assignments"
    DEFAULT_QUIZZES_DIR: ClassVar[str] = "quizzes"
    DEFAULT_TIMEZONE: ClassVar[str] = COURSE_DEFAULT_TIMEZONE

    config_path: Path
    repo_root: Path
    timezone: str
    integrations: dict[str, IntegrationConfig]
    paths: CoursePathsConfig
    staff: list[StaffMember] = field(default_factory=list)
    schedule: ScheduleConfig | None = None

    def get_integration(self, name: str, config_type: type[T]) -> T | None:
        value = self.integrations.get(name)
        if value is None:
            return None
        if not isinstance(value, config_type):
            raise CoursemdValidationError(
                f"Integration {name!r} is not of expected type {config_type.__name__}."
            )
        return value

    @staticmethod
    def _load_integrations(
        integrations_map: dict[str, Any],
        *,
        repo_root: Path,
    ) -> dict[str, IntegrationConfig]:
        context = IntegrationConfigContext(repo_root=repo_root)
        raw_integrations: dict[str, Any] = {}

        for raw_name, raw_value in integrations_map.items():
            if not raw_name.strip():
                raise CoursemdValidationError(
                    f"integrations keys must be non-empty strings in {CONFIG_FILENAME}."
                )
            config_type = IntegrationConfig.get_type(raw_name)
            if config_type is None:
                supported = ", ".join(
                    sorted(config_type.metavar for config_type in IntegrationConfig.iter_types())
                )
                raise CoursemdValidationError(
                    f"Unknown integration {raw_name!r} in {CONFIG_FILENAME}. "
                    f"Supported integrations: {supported}."
                )
            if config_type.metavar in raw_integrations:
                raise CoursemdValidationError(
                    f"Integration {config_type.metavar!r} is configured more than once in "
                    f"{CONFIG_FILENAME}."
                )
            raw_integrations[config_type.metavar] = raw_value

        integrations: dict[str, IntegrationConfig] = {}
        for config_type in IntegrationConfig.iter_types():
            raw_value = raw_integrations.get(config_type.metavar)
            if raw_value is None:
                if config_type.required:
                    raise CoursemdValidationError(
                        f"integrations.{config_type.metavar} is required in {CONFIG_FILENAME}."
                    )
                continue
            integrations[config_type.metavar] = config_type.parse(raw_value, context=context)

        return integrations

    @staticmethod
    def discover_path(start_dir: Path | None = None) -> Path:
        current_dir = (start_dir or Path.cwd()).resolve()
        for directory in (current_dir, *current_dir.parents):
            config_path = directory / CONFIG_FILENAME
            if config_path.is_file():
                return config_path
        raise CoursemdValidationError(
            f"Could not find {CONFIG_FILENAME} in {current_dir} or any parent directory."
        )

    @classmethod
    def load(cls, start_dir: Path | None = None) -> Self:
        load_builtin_integration_configs()
        config_path = cls.discover_path(start_dir=start_dir)
        repo_root = config_path.parent

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                loaded_config = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise CoursemdValidationError(f"invalid YAML: {exc}", source_path=config_path) from exc

        raw_config: Any = {} if loaded_config is None else loaded_config

        config_map = require_mapping(raw_config, label="Top-level config")
        integrations_map = require_mapping(config_map.get("integrations"), label="integrations")
        paths_map = require_mapping(config_map.get("paths"), label="paths")
        schedule = (
            ScheduleConfig.parse(config_map["schedule"]) if "schedule" in config_map else None
        )

        env_file = paths_map.get("env_file", ".env")
        if env_file is not None and (not isinstance(env_file, str) or not env_file.strip()):
            raise CoursemdValidationError(
                f"paths.env_file must be a non-empty string in {CONFIG_FILENAME}."
            )

        return cls(
            config_path=config_path,
            repo_root=repo_root,
            timezone=require_timezone(
                config_map.get("timezone", cls.DEFAULT_TIMEZONE),
                label="timezone",
            ),
            integrations=cls._load_integrations(integrations_map, repo_root=repo_root),
            paths=CoursePathsConfig(
                data_dir=resolve_relative_path(
                    repo_root,
                    paths_map.get("data_dir"),
                    label="paths.data_dir",
                ),
                assignments_dir=resolve_relative_path(
                    repo_root,
                    paths_map.get("assignments_dir"),
                    label="paths.assignments_dir",
                ),
                quizzes_dir=resolve_relative_path(
                    repo_root,
                    paths_map.get("quizzes_dir"),
                    label="paths.quizzes_dir",
                ),
                env_file=env_file.strip() if isinstance(env_file, str) else ".env",
            ),
            staff=StaffMember.from_list(config_map.get("staff")),
            schedule=schedule,
        )
