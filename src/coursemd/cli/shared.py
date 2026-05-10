"""Shared helpers for coursemd CLI entrypoints."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import typer

from coursemd.core.config import CourseConfig
from coursemd.core.loaders.repository import load_repository_env
from coursemd.core.utils import set_course_timezone


@dataclass
class AppState:
    config: CourseConfig

    @property
    def repo_root(self) -> Path:
        return self.config.repo_root

    @classmethod
    def load(cls, start_dir: Path | None = None) -> AppState:
        config = CourseConfig.load(start_dir=start_dir)
        load_repository_env(config.repo_root, filename=config.paths.env_file, override=False)
        set_course_timezone(config.timezone)
        return cls(config=config)

    @classmethod
    def from_typer(cls, ctx: typer.Context) -> AppState:
        if isinstance(ctx.obj, AppState):
            return ctx.obj
        state = cls.load()
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


def write_json_output(output_json: Path | None, results: list[dict[str, Any]]) -> None:
    if output_json is None:
        return
    output_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    typer.echo(f"\nWrote JSON results to {output_json}")


