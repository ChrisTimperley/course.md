"""Shared helpers for the package CLI."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import typer

from coursemd.config import CoursemdConfig, load_coursemd_config
from coursemd.loaders.repository import load_repository_env
from coursemd.utils import set_course_timezone


@dataclass
class AppState:
    config: CoursemdConfig

    @property
    def repo_root(self) -> Path:
        return self.config.repo_root


def load_app_state(start_dir: Path | None = None) -> AppState:
    config = load_coursemd_config(start_dir=start_dir)
    load_repository_env(config.repo_root, filename=config.paths.env_file, override=False)
    set_course_timezone(config.timezone)
    return AppState(config=config)


def get_state(ctx: typer.Context) -> AppState:
    if isinstance(ctx.obj, AppState):
        return ctx.obj
    state = load_app_state()
    ctx.obj = state
    return state


def require_paths_exist(paths: Sequence[Path], *, label: str) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise click.ClickException(f"{label} file(s) not found: {', '.join(missing)}")


def normalize_input_paths(paths: Sequence[Path], *, repo_root: Path) -> list[Path]:
    normalized: list[Path] = []
    for path in paths:
        normalized.append(path if path.is_absolute() else (repo_root / path).resolve())
    return normalized


def default_data_files(state: AppState) -> list[Path]:
    if not state.config.paths.data_dir.exists():
        return []
    return sorted(state.config.paths.data_dir.glob("*.yaml"))


def default_assignment_files(state: AppState) -> list[Path]:
    if not state.config.paths.assignments_dir.exists():
        return []
    return sorted(
        path for path in state.config.paths.assignments_dir.glob("*.md") if path.name != "index.md"
    )


def default_quiz_files(state: AppState) -> list[Path]:
    if not state.config.paths.quizzes_dir.exists():
        return []
    return sorted(
        path for path in state.config.paths.quizzes_dir.glob("*.md") if path.name != "index.md"
    )


def site_project_dir(state: AppState) -> Path:
    return state.config.site_project_dir


def slides_dir(state: AppState) -> Path:
    return state.config.slides.directory


def parse_group_category_id_override() -> int | None:
    group_category_env = os.environ.get("CANVAS_GROUP_CATEGORY_ID", "").strip()
    if not group_category_env:
        return None
    try:
        return int(group_category_env)
    except ValueError:
        return None


def require_canvas_credentials(course_id: str | None, *, plan_only: bool) -> tuple[str, str]:
    if plan_only:
        return "", course_id or ""
    if not course_id:
        raise click.ClickException(
            "course_id is required unless --plan-only is used. "
            "Set it in .coursemd.yml or pass --course-id."
        )
    token = os.environ.get("CANVAS_TOKEN", "").strip()
    if not token:
        raise click.ClickException("CANVAS_TOKEN must be set unless --plan-only is used.")
    return token, course_id


def write_json_output(output_json: Path | None, results: list[dict[str, Any]]) -> None:
    if output_json is None:
        return
    output_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    typer.echo(f"\nWrote JSON results to {output_json}")
