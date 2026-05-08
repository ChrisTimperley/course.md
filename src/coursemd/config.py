"""Configuration discovery and loading for coursemd repositories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import click
import yaml

from coursemd.constants import DEFAULT_CANVAS_BASE_URL
from coursemd.services.github_setup import (
    DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
    DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG,
    DEFAULT_GITHUB_RULESET_NAME,
)
from coursemd.utils import DEFAULT_TIMEZONE

CONFIG_FILENAME = ".coursemd.yml"
DEFAULT_INIT_SITE_BASE_URL = "https://example.edu/course"
DEFAULT_INIT_SITE_BACKEND = "mkdocs"
DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH = "assignments"
DEFAULT_INIT_CANVAS_COURSE_ID = "12345"
DEFAULT_INIT_SITE_PROJECT_DIR = "website"
DEFAULT_INIT_SLIDES_DIR = "slides"
DEFAULT_INIT_DATA_DIR = "data"
DEFAULT_INIT_ASSIGNMENTS_DIR = "assignments"
DEFAULT_INIT_QUIZZES_DIR = "quizzes"
DEFAULT_INIT_TIMEZONE = DEFAULT_TIMEZONE


@dataclass(frozen=True)
class CoursemdCanvasConfig:
    base_url: str
    course_id: str
    group_category_id: int | None = None


@dataclass(frozen=True)
class CoursemdSlidesConfig:
    directory: Path


@dataclass(frozen=True)
class CoursemdGithubConfig:
    organization: str
    instructors_team_slug: str = DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG
    ruleset_name: str = DEFAULT_GITHUB_RULESET_NAME
    default_repository_permission: str = DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION


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
    site_backend: str
    site_base_url: str
    site_project_dir: Path
    site_assignments_url_path: str
    slides: CoursemdSlidesConfig
    github: CoursemdGithubConfig | None
    canvas: CoursemdCanvasConfig | None
    paths: CoursemdPathsConfig


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise click.ClickException(f"{label} must be a mapping in {CONFIG_FILENAME}.")
    return value


def _optional_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    return _require_mapping(value, label=label)


def _require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise click.ClickException(f"{label} must be a non-empty string in {CONFIG_FILENAME}.")
    return value.strip()


def _require_text(value: Any, *, label: str) -> str:
    if value is None or isinstance(value, bool):
        raise click.ClickException(
            f"{label} must be a non-empty string or integer in {CONFIG_FILENAME}."
        )
    text = str(value).strip()
    if not text:
        raise click.ClickException(
            f"{label} must be a non-empty string or integer in {CONFIG_FILENAME}."
        )
    return text


def _optional_int(value: Any, *, label: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(f"{label} must be an integer in {CONFIG_FILENAME}.") from exc


def _resolve_relative_path(repo_root: Path, raw_path: Any, *, label: str) -> Path:
    path_value = _require_string(raw_path, label=label)
    return (repo_root / path_value).resolve()


def _require_permission(value: Any, *, label: str) -> str:
    permission = _require_string(value, label=label)
    if permission not in {"none", "read", "write", "admin"}:
        raise click.ClickException(
            f"{label} must be one of none, read, write, or admin in {CONFIG_FILENAME}."
        )
    return permission


def _require_url_path(value: Any, *, label: str) -> str:
    path = _require_string(value, label=label).strip("/")
    if not path:
        raise click.ClickException(f"{label} must not be empty in {CONFIG_FILENAME}.")
    return path


def _require_timezone(value: Any, *, label: str) -> str:
    timezone_name = _require_string(value, label=label)
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise click.ClickException(
            f"{label} must be a valid IANA timezone in {CONFIG_FILENAME} "
            "(example: America/New_York)."
        ) from exc
    return timezone_name


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
    config_path = discover_config_path(start_dir=start_dir)
    repo_root = config_path.parent

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw_config = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise click.ClickException(f"{config_path}: invalid YAML: {exc}") from exc

    config_map = _require_mapping(raw_config, label="Top-level config")
    site_map = _require_mapping(config_map.get("site"), label="site")
    slides_map = _optional_mapping(config_map.get("slides"), label="slides")
    github_map = _optional_mapping(config_map.get("github"), label="github")
    canvas_map = _optional_mapping(config_map.get("canvas"), label="canvas")
    paths_map = _require_mapping(config_map.get("paths"), label="paths")

    env_file = paths_map.get("env_file", ".env")
    if env_file is not None and (not isinstance(env_file, str) or not env_file.strip()):
        raise click.ClickException(
            f"paths.env_file must be a non-empty string in {CONFIG_FILENAME}."
        )

    github_config: CoursemdGithubConfig | None = None
    if github_map:
        github_config = CoursemdGithubConfig(
            organization=_require_string(
                github_map.get("organization"), label="github.organization"
            ),
            instructors_team_slug=_require_string(
                github_map.get("instructors_team_slug", DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG),
                label="github.instructors_team_slug",
            ),
            ruleset_name=_require_string(
                github_map.get("ruleset_name", DEFAULT_GITHUB_RULESET_NAME),
                label="github.ruleset_name",
            ),
            default_repository_permission=_require_permission(
                github_map.get(
                    "default_repository_permission",
                    DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
                ),
                label="github.default_repository_permission",
            ),
        )

    canvas_config: CoursemdCanvasConfig | None = None
    if canvas_map:
        canvas_config = CoursemdCanvasConfig(
            base_url=_require_string(canvas_map.get("base_url"), label="canvas.base_url"),
            course_id=_require_text(canvas_map.get("course_id"), label="canvas.course_id"),
            group_category_id=_optional_int(
                canvas_map.get("group_category_id"),
                label="canvas.group_category_id",
            ),
        )

    return CoursemdConfig(
        config_path=config_path,
        repo_root=repo_root,
        timezone=_require_timezone(
            config_map.get("timezone", DEFAULT_INIT_TIMEZONE),
            label="timezone",
        ),
        site_backend=_require_string(
            site_map.get("backend", DEFAULT_INIT_SITE_BACKEND),
            label="site.backend",
        ),
        site_base_url=_require_string(site_map.get("base_url"), label="site.base_url"),
        site_project_dir=_resolve_relative_path(
            repo_root,
            site_map.get("project_dir", DEFAULT_INIT_SITE_PROJECT_DIR),
            label="site.project_dir",
        ),
        site_assignments_url_path=_require_url_path(
            site_map.get("assignments_url_path", DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH),
            label="site.assignments_url_path",
        ),
        slides=CoursemdSlidesConfig(
            directory=_resolve_relative_path(
                repo_root,
                slides_map.get("dir", slides_map.get("project_dir", DEFAULT_INIT_SLIDES_DIR)),
                label="slides.dir",
            ),
        ),
        github=github_config,
        canvas=canvas_config,
        paths=CoursemdPathsConfig(
            data_dir=_resolve_relative_path(
                repo_root, paths_map.get("data_dir"), label="paths.data_dir"
            ),
            assignments_dir=_resolve_relative_path(
                repo_root,
                paths_map.get("assignments_dir"),
                label="paths.assignments_dir",
            ),
            quizzes_dir=_resolve_relative_path(
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
    timezone = _require_timezone(timezone, label="timezone")
    config: dict[str, Any] = {
        "timezone": timezone,
        "site": {
            "backend": site_backend,
            "base_url": site_base_url,
            "project_dir": site_project_dir,
            "assignments_url_path": site_assignments_url_path,
        },
        "slides": {
            "dir": slides_dir,
        },
        "paths": {
            "data_dir": data_dir,
            "assignments_dir": assignments_dir,
            "quizzes_dir": quizzes_dir,
        },
    }
    if include_canvas:
        config["canvas"] = {
            "base_url": canvas_base_url,
            "course_id": canvas_course_id,
        }
    if github_org is not None:
        config["github"] = {
            "organization": github_org,
            "instructors_team_slug": github_instructors_team_slug,
            "ruleset_name": github_ruleset_name,
            "default_repository_permission": github_default_repository_permission,
        }
    if env_file != ".env":
        config["paths"]["env_file"] = env_file
    return cast(str, yaml.safe_dump(config, sort_keys=False))
