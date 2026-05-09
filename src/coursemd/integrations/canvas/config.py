"""Canvas integration configuration."""

from __future__ import annotations

from dataclasses import dataclass

INTEGRATION_NAME = "canvas"
DEFAULT_CANVAS_BASE_URL = "https://canvas.instructure.com"
DEFAULT_INIT_CANVAS_COURSE_ID = "12345"


@dataclass(frozen=True)
class CanvasConfig:
    base_url: str
    course_id: str
    group_category_id: int | None = None


__all__ = [
    "CanvasConfig",
    "DEFAULT_CANVAS_BASE_URL",
    "DEFAULT_INIT_CANVAS_COURSE_ID",
    "INTEGRATION_NAME",
]
