"""Quarto-backed slides integration configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import click

from coursemd.core.config_helpers import (
    optional_version,
    require_mapping,
    resolve_relative_path,
)
from coursemd.core.integration_config import (
    IntegrationConfig,
    IntegrationConfigContext,
    register_integration_config,
)

INTEGRATION_NAME = "quarto"
DEFAULT_INIT_SLIDES_DIR = "slides"

if TYPE_CHECKING:
    from coursemd.core.config import CoursemdConfig


@register_integration_config
@dataclass(frozen=True)
class QuartoConfig(IntegrationConfig):
    metavar: ClassVar[str] = INTEGRATION_NAME

    directory: Path

    @classmethod
    def parse(cls, raw_value: Any, *, context: IntegrationConfigContext) -> QuartoConfig:
        config_map = require_mapping(raw_value, label=f"integrations.{cls.metavar}")
        optional_version(
            config_map.get("version"),
            label=f"integrations.{cls.metavar}.version",
        )
        return cls(
            directory=resolve_relative_path(
                context.repo_root,
                config_map.get("dir", config_map.get("project_dir", DEFAULT_INIT_SLIDES_DIR)),
                label=f"integrations.{cls.metavar}.dir",
            ),
        )


def get_quarto_config(config: CoursemdConfig) -> QuartoConfig | None:
    return config.get_integration(INTEGRATION_NAME, QuartoConfig)


def require_quarto_config(config: CoursemdConfig) -> QuartoConfig:
    quarto_config = get_quarto_config(config)
    if quarto_config is None:
        raise click.ClickException("Slides integration config is missing.")
    return quarto_config


SlidesConfig = QuartoConfig


__all__ = [
    "DEFAULT_INIT_SLIDES_DIR",
    "INTEGRATION_NAME",
    "QuartoConfig",
    "SlidesConfig",
    "get_quarto_config",
    "require_quarto_config",
]
