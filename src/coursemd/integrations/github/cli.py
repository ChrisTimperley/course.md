"""GitHub CLI commands."""

from __future__ import annotations

import json
from typing import Annotated

import click
import typer

from coursemd.cli.shared import AppState
from coursemd.integrations.github.config import (
    DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
    DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG,
    DEFAULT_GITHUB_RULESET_NAME,
    GitHubConfig,
)
from coursemd.integrations.github.setup import (
    GitHubSetupError,
    run_github_setup,
)

CLI_NAME = "github"
CLI_HELP = "GitHub organization workflows."


def _resolve_github_value(
    explicit_value: str | None,
    config_value: str | None,
    *,
    label: str,
) -> str:
    if explicit_value is not None and explicit_value.strip():
        return explicit_value.strip()
    if config_value is not None and config_value.strip():
        return config_value.strip()
    raise click.ClickException(
        f"{label} is required. Set it in .coursemd.yml or pass the corresponding option."
    )


def register_github_commands(github_app: typer.Typer) -> None:
    @github_app.command("setup")
    def github_setup_command(
        ctx: typer.Context,
        org: Annotated[
            str | None,
            typer.Option("--org", help="GitHub organization login to configure."),
        ] = None,
        instructors_team_slug: Annotated[
            str | None,
            typer.Option(
                "--instructors-team-slug",
                help="Team slug that should bypass the main-branch ruleset.",
            ),
        ] = None,
        ruleset_name: Annotated[
            str | None,
            typer.Option("--ruleset-name", help="Name of the org-level branch protection ruleset."),
        ] = None,
        default_repository_permission: Annotated[
            str,
            typer.Option(
                "--default-repository-permission",
                click_type=click.Choice(["none", "read", "write", "admin"], case_sensitive=True),
                help="Default permission granted to organization members on repositories.",
            ),
        ] = DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
        permissions_only: Annotated[
            bool,
            typer.Option(
                "--permissions-only", help="Only manage org default repository permissions."
            ),
        ] = False,
        rulesets_only: Annotated[
            bool,
            typer.Option("--rulesets-only", help="Only manage the org main-branch ruleset."),
        ] = False,
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Preview the changes without mutating GitHub state."),
        ] = False,
    ) -> int:
        state = AppState.from_typer(ctx)
        github_config = GitHubConfig.get(state.config)
        organization = _resolve_github_value(
            org,
            github_config.organization if github_config is not None else None,
            label="GitHub organization",
        )
        resolved_team_slug = _resolve_github_value(
            instructors_team_slug,
            github_config.instructors_team_slug
            if github_config is not None
            else DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG,
            label="GitHub instructors team slug",
        )
        resolved_ruleset_name = _resolve_github_value(
            ruleset_name,
            github_config.ruleset_name
            if github_config is not None
            else DEFAULT_GITHUB_RULESET_NAME,
            label="GitHub ruleset name",
        )
        resolved_default_permission = (
            github_config.default_repository_permission
            if github_config is not None
            and default_repository_permission == DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION
            else default_repository_permission
        )

        try:
            result = run_github_setup(
                organization=organization,
                instructors_team_slug=resolved_team_slug,
                ruleset_name=resolved_ruleset_name,
                default_repository_permission=resolved_default_permission,
                permissions_only=permissions_only,
                rulesets_only=rulesets_only,
                dry_run=dry_run,
            )
        except GitHubSetupError as exc:
            raise click.ClickException(str(exc)) from exc

        typer.echo(
            f"Resolved team '{result.instructors_team_slug}' in org "
            f"'{result.organization}' (ID: {result.team_id})."
        )

        if result.permissions is not None:
            current_permission = result.permissions.current_permission
            target_permission = result.permissions.target_permission
            typer.echo(
                "Default repository permission: "
                f"'{current_permission}' -> '{target_permission}'"
            )
            if result.permissions.changed:
                if result.permissions.applied:
                    typer.echo("Applied organization default repository permission update.")
                else:
                    typer.echo("Dry run: would update organization default repository permission.")
            else:
                typer.echo("Default repository permission already matches the target value.")

        if result.ruleset is not None:
            if result.ruleset.applied:
                action = "Updated" if result.ruleset.action == "update" else "Created"
                typer.echo(
                    f"{action} ruleset '{result.ruleset.ruleset_name}'"
                    f" (ID: {result.ruleset.ruleset_id})."
                )
            else:
                ruleset_name = result.ruleset.ruleset_name
                typer.echo(
                    f"Dry run: would configure ruleset '{ruleset_name}' "
                    "with payload:"
                )
                typer.echo(json.dumps(result.ruleset.payload, indent=2))

        return 0


def register_github_cli(app: typer.Typer) -> None:
    github_app = typer.Typer(no_args_is_help=True, help=CLI_HELP)
    app.add_typer(github_app, name=CLI_NAME)
    register_github_commands(github_app)


__all__ = ["register_github_cli", "register_github_commands"]
