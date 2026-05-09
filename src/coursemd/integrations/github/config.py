"""GitHub integration configuration."""

from __future__ import annotations

from dataclasses import dataclass

INTEGRATION_NAME = "github"
DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG = "instructors"
DEFAULT_GITHUB_RULESET_NAME = "Protect main branch"
DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION = "none"


@dataclass(frozen=True)
class GitHubConfig:
    organization: str
    instructors_team_slug: str = DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG
    ruleset_name: str = DEFAULT_GITHUB_RULESET_NAME
    default_repository_permission: str = DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION


__all__ = [
    "DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION",
    "DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG",
    "DEFAULT_GITHUB_RULESET_NAME",
    "GitHubConfig",
    "INTEGRATION_NAME",
]
