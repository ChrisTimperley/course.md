"""Canvas assignment sync command for the package CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import click
import typer

from coursemd.canvas.frontmatter import update_assignment_frontmatter_with_ids
from coursemd.canvas.resources import AssignmentCanvasClient
from coursemd.canvas.sync import CanvasSyncEvent, sync_assignments_to_canvas
from coursemd.cli.shared import (
    default_assignment_files,
    get_state,
    normalize_input_paths,
    require_canvas_credentials,
    require_paths_exist,
    write_json_output,
)
from coursemd.core.constants import DEFAULT_CANVAS_BASE_URL
from coursemd.core.loaders.assignments import load_assignment_specs
from coursemd.core.models.assignment import AssignmentSpec


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
