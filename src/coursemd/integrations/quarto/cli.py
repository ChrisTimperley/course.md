"""Quarto CLI commands."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from shutil import which
from typing import Annotated

import click
import typer
import yaml

from coursemd.cli.shared import AppState, click_error_boundary
from coursemd.integrations.quarto.config import QuartoConfig

CLI_NAME = "quarto"
CLI_HELP = "Build and preview course slides."
DEFAULT_QUARTO_OUTPUT_DIR = Path("build/slides/html")
DEFAULT_QUARTO_EXPORT_WIDTH = 1600
DEFAULT_QUARTO_EXPORT_HEIGHT = 900


@dataclass(frozen=True)
class _Slide:
    number: int
    title: str
    route: str


@dataclass
class _Section:
    title: str | None = None
    children: list[_Section] | None = None

    def add_child(self, child: _Section) -> None:
        if self.children is None:
            self.children = []
        self.children.append(child)


def _require_quarto_dir(directory: Path) -> Path:
    if not directory.is_dir():
        raise click.ClickException(f"Slides directory not found: {directory}")
    config_file = directory / "_quarto.yml"
    if not config_file.is_file():
        raise click.ClickException(f"Quarto config file not found: {config_file}")
    return directory


def _default_output_dir(repo_root: Path) -> Path:
    return (repo_root / DEFAULT_QUARTO_OUTPUT_DIR).resolve()


def _resolve_output_dir(repo_root: Path, output_dir: Path | None) -> Path:
    return (
        _default_output_dir(repo_root)
        if output_dir is None
        else output_dir
        if output_dir.is_absolute()
        else (repo_root / output_dir).resolve()
    )


def _resolve_export_dir(repo_root: Path, deck_path: Path, output_dir: Path | None) -> Path:
    if output_dir is not None:
        return output_dir if output_dir.is_absolute() else (repo_root / output_dir).resolve()
    return (repo_root / "build" / "slides" / deck_path.stem).resolve()


def _resolve_deck_path(
    *,
    repo_root: Path,
    slides_directory: Path,
    deck: Path | None,
) -> Path:
    if deck is None:
        candidates = sorted(
            path for path in slides_directory.glob("*.qmd") if not path.name.startswith("_")
        )
        if len(candidates) == 1:
            return candidates[0].resolve()
        if not candidates:
            raise click.ClickException(
                f"No slide deck found in {slides_directory}; pass a .qmd file to export."
            )
        raise click.ClickException(
            "Multiple slide decks found; pass the deck .qmd file to export."
        )

    candidate = deck if deck.is_absolute() else repo_root / deck
    if not candidate.is_file() and not deck.is_absolute():
        candidate = slides_directory / deck
    if not candidate.is_file():
        raise click.ClickException(f"Slide deck not found: {deck}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(slides_directory)
    except ValueError as exc:
        raise click.ClickException(
            f"Slide deck must be inside the configured Quarto directory: {slides_directory}"
        ) from exc
    return resolved


def _run_quarto(
    *,
    slides_directory: Path,
    quarto_command: str,
    output_dir: Path,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [  # noqa: S607
                "quarto",
                quarto_command,
                ".",
                "--output-dir",
                str(output_dir),
            ],
            cwd=slides_directory,
            check=False,
        )
    except FileNotFoundError as exc:
        raise click.ClickException(
            "quarto is required for slides commands but was not found on PATH."
        ) from exc
    return completed.returncode


def _render_export_deck(
    *,
    slides_directory: Path,
    deck_path: Path,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    deck_html = output_dir / "deck.html"
    source_arg = str(deck_path.relative_to(slides_directory))
    try:
        completed = subprocess.run(
            [  # noqa: S607
                "quarto",
                "render",
                source_arg,
                "--to",
                "revealjs",
                "--output",
                deck_html.name,
                "--output-dir",
                str(output_dir),
            ],
            cwd=slides_directory,
            check=False,
        )
    except FileNotFoundError as exc:
        raise click.ClickException(
            "quarto is required for slides commands but was not found on PATH."
        ) from exc
    if completed.returncode != 0:
        raise click.ClickException(f"quarto render failed with exit code {completed.returncode}.")
    if not deck_html.is_file():
        raise click.ClickException(f"Expected Quarto to write {deck_html}, but it was not found.")
    return deck_html


class _RevealSlideParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.roots: list[_Section] = []
        self._in_slides = False
        self._slides_div_depth = 0
        self._section_stack: list[_Section] = []
        self._heading_section: _Section | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "div" and self._has_class(attr_map, "slides"):
            self._in_slides = True
            self._slides_div_depth = 1
            return
        if self._in_slides and tag == "div":
            self._slides_div_depth += 1

        if not self._in_slides:
            return
        if tag == "section":
            section = _Section(title=self._section_title_from_attrs(attr_map))
            if self._section_stack:
                self._section_stack[-1].add_child(section)
            else:
                self.roots.append(section)
            self._section_stack.append(section)
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._section_stack:
            self._heading_section = self._section_stack[-1]
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        if not self._in_slides:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            if self._heading_section is not None and self._heading_section.title is None:
                title = " ".join("".join(self._heading_parts).split())
                if title:
                    self._heading_section.title = title
            self._heading_section = None
            self._heading_parts = []
            return
        if tag == "section" and self._section_stack:
            self._section_stack.pop()
            return
        if tag == "div":
            self._slides_div_depth -= 1
            if self._slides_div_depth <= 0:
                self._in_slides = False

    def handle_data(self, data: str) -> None:
        if self._heading_section is not None:
            self._heading_parts.append(data)

    @staticmethod
    def _has_class(attrs: dict[str, str | None], class_name: str) -> bool:
        return class_name in (attrs.get("class") or "").split()

    @staticmethod
    def _section_title_from_attrs(attrs: dict[str, str | None]) -> str | None:
        for key in ("data-title", "aria-label"):
            value = attrs.get(key)
            if value:
                return value
        return None


def _read_slide_index(deck_html: Path) -> list[_Slide]:
    parser = _RevealSlideParser()
    parser.feed(deck_html.read_text(encoding="utf-8"))
    slides: list[_Slide] = []
    for horizontal_index, section in enumerate(parser.roots):
        if section.children:
            for vertical_index, child in enumerate(section.children):
                slides.append(
                    _Slide(
                        number=len(slides) + 1,
                        title=child.title or section.title or f"Slide {len(slides) + 1}",
                        route=f"{horizontal_index}/{vertical_index}",
                    )
                )
        else:
            slides.append(
                _Slide(
                    number=len(slides) + 1,
                    title=section.title or f"Slide {len(slides) + 1}",
                    route=str(horizontal_index),
                )
            )
    if not slides:
        slides.append(_Slide(number=1, title="Slide 1", route="0"))
    return slides


def _find_browser(browser_path: Path | None) -> str:
    if browser_path is not None:
        if not browser_path.is_file():
            raise click.ClickException(f"Browser executable not found: {browser_path}")
        return str(browser_path)

    candidates = (
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "microsoft-edge",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    )
    for candidate in candidates:
        if "/" in candidate:
            path = Path(candidate)
            if path.is_file():
                return str(path)
        else:
            resolved = which(candidate)
            if resolved is not None:
                return resolved
    raise click.ClickException(
        "A Chromium-compatible browser is required for PDF and screenshot export. "
        "Install Chrome/Chromium or pass --browser-path."
    )


def _run_browser(args: list[str], *, description: str) -> None:
    try:
        completed = subprocess.run(args, check=False)
    except FileNotFoundError as exc:
        raise click.ClickException(f"Browser executable not found: {args[0]}") from exc
    if completed.returncode != 0:
        raise click.ClickException(f"{description} failed with exit code {completed.returncode}.")


def _export_pdf(*, browser: str, deck_html: Path, output_dir: Path) -> Path:
    pdf_path = output_dir / "deck.pdf"
    _run_browser(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--allow-file-access-from-files",
            f"--print-to-pdf={pdf_path}",
            f"{deck_html.as_uri()}?print-pdf",
        ],
        description="PDF export",
    )
    return pdf_path


def _export_screenshots(
    *,
    browser: str,
    deck_html: Path,
    output_dir: Path,
    slides: list[_Slide],
    width: int,
    height: int,
) -> dict[int, Path]:
    screenshot_dir = output_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[int, Path] = {}
    for slide in slides:
        screenshot_path = screenshot_dir / f"slide-{slide.number:03}.png"
        _run_browser(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--allow-file-access-from-files",
                f"--window-size={width},{height}",
                "--virtual-time-budget=1000",
                f"--screenshot={screenshot_path}",
                f"{deck_html.as_uri()}#/{slide.route}",
            ],
            description=f"Screenshot export for slide {slide.number}",
        )
        paths[slide.number] = screenshot_path
    return paths


def _write_export_index(
    *,
    output_dir: Path,
    slides: list[_Slide],
    pdf_path: Path | None,
    screenshot_paths: dict[int, Path],
) -> None:
    document: dict[str, object] = {
        "html": "deck.html",
        "slides": [
            {
                "number": slide.number,
                "title": slide.title,
                **(
                    {"image": screenshot_paths[slide.number].relative_to(output_dir).as_posix()}
                    if slide.number in screenshot_paths
                    else {}
                ),
            }
            for slide in slides
        ],
    }
    if pdf_path is not None:
        document["pdf"] = pdf_path.relative_to(output_dir).as_posix()
    index_path = output_dir / "index.yml"
    index_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def register_quarto_commands(quarto_app: typer.Typer) -> None:
    @quarto_app.command("build")
    def build_command(
        ctx: typer.Context,
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                resolve_path=True,
                file_okay=False,
                dir_okay=True,
                help="Directory where Quarto should write the built slides.",
            ),
        ] = None,
    ) -> int:
        with click_error_boundary():
            state = AppState.from_typer(ctx)
            quarto_config = QuartoConfig.require(state.config)
            directory = _require_quarto_dir(quarto_config.directory)

            resolved_output_dir = _resolve_output_dir(state.repo_root, output_dir)
            return _run_quarto(
                slides_directory=directory,
                quarto_command="render",
                output_dir=resolved_output_dir,
            )

    @quarto_app.command("preview")
    def preview_command(
        ctx: typer.Context,
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                resolve_path=True,
                file_okay=False,
                dir_okay=True,
                help="Directory where Quarto should write preview slides.",
            ),
        ] = None,
    ) -> int:
        with click_error_boundary():
            state = AppState.from_typer(ctx)
            quarto_config = QuartoConfig.require(state.config)
            directory = _require_quarto_dir(quarto_config.directory)
            resolved_output_dir = _resolve_output_dir(state.repo_root, output_dir)
            return _run_quarto(
                slides_directory=directory,
                quarto_command="preview",
                output_dir=resolved_output_dir,
            )

    @quarto_app.command("export")
    def export_command(
        ctx: typer.Context,
        deck: Annotated[
            Path | None,
            typer.Argument(
                resolve_path=False,
                help="Slide deck .qmd file. Defaults to the only .qmd file in the slides dir.",
            ),
        ] = None,
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                resolve_path=True,
                file_okay=False,
                dir_okay=True,
                help="Directory where exported deck assets should be written.",
            ),
        ] = None,
        browser_path: Annotated[
            Path | None,
            typer.Option(
                "--browser-path",
                resolve_path=True,
                file_okay=True,
                dir_okay=False,
                help="Chromium-compatible browser executable for PDF and screenshot export.",
            ),
        ] = None,
        pdf: Annotated[
            bool,
            typer.Option("--pdf/--no-pdf", help="Export deck.pdf using browser print mode."),
        ] = True,
        screenshots: Annotated[
            bool,
            typer.Option(
                "--screenshots/--no-screenshots",
                help="Export one PNG screenshot per slide.",
            ),
        ] = True,
        width: Annotated[
            int,
            typer.Option("--width", min=1, help="Screenshot viewport width in pixels."),
        ] = DEFAULT_QUARTO_EXPORT_WIDTH,
        height: Annotated[
            int,
            typer.Option("--height", min=1, help="Screenshot viewport height in pixels."),
        ] = DEFAULT_QUARTO_EXPORT_HEIGHT,
    ) -> None:
        with click_error_boundary():
            state = AppState.from_typer(ctx)
            quarto_config = QuartoConfig.require(state.config)
            directory = _require_quarto_dir(quarto_config.directory)
            deck_path = _resolve_deck_path(
                repo_root=state.repo_root,
                slides_directory=directory,
                deck=deck,
            )
            resolved_output_dir = _resolve_export_dir(state.repo_root, deck_path, output_dir)
            deck_html = _render_export_deck(
                slides_directory=directory,
                deck_path=deck_path,
                output_dir=resolved_output_dir,
            )
            slides = _read_slide_index(deck_html)
            browser = _find_browser(browser_path) if pdf or screenshots else None
            pdf_path = (
                _export_pdf(browser=browser, deck_html=deck_html, output_dir=resolved_output_dir)
                if pdf and browser is not None
                else None
            )
            screenshot_paths = (
                _export_screenshots(
                    browser=browser,
                    deck_html=deck_html,
                    output_dir=resolved_output_dir,
                    slides=slides,
                    width=width,
                    height=height,
                )
                if screenshots and browser is not None
                else {}
            )
            _write_export_index(
                output_dir=resolved_output_dir,
                slides=slides,
                pdf_path=pdf_path,
                screenshot_paths=screenshot_paths,
            )


def register_quarto_cli(app: typer.Typer) -> None:
    quarto_app = typer.Typer(no_args_is_help=True, help=CLI_HELP)
    app.add_typer(quarto_app, name=CLI_NAME)
    register_quarto_commands(quarto_app)


__all__ = ["register_quarto_cli"]
