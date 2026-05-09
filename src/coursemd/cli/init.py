"""Initialization command for the package CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import click
import typer

from coursemd.core.config import (
    CONFIG_FILENAME,
    DEFAULT_INIT_ASSIGNMENTS_DIR,
    DEFAULT_INIT_DATA_DIR,
    DEFAULT_INIT_QUIZZES_DIR,
    DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH,
    DEFAULT_INIT_SITE_BASE_URL,
    DEFAULT_INIT_SITE_PROJECT_DIR,
    DEFAULT_INIT_TIMEZONE,
    build_default_config_text,
)
from coursemd.integrations.canvas.config import (
    DEFAULT_CANVAS_BASE_URL,
    DEFAULT_INIT_CANVAS_COURSE_ID,
)
from coursemd.integrations.slides.config import DEFAULT_INIT_SLIDES_DIR


def register_init_command(app: typer.Typer) -> None:
    @app.command("init")
    def init_command(
        directory: Annotated[
            Path,
            typer.Argument(
                resolve_path=True,
                file_okay=False,
                dir_okay=True,
                help="Directory where the starter .coursemd.yml should be created.",
            ),
        ] = Path("."),
        site_base_url: Annotated[
            str,
            typer.Option("--site-base-url", help="Starter site base URL to write into the config."),
        ] = DEFAULT_INIT_SITE_BASE_URL,
        site_project_dir: Annotated[
            str,
            typer.Option(
                "--site-project-dir", help="Relative path to the MkDocs project directory."
            ),
        ] = DEFAULT_INIT_SITE_PROJECT_DIR,
        site_assignments_url_path: Annotated[
            str,
            typer.Option(
                "--site-assignments-url-path",
                help="URL path where assignment pages should be published.",
            ),
        ] = DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH,
        slides_dir: Annotated[
            str,
            typer.Option("--slides-dir", help="Relative path to the Quarto slides directory."),
        ] = DEFAULT_INIT_SLIDES_DIR,
        canvas_base_url: Annotated[
            str,
            typer.Option(
                "--canvas-base-url", help="Starter Canvas base URL to write into the config."
            ),
        ] = DEFAULT_CANVAS_BASE_URL,
        canvas_course_id: Annotated[
            str,
            typer.Option(
                "--canvas-course-id", help="Starter Canvas course ID to write into the config."
            ),
        ] = DEFAULT_INIT_CANVAS_COURSE_ID,
        include_canvas: Annotated[
            bool,
            typer.Option(
                "--include-canvas", help="Include Canvas sync settings in the starter config."
            ),
        ] = False,
        data_dir: Annotated[
            str,
            typer.Option("--data-dir", help="Relative path to the course data directory."),
        ] = DEFAULT_INIT_DATA_DIR,
        assignments_dir: Annotated[
            str,
            typer.Option("--assignments-dir", help="Relative path to the assignments directory."),
        ] = DEFAULT_INIT_ASSIGNMENTS_DIR,
        quizzes_dir: Annotated[
            str,
            typer.Option("--quizzes-dir", help="Relative path to the quizzes directory."),
        ] = DEFAULT_INIT_QUIZZES_DIR,
        env_file: Annotated[
            str,
            typer.Option("--env-file", help="Repository-local env file to auto-load for secrets."),
        ] = ".env",
        timezone: Annotated[
            str,
            typer.Option(
                "--timezone",
                help="IANA timezone for course dates, e.g. America/New_York.",
            ),
        ] = DEFAULT_INIT_TIMEZONE,
        force: Annotated[
            bool,
            typer.Option(
                "--force", help="Overwrite an existing .coursemd.yml in the target directory."
            ),
        ] = False,
    ) -> int:
        target_dir = directory.resolve()
        if not target_dir.exists():
            raise click.ClickException(f"Directory does not exist: {target_dir}")

        config_path = target_dir / CONFIG_FILENAME
        if config_path.exists() and not force:
            raise click.ClickException(
                f"{config_path} already exists. Use --force to overwrite it."
            )

        config_text = build_default_config_text(
            site_base_url=site_base_url,
            site_project_dir=site_project_dir,
            site_assignments_url_path=site_assignments_url_path,
            slides_dir=slides_dir,
            canvas_base_url=canvas_base_url,
            canvas_course_id=canvas_course_id,
            data_dir=data_dir,
            assignments_dir=assignments_dir,
            quizzes_dir=quizzes_dir,
            env_file=env_file,
            timezone=timezone,
            include_canvas=include_canvas,
        )
        config_path.write_text(config_text, encoding="utf-8")
        typer.echo(f"Wrote starter config to {config_path}")
        return 0
