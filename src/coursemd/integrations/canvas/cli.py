"""Canvas CLI commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import click
import typer

from coursemd.cli.shared import (
    default_assignment_files,
    default_quiz_files,
    get_state,
    normalize_input_paths,
    require_canvas_credentials,
    require_paths_exist,
    write_json_output,
)
from coursemd.core.constants import DEFAULT_CANVAS_BASE_URL
from coursemd.core.loaders.assignments import load_assignment_specs
from coursemd.core.loaders.quizzes import load_quiz_specs
from coursemd.core.models.assignment import AssignmentSpec
from coursemd.core.models.quiz import QuizSpec
from coursemd.integrations.canvas.frontmatter import (
    update_assignment_frontmatter_with_ids,
    update_quiz_frontmatter_with_canvas_id,
)
from coursemd.integrations.canvas.quizzes import total_quiz_points
from coursemd.integrations.canvas.resources import AssignmentCanvasClient, QuizCanvasClient
from coursemd.integrations.canvas.sync import (
    CanvasSyncEvent,
    sync_assignments_to_canvas,
    sync_quizzes_to_canvas,
)


def _print_assignment_plan(specs: list[AssignmentSpec]) -> None:
    typer.echo(f"Loaded {len(specs)} assignment spec(s) for the Canvas integration:")
    for spec in specs:
        unlock = f" | unlock {spec.unlock_at}" if spec.unlock_at else ""
        group = " [group]" if spec.group_assignment else ""
        assignment_group = spec.integrations.canvas.assignment_group or "<unassigned>"
        typer.echo(
            f"- {spec.name} | due {spec.due_at} | {spec.points_possible} pts{unlock}{group} | "
            f"group '{assignment_group}' | submissions={spec.submission_types} | "
            f"source={spec.source_file}"
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
    elif event.action == "create" and event.target == "assignment":
        typer.echo(f"Creating assignment '{event.name}'")
    elif event.action == "update" and event.target == "assignment":
        typer.echo(f"Updating assignment '{event.name}' (id={event.id})")
    elif event.action == "skip" and event.target == "assignment":
        typer.echo(f"Skipping '{event.name}' (id={event.id}): {event.reason}")
    elif event.action == "sync" and event.target == "rubric":
        typer.echo(f"  Syncing rubric for '{event.name}' ({event.count} criteria)")
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


def register_sync_canvas_assignments_command(canvas_app: typer.Typer) -> None:
    @canvas_app.command("assignments")
    def sync_canvas_assignments(
        ctx: typer.Context,
        assignment_files: Annotated[
            list[Path] | None,
            typer.Argument(
                help="Assignment Markdown files. Defaults to the configured assignments_dir.",
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
        site_base_url: Annotated[
            str | None,
            typer.Option(
                "--site-base-url",
                help="Course site base URL used in generated links.",
            ),
        ] = None,
        plan_only: Annotated[
            bool,
            typer.Option(
                "--plan-only",
                help="Parse and print the planned assignment sync without contacting Canvas.",
            ),
        ] = False,
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run", help="Contact Canvas, but do not create or update assignments."
            ),
        ] = False,
        publish: Annotated[
            bool,
            typer.Option("--publish", help="Force published=true for all synced assignments."),
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
        resolved_site_base_url = site_base_url or state.config.site_base_url
        resolved_base_url = base_url or (
            canvas_config.base_url if canvas_config is not None else DEFAULT_CANVAS_BASE_URL
        )
        resolved_course_id = course_id or (
            canvas_config.course_id if canvas_config is not None else None
        )
        group_category_id = canvas_config.group_category_id if canvas_config is not None else None
        files = normalize_input_paths(
            assignment_files or default_assignment_files(state),
            repo_root=repo_root,
        )
        if not files:
            raise click.ClickException("No assignment files found.")
        require_paths_exist(files, label="Assignment")

        specs = load_assignment_specs(
            files=files,
            site_base_url=resolved_site_base_url,
            assignment_url_path=state.config.site_assignments_url_path,
        )
        _print_assignment_plan(specs)

        token, resolved_course_id = require_canvas_credentials(
            resolved_course_id,
            plan_only=plan_only,
        )
        if plan_only:
            return 0

        with AssignmentCanvasClient(
            base_url=resolved_base_url, token=token, dry_run=dry_run
        ) as client:
            results = sync_assignments_to_canvas(
                client=client,
                course_id=resolved_course_id,
                specs=specs,
                publish_override=publish,
                group_category_id_override=group_category_id,
                reporter=_print_canvas_sync_event,
            )

        typer.echo("\nSync results:")
        for item in results:
            url = item.get("html_url") or "-"
            typer.echo(
                f"- {str(item['action']).upper():6} {item['name']} | id={item.get('id')} | {url}"
            )

        if not dry_run:
            update_assignment_frontmatter_with_ids(results)
        write_json_output(output_json, results)
        return 0


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


def main_sync_canvas_assignments(
    argv: list[str] | None = None,
    *,
    repo_root: Path | None = None,
    prog: str = "sync-canvas-assignments",
) -> int:
    from coursemd.cli import main

    args_list = [
        "canvas",
        "assignments",
        *(argv if argv is not None else sys.argv[1:]),
    ]
    return main(args_list, prog=prog, start_dir=repo_root)


def main_sync_canvas_quizzes(
    argv: list[str] | None = None,
    *,
    repo_root: Path | None = None,
    prog: str = "sync-canvas-quizzes",
) -> int:
    from coursemd.cli import main

    args_list = [
        "canvas",
        "quizzes",
        *(argv if argv is not None else sys.argv[1:]),
    ]
    return main(args_list, prog=prog, start_dir=repo_root)


__all__ = [
    "main_sync_canvas_assignments",
    "main_sync_canvas_quizzes",
    "register_sync_canvas_assignments_command",
    "register_sync_canvas_quizzes_command",
]
