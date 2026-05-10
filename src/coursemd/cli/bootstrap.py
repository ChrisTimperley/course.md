"""Typer-based package CLI for course automation workflows."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import click
import typer

from coursemd.cli.shared import AppState as AppState
from coursemd.cli.validate import register_validate_command
from coursemd.integrations import register_integration_clis

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Course automation CLI for data-driven course repositories.",
)
register_validate_command(app)
register_integration_clis(app)


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
    state = AppState.load(start_dir=start_dir) if start_dir is not None else None
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


