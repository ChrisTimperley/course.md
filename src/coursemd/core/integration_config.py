"""Registry-backed API for integration configuration types."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, TypeVar

import click

if TYPE_CHECKING:
    from coursemd.core.config import CoursemdConfig


@dataclass(frozen=True)
class IntegrationConfigContext:
    repo_root: Path


class IntegrationConfig(ABC):
    metavar: ClassVar[str]
    aliases: ClassVar[tuple[str, ...]] = ()
    required: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        _register_integration_config(cls)

    @classmethod
    def get(cls: type[TIntegrationConfig], config: CoursemdConfig) -> TIntegrationConfig | None:
        return config.get_integration(cls.metavar, cls)

    @classmethod
    def require(cls: type[TIntegrationConfig], config: CoursemdConfig) -> TIntegrationConfig:
        integration_config = cls.get(config)
        if integration_config is None:
            raise click.ClickException(cls.missing_config_message())
        return integration_config

    @classmethod
    def missing_config_message(cls) -> str:
        if cls.required:
            return f"integrations.{cls.metavar} is required in .coursemd.yml."
        return f"integrations.{cls.metavar} is not configured in .coursemd.yml."

    @classmethod
    @abstractmethod
    def parse(cls, raw_value: Any, *, context: IntegrationConfigContext) -> Self:
        raise NotImplementedError


TIntegrationConfig = TypeVar("TIntegrationConfig", bound=IntegrationConfig)


_INTEGRATION_CONFIGS: dict[str, type[IntegrationConfig]] = {}
_INTEGRATION_ALIASES: dict[str, str] = {}


def _register_integration_config(
    config_type: type[IntegrationConfig],
) -> type[IntegrationConfig]:
    name = getattr(config_type, "metavar", "").strip()
    if not name:
        raise ValueError("Integration config classes must declare a non-empty metavar.")

    existing = _INTEGRATION_CONFIGS.get(name)
    if existing is not None and existing is not config_type:
        raise ValueError(f"Integration config {name!r} is already registered.")
    _INTEGRATION_CONFIGS[name] = config_type

    for alias in getattr(config_type, "aliases", ()):  # pragma: no branch
        normalized_alias = alias.strip()
        if not normalized_alias:
            raise ValueError(f"Integration config {name!r} declared an empty alias.")
        existing_alias = _INTEGRATION_ALIASES.get(normalized_alias)
        if existing_alias is not None and existing_alias != name:
            raise ValueError(
                f"Integration alias {normalized_alias!r} is already mapped to {existing_alias!r}."
            )
        _INTEGRATION_ALIASES[normalized_alias] = name

    return config_type


def get_integration_config_type(name: str) -> type[IntegrationConfig] | None:
    normalized_name = name.strip()
    canonical_name = _INTEGRATION_ALIASES.get(normalized_name, normalized_name)
    return _INTEGRATION_CONFIGS.get(canonical_name)


def iter_integration_config_types() -> tuple[type[IntegrationConfig], ...]:
    return tuple(_INTEGRATION_CONFIGS.values())


__all__ = [
    "IntegrationConfig",
    "IntegrationConfigContext",
    "get_integration_config_type",
    "iter_integration_config_types",
]
