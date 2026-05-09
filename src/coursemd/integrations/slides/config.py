"""Quarto-backed slides integration configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from coursemd.core.config_helpers import (
    optional_version,
    require_mapping,
    resolve_relative_path,
)
from coursemd.core.integration_config import (
    IntegrationConfig,
    IntegrationConfigContext,
)

INTEGRATION_NAME = "quarto"
DEFAULT_INIT_SLIDES_DIR = "slides"

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
                config_map.get("dir", DEFAULT_INIT_SLIDES_DIR),
                label=f"integrations.{cls.metavar}.dir",
            ),
        )


SlidesConfig = QuartoConfig


__all__ = [
    "DEFAULT_INIT_SLIDES_DIR",
    "INTEGRATION_NAME",
    "QuartoConfig",
    "SlidesConfig",
]
