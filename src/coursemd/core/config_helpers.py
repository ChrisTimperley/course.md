"""Shared validation helpers for coursemd configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import click

CONFIG_FILENAME = ".coursemd.yml"


def require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise click.ClickException(f"{label} must be a mapping in {CONFIG_FILENAME}.")
    return cast(dict[str, Any], value)


def optional_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return cast(dict[str, Any], {})
    return require_mapping(value, label=label)


def require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise click.ClickException(f"{label} must be a non-empty string in {CONFIG_FILENAME}.")
    return value.strip()


def require_text(value: Any, *, label: str) -> str:
    if value is None or isinstance(value, bool):
        raise click.ClickException(
            f"{label} must be a non-empty string or integer in {CONFIG_FILENAME}."
        )
    text = str(value).strip()
    if not text:
        raise click.ClickException(
            f"{label} must be a non-empty string or integer in {CONFIG_FILENAME}."
        )
    return text


def optional_int(value: Any, *, label: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(f"{label} must be an integer in {CONFIG_FILENAME}.") from exc


def resolve_relative_path(repo_root: Path, raw_path: Any, *, label: str) -> Path:
    path_value = require_string(raw_path, label=label)
    return (repo_root / path_value).resolve()


def require_permission(value: Any, *, label: str) -> str:
    permission = require_string(value, label=label)
    if permission not in {"none", "read", "write", "admin"}:
        raise click.ClickException(
            f"{label} must be one of none, read, write, or admin in {CONFIG_FILENAME}."
        )
    return permission


def require_url_path(value: Any, *, label: str) -> str:
    path = require_string(value, label=label).strip("/")
    if not path:
        raise click.ClickException(f"{label} must not be empty in {CONFIG_FILENAME}.")
    return path


def require_timezone(value: Any, *, label: str) -> str:
    timezone_name = require_string(value, label=label)
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise click.ClickException(
            f"{label} must be a valid IANA timezone in {CONFIG_FILENAME} "
            "(example: America/New_York)."
        ) from exc
    return timezone_name


def optional_version(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    return require_string(value, label=label)


__all__ = [
    "CONFIG_FILENAME",
    "optional_int",
    "optional_mapping",
    "optional_version",
    "require_mapping",
    "require_permission",
    "require_string",
    "require_text",
    "require_timezone",
    "require_url_path",
    "resolve_relative_path",
]
