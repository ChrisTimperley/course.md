"""Integration packages for external systems and tooling."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer

_BUILTIN_INTEGRATION_CONFIG_MODULES = (
    "coursemd.integrations.mkdocs.config",
    "coursemd.integrations.canvas.config",
    "coursemd.integrations.github.config",
    "coursemd.integrations.quarto.config",
)
_builtin_integrations_loaded = False


def load_builtin_integration_configs() -> None:
    global _builtin_integrations_loaded  # noqa: PLW0603

    if _builtin_integrations_loaded:
        return

    for module_name in _BUILTIN_INTEGRATION_CONFIG_MODULES:
        importlib.import_module(module_name)
    _builtin_integrations_loaded = True


def register_integration_clis(app: typer.Typer) -> None:
    from coursemd.integrations.canvas.cli import register_canvas_cli  # noqa: PLC0415
    from coursemd.integrations.github.cli import register_github_cli  # noqa: PLC0415
    from coursemd.integrations.mkdocs.cli import register_site_cli  # noqa: PLC0415
    from coursemd.integrations.quarto.cli import register_quarto_cli  # noqa: PLC0415

    register_canvas_cli(app)
    register_site_cli(app)
    register_quarto_cli(app)
    register_github_cli(app)


