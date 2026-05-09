"""GitHub integration configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from coursemd.core.config_helpers import (
    optional_version,
    require_mapping,
    require_permission,
    require_string,
)
from coursemd.core.integration_config import (
    IntegrationConfig,
    IntegrationConfigContext,
    register_integration_config,
)

INTEGRATION_NAME = "github"
DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG = "instructors"
DEFAULT_GITHUB_RULESET_NAME = "Protect main branch"
DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION = "none"


@register_integration_config
@dataclass(frozen=True)
class GitHubConfig(IntegrationConfig):
    metavar: ClassVar[str] = INTEGRATION_NAME

    organization: str
    instructors_team_slug: str = DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG
    ruleset_name: str = DEFAULT_GITHUB_RULESET_NAME
    default_repository_permission: str = DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION

    @classmethod
    def parse(cls, raw_value: Any, *, context: IntegrationConfigContext) -> GitHubConfig:
        del context
        config_map = require_mapping(raw_value, label=f"integrations.{cls.metavar}")
        optional_version(
            config_map.get("version"),
            label=f"integrations.{cls.metavar}.version",
        )
        return cls(
            organization=require_string(
                config_map.get("organization"),
                label=f"integrations.{cls.metavar}.organization",
            ),
            instructors_team_slug=require_string(
                config_map.get(
                    "instructors_team_slug",
                    DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG,
                ),
                label=f"integrations.{cls.metavar}.instructors_team_slug",
            ),
            ruleset_name=require_string(
                config_map.get("ruleset_name", DEFAULT_GITHUB_RULESET_NAME),
                label=f"integrations.{cls.metavar}.ruleset_name",
            ),
            default_repository_permission=require_permission(
                config_map.get(
                    "default_repository_permission",
                    DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION,
                ),
                label=f"integrations.{cls.metavar}.default_repository_permission",
            ),
        )


__all__ = [
    "DEFAULT_GITHUB_DEFAULT_REPOSITORY_PERMISSION",
    "DEFAULT_GITHUB_INSTRUCTORS_TEAM_SLUG",
    "DEFAULT_GITHUB_RULESET_NAME",
    "GitHubConfig",
    "INTEGRATION_NAME",
]
