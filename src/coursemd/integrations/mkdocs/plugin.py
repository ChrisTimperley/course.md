"""MkDocs backend adapter for coursemd course repositories."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import frontmatter
from jinja2 import Environment, FileSystemLoader
from mkdocs.config import config_options
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File, Files
from mkdocs.structure.nav import Navigation

from coursemd.core.config import CoursemdConfig, load_coursemd_config
from coursemd.core.loaders.dates import parse_date
from coursemd.core.loaders.repository import load_course_repository
from coursemd.core.macros import define_env
from coursemd.core.models.repository import CourseRepository
from coursemd.core.utils import current_date, set_course_timezone
from coursemd.integrations.canvas.config import INTEGRATION_NAME as CANVAS_INTEGRATION_NAME
from coursemd.integrations.canvas.config import CanvasConfig
from coursemd.integrations.mkdocs.config import MkdocsIntegrationConfig, require_mkdocs_config

MacroFunction = Callable[..., Any]


@dataclass
class _MacroRegistry:
    """Small compatibility layer for functions written for mkdocs-macros."""

    conf: dict[str, Any]
    variables: dict[str, Any]
    macros: dict[str, MacroFunction] = field(default_factory=dict)

    def macro(self, func: MacroFunction) -> MacroFunction:
        self.macros[func.__name__] = func
        return func


class CoursemdPlugin(BasePlugin):
    """MkDocs plugin that adapts a coursemd repository into a MkDocs site."""

    config_scheme = (
        ("config_file", config_options.Optional(config_options.Type(str))),
        ("generate_nav", config_options.Type(bool, default=True)),
    )

    course_config: CoursemdConfig
    mkdocs_integration: MkdocsIntegrationConfig
    course_repository: CourseRepository
    course_data: dict[str, Any]
    current_date: dt.date
    in_preview: bool
    removed_files: set[str]
    macro_registry: _MacroRegistry

    def on_startup(self, command: str, *args: Any, **kwargs: Any) -> None:
        self.in_preview = command == "serve"
        self.current_date = current_date()
        self.removed_files = set()

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig:
        config_path = self._resolve_coursemd_config_path(config)
        self.course_config = load_coursemd_config(start_dir=config_path.parent)
        self.mkdocs_integration = require_mkdocs_config(self.course_config)
        set_course_timezone(self.course_config.timezone)
        self.course_repository = self._load_course_repository()
        self.course_data = self._build_course_data()
        self.in_preview = getattr(self, "in_preview", False) or self._env_truthy("COURSEMD_PREVIEW")
        self.current_date = current_date()
        self.removed_files = getattr(self, "removed_files", set())

        extra = {
            **dict(config.get("extra", {})),
            "canvas_course_id": self.course_data.get("schedule", {})
            .get("course", {})
            .get("canvas_course_id"),
        }
        canvas_config = self.course_config.get_integration(CANVAS_INTEGRATION_NAME, CanvasConfig)
        if canvas_config is not None:
            extra["canvas_base_url"] = canvas_config.base_url
        extra["course_timezone"] = self.course_config.timezone
        config["extra"] = extra

        self._configure_watch(config)
        if self.config.get("generate_nav", True):
            config["nav"] = self._generated_nav(config.get("nav") or [])
        return config

    def on_files(self, files: Files, *, config: MkDocsConfig, **kwargs: Any) -> Files:
        self._add_generated_pages(files, config)
        if not self.in_preview:
            for file in list(files.documentation_pages()):
                metadata = self._load_file_metadata(file)
                if self._should_remove_file(metadata):
                    print(f"Removing file: {file.src_path}")
                    self.removed_files.add(file.src_uri)
                    files.remove(file)
        return files

    def on_nav(self, nav: Navigation, **kwargs: Any) -> Navigation:
        if not self.in_preview and self.removed_files:
            nav.items = list(self._filter_nav_items(nav.items))
        return nav

    def on_page_markdown(
        self,
        markdown: str,
        *,
        page: Any,
        config: MkDocsConfig,
        files: Files,
    ) -> str:
        markdown = self._normalize_generated_frontmatter(markdown, page)
        registry = self._macro_registry(config=config, page=page)
        template_env = Environment(
            loader=FileSystemLoader(str(config.docs_dir)),
            autoescape=False,
        )
        template_env.globals.update(registry.variables)
        template_env.globals.update(registry.macros)
        return template_env.from_string(markdown).render()

    def on_env(self, env: Any, *, config: MkDocsConfig, files: Files) -> Any:
        registry = self._macro_registry(config=config, page=None)
        env.globals.update(registry.variables)
        env.globals.update(registry.macros)
        return env

    def _resolve_coursemd_config_path(self, config: MkDocsConfig) -> Path:
        configured = self.config.get("config_file")
        if configured:
            config_dir = Path(config.config_file_path).parent
            path = Path(configured)
            return path if path.is_absolute() else (config_dir / path).resolve()
        return Path(config.config_file_path).parent

    def _load_course_repository(self) -> CourseRepository:
        data_dir = self.course_config.paths.data_dir
        data_files: list[Path] = []
        if data_dir.is_dir():
            data_files = sorted(
                path
                for path in data_dir.iterdir()
                if path.is_file() and path.suffix in {".yaml", ".yml"}
            )
        assignment_files = self._assignment_macro_files()
        quiz_files = self._quiz_macro_files()

        return load_course_repository(
            repo_root=self.course_config.repo_root,
            data_files=data_files,
            assignment_files=assignment_files,
            quiz_files=quiz_files,
            site_base_url=self.mkdocs_integration.base_url,
            assignment_url_path=self.mkdocs_integration.assignments_url_path,
            canvas_base_url=(
                canvas_config.base_url
                if (canvas_config := self.course_config.get_integration(
                    CANVAS_INTEGRATION_NAME,
                    CanvasConfig,
                ))
                is not None
                else ""
            ),
        )

    def _build_course_data(self) -> dict[str, Any]:
        course_data = dict(self.course_repository.data)
        schedule = course_data.get("schedule")
        if isinstance(schedule, dict):
            schedule_data = dict(schedule)
            schedule_data["assignments"] = self.course_repository.schedule_assignments
            schedule_data["quizzes"] = self.course_repository.schedule_quizzes
            course_data["schedule"] = schedule_data
        return course_data

    def _configure_watch(self, config: MkDocsConfig) -> None:
        watched = list(config.get("watch") or [])
        for path in (
            self.course_config.paths.data_dir,
            self.course_config.paths.assignments_dir,
            self.course_config.paths.quizzes_dir,
        ):
            text = str(path)
            if text not in watched:
                watched.append(text)
        config["watch"] = watched

    def _generated_nav(self, nav: list[Any]) -> list[Any]:
        assignment_nav = self._nav_items_for_markdown_dir(
            self.course_config.paths.assignments_dir,
            base_uri=self.mkdocs_integration.assignments_url_path,
            include_index=True,
        )

        output: list[Any] = []
        saw_assignments = False
        for item in nav:
            key = self._nav_key(item)
            if key == "Assignments":
                saw_assignments = True
                if assignment_nav:
                    output.append({"Assignments": assignment_nav})
                continue
            output.append(item)

        if assignment_nav and not saw_assignments:
            output.append({"Assignments": assignment_nav})
        return output

    def _nav_items_for_markdown_dir(
        self,
        directory: Path,
        *,
        base_uri: str,
        include_index: bool,
    ) -> list[Any]:
        if not directory.is_dir():
            return []
        paths = sorted(directory.glob("*.md"))
        if not include_index:
            paths = [path for path in paths if path.name != "index.md"]
        else:
            paths = sorted(paths, key=lambda path: (path.name != "index.md", path.name))
        items: list[Any] = []
        for path in paths:
            metadata = self._load_markdown_metadata(path)
            if not self.in_preview and self._should_remove_file(metadata):
                continue
            title = str(metadata.get("title") or path.stem).strip()
            items.append({title: f"{base_uri}/{path.name}"})
        return items

    def _add_generated_pages(self, files: Files, config: MkDocsConfig) -> None:
        for directory, base_uri, include_index in (
            (
                self.course_config.paths.assignments_dir,
                self.mkdocs_integration.assignments_url_path,
                True,
            ),
        ):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.md")):
                if not include_index and path.name == "index.md":
                    continue
                src_uri = f"{base_uri}/{path.name}"
                if files.get_file_from_path(src_uri) is not None:
                    continue
                files.append(File.generated(config, src_uri, abs_src_path=str(path)))

    def _macro_registry(self, *, config: MkDocsConfig, page: Any | None) -> _MacroRegistry:
        variables = {
            **self.course_data,
        }
        if page is not None:
            variables["page"] = page

        registry = _MacroRegistry(
            conf={
                "docs_dir": str(config.docs_dir),
                "extra": dict(config.get("extra", {})),
            },
            variables=variables,
        )
        define_env(registry)
        return registry

    def _assignment_macro_files(self) -> list[Path]:
        directory = self.course_config.paths.assignments_dir
        if not directory.is_dir():
            return []
        return sorted(path for path in directory.glob("*.md") if path.name != "index.md")

    def _quiz_macro_files(self) -> list[Path]:
        directory = self.course_config.paths.quizzes_dir
        if not directory.is_dir():
            return []
        return sorted(path for path in directory.glob("*.md") if path.name != "index.md")

    def _load_file_metadata(self, file: File) -> dict[str, Any]:
        if not file.abs_src_path:
            return {}
        return self._load_markdown_metadata(Path(file.abs_src_path))

    def _load_markdown_metadata(self, path: Path) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], frontmatter.load(path).metadata)
        except Exception:
            return {}

    def _normalize_generated_frontmatter(self, markdown: str, page: Any) -> str:
        if not markdown.startswith("---"):
            return markdown
        try:
            post = frontmatter.loads(markdown)
        except Exception:
            return markdown
        if post.metadata:
            page.meta.update(post.metadata)
        return cast(str, post.content)

    def _should_remove_file(self, metadata: dict[str, Any]) -> bool:
        if metadata.get("draft"):
            return True

        check_date = parse_date(metadata.get("reveal_date") or metadata.get("release_date"))
        return check_date is not None and check_date > self.current_date

    def _filter_nav_items(self, items: Any) -> Any:
        for item in items:
            if hasattr(item, "url") and item.url in self.removed_files:
                continue
            if hasattr(item, "children") and item.children:
                filtered_children = list(self._filter_nav_items(item.children))
                if filtered_children:
                    item.children = filtered_children
                    yield item
            else:
                yield item

    def _nav_key(self, item: Any) -> str | None:
        if isinstance(item, dict) and len(item) == 1:
            return cast(str, next(iter(item)))
        return None

    def _env_truthy(self, name: str) -> bool:
        import os

        return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
