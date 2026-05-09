"""MkDocs CLI commands."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import click
import typer
from mkdocs.commands.build import build as mkdocs_build
from mkdocs.commands.serve import serve as mkdocs_serve
from mkdocs.config import load_config
from mkdocs.plugins import PluginCollection

from coursemd.cli.shared import get_state, site_project_dir

DEFAULT_PREVIEW_CURRENT_DATE = "2999-12-12"
PREVIEW_EXCLUDED_PLUGINS: tuple[str, ...] = ()
SUPPORTED_SITE_BACKENDS = {"mkdocs"}


def _require_site_project_dir(project_dir: Path) -> Path:
    if not project_dir.is_dir():
        raise click.ClickException(f"Site project directory not found: {project_dir}")
    config_file = project_dir / "mkdocs.yml"
    if not config_file.is_file():
        raise click.ClickException(f"MkDocs config file not found: {config_file}")
    return config_file


def _filtered_plugins(
    plugins: PluginCollection,
    *,
    excluded_names: tuple[str, ...] = (),
) -> PluginCollection:
    if not excluded_names:
        return plugins

    filtered = PluginCollection()
    for name, plugin in plugins.items():
        if name not in excluded_names:
            filtered[name] = plugin
    return filtered


def _preview_url(dev_addr: str | None) -> str:
    bind = (dev_addr or "127.0.0.1:8000").strip()
    host, sep, port = bind.partition(":")
    if not sep:
        host = bind
        port = "8000"
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    return f"http://{host}:{port}/"


@contextmanager
def _site_runtime_context(
    *,
    project_dir: Path,
    current_date_override: str | None = None,
    preview: bool = False,
) -> Iterator[None]:
    previous_cwd = Path.cwd()
    previous_current_date = os.environ.get("CURRENT_DATE_OVERRIDE")
    previous_coursemd_preview = os.environ.get("COURSEMD_PREVIEW")

    os.chdir(project_dir)
    if current_date_override is None:
        os.environ.pop("CURRENT_DATE_OVERRIDE", None)
    else:
        os.environ["CURRENT_DATE_OVERRIDE"] = current_date_override
    if preview:
        os.environ["COURSEMD_PREVIEW"] = "1"
    else:
        os.environ.pop("COURSEMD_PREVIEW", None)

    try:
        yield
    finally:
        os.chdir(previous_cwd)
        if previous_current_date is None:
            os.environ.pop("CURRENT_DATE_OVERRIDE", None)
        else:
            os.environ["CURRENT_DATE_OVERRIDE"] = previous_current_date
        if previous_coursemd_preview is None:
            os.environ.pop("COURSEMD_PREVIEW", None)
        else:
            os.environ["COURSEMD_PREVIEW"] = previous_coursemd_preview


def _build_site(
    *,
    config_file: Path,
    project_dir: Path,
    site_dir: Path | None,
    strict: bool,
    current_date_override: str | None = None,
    excluded_plugins: tuple[str, ...] = (),
    preview: bool = False,
) -> int:
    with _site_runtime_context(
        project_dir=project_dir,
        current_date_override=current_date_override,
        preview=preview,
    ):
        config = load_config(
            config_file=str(config_file),
            site_dir=str(site_dir) if site_dir is not None else None,
            strict=strict,
        )
        config.plugins = _filtered_plugins(
            config.plugins,
            excluded_names=excluded_plugins,
        )
        config.plugins.on_startup(command="build", dirty=False)
        try:
            mkdocs_build(config, dirty=False)
        finally:
            config.plugins.on_shutdown()
    return 0


def _preview_site(
    *,
    config_file: Path,
    dev_addr: str | None,
    current_date_override: str,
    dirty: bool,
) -> int:
    with _site_runtime_context(
        project_dir=config_file.parent,
        current_date_override=current_date_override,
        preview=True,
    ):
        typer.echo(f"Previewing site at {_preview_url(dev_addr)}")
        mkdocs_serve(
            config_file=str(config_file),
            dev_addr=dev_addr,
            build_type="dirty" if dirty else None,
            open_in_browser=False,
        )
    return 0


def register_site_commands(site_app: typer.Typer) -> None:
    def require_supported_backend(ctx: typer.Context) -> tuple[Path, Path]:
        state = get_state(ctx)
        if state.config.site_backend not in SUPPORTED_SITE_BACKENDS:
            raise click.ClickException(
                f"Unsupported site backend '{state.config.site_backend}'. "
                "Only 'mkdocs' is supported in this release."
            )
        project_dir = site_project_dir(state)
        config_file = _require_site_project_dir(project_dir)
        return project_dir, config_file

    @site_app.command("build")
    def build_command(
        ctx: typer.Context,
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                resolve_path=True,
                file_okay=False,
                dir_okay=True,
                help="Directory where MkDocs should write the built site.",
            ),
        ] = None,
        strict: Annotated[
            bool,
            typer.Option("--strict", help="Fail on warnings reported by MkDocs."),
        ] = False,
    ) -> int:
        state = get_state(ctx)
        project_dir, config_file = require_supported_backend(ctx)
        resolved_output_dir = None
        if output_dir is not None:
            resolved_output_dir = (
                output_dir if output_dir.is_absolute() else (state.repo_root / output_dir).resolve()
            )

        return _build_site(
            config_file=config_file,
            project_dir=project_dir,
            site_dir=resolved_output_dir,
            strict=strict,
        )

    @site_app.command("build-preview")
    def build_preview_command(
        ctx: typer.Context,
        output_dir: Annotated[
            Path,
            typer.Option(
                "--output-dir",
                resolve_path=True,
                file_okay=False,
                dir_okay=True,
                help="Directory where MkDocs should write the preview site.",
            ),
        ],
        strict: Annotated[
            bool,
            typer.Option("--strict", help="Fail on warnings reported by MkDocs."),
        ] = False,
        current_date_override: Annotated[
            str,
            typer.Option(
                "--current-date-override",
                help="Date used when preview-building unreleased course content.",
            ),
        ] = DEFAULT_PREVIEW_CURRENT_DATE,
    ) -> int:
        state = get_state(ctx)
        project_dir, config_file = require_supported_backend(ctx)
        resolved_output_dir = (
            output_dir if output_dir.is_absolute() else (state.repo_root / output_dir).resolve()
        )

        return _build_site(
            config_file=config_file,
            project_dir=project_dir,
            site_dir=resolved_output_dir,
            strict=strict,
            current_date_override=current_date_override,
            excluded_plugins=PREVIEW_EXCLUDED_PLUGINS,
            preview=True,
        )

    @site_app.command("preview")
    def preview_command(
        ctx: typer.Context,
        dev_addr: Annotated[
            str | None,
            typer.Option("--dev-addr", help="Bind address for mkdocs serve, e.g. 127.0.0.1:8000."),
        ] = None,
        current_date_override: Annotated[
            str,
            typer.Option(
                "--current-date-override",
                help="Date used when previewing unreleased course content.",
            ),
        ] = DEFAULT_PREVIEW_CURRENT_DATE,
        dirty: Annotated[
            bool,
            typer.Option("--dirty", help="Pass --dirty to mkdocs serve for faster rebuilds."),
        ] = False,
    ) -> int:
        _project_dir, config_file = require_supported_backend(ctx)
        return _preview_site(
            config_file=config_file,
            dev_addr=dev_addr,
            current_date_override=current_date_override,
            dirty=dirty,
        )


__all__ = [
    "DEFAULT_PREVIEW_CURRENT_DATE",
    "PREVIEW_EXCLUDED_PLUGINS",
    "PluginCollection",
    "SUPPORTED_SITE_BACKENDS",
    "load_config",
    "mkdocs_build",
    "mkdocs_serve",
    "register_site_commands",
]
