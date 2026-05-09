"""Slides CLI commands."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import click
import typer

from coursemd.cli.shared import get_state, slides_dir

DEFAULT_SLIDES_OUTPUT_DIR = Path("build/slides/html")


def _require_slides_dir(directory: Path) -> Path:
    if not directory.is_dir():
        raise click.ClickException(f"Slides directory not found: {directory}")
    config_file = directory / "_quarto.yml"
    if not config_file.is_file():
        raise click.ClickException(f"Quarto config file not found: {config_file}")
    return directory


def _default_output_dir(repo_root: Path) -> Path:
    return (repo_root / DEFAULT_SLIDES_OUTPUT_DIR).resolve()


def _run_quarto(
    *,
    slides_directory: Path,
    quarto_command: str,
    output_dir: Path,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [
                "quarto",
                quarto_command,
                ".",
                "--output-dir",
                str(output_dir),
            ],
            cwd=slides_directory,
            check=False,
        )
    except FileNotFoundError as exc:
        raise click.ClickException(
            "quarto is required for slides commands but was not found on PATH."
        ) from exc
    return completed.returncode


def register_slides_commands(slides_app: typer.Typer) -> None:
    @slides_app.command("build")
    def build_command(
        ctx: typer.Context,
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                resolve_path=True,
                file_okay=False,
                dir_okay=True,
                help="Directory where Quarto should write the built slides.",
            ),
        ] = None,
    ) -> int:
        state = get_state(ctx)
        directory = _require_slides_dir(slides_dir(state))
        resolved_output_dir = (
            _default_output_dir(state.repo_root)
            if output_dir is None
            else output_dir
            if output_dir.is_absolute()
            else (state.repo_root / output_dir).resolve()
        )
        return _run_quarto(
            slides_directory=directory,
            quarto_command="render",
            output_dir=resolved_output_dir,
        )

    @slides_app.command("preview")
    def preview_command(
        ctx: typer.Context,
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                resolve_path=True,
                file_okay=False,
                dir_okay=True,
                help="Directory where Quarto should write preview slides.",
            ),
        ] = None,
    ) -> int:
        state = get_state(ctx)
        directory = _require_slides_dir(slides_dir(state))
        resolved_output_dir = (
            _default_output_dir(state.repo_root)
            if output_dir is None
            else output_dir
            if output_dir.is_absolute()
            else (state.repo_root / output_dir).resolve()
        )
        return _run_quarto(
            slides_directory=directory,
            quarto_command="preview",
            output_dir=resolved_output_dir,
        )


__all__ = ["DEFAULT_SLIDES_OUTPUT_DIR", "register_slides_commands", "subprocess"]
