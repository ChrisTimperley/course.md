"""Canvas quiz sync command for the package CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import click
import typer

from coursemd.adapters.canvas.frontmatter import update_quiz_frontmatter_with_canvas_id
from coursemd.adapters.canvas.quizzes import total_quiz_points
from coursemd.adapters.canvas.resources import QuizCanvasClient
from coursemd.adapters.canvas.sync import CanvasSyncEvent, sync_quizzes_to_canvas
from coursemd.cli.shared import (
    default_quiz_files,
    get_state,
    normalize_input_paths,
    require_canvas_credentials,
    require_paths_exist,
    write_json_output,
)
from coursemd.constants import DEFAULT_CANVAS_BASE_URL
from coursemd.loaders.quizzes import load_quiz_specs
from coursemd.models.quiz import QuizSpec


def _print_quiz_plan(specs: list[QuizSpec]) -> None:
    typer.echo(f"Loaded {len(specs)} quiz spec(s) for the Canvas integration:")
    for spec in specs:
        unlock = f" | unlock {spec.unlock_at}" if spec.unlock_at else ""
        readings = f" | readings={len(spec.readings)}" if spec.readings else ""
        canvas = spec.integrations.canvas
        typer.echo(
            f"- {spec.title} | type={canvas.quiz_type or '<unset>'} | due {spec.due_at} | "
            f"{total_quiz_points(spec)} pts | {len(spec.questions)} questions{readings}{unlock} | "
            f"group '{canvas.assignment_group or '<unassigned>'}' | source={spec.source_file}"
        )


def _print_canvas_sync_event(event: CanvasSyncEvent) -> None:
    if event.dry_run:
        target = event.target.replace("_", " ")
        suffix = f" '{event.name}'" if event.name else ""
        id_text = f" (id={event.id})" if event.id is not None else ""
        typer.echo(f"[dry-run] {event.action.upper()} {target}{suffix}{id_text}")
        return

    if event.action == "create" and event.target == "assignment_group":
        typer.echo(f"Creating assignment group '{event.name}'")
    elif event.action == "create" and event.target == "quiz":
        typer.echo(f"Creating quiz '{event.name}'")
    elif event.action == "update" and event.target == "quiz":
        typer.echo(f"Updating quiz '{event.name}' (id={event.id})")
    elif event.action == "skip" and event.target == "quiz":
        typer.echo(f"Skipping '{event.name}' (id={event.id}): {event.reason}")
    elif event.action == "delete" and event.target == "quiz_question":
        typer.echo(f"  Deleted question id={event.id}")
    elif event.action == "create" and event.target == "quiz_question":
        typer.echo(f"  Creating question {event.name}")


def register_sync_canvas_quizzes_command(canvas_app: typer.Typer) -> None:
    @canvas_app.command("quizzes")
    def sync_canvas_quizzes(
        ctx: typer.Context,
        quiz_files: Annotated[
            list[Path] | None,
            typer.Argument(
                help="Quiz Markdown files. Defaults to the configured quizzes_dir.",
            ),
        ] = None,
        course_id: Annotated[
            str | None,
            typer.Option(
                "--course-id",
                help="Canvas course ID. Required unless --plan-only is used.",
            ),
        ] = None,
        base_url: Annotated[
            str | None,
            typer.Option(
                "--base-url",
                help="Canvas base URL.",
            ),
        ] = None,
        plan_only: Annotated[
            bool,
            typer.Option(
                "--plan-only",
                help="Parse and print the planned quiz sync without contacting Canvas.",
            ),
        ] = False,
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Contact Canvas, but do not create or update quizzes."),
        ] = False,
        publish: Annotated[
            bool,
            typer.Option("--publish", help="Force published=true for all synced quizzes."),
        ] = False,
        force: Annotated[
            bool,
            typer.Option("--force", help="Update quizzes even if they already have submissions."),
        ] = False,
        output_json: Annotated[
            Path | None,
            typer.Option(
                "--output-json",
                resolve_path=True,
                help="Optional path to write sync results as JSON.",
            ),
        ] = None,
    ) -> int:
        state = get_state(ctx)
        repo_root = state.repo_root
        canvas_config = state.config.canvas
        resolved_base_url = base_url or (
            canvas_config.base_url if canvas_config is not None else DEFAULT_CANVAS_BASE_URL
        )
        resolved_course_id = course_id or (
            canvas_config.course_id if canvas_config is not None else None
        )
        files = normalize_input_paths(quiz_files or default_quiz_files(state), repo_root=repo_root)
        if not files:
            raise click.ClickException(
                "No quiz files found. Add files to the configured quizzes_dir or pass paths."
            )
        require_paths_exist(files, label="Quiz")

        specs = load_quiz_specs(files)
        _print_quiz_plan(specs)

        token, resolved_course_id = require_canvas_credentials(
            resolved_course_id,
            plan_only=plan_only,
        )
        if plan_only:
            return 0

        with QuizCanvasClient(base_url=resolved_base_url, token=token, dry_run=dry_run) as client:
            results = sync_quizzes_to_canvas(
                client=client,
                course_id=resolved_course_id,
                specs=specs,
                publish_override=publish,
                skip_if_submissions=not force,
                reporter=_print_canvas_sync_event,
            )

        typer.echo("\nSync results:")
        for item in results:
            url = item.get("html_url") or "-"
            typer.echo(
                f"- {str(item['action']).upper():6} {item['title']} | id={item.get('id')} | {url}"
            )

        if not dry_run:
            update_quiz_frontmatter_with_canvas_id(results)
        write_json_output(output_json, results)
        return 0
