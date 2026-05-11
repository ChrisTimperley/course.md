"""Integration packages for external systems and tooling."""

from __future__ import annotations

import importlib
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

from coursemd.core.integration_config import IntegrationConfig

if TYPE_CHECKING:
    import typer

_INTEGRATION_ENTRYPOINT_GROUP = "coursemd.integrations"
_builtin_integrations_loaded = False


def load_builtin_integration_configs() -> None:
    global _builtin_integrations_loaded  # noqa: PLW0603

    if _builtin_integrations_loaded:
        return

    for integration_entry_point in entry_points(group=_INTEGRATION_ENTRYPOINT_GROUP):
        importlib.import_module(integration_entry_point.value)
    _builtin_integrations_loaded = True


def register_integration_clis(app: typer.Typer) -> None:
    load_builtin_integration_configs()

    for integration_config_type in IntegrationConfig.iter_types():
        integration_config_type.register_cli(app)


