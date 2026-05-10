"""Canvas integration configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from coursemd.core.config_helpers import (
    optional_int,
    optional_version,
    require_mapping,
    require_string,
    require_text,
)
from coursemd.core.integration_config import (
    IntegrationConfig,
    IntegrationConfigContext,
)

INTEGRATION_NAME = "canvas"
DEFAULT_CANVAS_BASE_URL = "https://canvas.instructure.com"
DEFAULT_INIT_CANVAS_COURSE_ID = "12345"

@dataclass(frozen=True)
class CanvasConfig(IntegrationConfig):
    metavar: ClassVar[str] = INTEGRATION_NAME

    base_url: str
    course_id: str
    group_category_id: int | None = None

    @classmethod
    def parse(cls, raw_value: Any, *, context: IntegrationConfigContext) -> CanvasConfig:
        del context
        config_map = require_mapping(raw_value, label=f"integrations.{cls.metavar}")
        optional_version(
            config_map.get("version"),
            label=f"integrations.{cls.metavar}.version",
        )
        return cls(
            base_url=require_string(
                config_map.get("base_url"),
                label=f"integrations.{cls.metavar}.base_url",
            ),
            course_id=require_text(
                config_map.get("course_id"),
                label=f"integrations.{cls.metavar}.course_id",
            ),
            group_category_id=optional_int(
                config_map.get("group_category_id"),
                label=f"integrations.{cls.metavar}.group_category_id",
            ),
        )


__all__ = [
    "CanvasConfig",
    "DEFAULT_CANVAS_BASE_URL",
]
