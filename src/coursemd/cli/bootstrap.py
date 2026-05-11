"""Typer-based package CLI for course automation workflows."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import click
import typer

from coursemd.cli.shared import AppState
from coursemd.cli.validate import register_validate_command
from coursemd.integrations import register_integration_clis

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Course automation CLI for data-driven course repositories.",
)
register_validate_command(app)
register_integration_clis(app)


@app.callback()
def main_callback(ctx: typer.Context) -> None:  # noqa: ARG001
    return None


def _is_core_error(exc: Exception) -> bool:
    return any(
        cls.__name__ == "CoursemdError" and cls.__module__ == "coursemd.core.exceptions"
        for cls in exc.__class__.__mro__
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    prog: str = "coursemd",
    start_dir: Path | None = None,
) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    try:
        state = AppState.load(start_dir=start_dir) if start_dir is not None else None
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
    except Exception as exc:  # noqa: BLE001
        if _is_core_error(exc):
            click.ClickException(str(exc)).show(file=sys.stderr)
            return 1
        typer.echo(f"Error: {exc}", err=True)
        return 1


