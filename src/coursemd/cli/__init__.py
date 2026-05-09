"""CLI package exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

import click
import typer

_APP_EXPORTS = {
    "AppState",
    "app",
    "canvas_app",
    "github_app",
    "main",
    "main_callback",
    "site_app",
    "slides_app",
}

__all__ = sorted(
    _APP_EXPORTS
    | {
        "typer",
        "_is_optional_dependency_error",
        "_load_register_function",
        "_optional_dependency_message",
        "_register_optional_group_commands",
        "_register_unavailable_command",
    }
)


def _load_register_function(module_name: str, function_name: str) -> Any:
    module = import_module(module_name)
    return getattr(module, function_name)


def _is_optional_dependency_error(exc: ModuleNotFoundError, module_names: set[str]) -> bool:
    module_name = exc.name or ""
    return any(module_name == name or module_name.startswith(f"{name}.") for name in module_names)


def _optional_dependency_message(
    extra_name: str,
    command_paths: list[str] | tuple[str, ...],
) -> str:
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
    loaders: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    fallback_commands: list[str] | tuple[str, ...],
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


def main(*args: Any, **kwargs: Any) -> int:
    module = import_module("coursemd.cli.bootstrap")
    bootstrap_main = getattr(module, "main")
    return int(bootstrap_main(*args, **kwargs))


def __getattr__(name: str) -> Any:
    if name in _APP_EXPORTS:
        module = import_module("coursemd.cli.bootstrap")
        return getattr(module, name)
    raise AttributeError(f"module 'coursemd.cli' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _APP_EXPORTS)
