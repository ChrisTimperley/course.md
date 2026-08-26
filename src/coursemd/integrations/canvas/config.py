"""Canvas integration configuration."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    import typer

from coursemd.core.config_helpers import (
    CONFIG_FILENAME,
    optional_int,
    optional_mapping,
    optional_version,
    require_mapping,
    require_string,
    require_text,
)
from coursemd.core.exceptions import CoursemdValidationError
from coursemd.core.integration_config import (
    IntegrationConfig,
    IntegrationConfigContext,
)

INTEGRATION_NAME = "canvas"
DEFAULT_CANVAS_BASE_URL = "https://canvas.instructure.com"
DEFAULT_INIT_CANVAS_COURSE_ID = "12345"
DEFAULT_PARTICIPATION_ASSIGNMENT_GROUP = "Participation"
MAX_GROUP_WEIGHT = 100


def _optional_percentage(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError
    try:
        percentage = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError from exc
    if not math.isfinite(percentage) or percentage < 0 or percentage > MAX_GROUP_WEIGHT:
        raise ValueError
    return percentage


def _optional_count(value: Any, *, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise CoursemdValidationError(f"{label} must be an integer in {CONFIG_FILENAME}.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise CoursemdValidationError(
                f"{label} must be an integer in {CONFIG_FILENAME}."
            ) from exc
    raise CoursemdValidationError(f"{label} must be an integer in {CONFIG_FILENAME}.")


@dataclass(frozen=True)
class CanvasParticipationConfig:
    """Canvas policy for lecture participation assignments."""

    assignment_group: str = DEFAULT_PARTICIPATION_ASSIGNMENT_GROUP
    group_weight: float | None = None
    drop_lowest: int | None = None

    @classmethod
    def parse(cls, raw_value: Any) -> CanvasParticipationConfig:
        config_map = optional_mapping(
            raw_value,
            label=f"integrations.{INTEGRATION_NAME}.participation",
        )
        assignment_group_raw = config_map.get(
            "assignment_group",
            DEFAULT_PARTICIPATION_ASSIGNMENT_GROUP,
        )
        assignment_group = require_string(
            assignment_group_raw,
            label=f"integrations.{INTEGRATION_NAME}.participation.assignment_group",
        )
        try:
            group_weight = _optional_percentage(config_map.get("group_weight"))
        except (TypeError, ValueError) as exc:
            raise CoursemdValidationError(
                f"integrations.{INTEGRATION_NAME}.participation.group_weight must be a "
                "number from 0 through 100."
            ) from exc
        drop_lowest = _optional_count(
            config_map.get("drop_lowest"),
            label=f"integrations.{INTEGRATION_NAME}.participation.drop_lowest",
        )
        if drop_lowest is not None and drop_lowest < 0:
            raise CoursemdValidationError(
                f"integrations.{INTEGRATION_NAME}.participation.drop_lowest must not be "
                "negative."
            )
        return cls(
            assignment_group=assignment_group,
            group_weight=group_weight,
            drop_lowest=drop_lowest,
        )

@dataclass(frozen=True)
class CanvasConfig(IntegrationConfig):
    metavar: ClassVar[str] = INTEGRATION_NAME

    base_url: str
    course_id: str
    group_category_id: int | None = None
    participation: CanvasParticipationConfig = field(
        default_factory=CanvasParticipationConfig,
    )

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
            participation=CanvasParticipationConfig.parse(config_map.get("participation")),
        )

    @classmethod
    def register_cli(cls, app: typer.Typer) -> None:
        del cls
        from coursemd.integrations.canvas.cli import register_canvas_cli  # noqa: PLC0415

        register_canvas_cli(app)


__all__ = [
    "DEFAULT_CANVAS_BASE_URL",
    "DEFAULT_PARTICIPATION_ASSIGNMENT_GROUP",
    "CanvasConfig",
    "CanvasParticipationConfig",
]
