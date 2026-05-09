"""Configuration discovery and loading for coursemd repositories."""

from __future__ import annotations

__all__ = [
    "CourseConfig",
    "CoursePathsConfig",
]

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Self, TypeVar

import click
import yaml

from ..integrations import load_builtin_integration_configs
from .config_helpers import (
    CONFIG_FILENAME,
    require_mapping,
    require_timezone,
    resolve_relative_path,
)
from .integration_config import (
    IntegrationConfig,
    IntegrationConfigContext,
)
from .utils import DEFAULT_TIMEZONE as COURSE_DEFAULT_TIMEZONE

T = TypeVar("T", bound=IntegrationConfig)


@dataclass(frozen=True)
class CoursePathsConfig:
    data_dir: Path
    assignments_dir: Path
    quizzes_dir: Path
    env_file: str = ".env"


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

    def get_integration(self, name: str, config_type: type[T]) -> T | None:
        value = self.integrations.get(name)
        if value is None:
            return None
        if not isinstance(value, config_type):
            raise TypeError(
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
                raise click.ClickException(
                    f"integrations keys must be non-empty strings in {CONFIG_FILENAME}."
                )
            config_type = IntegrationConfig.get_type(raw_name)
            if config_type is None:
                supported = ", ".join(
                    sorted(config_type.metavar for config_type in IntegrationConfig.iter_types())
                )
                raise click.ClickException(
                    f"Unknown integration {raw_name!r} in {CONFIG_FILENAME}. "
                    f"Supported integrations: {supported}."
                )
            if config_type.metavar in raw_integrations:
                raise click.ClickException(
                    f"Integration {config_type.metavar!r} is configured more than once in "
                    f"{CONFIG_FILENAME}."
                )
            raw_integrations[config_type.metavar] = raw_value

        integrations: dict[str, IntegrationConfig] = {}
        for config_type in IntegrationConfig.iter_types():
            raw_value = raw_integrations.get(config_type.metavar)
            if raw_value is None:
                if config_type.required:
                    raise click.ClickException(
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
        raise click.ClickException(
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
            raise click.ClickException(f"{config_path}: invalid YAML: {exc}") from exc

        raw_config: Any = {} if loaded_config is None else loaded_config

        config_map = require_mapping(raw_config, label="Top-level config")
        integrations_map = require_mapping(config_map.get("integrations"), label="integrations")
        paths_map = require_mapping(config_map.get("paths"), label="paths")

        env_file = paths_map.get("env_file", ".env")
        if env_file is not None and (not isinstance(env_file, str) or not env_file.strip()):
            raise click.ClickException(
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
        )
