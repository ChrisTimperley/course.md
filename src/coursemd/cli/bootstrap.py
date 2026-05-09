"""Typer-based package CLI for course automation workflows."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from importlib import import_module
from pathlib import Path
from typing import Any

import click
import typer

from coursemd.cli.shared import AppState as AppState
from coursemd.cli.shared import load_app_state

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Course automation CLI for data-driven course repositories.",
)
canvas_app = typer.Typer(no_args_is_help=True, help="Canvas LMS workflows.")
site_app = typer.Typer(no_args_is_help=True, help="Build and preview the course website.")
slides_app = typer.Typer(no_args_is_help=True, help="Build and preview course slides.")
github_app = typer.Typer(no_args_is_help=True, help="GitHub organization workflows.")

app.add_typer(canvas_app, name="canvas")
app.add_typer(site_app, name="site")
app.add_typer(slides_app, name="slides")
app.add_typer(github_app, name="github")


def _load_register_function(module_name: str, function_name: str) -> Any:
    module = import_module(module_name)
    return getattr(module, function_name)


def _is_optional_dependency_error(exc: ModuleNotFoundError, module_names: set[str]) -> bool:
    module_name = exc.name or ""
    return any(module_name == name or module_name.startswith(f"{name}.") for name in module_names)


def _optional_dependency_message(extra_name: str, command_paths: Sequence[str]) -> str:
    commands = ", ".join(f"`{command_path}`" for command_path in command_paths)
    return (
        f"{commands} require the optional `{extra_name}` dependencies. "
        f'Install them with `pip install "coursemd[{extra_name}]"`.'
    )


def _register_unavailable_command(app: typer.Typer, command_name: str, message: str) -> None:
    @app.command(command_name)
    def unavailable_command() -> int:
        raise click.ClickException(message)


def _register_optional_group_commands(
    app: typer.Typer,
    *,
    loaders: Sequence[tuple[str, str]],
    fallback_commands: Sequence[str],
    optional_modules: set[str],
    extra_name: str,
) -> None:
    try:
        for module_name, function_name in loaders:
            _load_register_function(module_name, function_name)(app)
    except ModuleNotFoundError as exc:
        if not _is_optional_dependency_error(exc, optional_modules):
            raise
        message = _optional_dependency_message(extra_name, fallback_commands)
        for command_name in fallback_commands:
            _register_unavailable_command(app, command_name.split()[-1], message)


_load_register_function("coursemd.cli.validate", "register_validate_command")(app)
_load_register_function("coursemd.cli.init", "register_init_command")(app)
_load_register_function("coursemd.slides.cli", "register_slides_commands")(slides_app)
_load_register_function("coursemd.github.cli", "register_github_commands")(github_app)

_register_optional_group_commands(
    site_app,
    loaders=[("coursemd.mkdocs.cli", "register_site_commands")],
    fallback_commands=[
        "coursemd site build",
        "coursemd site build-preview",
        "coursemd site preview",
    ],
    optional_modules={"mkdocs"},
    extra_name="mkdocs",
)

_register_optional_group_commands(
    canvas_app,
    loaders=[
        ("coursemd.canvas.cli", "register_sync_canvas_assignments_command"),
        ("coursemd.canvas.cli", "register_sync_canvas_quizzes_command"),
    ],
    fallback_commands=[
        "coursemd canvas assignments",
        "coursemd canvas quizzes",
    ],
    optional_modules={"requests"},
    extra_name="canvas",
)


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    return None


def main(
    argv: Sequence[str] | None = None,
    *,
    prog: str = "coursemd",
    start_dir: Path | None = None,
) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    state = load_app_state(start_dir=start_dir) if start_dir is not None else None
    try:
        result = app(args=args_list, prog_name=prog, standalone_mode=False, obj=state)
        return int(result) if isinstance(result, int) else 0
    except typer.Exit as exc:
        return int(exc.exit_code)
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return int(exc.exit_code)
    except click.Abort:
        typer.echo("Aborted.", err=True)
        return 1
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        return 1


__all__ = [
    "AppState",
    "app",
    "canvas_app",
    "github_app",
    "main",
    "main_callback",
    "site_app",
    "slides_app",
    "typer",
    "_is_optional_dependency_error",
    "_load_register_function",
    "_optional_dependency_message",
    "_register_optional_group_commands",
    "_register_unavailable_command",
]
