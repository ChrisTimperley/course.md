"""MkDocs integration configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import click

from coursemd.core.config_helpers import (
    optional_version,
    require_mapping,
    require_string,
    require_url_path,
    resolve_relative_path,
)
from coursemd.core.integration_config import (
    IntegrationConfig,
    IntegrationConfigContext,
    register_integration_config,
)

INTEGRATION_NAME = "mkdocs"
DEFAULT_INIT_SITE_BASE_URL = "https://example.edu/course"
DEFAULT_INIT_SITE_BACKEND = "mkdocs"
DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH = "assignments"
DEFAULT_INIT_SITE_PROJECT_DIR = "website"
SUPPORTED_SITE_BACKENDS = {DEFAULT_INIT_SITE_BACKEND}

@register_integration_config
@dataclass(frozen=True)
class MkdocsIntegrationConfig(IntegrationConfig):
    metavar: ClassVar[str] = INTEGRATION_NAME
    required: ClassVar[bool] = True

    base_url: str
    project_dir: Path
    assignments_url_path: str = DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH
    backend: str = DEFAULT_INIT_SITE_BACKEND

    @classmethod
    def parse(
        cls,
        raw_value: Any,
        *,
        context: IntegrationConfigContext,
    ) -> MkdocsIntegrationConfig:
        config_map = require_mapping(raw_value, label=f"integrations.{cls.metavar}")
        optional_version(
            config_map.get("version"),
            label=f"integrations.{cls.metavar}.version",
        )
        backend = require_string(
            config_map.get("backend", DEFAULT_INIT_SITE_BACKEND),
            label=f"integrations.{cls.metavar}.backend",
        )
        if backend not in SUPPORTED_SITE_BACKENDS:
            raise click.ClickException(
                f"integrations.{cls.metavar}.backend must be one of "
                f"{', '.join(sorted(SUPPORTED_SITE_BACKENDS))} in .coursemd.yml."
            )
        return cls(
            backend=backend,
            base_url=require_string(
                config_map.get("base_url"),
                label=f"integrations.{cls.metavar}.base_url",
            ),
            project_dir=resolve_relative_path(
                context.repo_root,
                config_map.get("project_dir", DEFAULT_INIT_SITE_PROJECT_DIR),
                label=f"integrations.{cls.metavar}.project_dir",
            ),
            assignments_url_path=require_url_path(
                config_map.get(
                    "assignments_url_path",
                    DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH,
                ),
                label=f"integrations.{cls.metavar}.assignments_url_path",
            ),
        )


__all__ = [
    "DEFAULT_INIT_SITE_ASSIGNMENTS_URL_PATH",
    "DEFAULT_INIT_SITE_BACKEND",
    "DEFAULT_INIT_SITE_BASE_URL",
    "DEFAULT_INIT_SITE_PROJECT_DIR",
    "INTEGRATION_NAME",
    "MkdocsIntegrationConfig",
    "SUPPORTED_SITE_BACKENDS",
]
