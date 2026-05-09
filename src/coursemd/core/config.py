"""Configuration discovery and loading for coursemd repositories."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import click
import yaml

from ..integrations.canvas.config import DEFAULT_CANVAS_BASE_URL, DEFAULT_INIT_CANVAS_COURSE_ID
from ..integrations.github.config import (
    DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
    DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG,
    DEFAULT_GITHUB_RULESET_NAME,
)
from ..integrations.mkdocs.config import (
    DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH,
    DEFAULT_INIT_SITE_BACKEND,
    DEFAULT_INIT_SITE_BASE_URL,
    DEFAULT_INIT_SITE_PROJECT_DIR,
)
from ..integrations.slides.config import DEFAULT_INIT_SLIDES_DIR
from .config_helpers import (
    CONFIG_FILENAME,
    require_mapping,
    require_timezone,
    resolve_relative_path,
)
from .integration_config import (
    IntegrationConfigContext,
    get_integration_config_type,
    iter_integration_config_types,
)
from .utils import DEFAULT_TIMEZONE

if TYPE_CHECKING:
    from ..integrations.mkdocs.config import MkdocsIntegrationConfig

DEFAULT_INIT_DATA_DIR = "data"
DEFAULT_INIT_ASSIGNMENTS_DIR = "assignments"
DEFAULT_INIT_QUIZZES_DIR = "quizzes"
DEFAULT_INIT_TIMEZONE = DEFAULT_TIMEZONE

_BUILTIN_INTEGRATION_CONFIG_MODULES = (
    "coursemd.integrations.mkdocs.config",
    "coursemd.integrations.canvas.config",
    "coursemd.integrations.github.config",
    "coursemd.integrations.slides.config",
)
_LEGACY_INTEGRATION_KEYS = {
    "site": "integrations.mkdocs",
    "canvas": "integrations.canvas",
    "github": "integrations.github",
    "slides": "integrations.quarto",
    "quarto": "integrations.quarto",
}
_builtin_integrations_loaded = False


@dataclass(frozen=True)
class CoursemdPathsConfig:
    data_dir: Path
    assignments_dir: Path
    quizzes_dir: Path
    env_file: str = ".env"


@dataclass(frozen=True)
class CoursemdConfig:
    config_path: Path
    repo_root: Path
    timezone: str
    integrations: dict[str, object]
    paths: CoursemdPathsConfig

    def get_integration(self, name: str, config_type: type[T]) -> T | None:
        value = self.integrations.get(name)
        if value is None:
            return None
        if not isinstance(value, config_type):
            raise TypeError(
                f"Integration {name!r} is not of expected type {config_type.__name__}."
            )
        return value

    @property
    def site_backend(self) -> str:
        return self._mkdocs_config().backend

    @property
    def site_base_url(self) -> str:
        return self._mkdocs_config().base_url

    @property
    def site_project_dir(self) -> Path:
        return self._mkdocs_config().project_dir

    @property
    def site_assignments_url_path(self) -> str:
        return self._mkdocs_config().assignments_url_path

    def _mkdocs_config(self) -> MkdocsIntegrationConfig:
        from ..integrations.mkdocs.config import INTEGRATION_NAME, MkdocsIntegrationConfig

        config = self.get_integration(INTEGRATION_NAME, MkdocsIntegrationConfig)
        if config is None:
            raise RuntimeError("MkDocs integration config is required but missing.")
        return config


T = TypeVar("T")


def _load_builtin_integration_configs() -> None:
    global _builtin_integrations_loaded

    if _builtin_integrations_loaded:
        return

    for module_name in _BUILTIN_INTEGRATION_CONFIG_MODULES:
        importlib.import_module(module_name)
    _builtin_integrations_loaded = True


def _reject_legacy_integration_keys(config_map: dict[str, Any]) -> None:
    legacy_keys = [key for key in _LEGACY_INTEGRATION_KEYS if key in config_map]
    if not legacy_keys:
        return

    guidance = ", ".join(
        f"{key} -> {_LEGACY_INTEGRATION_KEYS[key]}" for key in sorted(legacy_keys)
    )
    raise click.ClickException(
        f"Moved config keys detected in {CONFIG_FILENAME}: {guidance}. "
        "Use the integrations mapping instead."
    )


def _load_integrations(
    integrations_map: dict[str, Any],
    *,
    repo_root: Path,
) -> dict[str, object]:
    context = IntegrationConfigContext(repo_root=repo_root)
    raw_integrations: dict[str, Any] = {}

    for raw_name, raw_value in integrations_map.items():
        if not raw_name.strip():
            raise click.ClickException(
                f"integrations keys must be non-empty strings in {CONFIG_FILENAME}."
            )
        config_type = get_integration_config_type(raw_name)
        if config_type is None:
            supported = ", ".join(
                sorted(config_type.metavar for config_type in iter_integration_config_types())
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

    integrations: dict[str, object] = {}
    for config_type in iter_integration_config_types():
        raw_value = raw_integrations.get(config_type.metavar)
        if raw_value is None:
            if config_type.required:
                raise click.ClickException(
                    f"integrations.{config_type.metavar} is required in {CONFIG_FILENAME}."
                )
            continue
        integrations[config_type.metavar] = config_type.parse(raw_value, context=context)

    return integrations


def discover_config_path(start_dir: Path | None = None) -> Path:
    current_dir = (start_dir or Path.cwd()).resolve()
    for directory in (current_dir, *current_dir.parents):
        config_path = directory / CONFIG_FILENAME
        if config_path.is_file():
            return config_path
    raise click.ClickException(
        f"Could not find {CONFIG_FILENAME} in {current_dir} or any parent directory."
    )


def load_coursemd_config(start_dir: Path | None = None) -> CoursemdConfig:
    _load_builtin_integration_configs()
    config_path = discover_config_path(start_dir=start_dir)
    repo_root = config_path.parent

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded_config = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise click.ClickException(f"{config_path}: invalid YAML: {exc}") from exc

    raw_config: Any = {} if loaded_config is None else loaded_config

    config_map = require_mapping(raw_config, label="Top-level config")
    _reject_legacy_integration_keys(config_map)
    integrations_map = require_mapping(config_map.get("integrations"), label="integrations")
    paths_map = require_mapping(config_map.get("paths"), label="paths")

    env_file = paths_map.get("env_file", ".env")
    if env_file is not None and (not isinstance(env_file, str) or not env_file.strip()):
        raise click.ClickException(
            f"paths.env_file must be a non-empty string in {CONFIG_FILENAME}."
        )

    return CoursemdConfig(
        config_path=config_path,
        repo_root=repo_root,
        timezone=require_timezone(
            config_map.get("timezone", DEFAULT_INIT_TIMEZONE),
            label="timezone",
        ),
        integrations=_load_integrations(integrations_map, repo_root=repo_root),
        paths=CoursemdPathsConfig(
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


def build_default_config_text(
    *,
    site_base_url: str = DEFAULT_INIT_SITE_BASE_URL,
    site_backend: str = DEFAULT_INIT_SITE_BACKEND,
    site_project_dir: str = DEFAULT_INIT_SITE_PROJECT_DIR,
    site_assignments_url_path: str = DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH,
    slides_dir: str = DEFAULT_INIT_SLIDES_DIR,
    github_org: str | None = None,
    github_instructors_team_slug: str = DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG,
    github_ruleset_name: str = DEFAULT_GITHUB_RULESET_NAME,
    github_default_repository_permission: str = DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
    canvas_base_url: str = DEFAULT_CANVAS_BASE_URL,
    canvas_course_id: str = DEFAULT_INIT_CANVAS_COURSE_ID,
    data_dir: str = DEFAULT_INIT_DATA_DIR,
    assignments_dir: str = DEFAULT_INIT_ASSIGNMENTS_DIR,
    quizzes_dir: str = DEFAULT_INIT_QUIZZES_DIR,
    env_file: str = ".env",
    timezone: str = DEFAULT_INIT_TIMEZONE,
    include_canvas: bool = False,
) -> str:
    timezone = require_timezone(timezone, label="timezone")
    integrations: dict[str, Any] = {
        "mkdocs": {
            "backend": site_backend,
            "base_url": site_base_url,
            "project_dir": site_project_dir,
            "assignments_url_path": site_assignments_url_path,
        },
        "quarto": {
            "dir": slides_dir,
        },
    }
    if include_canvas:
        integrations["canvas"] = {
            "base_url": canvas_base_url,
            "course_id": canvas_course_id,
        }
    if github_org is not None:
        integrations["github"] = {
            "organization": github_org,
            "instructors_team_slug": github_instructors_team_slug,
            "ruleset_name": github_ruleset_name,
            "default_repository_permission": github_default_repository_permission,
        }

    config: dict[str, Any] = {
        "timezone": timezone,
        "integrations": integrations,
        "paths": {
            "data_dir": data_dir,
            "assignments_dir": assignments_dir,
            "quizzes_dir": quizzes_dir,
        },
    }
    if env_file != ".env":
        config["paths"]["env_file"] = env_file
    return yaml.safe_dump(config, sort_keys=False)


__all__ = [
    "CONFIG_FILENAME",
    "CoursemdConfig",
    "CoursemdPathsConfig",
    "DEFAULT_INIT_ASSIGNMENTS_DIR",
    "DEFAULT_INIT_DATA_DIR",
    "DEFAULT_INIT_QUIZZES_DIR",
    "DEFAULT_INIT_TIMEZONE",
    "build_default_config_text",
    "discover_config_path",
    "load_coursemd_config",
]
