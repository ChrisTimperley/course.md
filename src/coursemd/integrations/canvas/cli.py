"""Canvas CLI commands."""

from __future__ import annotations

import os
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Any

import click
import typer

from coursemd.cli.shared import (
    AppState,
    click_error_boundary,
    default_assignment_files,
    default_quiz_files,
    normalize_input_paths,
    require_paths_exist,
    write_json_output,
)
from coursemd.core.loaders.quizzes import load_quiz_specs
from coursemd.core.loaders.specs import load_assignments
from coursemd.integrations.canvas.config import DEFAULT_CANVAS_BASE_URL, CanvasConfig
from coursemd.integrations.canvas.models import canvas_assignment_submissions, canvas_quiz
from coursemd.integrations.canvas.quizzes import QUIZ_TYPE_MAP

if TYPE_CHECKING:
    from coursemd.core.models.assignment import Assignment
    from coursemd.core.models.quiz import QuizSpec
from coursemd.integrations.canvas.frontmatter import (
    update_assignment_frontmatter_with_ids,
    update_quiz_frontmatter_with_canvas_id,
)
from coursemd.integrations.canvas.quizzes import total_quiz_points
from coursemd.integrations.canvas.resources import AssignmentCanvasClient, QuizCanvasClient
from coursemd.integrations.canvas.sync import sync_assignments_to_canvas, sync_quizzes_to_canvas
from coursemd.integrations.mkdocs.config import MkdocsIntegrationConfig

CLI_NAME = "canvas"
CLI_HELP = "Canvas LMS workflows."


def _register_unavailable_command(app: typer.Typer, command_name: str, message: str) -> None:
    @app.command(command_name)
    def unavailable_command() -> int:
        raise click.ClickException(message)


def _register_unavailable_canvas_commands(canvas_app: typer.Typer) -> None:
    message = (
        "coursemd canvas assignments, coursemd canvas quizzes require the optional "
        '`canvas` dependencies. Install them with `pip install "coursemd[canvas]"`.'
    )
    _register_unavailable_command(canvas_app, "assignments", message)
    _register_unavailable_command(canvas_app, "quizzes", message)


def _print_assignment_plan(specs: list[Assignment]) -> None:
    typer.echo(f"Loaded {len(specs)} assignment spec(s) for the Canvas integration:")
    for assignment in specs:
        submissions = canvas_assignment_submissions(assignment)
        if len(submissions) > 1:
            typer.echo(f"- {assignment.name} | {len(submissions)} Canvas checkpoints")
        for spec in submissions:
            unlock = f" | unlock {spec.unlock_at}" if spec.unlock_at else ""
            group = " [group]" if spec.group_assignment else ""
            assignment_group = spec.canvas_assignment_group or "<unassigned>"
            due_text = spec.due_at or assignment.due_date.isoformat()
            typer.echo(
                f"- {spec.name} | due {due_text} | {spec.points_possible} pts"
                f"{unlock}{group} | group '{assignment_group}' | "
                f"submissions={spec.submission_types} | source={spec.source_file}"
            )


def _print_canvas_sync_event(event: Any) -> None:
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
        canvas = canvas_quiz(spec.integrations, spec.source_type, QUIZ_TYPE_MAP)
        typer.echo(
            f"- {spec.title} | type={canvas.quiz_type or '<unset>'} | due {spec.due_at} | "
            f"{total_quiz_points(spec)} pts | {len(spec.questions)} questions{readings}{unlock} | "
            f"group '{canvas.assignment_group or '<unassigned>'}' | source={spec.source_file}"
        )


def parse_group_category_id_override() -> int | None:
    group_category_env = os.environ.get("CANVAS_GROUP_CATEGORY_ID", "").strip()
    if not group_category_env:
        return None
    try:
        return int(group_category_env)
    except ValueError:
        return None


def require_canvas_credentials(course_id: str | None, *, plan_only: bool) -> tuple[str, str]:
    if plan_only:
        return "", course_id or ""
    if not course_id:
        raise click.ClickException(
            "course_id is required unless --plan-only is used. "
            "Set it in .coursemd.yml or pass --course-id."
        )
    token = os.environ.get("CANVAS_TOKEN", "").strip()
    if not token:
        raise click.ClickException("CANVAS_TOKEN must be set unless --plan-only is used.")
    return token, course_id


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
        with click_error_boundary():
            state = AppState.from_typer(ctx)
            repo_root = state.repo_root
            mkdocs_config = MkdocsIntegrationConfig.require(state.config)
            canvas_config = CanvasConfig.get(state.config)
            resolved_site_base_url = site_base_url or mkdocs_config.base_url
            resolved_base_url = base_url or (
                canvas_config.base_url if canvas_config is not None else DEFAULT_CANVAS_BASE_URL
            )
            resolved_course_id = course_id or (
                canvas_config.course_id if canvas_config is not None else None
            )
            group_category_id = (
                canvas_config.group_category_id if canvas_config is not None else None
            )
            files = normalize_input_paths(
                assignment_files or default_assignment_files(state),
                repo_root=repo_root,
            )
            if not files:
                raise click.ClickException("No assignment files found.")
            require_paths_exist(files, label="Assignment")

            specs = load_assignments(
                files=files,
                assignment_url_path=mkdocs_config.assignments_url_path,
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
                    site_base_url=resolved_site_base_url,
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
        with click_error_boundary():
            state = AppState.from_typer(ctx)
            repo_root = state.repo_root
            canvas_config = CanvasConfig.get(state.config)
            resolved_base_url = base_url or (
                canvas_config.base_url if canvas_config is not None else DEFAULT_CANVAS_BASE_URL
            )
            resolved_course_id = course_id or (
                canvas_config.course_id if canvas_config is not None else None
            )
            files = normalize_input_paths(
                quiz_files or default_quiz_files(state),
                repo_root=repo_root,
            )
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

            with QuizCanvasClient(
                base_url=resolved_base_url,
                token=token,
                dry_run=dry_run,
            ) as client:
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


def register_canvas_cli(app: typer.Typer) -> None:
    canvas_app = typer.Typer(no_args_is_help=True, help=CLI_HELP)
    app.add_typer(canvas_app, name=CLI_NAME)

    try:
        register_sync_canvas_assignments_command(canvas_app)
        register_sync_canvas_quizzes_command(canvas_app)
    except ModuleNotFoundError as exc:
        module_name = exc.name or ""
        if module_name != "requests" and not module_name.startswith("requests."):
            raise
        _register_unavailable_canvas_commands(canvas_app)


__all__ = (
    "register_canvas_cli",
)
