"""GitHub organization setup orchestration."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from coursemd.integrations.github.client import GhCliGitHubClient, GitHubClient, GitHubClientError
from coursemd.integrations.github.config import (
    DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
    DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG,
    DEFAULT_GITHUB_RULESET_NAME,
)
from coursemd.integrations.github.rulesets import build_main_branch_ruleset_payload


class GitHubSetupError(RuntimeError):
    """Raised when GitHub organization setup cannot complete."""


@dataclass(frozen=True)
class GitHubPermissionsResult:
    current_permission: str
    target_permission: str
    changed: bool
    applied: bool


@dataclass(frozen=True)
class GitHubRulesetResult:
    ruleset_name: str
    existing_ruleset_id: int | None
    action: str
    applied: bool
    ruleset_id: int | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class GitHubSetupResult:
    organization: str
    instructors_team_slug: str
    team_id: int
    permissions: GitHubPermissionsResult | None
    ruleset: GitHubRulesetResult | None


def _run_command(
    args: Sequence[str],
    *,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    from coursemd.integrations.github.client import run_command

    return run_command(args, input_text=input_text)


def _default_client() -> GitHubClient:
    return GhCliGitHubClient(command_runner=_run_command)


def run_github_setup(
    *,
    organization: str,
    instructors_team_slug: str = DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG,
    ruleset_name: str = DEFAULT_GITHUB_RULESET_NAME,
    default_repository_permission: str = DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
    permissions_only: bool = False,
    rulesets_only: bool = False,
    dry_run: bool = False,
    client: GitHubClient | None = None,
) -> GitHubSetupResult:
    """Configure GitHub organization defaults and the main-branch ruleset."""

    if permissions_only and rulesets_only:
        raise GitHubSetupError("--permissions-only and --rulesets-only cannot be used together.")

    github_client = client or _default_client()
    try:
        github_client.ensure_available()
        github_client.ensure_authenticated()
        team_id = github_client.get_team_id(
            organization=organization,
            team_slug=instructors_team_slug,
        )

        permissions_result: GitHubPermissionsResult | None = None
        if not rulesets_only:
            current_permission = github_client.get_default_repository_permission(
                organization=organization
            )
            changed = current_permission != default_repository_permission
            if changed and not dry_run:
                github_client.set_default_repository_permission(
                    organization=organization,
                    permission=default_repository_permission,
                )
            permissions_result = GitHubPermissionsResult(
                current_permission=current_permission,
                target_permission=default_repository_permission,
                changed=changed,
                applied=changed and not dry_run,
            )

        ruleset_result: GitHubRulesetResult | None = None
        if not permissions_only:
            payload = build_main_branch_ruleset_payload(
                team_id=team_id,
                ruleset_name=ruleset_name,
            )
            existing_ruleset_id: int | None = None
            action = "plan"
            ruleset_id: int | None = None
            if not dry_run:
                existing_ruleset_id = github_client.find_ruleset_id(
                    organization=organization,
                    ruleset_name=ruleset_name,
                )
                if existing_ruleset_id is None:
                    action = "create"
                    ruleset_id = github_client.create_ruleset(
                        organization=organization,
                        payload=payload,
                    )
                else:
                    action = "update"
                    ruleset_id = github_client.update_ruleset(
                        organization=organization,
                        ruleset_id=existing_ruleset_id,
                        payload=payload,
                    )
            ruleset_result = GitHubRulesetResult(
                ruleset_name=ruleset_name,
                existing_ruleset_id=existing_ruleset_id,
                action=action,
                applied=not dry_run,
                ruleset_id=ruleset_id,
                payload=payload,
            )
    except GitHubClientError as exc:
        raise GitHubSetupError(str(exc)) from exc

    return GitHubSetupResult(
        organization=organization,
        instructors_team_slug=instructors_team_slug,
        team_id=team_id,
        permissions=permissions_result,
        ruleset=ruleset_result,
    )
