"""Slides integration configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

INTEGRATION_NAME = "slides"
DEFAULT_INIT_SLIDES_DIR = "slides"


@dataclass(frozen=True)
class SlidesConfig:
    directory: Path


__all__ = ["DEFAULT_INIT_SLIDES_DIR", "INTEGRATION_NAME", "SlidesConfig"]
