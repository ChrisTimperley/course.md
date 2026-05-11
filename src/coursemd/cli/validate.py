"""Validate repository content for the package CLI."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer

from coursemd.cli.shared import (
    AppState,
    click_error_boundary,
    default_assignment_files,
    default_data_files,
    default_quiz_files,
    normalize_input_paths,
    require_paths_exist,
)
from coursemd.core.models.repository import CourseRepository


def register_validate_command(app: typer.Typer) -> None:
    @app.command()
    def validate(
        ctx: typer.Context,
        assignment_files: Annotated[
            list[Path] | None,
            typer.Option(
                "--assignment-file",
                help=(
                    "Assignment Markdown files to validate. "
                    "Defaults to the configured assignments_dir."
                ),
            ),
        ] = None,
        quiz_files: Annotated[
            list[Path] | None,
            typer.Option(
                "--quiz-file",
                help="Quiz Markdown files to validate. Defaults to the configured quizzes_dir.",
            ),
        ] = None,
        data_files: Annotated[
            list[Path] | None,
            typer.Option(
                "--data-file",
                help="YAML data files to validate. Defaults to the configured data_dir.",
            ),
        ] = None,
    ) -> int:
        with click_error_boundary():
            state = AppState.from_typer(ctx)
            repo_root = state.repo_root
            resolved_assignment_files = normalize_input_paths(
                assignment_files or default_assignment_files(state),
                repo_root=repo_root,
            )
            resolved_quiz_files = normalize_input_paths(
                quiz_files or default_quiz_files(state),
                repo_root=repo_root,
            )
            resolved_data_files = normalize_input_paths(
                data_files or default_data_files(state),
                repo_root=repo_root,
            )

            require_paths_exist(resolved_assignment_files, label="Assignment")
            require_paths_exist(resolved_quiz_files, label="Quiz")
            require_paths_exist(resolved_data_files, label="Data")

            repository = CourseRepository.build(
                state.config,
                data_files=resolved_data_files,
                assignment_files=resolved_assignment_files,
                quiz_files=resolved_quiz_files,
            )

        typer.echo(
            f"Validated {len(resolved_data_files)} data file(s), "
            f"{len(repository.assignments)} assignment spec(s), and "
            f"{len(repository.quizzes)} quiz spec(s)."
        )
        typer.echo("Validation passed.")
        return 0
