"""Integration packages for external systems and tooling."""

from __future__ import annotations

import typer


def register_integration_clis(app: typer.Typer) -> None:
    from coursemd.integrations.canvas.cli import register_canvas_cli
    from coursemd.integrations.github.cli import register_github_cli
    from coursemd.integrations.mkdocs.cli import register_site_cli
    from coursemd.integrations.slides.cli import register_slides_cli

    register_canvas_cli(app)
    register_site_cli(app)
    register_slides_cli(app)
    register_github_cli(app)


__all__ = ["register_integration_clis"]
