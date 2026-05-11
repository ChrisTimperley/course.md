"""Markdown frontmatter loading helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

import frontmatter  # type: ignore[import-untyped]
import yaml

from coursemd.core.exceptions import CoursemdValidationError


def load_markdown_post(source_file: Path) -> frontmatter.Post:
    """Load a Markdown file with YAML frontmatter."""

    try:
        return frontmatter.load(source_file)
    except yaml.YAMLError as exc:
        raise CoursemdValidationError(
            f"invalid Markdown frontmatter YAML: {exc}",
            source_path=source_file,
        ) from exc


def load_markdown_metadata(source_file: Path) -> dict[str, Any]:
    """Load only the frontmatter metadata for a Markdown file."""

    return cast("dict[str, Any]", load_markdown_post(source_file).metadata)
